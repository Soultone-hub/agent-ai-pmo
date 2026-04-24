"""
Service d'anonymisation PII locale — conformité RGPD.

Principle : tout ce qui peut relier le projet à une personne physique est masqué.
Les données analytiques (montants, dates, métriques) sont CONSERVÉES intactes.

GROQ ne voit JAMAIS les données sensibles.

Entités anonymisées :
  - NOM_PROPRE  : "Jean-Pierre Dupont" → [NOM_PROPRE_1]
  - EMAIL       : "jean@acme.fr"       → [EMAIL_1]
  - TELEPHONE   : "06 12 34 56 78"     → [TELEPHONE_1]
  - ADRESSE     : "12 rue de la Paix"  → [ADRESSE_1]
  - VILLE       : "Lyon", "Bordeaux"   → [VILLE_1]
  - IBAN        : "FR76 3000..."        → [IBAN_1]
  - SIRET       : "123 456 789 01234"  → [SIRET_1]
  - CARTE_CB    : "4111 1111 1111 1111"→ [CARTE_CB_1]
  - IP          : "192.168.1.1"        → [IP_1]

Données CONSERVÉES (utiles à l'analyse PMO) :
  - Montants financiers  : 150 000 €, 1,2 M€
  - Dates / délais       : 15/04/2026, Q3 2026
  - Métriques / KPI      : 87%, 3 jours de retard
"""

import re
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Liste des villes françaises les plus courantes ────────────────────────────
# (utilisée pour détecter les villes isolées hors contexte d'adresse)
VILLES_FRANCE = {
    "Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes", "Strasbourg",
    "Montpellier", "Bordeaux", "Lille", "Rennes", "Reims", "Le Havre", "Toulon",
    "Grenoble", "Dijon", "Angers", "Nîmes", "Villeurbanne", "Saint-Étienne",
    "Clermont-Ferrand", "Le Mans", "Aix-en-Provence", "Brest", "Tours",
    "Amiens", "Limoges", "Annecy", "Perpignan", "Boulogne-Billancourt",
    "Metz", "Besançon", "Orléans", "Mulhouse", "Rouen", "Caen", "Nancy",
    "Saint-Denis", "Argenteuil", "Paul", "Montreuil", "Versailles",
    "Nanterre", "Créteil", "Avignon", "Poitiers", "Colombes", "Fort-de-France",
    "Courbevoie", "Vitry-sur-Seine", "Rueil-Malmaison", "La Rochelle",
    "Dunkerque", "Cannes", "Antibes", "Bayonne", "Épinal", "Quimper",
    "Lorient", "Valence", "Pau", "Calais", "Bourges", "Troyes",
    "Issy-les-Moulineaux", "Levallois-Perret", "Ajaccio", "Liège",
    "Genève", "Lausanne", "Bruxelles", "Luxembourg", "Monaco",
    "Londres", "Berlin", "Madrid", "Rome", "Lisbonne", "Amsterdam",
    "Casablanca", "Tunis", "Alger", "Dakar", "Abidjan",
}

# Préfixes de voies pour la détection d'adresses
TYPES_VOIE = (
    r"(?:rue|avenue|boulevard|blvd|bd|allée|impasse|place|chemin|route|voie"
    r"|passage|cour|square|résidence|villa|hameau|lotissement|quartier"
    r"|cité|domaine|parc|zone|zi|zac|za|zae|zui)"
)

