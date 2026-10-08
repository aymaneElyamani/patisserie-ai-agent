"""Structured local search for the pastry recipe database."""

import csv
import re
import unicodedata
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from rapidfuzz import fuzz, process

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "data.csv"

REQUIRED_CSV_FIELDS = (
    "id", "nom", "categorie", "ingredients", "etapes", "outils",
    "temps_preparation_min", "type_cuisson", "four_temperature_C",
    "four_duree_min", "nombre_portions", "difficulte", "photos",
)

STOP_WORDS = {
    # French question and recipe boilerplate
    "a", "ai", "au", "aux", "avec", "combien", "comment", "de", "des",
    "donne", "du", "en", "est", "et", "faire", "faut", "il", "ingredient",
    "ingredients", "je", "la", "le", "les", "materiel", "moi", "patisserie",
    "patisseries", "pour", "preparation", "preparer", "puis", "quel", "quelle",
    "quelles", "quels", "recette", "sans", "sont", "temperature", "temps",
    "un", "une", "veux",
    # English question and recipe boilerplate
    "a", "an", "and", "how", "make", "of", "recipe", "the", "to", "want",
    "with",
    # Common Darija transliterations
    "bghit", "dyal", "kifach", "ndir",
}

FOLLOW_UP_MARKERS = {
    "aussi", "celle", "celui", "elle", "elles", "encore", "et", "eux",
    "lui", "version",
}


