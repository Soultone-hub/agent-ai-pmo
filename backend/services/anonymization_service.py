"""
Service d'anonymisation PII locale — protection des données personnelles (RGPD/loi béninoise).

Principle : tout ce qui peut relier le projet à une personne physique est masqué.
Les données analytiques (montants, dates, métriques) sont CONSERVÉES intactes.

GROQ ne voit JAMAIS les données sensibles.

Entités anonymisées :
  - NOM_PROPRE  : "Koffi Adjovi"         → [NOM_PROPRE_1]
  - EMAIL       : "koffi@entreprise.bj"  → [EMAIL_1]
  - TELEPHONE   : "+229 97 12 34 56"     → [TELEPHONE_1]
  - ADRESSE     : "12 rue du Commerce"   → [ADRESSE_1]
  - VILLE       : "Cotonou", "Parakou"   → [VILLE_1]
  - IBAN        : "BJ89 XXX..."          → [IBAN_1]
  - IFU         : "1234567890123"        → [IFU_1]
  - RCCM        : "RB/COT/2021/B/1234"  → [RCCM_1]
  - CARTE_CB    : "4111 1111 1111 1111" → [CARTE_CB_1]
  - IP          : "192.168.1.1"          → [IP_1]

Données CONSERVÉES (utiles à l'analyse PMO) :
  - Montants financiers  : 500 000 FCFA, 1,2 million FCFA
  - Dates / délais       : 15/04/2026, T3 2026
  - Métriques / KPI      : 87%, 3 jours de retard
"""

import regex as re   # pip install regex — supérieur à stdlib re : Unicode \p{Lu} \p{Ll}, lookbehind variable, groupes atomiques
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Villes du Bénin et de la sous-région Afrique de l'Ouest ───────────────────
VILLES_AFRIQUE_OUEST = {
    # Bénin
    "Cotonou", "Porto-Novo", "Parakou", "Djougou", "Bohicon", "Kandi",
    "Ouidah", "Abomey-Calavi", "Lokossa", "Natitingou", "Malanville",
    "Abomey", "Tchaourou", "Bembereke", "Nikki", "Savalou", "Savé",
    "Dassa-Zoumé", "Kpomassè", "Calavi", "Semes",
    # Togo
    "Lomé", "Sokodé", "Kara", "Palimé", "Atakpamé", "Tsevié",
    # Nigeria
    "Lagos", "Abuja", "Ibadan", "Kano", "Kaduna", "Port Harcourt",
    # Ghana
    "Accra", "Kumasi", "Tamale",
    # Côte d'Ivoire
    "Abidjan", "Yamoussoukro", "Bouaké",
    # Sénégal
    "Dakar", "Thiès", "Saint-Louis",
    # Niger
    "Niamey", "Zinder", "Maradi",
    # Burkina Faso
    "Ouagadougou", "Bobo-Dioulasso",
    # Mali
    "Bamako", "Sikasso",
    # Autres capitales régionales
    "Yaoundé", "Douala", "Libreville", "Brazzaville", "Kinshasa",
    "Lompo", "Conakry", "Freetown", "Monrovia", "Bissau",
}

# Préfixes de voies pour la détection d'adresses (multilingual : fr + local)
TYPES_VOIE = (
    r"(?:rue|avenue|boulevard|blvd|bd|allée|impasse|place|chemin|route|voie"
    r"|passage|cour|square|résidence|villa|quartier|cé|lot|ilôt|carré"
    r"|cité|domaine|zone|carrefour|rond-point)"
)