# ── Patterns PII (ordre : du plus spécifique au plus général) ─────────────────
ENTITY_PATTERNS = [
    # IBAN — très structuré
    (
        "IBAN",
        r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]{4}){4,7}\b",
    ),

    # Carte bancaire (16 chiffres groupés)
    (
        "CARTE_CB",
        r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
    ),

    # SIRET (14 chiffres) — avant SIREN pour matcher le plus long d'abord
    (
        "SIRET",
        r"\b\d{3}[\s.]?\d{3}[\s.]?\d{3}[\s.]?\d{5}\b",
    ),

    # SIREN (9 chiffres)
    (
        "SIREN",
        r"\b\d{3}[\s.]?\d{3}[\s.]?\d{3}\b",
    ),

    # Email
    (
        "EMAIL",
        r"\b[\w.+%-]+@[\w.-]+\.[a-zA-Z]{2,}\b",
    ),

    # Téléphone français (fixe, mobile, international)
    (
        "TELEPHONE",
        (
            r"\b(?:"
            r"(?:\+33|0033)[\s.\-]?[1-9](?:[\s.\-]?\d{2}){4}"
            r"|0[1-9](?:[\s.\-]?\d{2}){4}"
            r")\b"
        ),
    ),

    # Adresse complète : numéro + type de voie + nom de voie
    (
        "ADRESSE",
        (
            r"\b\d{1,4}(?:\s*(?:bis|ter|quater))?"
            r"\s+" + TYPES_VOIE + r"\s+[A-Za-zÀ-ÿ\s'\-]{2,40}\b"
        ),
    ),

    # Code postal (5 chiffres français — souvent suivi d'une ville)
    (
        "CODE_POSTAL",
        r"\b(?:0[1-9]|[1-8]\d|9[0-5]|97[1-6])\d{3}\b",
    ),

    # URL personnelle (on garde les domaines génériques, exclut les grandes plateformes)
    (
        "URL",
        r"https?://(?!(?:www\.)?(?:google|microsoft|amazon|github|wikipedia)\.)[^\s\"'<>]+",
    ),

    # Adresse IP
    (
        "IP",
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    ),

    # Noms propres : 2 à 4 mots avec majuscule initiale
    # Heuristique : pas en début de phrase (précédé d'un espace ou ponctuation)
    (
        "NOM_PROPRE",
        (
            r"(?<=[,;:\s\(«»\"\'])?"
            r"\b[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜŸÆŒ][a-zàâäéèêëîïôùûüÿæœ\-]+"
            r"(?:\s+[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜŸÆŒ][a-zàâäéèêëîïôùûüÿæœ\-]+){1,3}\b"
        ),
    ),
]

# Mots qui matchent NOM_PROPRE mais ne sont pas des personnes
NOM_PROPRE_WHITELIST: set[str] = {
    # Mois et jours
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
    # Titres et fonctions (sans nom de famille attaché)
    "Monsieur", "Madame", "Directeur", "Directrice", "Président", "Chef",
    "Responsable", "Manager", "Ingénieur", "Consultant", "Architecte",
    # Termes PMO
    "Charte", "Cadrage", "Annexe", "Article", "Section", "Phase", "Étape",
    "Version", "Rapport", "Projet", "Budget", "Planning", "Cahier", "Charges",
    "Comité", "Pilotage", "Copil", "Direction", "Générale", "Stratégie",
    # Organisations génériques reconnaissables
    "Microsoft", "Google", "Amazon", "Apple", "Oracle", "SAP", "IBM",
    "Salesforce", "Capgemini", "Accenture", "Sopra", "Sopra Steria",
    # Pays et grandes régions
    "France", "Europe", "Afrique", "Asie", "Amérique", "Royaume-Uni",
    "Île-de-France", "Auvergne-Rhône-Alpes",
} | VILLES_FRANCE  # Les villes sont gérées séparément, mais on les exclut du NOM_PROPRE


def _detect_ville(text: str, counters: dict, real_to_placeholder: dict) -> None:
    """Détecte les noms de villes connus dans le texte."""
    for ville in VILLES_FRANCE:
        pattern = r"\b" + re.escape(ville) + r"\b"
        if re.search(pattern, text, re.UNICODE):
            if ville not in real_to_placeholder:
                counters["VILLE"] += 1
                placeholder = f"[VILLE_{counters['VILLE']}]"
                real_to_placeholder[ville] = placeholder