def normalize_text(value: str | None) -> str:
    """Lowercase text, remove accents, and normalize Unicode punctuation."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        character for character in value if not unicodedata.combining(character)
    ).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).replace("_", " ")
    return " ".join(value.split())


def extract_terms(query: str) -> list[str]:
    """Extract useful search terms from a user question."""
    return [
        term for term in normalize_text(query).split()
        if len(term) >= 2 and term not in STOP_WORDS
    ]


@lru_cache(maxsize=1)
def load_recipes() -> tuple[dict[str, str], ...]:
    """Load the recipe file once and keep it in memory."""
    with CSV_PATH.open(mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, delimiter=";")
        missing_fields = set(REQUIRED_CSV_FIELDS) - set(reader.fieldnames or ())
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise RuntimeError(f"Colonnes CSV manquantes : {missing}")
        return tuple(dict(row) for row in reader)


def is_safe_photo_url(value: str | None) -> bool:
    """Accept only public HTTPS URLs from the recipe photo column."""
    if not value:
        return False
    parsed = urlsplit(value.strip())
    return bool(
        parsed.scheme == "https" and parsed.hostname and not parsed.username
        and not parsed.password and not parsed.fragment
    )


def _recipe_alias(recipe_name: str) -> str:
    """Return a natural alias, ignoring a parenthetical qualifier."""
    return normalize_text(re.sub(r"\([^)]*\)", " ", recipe_name))


def _exact_recipe_matches(query: str) -> list[dict[str, str]]:
    normalized_query = normalize_text(query)
    matches: list[tuple[int, dict[str, str]]] = []
    for recipe in load_recipes():
        aliases = {normalize_text(recipe["nom"]), _recipe_alias(recipe["nom"])}
        aliases.discard("")
        lengths = [len(alias) for alias in aliases if alias in normalized_query]
        if lengths:
            matches.append((max(lengths), recipe))
    if not matches:
        return []
    # Prefer the most specific name when one name contains another.
    longest = max(length for length, _ in matches)
    return [recipe for length, recipe in matches if length == longest]


def _category_matches(query: str) -> list[dict[str, str]] | None:
    normalized_query = normalize_text(query)
    recipes = load_recipes()
    categories = {
        normalize_text(recipe["categorie"])
        for recipe in recipes if recipe.get("categorie")
    }
    requested = {
        category for category in categories
        if category and category in normalized_query
    }
    if not requested:
        return None
    return [
        recipe for recipe in recipes
        if normalize_text(recipe["categorie"]) in requested
    ]


def _cooking_type_matches(query: str) -> list[dict[str, str]] | None:
    normalized_query = normalize_text(query)
    recipes = load_recipes()
    without_oven_phrases = (
        "sans four", "sans cuisson au four", "pas de four", "without oven",
        "no oven",
    )
    if any(phrase in normalized_query for phrase in without_oven_phrases):
        return [
            recipe for recipe in recipes
            if normalize_text(recipe["type_cuisson"]) != "four"
        ]

    cooking_types = {
        normalize_text(recipe["type_cuisson"])
        for recipe in recipes if recipe.get("type_cuisson")
    }
    requested = {
        cooking_type for cooking_type in cooking_types
        if cooking_type in normalized_query
    }
    if not requested:
        return None
    return [
        recipe for recipe in recipes
        if normalize_text(recipe["type_cuisson"]) in requested
    ]


def _difficulty_matches(query: str) -> list[dict[str, str]] | None:
    normalized_query = normalize_text(query)
    recipes = load_recipes()
    difficulties = {
        normalize_text(recipe["difficulte"])
        for recipe in recipes if recipe.get("difficulte")
    }
    requested = {
        difficulty for difficulty in difficulties
        if difficulty in normalized_query
    }
    if not requested:
        return None
    return [
        recipe for recipe in recipes
        if normalize_text(recipe["difficulte"]) in requested
    ]


def _ingredient_matches(query: str) -> list[dict[str, str]] | None:
    """Apply explicit 'with/without ingredient' filters from recipe data."""
    normalized_query = normalize_text(query)
    include_markers = ("avec ", "a base de ", "contenant ", "contains ", "with ")
    exclude_markers = ("sans ", "without ")
    ignored = {"four", "cuisson", "friture", "poele", "vapeur"}

    def terms_after(markers: tuple[str, ...]) -> list[str]:
        for marker in markers:
            if marker not in normalized_query:
                continue
            tail = normalized_query.split(marker, 1)[1]
            other_markers = include_markers + exclude_markers
            cut_positions = [
                tail.index(other)
                for other in other_markers
                if other in tail
            ]
            if cut_positions:
                tail = tail[:min(cut_positions)]
            return [term for term in extract_terms(tail) if term not in ignored]
        return []

    include_terms = terms_after(include_markers)
    exclude_terms = terms_after(exclude_markers)
    if not include_terms and not exclude_terms:
        return None

    def ingredient_has(term: str, recipe: dict[str, str]) -> bool:
        ingredient_terms = normalize_text(recipe["ingredients"]).split()
        return any(
            fuzz.ratio(term, ingredient) >= 84 for ingredient in ingredient_terms
        )

    return [
        recipe for recipe in load_recipes()
        if all(ingredient_has(term, recipe) for term in include_terms)
        and not any(ingredient_has(term, recipe) for term in exclude_terms)
    ]


def _has_related_name_term(query_terms: Iterable[str], recipe_name: str) -> bool:
    """Allow spelling mistakes while requiring real lexical evidence."""
    name_terms = extract_terms(recipe_name)
    return any(
        fuzz.ratio(query_term, name_term) >= 78
        for query_term in query_terms for name_term in name_terms
    )


def search_recipes(
    query: str,
    limit: int | None = 3,
    minimum_score: float = 60,
) -> list[dict[str, str]]:
    """Resolve names, categories and cooking filters, then tolerate typos.

    Structured matches return every matching recipe. ``limit`` applies only to
    fuzzy name search, where it prevents weak alternatives flooding the context.
    """
    exact_matches = _exact_recipe_matches(query)
    if exact_matches:
        return exact_matches
    structured_groups = [
        matches for matches in (
            _cooking_type_matches(query),
            _difficulty_matches(query),
            _category_matches(query),
            _ingredient_matches(query),
        )
        if matches is not None
    ]
    if structured_groups:
        allowed_ids = {
            recipe["id"] for recipe in structured_groups[0]
        }
        for matches in structured_groups[1:]:
            allowed_ids &= {recipe["id"] for recipe in matches}
        return [
            recipe for recipe in load_recipes()
            if recipe["id"] in allowed_ids
        ]

    query_terms = extract_terms(query)
    if not query_terms:
        return []
    recipes = load_recipes()
    choices = {
        index: normalize_text(recipe["nom"])
        for index, recipe in enumerate(recipes)
    }
    matches = process.extract(
        " ".join(query_terms), choices, scorer=fuzz.WRatio, limit=limit,
        score_cutoff=minimum_score,
    )
    return [
        recipes[index] for _, _, index in matches
        if _has_related_name_term(query_terms, recipes[index]["nom"])
    ]


def _is_follow_up(query: str) -> bool:
    terms = normalize_text(query).split()
    return len(terms) <= 10 and bool(set(terms) & FOLLOW_UP_MARKERS)


def _resolve_from_history(
    query: str,
    previous_user_messages: Iterable[str],
) -> list[dict[str, str]]:
    current_matches = search_recipes(query, limit=5)
    if current_matches and (len(current_matches) == 1 or not _is_follow_up(query)):
        return current_matches

    for previous_query in reversed(list(previous_user_messages)):
        previous_matches = search_recipes(previous_query, limit=5)
        if not previous_matches:
            continue
        if not current_matches:
            return previous_matches
        previous_categories = {
            normalize_text(recipe["categorie"]) for recipe in previous_matches
        }
        same_category = [
            recipe for recipe in current_matches
            if normalize_text(recipe["categorie"]) in previous_categories
        ]
        return same_category or current_matches
    return current_matches


def _format_full_recipe(recipe: dict[str, str]) -> str:
    photo = (
        f"Photo: {recipe['photos'].strip()}"
        if is_safe_photo_url(recipe.get("photos")) else "Photo: aucune"
    )
    return "\n".join([
        f"Identifiant: {recipe['id']}",
        f"Nom: {recipe['nom']}",
        f"Catégorie: {recipe['categorie']}",
        f"Ingrédients: {recipe['ingredients']}",
        f"Étapes: {recipe['etapes']}",
        f"Outils: {recipe['outils']}",
        (
            f"Cuisson: {recipe['type_cuisson']}, "
            f"{recipe['four_temperature_C']} °C, "
            f"{recipe['four_duree_min']} min"
        ),
        f"Préparation: {recipe['temps_preparation_min']} min",
        f"Portions: {recipe['nombre_portions']}",
        f"Difficulté: {recipe['difficulte']}",
        photo,
    ])


def _format_recipe_summary(recipe: dict[str, str]) -> str:
    return (
        f"- {recipe['nom']} (id {recipe['id']}) — "
        f"cuisson: {recipe['type_cuisson']}, "
        f"{recipe['four_temperature_C']} °C, "
        f"{recipe['four_duree_min']} min; "
        f"préparation: {recipe['temps_preparation_min']} min; "
        f"portions: {recipe['nombre_portions']}; "
        f"difficulté: {recipe['difficulte']}"
    )


def build_recipe_context(
    user_content: str,
    previous_user_messages: Iterable[str] = (),
) -> str:
    """Build detailed or compact context for the resolved request."""
    recipes = _resolve_from_history(user_content, previous_user_messages)
    if not recipes:
        return ""
    if len(recipes) <= 3:
        return "\n\n---\n\n".join(_format_full_recipe(recipe) for recipe in recipes)
    cooking_types = ", ".join(dict.fromkeys(
        recipe["type_cuisson"] for recipe in recipes
    ))
    return (
        "Chaque recette ci-dessous satisfait déjà les critères de la demande. "
        f"La liste exhaustive contient {len(recipes)} recettes et les types de "
        f"cuisson suivants: {cooking_types}. Ne la filtre pas une seconde fois, "
        "ne la réduis pas à un seul type de cuisson et n'ajoute aucune recette "
        "extérieure. Restitue chacun des noms fournis.\n"
        "Recettes correspondant aux critères:\n"
    ) + "\n".join(
        _format_recipe_summary(recipe) for recipe in recipes
    )
