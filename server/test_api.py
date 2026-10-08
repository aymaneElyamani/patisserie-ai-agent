"""Regression tests for application startup and core API behavior."""

import tempfile
import unittest
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from httpx import Request, Response
from openai import AuthenticationError, OpenAIError
from sqlmodel import Session, SQLModel, create_engine

from server.database import get_session
from server.exceptions import ChatbotUnavailableError
from server.main import app
from server.services import ChatbotService
from server.utils import (
    REQUIRED_CSV_FIELDS,
    build_recipe_context,
    is_safe_photo_url,
    load_recipes,
    search_recipes,
)


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "test.db"
        self.engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(self.engine)

        def get_test_session() -> Generator[Session, None, None]:
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_session] = get_test_session
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_directory.cleanup()

    def test_root_reports_service_status(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["documentation"], "/docs")
        self.assertNotIn("interface", response.json())
        self.assertEqual(self.client.get("/app").status_code, 404)

    def test_conversation_chat_flow(self) -> None:
        create_response = self.client.post(
            "/api/conversations",
            json={"title": "Commande"},
        )
        self.assertEqual(create_response.status_code, 201)
        conversation_id = create_response.json()["id"]

        with patch(
            "server.services.agentOpenAIClient.chat.completions.create"
        ) as create_completion:
            create_completion.return_value = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                "<p>Bonjour ! Que puis-je préparer pour vous ?</p>"
                            )
                        )
                    )
                ]
            )
            chat_response = self.client.post(
                f"/api/conversations/{conversation_id}/chat",
                json={"content": "Bonjour"},
            )

            create_completion.return_value = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="Nous pouvons préparer plusieurs formats."
                        )
                    )
                ]
            )
            follow_up_response = self.client.post(
                f"/api/conversations/{conversation_id}/chat",
                json={"content": "Et pour dix personnes ?"},
            )

        self.assertEqual(chat_response.status_code, 200)
        self.assertEqual(chat_response.json()["user_message"]["role"], "user")
        self.assertEqual(
            chat_response.json()["assistant_message"]["role"],
            "assistant",
        )
        self.assertEqual(
            chat_response.json()["assistant_message"]["content"],
            "<p>Bonjour ! Que puis-je préparer pour vous ?</p>",
        )
        self.assertEqual(follow_up_response.status_code, 200)
        request = create_completion.call_args.kwargs
        self.assertEqual(
            [message["role"] for message in request["messages"]],
            ["system", "assistant", "user", "assistant", "user"],
        )
        self.assertEqual(
            request["messages"][-1]["content"],
            "Et pour dix personnes ?",
        )
        self.assertIn(
            "Retourne uniquement un petit fragment HTML",
            request["messages"][0]["content"],
        )
        self.assertIn("champ `Photo`", request["messages"][0]["content"])

        detail_response = self.client.get(
            f"/api/conversations/{conversation_id}"
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(len(detail_response.json()["messages"]), 5)

    def test_new_conversation_has_default_title_and_welcome_message(self) -> None:
        response = self.client.post("/api/conversations", json={})

        self.assertEqual(response.status_code, 201)
        conversation = response.json()
        self.assertEqual(conversation["title"], "Nouvelle conversation")
        self.assertEqual(len(conversation["messages"]), 1)
        self.assertEqual(conversation["messages"][0]["role"], "assistant")
        self.assertIn("Bienvenue chez pâtissIA", conversation["messages"][0]["content"])

    def test_chat_replaces_default_title_with_conversation_context(self) -> None:
        conversation = self.client.post("/api/conversations", json={}).json()

        with patch(
            "server.services.agentOpenAIClient.chat.completions.create"
        ) as create_completion:
            create_completion.side_effect = [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="<p>Voici la recette.</p>")
                        )
                    ]
                ),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="Ghriba aux amandes")
                        )
                    ]
                ),
            ]
            response = self.client.post(
                f"/api/conversations/{conversation['id']}/chat",
                json={"content": "Donne-moi la recette de Ghriba aux amandes"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["conversation_title"],
            "Ghriba aux amandes",
        )
        detail = self.client.get(
            f"/api/conversations/{conversation['id']}"
        ).json()
        self.assertEqual(detail["title"], "Ghriba aux amandes")
        self.assertEqual(create_completion.call_count, 2)
        title_request = create_completion.call_args.kwargs["messages"]
        self.assertIn("Génère un titre", title_request[0]["content"])
        self.assertIn(
            "Donne-moi la recette de Ghriba aux amandes",
            [message["content"] for message in title_request],
        )

    def test_greeting_keeps_default_title_until_topic_is_known(self) -> None:
        conversation = self.client.post("/api/conversations", json={}).json()

        with patch(
            "server.services.agentOpenAIClient.chat.completions.create"
        ) as create_completion:
            create_completion.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="<p>Bonjour !</p>"))]
            )
            response = self.client.post(
                f"/api/conversations/{conversation['id']}/chat",
                json={"content": "Bonjour"},
            )

        self.assertEqual(response.json()["conversation_title"], "Nouvelle conversation")

    def test_custom_title_is_not_overwritten_by_chat(self) -> None:
        conversation = self.client.post(
            "/api/conversations",
            json={"title": "Commande anniversaire"},
        ).json()

        with patch(
            "server.services.agentOpenAIClient.chat.completions.create"
        ) as create_completion:
            create_completion.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="<p>D'accord.</p>"))]
            )
            response = self.client.post(
                f"/api/conversations/{conversation['id']}/chat",
                json={"content": "Je veux préparer des macarons"},
            )

        self.assertEqual(response.json()["conversation_title"], "Commande anniversaire")

    def test_unknown_conversation_returns_404(self) -> None:
        response = self.client.get("/api/conversations/999")
        self.assertEqual(response.status_code, 404)

    def test_csv_columns_and_photo_values(self) -> None:
        recipes = load_recipes()
        self.assertEqual(tuple(recipes[0]), REQUIRED_CSV_FIELDS)
        self.assertTrue(all(recipe["photos"].startswith("https://") for recipe in recipes))

    def test_photo_url_validation_rejects_unsafe_values(self) -> None:
        self.assertTrue(is_safe_photo_url("https://example.com/photo.jpg"))
        self.assertFalse(is_safe_photo_url("http://example.com/photo.jpg"))
        self.assertFalse(is_safe_photo_url("javascript:alert(1)"))
        self.assertFalse(is_safe_photo_url("https://user:pass@example.com/photo.jpg"))
        self.assertFalse(is_safe_photo_url("https://example.com/photo.jpg#fragment"))

    def test_rapidfuzz_recipe_search_handles_typo(self) -> None:
        matches = search_recipes("griba amand", limit=1)
        self.assertEqual(matches[0]["nom"], "Ghriba aux amandes")

    def test_rapidfuzz_recipe_search_rejects_unrelated_question(self) -> None:
        self.assertEqual(search_recipes("Qui est le président du Brésil ?"), [])

    def test_specific_recipe_wins_over_related_variants(self) -> None:
        matches = search_recipes(
            "À quelle température cuire la ghriba bahla ?"
        )
        self.assertEqual([recipe["id"] for recipe in matches], ["7"])

    def test_category_search_returns_every_matching_recipe(self) -> None:
        matches = search_recipes("Combien de temps de cuisson pour les ghriba ?")
        self.assertEqual([recipe["id"] for recipe in matches], [
            "1", "2", "3", "4", "5", "6", "7", "8",
        ])

    def test_cooking_filter_is_data_driven(self) -> None:
        matches = search_recipes("Quelles pâtisseries puis-je faire sans four ?")
        self.assertGreater(len(matches), 3)
        self.assertTrue(all(recipe["type_cuisson"] != "Four" for recipe in matches))
        self.assertIn("Chebakia", {recipe["nom"] for recipe in matches})
        self.assertIn("Baghrir", {recipe["nom"] for recipe in matches})
        context = build_recipe_context("Quelles pâtisseries puis-je faire sans four ?")
        self.assertIn("liste exhaustive contient 31 recettes", context)
        self.assertIn("Friture", context)
        self.assertIn("Poêle", context)
        self.assertIn("Vapeur", context)

    def test_other_cooking_type_filter_is_not_recipe_specific(self) -> None:
        matches = search_recipes("Donne-moi les pâtisseries à la poêle")
        self.assertTrue(matches)
        self.assertTrue(all(recipe["type_cuisson"] == "Poêle" for recipe in matches))

    def test_structured_filters_can_be_combined(self) -> None:
        matches = search_recipes("Quelles recettes à la poêle sont faciles ?")
        self.assertTrue(matches)
        self.assertTrue(all(
            recipe["type_cuisson"] == "Poêle"
            and recipe["difficulte"] == "Facile"
            for recipe in matches
        ))

    def test_explicit_ingredient_filter_uses_all_recipe_rows(self) -> None:
        matches = search_recipes("Quelles pâtisseries avec des pistaches ?")
        self.assertTrue(matches)
        self.assertTrue(all("pistache" in recipe["ingredients"].casefold() for recipe in matches))

    def test_ingredient_filter_ignores_category_words_before_marker(self) -> None:
        matches = search_recipes("Quelles ghriba avec des amandes ?")
        self.assertEqual([recipe["id"] for recipe in matches], ["1"])

    def test_inclusion_and_exclusion_ingredient_filters_compose(self) -> None:
        matches = search_recipes("Pâtisseries avec amandes sans miel")
        self.assertTrue(matches)
        self.assertTrue(all(
            "amande" in recipe["ingredients"].casefold()
            and "miel" not in recipe["ingredients"].casefold()
            for recipe in matches
        ))

    def test_follow_up_reuses_previous_recipe(self) -> None:
        context = build_recipe_context(
            "Et combien de temps de préparation, pour combien de personnes ?",
            ["Quelle est la difficulté de la chebakia et quels outils faut-il ?"],
        )
        self.assertIn("Nom: Chebakia", context)
        self.assertIn("Préparation: 90 min", context)
        self.assertIn("Portions: 50", context)

    def test_variant_follow_up_uses_previous_recipe_family(self) -> None:
        context = build_recipe_context(
            "Et la version à la pistache ?",
            ["Quels sont les ingrédients de la corne de gazelle classique ?"],
        )
        self.assertIn("Nom: Corne de gazelle à la pistache", context)
        self.assertNotIn("Nom: Tarte à la pistache", context)

    def test_unrelated_recipe_does_not_create_a_fuzzy_false_positive(self) -> None:
        self.assertEqual(search_recipes("pizza margherita"), [])

    def test_unicode_normalization_preserves_arabic_words(self) -> None:
        from server.utils import normalize_text

        self.assertEqual(normalize_text("حلويات مغربية"), "حلويات مغربية")

    def test_csv_recipe_response_contains_its_exact_image(self) -> None:
        conversation_id = self.client.post(
            "/api/conversations",
            json={"title": "Ghriba"},
        ).json()["id"]
        expected_url = load_recipes()[0]["photos"]

        with patch("server.services.IS_CSV_DATA_ACTIVE", True), patch(
            "server.services.agentOpenAIClient.chat.completions.create"
        ) as create_completion:
            create_completion.return_value = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                "<p>Recette trouvée.</p>"
                                f'<figure><img src="{expected_url}" '
                                'alt="Ghriba aux amandes"></figure>'
                            )
                        )
                    )
                ]
            )
            response = self.client.post(
                f"/api/conversations/{conversation_id}/chat",
                json={"content": "Donne-moi la recette de Ghriba aux amandes"},
            )

        self.assertEqual(response.status_code, 200)
        content = response.json()["assistant_message"]["content"]
        self.assertIn(f'src="{expected_url}"', content)
        request_messages = create_completion.call_args.kwargs["messages"]
        self.assertIn(f"Photo: {expected_url}", request_messages[1]["content"])

    def test_unrelated_question_does_not_receive_an_image(self) -> None:
        with patch("server.services.IS_CSV_DATA_ACTIVE", True), patch(
            "server.services.agentOpenAIClient.chat.completions.create"
        ) as create_completion:
            create_completion.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="<p>Non.</p>"))]
            )
            content = self.client.post(
                "/api/conversations",
                json={"title": "Hors domaine"},
            ).json()
            response = self.client.post(
                f"/api/conversations/{content['id']}/chat",
                json={"content": "Qui est le président du Brésil ?"},
            )

        self.assertNotIn("<img", response.json()["assistant_message"]["content"])

    def test_model_prompt_is_logged_to_the_server_console(self) -> None:
        with patch(
            "server.services.agentOpenAIClient.chat.completions.create"
        ) as create_completion, self.assertLogs(
            "uvicorn.error",
            level="INFO",
        ) as captured_logs:
            create_completion.return_value = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="<p>Bonjour !</p>")
                    )
                ]
            )
            ChatbotService.generate_response([], "Bonjour")

        console_output = "\n".join(captured_logs.output)
        self.assertIn("Prompt envoyé au chatbot (réponse)", console_output)
        self.assertIn('"content": "Bonjour"', console_output)

    def test_openai_failure_returns_503_without_saving_message(self) -> None:
        conversation = self.client.post(
            "/api/conversations",
            json={"title": "Commande"},
        ).json()

        with patch(
            "server.services.agentOpenAIClient.chat.completions.create",
            side_effect=OpenAIError("AI provider unavailable"),
        ):
            response = self.client.post(
                f"/api/conversations/{conversation['id']}/chat",
                json={"content": "Bonjour"},
            )

        self.assertEqual(response.status_code, 503)
        detail = self.client.get(
            f"/api/conversations/{conversation['id']}"
        ).json()
        self.assertEqual(len(detail["messages"]), 1)
        self.assertEqual(detail["messages"][0]["role"], "assistant")

    def test_authentication_failure_has_actionable_notebook_message(self) -> None:
        authentication_error = AuthenticationError(
            "Invalid API key",
            response=Response(
                401,
                request=Request("POST", "https://example.com"),
            ),
            body=None,
        )

        with patch(
            "server.services.agentOpenAIClient.chat.completions.create",
            side_effect=authentication_error,
        ):
            with self.assertRaises(ChatbotUnavailableError) as captured:
                ChatbotService.generate_response([], "Bonjour")

        self.assertIn("Mettez à jour GROQ_API", str(captured.exception))
        self.assertIn("redémarrez", str(captured.exception))


if __name__ == "__main__":
    unittest.main()