def _build_mapping(text: str) -> dict[str, str]:
    """
    Scanne le texte et construit le mapping { valeur_réelle → placeholder }.
    Seules les données PII sont ciblées. Montants et dates sont ignorés.
    """
    real_to_placeholder: dict[str, str] = {}
    counters: dict[str, int] = defaultdict(int)

    # 1. Détection par regex
    for entity_type, pattern in ENTITY_PATTERNS:
        try:
            for match in re.finditer(pattern, text, re.UNICODE | re.IGNORECASE):
                real_value = match.group(0).strip()

                if not real_value:
                    continue

                # Filtres spécifiques NOM_PROPRE
                if entity_type == "NOM_PROPRE":
                    if real_value in NOM_PROPRE_WHITELIST:
                        continue
                    # Un seul mot sans espace = probablement pas un nom complet
                    if " " not in real_value and "-" not in real_value:
                        continue
                    # Déjà capturé par un pattern précédent (ex: EMAIL qui contient un nom)
                    if real_value in real_to_placeholder:
                        continue

                if real_value not in real_to_placeholder:
                    counters[entity_type] += 1
                    placeholder = f"[{entity_type}_{counters[entity_type]}]"
                    real_to_placeholder[real_value] = placeholder

        except re.error as e:
            logger.warning(f"Regex error for pattern {entity_type}: {e}")
            continue

    # 2. Détection des villes connues
    _detect_ville(text, counters, real_to_placeholder)

    return real_to_placeholder


def anonymize(text: str) -> tuple[str, dict[str, str]]:
    """
    Anonymise les données PII du texte. Les montants et dates sont conservés.

    Args:
        text: Texte brut extrait du document

    Returns:
        anonymized_text: Texte sûr pour envoi au LLM (Groq ne voit pas les PII)
        mapping: { "[EMAIL_1]": "jean@acme.fr", ... } pour la dé-anonymisation
    """
    if not text or not text.strip():
        return text, {}

    real_to_placeholder = _build_mapping(text)

    if not real_to_placeholder:
        logger.info("Anonymisation PII : aucune donnée personnelle détectée.")
        return text, {}

    # Remplacer du plus long au plus court (évite les substitutions partielles)
    anonymized = text
    for real_value, placeholder in sorted(
        real_to_placeholder.items(), key=lambda x: len(x[0]), reverse=True
    ):
        anonymized = anonymized.replace(real_value, placeholder)

    # Inverser le mapping pour la dé-anonymisation : placeholder → vraie valeur
    mapping: dict[str, str] = {v: k for k, v in real_to_placeholder.items()}

    nb = len(mapping)
    types_found = sorted({p.split("_")[0].lstrip("[") for p in mapping.keys()})
    logger.info(f"Anonymisation PII : {nb} entité(s) masquée(s) — {types_found}")

    return anonymized, mapping


def deanonymize(text: str, mapping: dict[str, str]) -> str:
    """
    Remplace les placeholders dans une chaîne par les vraies valeurs.

    mapping = { "[EMAIL_1]": "jean@acme.fr", "[NOM_PROPRE_1]": "Jean Dupont", ... }
    """
    if not text or not mapping:
        return text
    for placeholder, real_value in mapping.items():
        text = text.replace(placeholder, real_value)
    return text


def deanonymize_result(data, mapping: dict[str, str]):
    """
    Parcourt récursivement un résultat JSON (dict / list / str) et remplace
    tous les placeholders PII par les vraies valeurs.

    Appelé UNIQUEMENT côté serveur, après la réponse du LLM,
    AVANT de renvoyer la réponse au frontend.

    Groq n'a JAMAIS vu les données réelles.
    """
    if not mapping:
        return data
    if isinstance(data, str):
        return deanonymize(data, mapping)
    if isinstance(data, list):
        return [deanonymize_result(item, mapping) for item in data]
    if isinstance(data, dict):
        return {key: deanonymize_result(value, mapping) for key, value in data.items()}
    # Nombres, booléens, None : inchangés
    return data


def get_anonymization_summary(mapping: dict[str, str]) -> dict:
    """Retourne un résumé des entités anonymisées (pour les logs / UI)."""
    summary: dict[str, int] = defaultdict(int)
    for placeholder in mapping.keys():
        entity_type = placeholder.split("_")[0].lstrip("[")
        summary[entity_type] += 1
    return dict(summary)


def merge_maps_from_docs(docs: list) -> dict[str, str]:
    """
    Fusionne les anonymization_map de plusieurs documents en un seul mapping.

    Args:
        docs: liste d'objets Document ORM

    Returns:
        mapping fusionné { "[PLACEHOLDER]": "valeur_réelle", ... }
        → dict vide si aucun document n'est anonymisé
    """
    merged: dict[str, str] = {}
    for doc in docs:
        if doc.is_anonymized and doc.anonymization_map:
            merged.update(doc.anonymization_map)
    return merged
