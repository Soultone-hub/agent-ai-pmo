"""
anonymization_service.py — Adaptateur vers la Pipeline d'anonymisation.

Ce fichier est le point d'entrée unique pour tous les routers FastAPI.
Il délègue tout le travail réel au module `pipeline/` et expose
exactement les mêmes fonctions publiques qu'avant pour ne pas casser
les imports existants.

API publique conservée :
    anonymize(text)                        → (anonymized_text, mapping)
    deanonymize(text, mapping)             → str
    deanonymize_result(data, mapping)      → dict | list | str
    get_anonymization_summary(mapping)     → dict
    merge_maps_from_docs(docs)             → dict
"""

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Import de la pipeline (package Python standard) ────────────────────────────
# uvicorn est lancé depuis c:\agent-ia-pmo\backend_FastAPI\agent-ia-pmo
# donc `pipeline/` est directement importable comme package.
try:
    from pipeline import AnonymizationPipeline
    _pipeline: AnonymizationPipeline | None = AnonymizationPipeline()
    logger.info("Pipeline d'anonymisation chargée depuis pipeline/.")
    _PIPELINE_AVAILABLE = True
except Exception as e:
    logger.warning(
        "Impossible de charger pipeline/ (%s). "
        "Le service d'anonymisation sera désactivé.",
        e
    )
    with open("pipeline_import_error.log", "w", encoding="utf-8") as f:
        import traceback
        traceback.print_exc(file=f)
    _pipeline = None
    _PIPELINE_AVAILABLE = False


# ── Fonctions publiques (interface identique à l'ancienne implémentation) ──────

def anonymize(text: str) -> tuple[str, dict[str, str]]:
    """
    Anonymise les données PII du texte via la nouvelle pipeline.

    Returns:
        anonymized_text : Texte sûr pour envoi au LLM
        mapping         : { "[PLACEHOLDER]": "valeur_réelle" }
    """
    if not text or not text.strip():
        return text, {}

    if not _PIPELINE_AVAILABLE or _pipeline is None:
        logger.warning("Pipeline indisponible — texte envoyé sans anonymisation.")
        return text, {}

    try:
        result = _pipeline.run(text)

        # La pipeline retourne mapping = { "Jean Dupont" → "[PERSONNE_1]" }
        # On l'inverse : { "[PERSONNE_1]" → "Jean Dupont" } (convention des routers)
        inverse_mapping: dict[str, str] = {v: k for k, v in result.mapping.items()}

        nb = len(inverse_mapping)
        if nb:
            types_found = sorted({p.split("_")[0].lstrip("[") for p in inverse_mapping})
            logger.info("Anonymisation PII : %d entité(s) masquée(s) — %s", nb, types_found)
        else:
            logger.info("Anonymisation PII : aucune donnée personnelle détectée.")

        return result.clean_text, inverse_mapping

    except Exception as e:
        logger.error("Erreur lors de l'anonymisation : %s — texte retourné brut.", e)
        return text, {}


def deanonymize(text: str, mapping: dict[str, str]) -> str:
    """
    Remplace les placeholders dans une chaîne par les vraies valeurs.
    mapping = { "[PERSONNE_1]": "Jean Dupont", ... }
    """
    if not text or not mapping:
        return text
    for placeholder, real_value in mapping.items():
        text = text.replace(placeholder, real_value)
    return text


def deanonymize_result(data: object, mapping: dict[str, str]) -> object:
    """
    Parcourt récursivement un résultat JSON et remplace les placeholders.
    Appelé côté serveur, après la réponse du LLM, avant envoi au frontend.
    """
    if not mapping:
        return data
    if isinstance(data, str):
        return deanonymize(data, mapping)
    if isinstance(data, list):
        return [deanonymize_result(item, mapping) for item in data]
    if isinstance(data, dict):
        return {key: deanonymize_result(value, mapping) for key, value in data.items()}
    return data


def get_anonymization_summary(mapping: dict[str, str]) -> dict[str, int]:
    """Retourne un résumé des entités anonymisées (pour les logs / UI)."""
    summary: dict[str, int] = defaultdict(int)
    for placeholder in mapping.keys():
        entity_type = placeholder.split("_")[0].lstrip("[")
        summary[entity_type] += 1
    return dict(summary)


def merge_maps_from_docs(docs: list) -> dict[str, str]:
    """
    Fusionne les anonymization_map de plusieurs documents en un seul mapping.
    """
    merged: dict[str, str] = {}
    for doc in docs:
        if doc.is_anonymized and doc.anonymization_map:
            merged.update(doc.anonymization_map)
    return merged
