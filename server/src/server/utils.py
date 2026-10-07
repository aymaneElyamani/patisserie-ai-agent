"""Lightweight local search for the pastry CSV database."""

import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from rapidfuzz import fuzz, process

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "data.csv"

REQUIRED_CSV_FIELDS = (
    "id",
    "nom",
    "categorie",
    "ingredients",
    "etapes",
    "outils",
    "temps_preparation_min",
    "type_cuisson",
    "four_temperature_C",
    "four_duree_min",
    "nombre_portions",
    "difficulte",
    "photos",
)

STOP_WORDS = {
    # French
    "a", "au", "aux", "avec", "de", "des", "du", "en",
    "et", "la", "le", "les", "pour", "recette", "une", "un",
    "je", "veux", "faire", "comment", "donne", "moi", "preparer",

    # English
    "a", "an", "and", "how", "make", "of", "recipe", "the", "to",
    "want", "with",

    # Common Darija/Arabic transliterations
    "bghit", "dyal", "kifach", "ndir",
}


def normalize_text(value: str | None) -> str:
    """Lowercase text, remove accents, and normalize punctuation."""
    if not value:
        return ""

    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def extract_terms(query: str) -> list[str]:
    """Extract useful search terms from a user question."""
    return [
        term
        for term in normalize_text(query).split()
        if len(term) >= 2 and term not in STOP_WORDS
    ]


@lru_cache(maxsize=1)
def load_recipes() -> tuple[dict[str, str], ...]:
    """Load the CSV once and keep it in memory."""
    with CSV_PATH.open(
        mode="r",
        encoding="utf-8-sig",  # Handles the BOM in your CSV
        newline="",
    ) as csv_file:
        reader = csv.DictReader(csv_file, delimiter=";")
        missing_fields = set(REQUIRED_CSV_FIELDS) - set(reader.fieldnames or ())
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise RuntimeError(f"Colonnes CSV manquantes : {missing}")
        return tuple(dict(row) for row in reader)


def is_safe_photo_url(value: str | None) -> bool:
    """Accept only public HTTPS URLs from the CSV photo column."""
    if not value:
        return False
    parsed = urlsplit(value.strip())
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
    )


def search_recipes(
    query: str,
    limit: int = 3,
    minimum_score: float = 60,
) -> list[dict[str, str]]:
    """Find recipe names with RapidFuzz, tolerating accents and small typos."""
    search_query = " ".join(extract_terms(query))
    if not search_query:
        return []

    recipes = load_recipes()
    choices = {
        index: normalize_text(recipe.get("nom"))
        for index, recipe in enumerate(recipes)
    }
    matches = process.extract(
        search_query,
        choices,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=minimum_score,
    )
    return [recipes[index] for _, _, index in matches]







def build_recipe_context(user_content: str) -> str:
    recipes = search_recipes(user_content, limit=3)

    if not recipes:
        return ""

    entries = []

    for recipe in recipes:
        entries.append(
            "\n".join(
                [
                    f"Nom: {recipe['nom']}",
                    f"Catégorie: {recipe['categorie']}",
                    f"Ingrédients: {recipe['ingredients']}",
                    f"Étapes: {recipe['etapes']}",
                    f"Outils: {recipe['outils']}",
                    (
                        "Cuisson: "
                        f"{recipe['type_cuisson']}, "
                        f"{recipe['four_temperature_C']} °C, "
                        f"{recipe['four_duree_min']} min"
                    ),
                    f"Portions: {recipe['nombre_portions']}",
                    f"Difficulté: {recipe['difficulte']}",
                    (
                        f"Photo CSV: {recipe['photos'].strip()}"
                        if is_safe_photo_url(recipe.get("photos"))
                        else "Photo CSV: aucune"
                    ),
                ]
            )
        )

    return "\n\n---\n\n".join(entries)