# ── Patterns PII (ordre : du plus spécifique au plus général) ─────────────────
ENTITY_PATTERNS = [
    # IBAN UEMOA/Bénin (BJ + codes des pays membres : BF, CI, GW, ML, NE, SN, TG)
    # Format : 2 lettres pays + 2 chiffres clé + jusqu'à 24 caractères
    (
        "IBAN",
        r"\b(?:BJ|BF|CI|GW|ML|NE|SN|TG|[A-Z]{2})\d{2}(?:[\s-]?[A-Z0-9]{4}){4,7}\b",
    ),

    # Carte bancaire (16 chiffres groupés)
    (
        "CARTE_CB",
        r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
    ),

    # IFU (Identifiant Fiscal Unique du Bénin — 13 chiffres)
    (
        "IFU",
        r"\bIFU\s*:?\s*\d{13}\b|\b\d{13}\b",
    ),

    # RCCM (Registre du Commerce et du Crédit Mobilier)
    # Format ex: RB/COT/2021/B/1234 ou RF/LME/2020/A/5678
    (
        "RCCM",
        r"\bR[A-Z]/[A-Z]{2,4}/\d{4}/[A-Z]/\d+\b",
    ),

    # Email
    (
        "EMAIL",
        r"\b[\w.+%-]+@[\w.-]+\.[a-zA-Z]{2,}\b",
    ),

    # Téléphone Bénin (+229) et Afrique de l'Ouest
    # Bénin: +229 XX XX XX XX (8 chiffres) ou 00229...
    # Formats régionaux : +225, +228, +234, +221, +226, +223, +227
    (
        "TELEPHONE",
        (
            r"\b(?:"
            r"(?:\+|00)229\s?(?:01\d(?:\s?\d){7}|(?:97|98|99|90|91|94|95|96)\d(?:\s?\d){5})"
            r"|(?:\+|00)(?:225|228|221|226|223|227)\s?\d(?:\s?\d){7}"
            r"|(?:\+|00)234\s?\d(?:\s?\d){9}"
            r"|(?:\+|00)33\s?[1-9](?:\s?\d{2}){4}"
            r"|0[1-9](?:\s?\d{2}){4}"
            r"|01\d(?:\s?\d){7}"
            r"|(?:97|98|99|90|91|94|95|96)\d(?:\s?\d){5}"
            r")\b"
        ),
    ),

    # Adresse complète : numéro + type de voie + nom de voie
    (
        "ADRESSE",
        (
            r"\b\d{1,4}(?:\s*(?:bis|ter|quater))?"
            r"\s+" + TYPES_VOIE + r"\s+[A-Za-z\xC0-\xFF\s'\-]{2,40}\b"
        ),
    ),

    # URL personnelle
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
    # \p{Lu} = toute lettre majuscule Unicode, \p{Ll} = minuscule
    # Fonctionne avec la lib 'regex' (pas stdlib re)
    # Ex: Koffi Adjovi, Jean-Baptiste Ahossou, Dossou Rodrigue
    (
        "NOM_PROPRE",
        (
            r"\b\p{Lu}[\p{Ll}\p{Lu}'\u2019\-]+"
            r"(?:\s+(?:\p{Ll}{1,3}\s+)?"
            r"\p{Lu}[\p{Ll}\p{Lu}'\u2019\-]+){1,3}\b"
        ),
    ),
]

# Mots qui matchent NOM_PROPRE mais ne sont pas des personnes
NOM_PROPRE_WHITELIST: set[str] = {
    # Mois et jours
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
    # Titres et fonctions
    "Monsieur", "Madame", "Directeur", "Directrice", "Président", "Chef",
    "Responsable", "Manager", "Ingénieur", "Consultant", "Architecte",
    "Coordinateur", "Coordonnatrice", "Représentant", "Délégué",
    # Termes PMO
    "Charte", "Cadrage", "Annexe", "Article", "Section", "Phase", "Étape",
    "Version", "Rapport", "Projet", "Budget", "Planning", "Cahier", "Charges",
    "Comité", "Pilotage", "Copil", "Direction", "Générale", "Stratégie",
    # Institutions béninoises et africaines
    "Ministère", "Direction Générale", "Office Nationale", "Agence Nationale",
    "Gouvernement", "Présidence", "République", "Bénin",
    "UEMOA", "CEDEAO", "BCEAO", "BIDC", "BAD", "PNUD", "UNICEF", "OMS",
    # Grandes organisations tech
    "Microsoft", "Google", "Amazon", "Apple", "Oracle", "SAP", "IBM",
    # Pays et régions
    "Afrique", "Asie", "Amérique", "Europe",
    "Afrique Ouest", "Afrique Centrale", "Sahel",
    "Nigeria", "Ghana", "Togo", "Niger", "Burkina", "Mali",
    "Sénégal", "Côte Ivoire", "Cameroun", "Gabon",
} | VILLES_AFRIQUE_OUEST  # Les villes sont exclues du pattern NOM_PROPRE


def _detect_ville(text: str, counters: dict, real_to_placeholder: dict) -> None:
    """Détecte les noms de villes connus dans le texte."""
    for ville in VILLES_AFRIQUE_OUEST:
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
