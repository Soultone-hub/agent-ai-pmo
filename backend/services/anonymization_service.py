"""
Service d'anonymisation PII locale — protection des données personnelles (RGPD/loi béninoise).

Principle : tout ce qui peut relier le projet à une personne PHYSIQUE est masqué.
Les données analytiques (montants, dates, métriques) sont CONSERVÉES intactes.
Le contenu textuel du document (titres, sections, termes techniques) est CONSERVÉ.

GROQ ne voit JAMAIS les données sensibles.

Entités anonymisées :
  - NOM_PROPRE  : "AMOUSSA Soultone"       → [NOM_PROPRE_1]
  - EMAIL       : "koffi@entreprise.bj"    → [EMAIL_1]
  - TELEPHONE   : "+229 01 97 12 34 56"    → [TELEPHONE_1]
  - ADRESSE     : "12 avenue du Commerce"  → [ADRESSE_1]
  - VILLE       : "Cotonou", "Parakou"     → [VILLE_1]
  - IBAN        : "BJ89 XXX..."            → [IBAN_1]
  - IFU         : "1234567890123"          → [IFU_1]
  - RCCM        : "RB/COT/2021/B/1234"    → [RCCM_1]
  - CARTE_CB    : "4111 1111 1111 1111"   → [CARTE_CB_1]
  - IP          : "192.168.1.1"            → [IP_1]

Stratégie NOM_PROPRE (clé du système) :
  - Seuls les NOMS DE PERSONNES sont masqués.
  - Critère : au moins un composant doit être en MAJUSCULES ENTIÈRES (≥ 2 lettres).
    → "AMOUSSA Soultone"  ✅  (AMOUSSA est tout en majuscules)
    → "DOMINGO Jordan"    ✅  (DOMINGO est tout en majuscules)
    → "Informations générales"  ❌  (aucun mot 100% majuscules)
    → "Développement Agent IA"  ❌  (aucun mot 100% majuscules ≥ 2 lettres)

Données CONSERVÉES (utiles à l'analyse PMO) :
  - Montants financiers  : 500 000 FCFA, 280 000 FCFA
  - Dates / délais       : 15/04/2026, T3 2026, 24 Avril 2026
  - Métriques / KPI      : 87%, 3 jours de retard
  - Texte structurel     : titres, sections, termes techniques
"""

import regex as re   # pip install regex — supérieur à stdlib re : Unicode \\p{Lu} \\p{Ll}
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Villes du Bénin et de la sous-région Afrique de l'Ouest ───────────────────
VILLES_AFRIQUE_OUEST = {
    # Bénin
    "Cotonou", "Porto-Novo", "Parakou", "Djougou", "Bohicon", "Kandi",
    "Ouidah", "Abomey-Calavi", "Lokossa", "Natitingou", "Malanville",
    "Abomey", "Tchaourou", "Bembereke", "Nikki", "Savalou", "Savé",
    "Dassa-Zoumé", "Kpomassè", "Calavi",
    # Togo
    "Lomé", "Sokodé", "Kara", "Palimé", "Atakpamé", "Tsevié",
    # Nigeria
    "Lagos", "Abuja", "Ibadan", "Kano", "Kaduna",
    # Ghana
    "Accra", "Kumasi", "Tamale",
    # Côte d'Ivoire
    "Abidjan", "Yamoussoukro", "Bouaké",
    # Sénégal
    "Dakar", "Thiès",
    # Niger
    "Niamey", "Zinder", "Maradi",
    # Burkina Faso
    "Ouagadougou", "Bobo-Dioulasso",
    # Mali
    "Bamako", "Sikasso",
    # Autres
    "Yaoundé", "Douala", "Libreville", "Brazzaville", "Kinshasa",
    "Conakry", "Freetown", "Monrovia",
}

# Préfixes de voies pour la détection d'adresses
TYPES_VOIE = (
    r"(?:rue|avenue|boulevard|blvd|bd|allée|impasse|place|chemin|route|voie"
    r"|passage|cour|square|résidence|villa|quartier|lot|ilôt|carré"
    r"|cité|domaine|zone|carrefour|rond-point)"
)

# ── Patterns PII (ordre : du plus spécifique au plus général) ─────────────────
ENTITY_PATTERNS = [
    # IBAN UEMOA/Bénin
    (
        "IBAN",
        r"\b(?:BJ|BF|CI|GW|ML|NE|SN|TG|[A-Z]{2})\d{2}(?:[\s-]?[A-Z0-9]{4}){4,7}\b",
    ),

    # Carte bancaire (16 chiffres groupés)
    (
        "CARTE_CB",
        r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
    ),

    # IFU (Identifiant Fiscal Unique Bénin — 13 chiffres)
    (
        "IFU",
        r"\bIFU\s*:?\s*\d{13}\b|\b\d{13}\b",
    ),

    # RCCM
    (
        "RCCM",
        r"\bR[A-Z]/[A-Z]{2,4}/\d{4}/[A-Z]/\d+\b",
    ),

    # Email
    (
        "EMAIL",
        r"\b[\w.+%-]+@[\w.-]+\.[a-zA-Z]{2,}\b",
    ),

    # Téléphone Bénin (+229, 10 chiffres depuis 2024) et CEDEAO
    (
        "TELEPHONE",
        (
            r"\b(?:"
            r"(?:\+|00)229\s?(?:01\d(?:\s?\d){7}|(?:97|98|99|90|91|94|95|96)\d(?:\s?\d){5})"
            r"|(?:\+|00)(?:225|228|221|226|223|227)\s?\d(?:\s?\d){7}"
            r"|(?:\+|00)234\s?\d(?:\s?\d){9}"
            r"|01\d(?:\s?\d){7}"
            r"|(?:97|98|99|90|91|94|95|96)\d(?:\s?\d){5}"
            r")\b"
        ),
    ),

    # Adresse complète
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

    # ── Noms de PERSONNES — pattern strict ────────────────────────────────────
    # Critère : au moins un composant doit être en MAJUSCULES ENTIÈRES (≥ 2 lettres).
    # Cela distingue les noms propres de personnes des titres/termes courants.
    #
    # Cas 1 : NOM_MAJUSCULES + 1-2 Prénoms Title Case
    #   → "AMOUSSA Soultone", "DOMINGO Jordan Baptiste"
    # Cas 2 : 1-2 Prénoms Title Case + NOM_MAJUSCULES
    #   → "Soultone AMOUSSA", "Jordan DOMINGO"
    (
        "NOM_PROPRE",
        (
            # Cas 1 : MOT_EN_MAJUSCULES (≥2 lettres) suivi de 1-2 mots Title Case
            r"\b\p{Lu}{2,}(?:\-\p{Lu}{2,})*(?:[ \t]+\p{Lu}\p{Ll}[\p{Ll}\p{Lu}\-']{1,}){1,2}\b"
            r"|"
            # Cas 2 : 1-2 mots Title Case suivis d'un MOT_EN_MAJUSCULES (≥2 lettres)
            r"\b\p{Lu}\p{Ll}[\p{Ll}\p{Lu}\-']{1,}(?:[ \t]+\p{Lu}\p{Ll}[\p{Ll}\p{Lu}\-']{1,})?"
            r"[ \t]+\p{Lu}{2,}(?:\-\p{Lu}{2,})*\b"
        ),
    ),
]

# ── Sigles/acronymes en MAJUSCULES qui ne sont PAS des noms de personnes ──────
ACRONYMS_WHITELIST: set[str] = {
    # Mois et jours
    "JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN",
    "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE",
    "LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE",
    # Titres et fonctions
    "MONSIEUR", "MADAME", "DIRECTEUR", "DIRECTRICE", "PRÉSIDENT", "CHEF",
    "RESPONSABLE", "MANAGER", "INGÉNIEUR", "CONSULTANT", "ARCHITECTE",
    "COORDINATEUR", "COORDONNATRICE", "REPRÉSENTANT", "DÉLÉGUÉ",
    # Gestion de projet / Termes PMO
    "CHARTE", "CADRAGE", "ANNEXE", "ARTICLE", "SECTION", "PHASE", "ÉTAPE",
    "VERSION", "RAPPORT", "PROJET", "BUDGET", "PLANNING", "CAHIER", "CHARGES",
    "COMITÉ", "PILOTAGE", "DIRECTION", "GÉNÉRALE", "STRATÉGIE", "DÉVELOPPEMENT",
    "PROTOTYPE", "FONCTIONNEL", "ANALYSE", "ARCHITECTURE", "LOGICIELLE",
    "INFORMATIQUE", "SCIENCES", "FILIÈRE", "ACADÉMIQUE", "THÈME",
    "PMO", "COPIL", "SCRUM", "AGILE", "KPI",
    "EF1", "EF2", "EF3", "EF4", "EF5", "EF6", "EF7",
    # Tech & IA
    "IA", "LLM", "RAG", "API", "REST", "SQL", "JSON", "XML", "HTML", "CSS",
    "JWT", "CRUD", "ORM", "CLI", "URL", "SSL", "TLS", "SSH",
    # Formats de fichiers
    "PDF", "DOCX", "XLSX", "PPTX", "CSV", "EML", "MSG",
    # Infra
    "VPS", "RAM", "CPU", "GPU", "CI", "CD",
    # Institutions, Pays et Régions
    "MINISTÈRE", "GOUVERNEMENT", "PRÉSIDENCE", "RÉPUBLIQUE", "BÉNIN",
    "AFRIQUE", "ASIE", "AMÉRIQUE", "EUROPE", "OUEST", "CENTRALE", "SAHEL",
    "NIGERIA", "GHANA", "TOGO", "NIGER", "BURKINA", "MALI", "SÉNÉGAL",
    "CÔTE", "IVOIRE", "CAMEROUN", "GABON",
    "ESGIS", "UEMOA", "CEDEAO", "BCEAO", "BIDC", "BAD", "PNUD", "UNICEF",
    "OMS", "FAO", "UNESCO", "APDP",
    # Monnaies
    "FCFA", "CFA",
    # Divers
    "NB", "PS", "RH", "DG", "DRH", "DSI", "CTO", "CEO", "PDG", "NOVATECH",
}

# ── Mots Title Case fréquents dans les documents PMO (faux positifs whitelist) ─
# Note : la whitelist ne sert qu'à filtrer les faux positifs résiduels du pattern,
# qui est déjà très restrictif (exige un composant en MAJUSCULES).
NOM_PROPRE_WHITELIST: set[str] = {
    # Mois et jours
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
    # Titres et fonctions
    "Monsieur", "Madame", "Directeur", "Directrice", "Président", "Chef",
    "Responsable", "Manager", "Ingénieur", "Consultant", "Architecte",
    "Coordinateur", "Coordonnatrice", "Représentant", "Délégué",
    # Termes PMO courants
    "Charte", "Cadrage", "Annexe", "Article", "Section", "Phase", "Étape",
    "Version", "Rapport", "Projet", "Budget", "Planning", "Cahier", "Charges",
    "Comité", "Pilotage", "Copil", "Direction", "Générale", "Stratégie",
    "Développement", "Prototype", "Fonctionnel", "Analyse", "Architecture",
    "Logicielle", "Informatique", "Sciences", "Filière", "Académique", "Thème",
    # Institutions béninoises et africaines
    "Ministère", "Gouvernement", "Présidence", "République", "Bénin",
    "Afrique", "Asie", "Amérique", "Europe", "Ouest", "Centrale", "Sahel",
    "Nigeria", "Ghana", "Togo", "Niger", "Burkina", "Mali", "Sénégal",
    "Côte", "Ivoire", "Cameroun", "Gabon",
    # Institutions / marques connues
    "Microsoft", "Google", "Amazon", "Apple", "Oracle", "SAP", "IBM",
    "PostgreSQL", "ChromaDB", "FastAPI", "React", "Streamlit",
    "GitHub", "Hetzner", "Groq", "LLaMA", "NovaTech",
} | VILLES_AFRIQUE_OUEST


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
    Seules les données PII sont ciblées. Montants, dates et texte structurel sont ignorés.
    """
    real_to_placeholder: dict[str, str] = {}
    counters: dict[str, int] = defaultdict(int)

    for entity_type, pattern in ENTITY_PATTERNS:
        try:
            flags = re.UNICODE
            if entity_type != "NOM_PROPRE":
                flags |= re.IGNORECASE
            for match in re.finditer(pattern, text, flags):
                real_value = match.group(0).strip()

                if not real_value:
                    continue

                if entity_type == "NOM_PROPRE":
                    # Exclure si c'est dans la whitelist Title Case
                    if real_value in NOM_PROPRE_WHITELIST:
                        continue
                    # Exclure si l'un des mots est un acronyme connu
                    words = real_value.split()
                    if any(w in ACRONYMS_WHITELIST for w in words):
                        continue
                    # Exclure si déjà capturé par un autre pattern
                    if real_value in real_to_placeholder:
                        continue
                    # Sécurité : vérifier qu'il y a bien un mot tout en majuscules
                    has_all_caps = any(
                        w == w.upper() and len(w) >= 2 and w.isalpha()
                        for w in words
                    )
                    if not has_all_caps:
                        continue

                if real_value not in real_to_placeholder:
                    counters[entity_type] += 1
                    placeholder = f"[{entity_type}_{counters[entity_type]}]"
                    real_to_placeholder[real_value] = placeholder

        except re.error as e:
            logger.warning(f"Regex error for pattern {entity_type}: {e}")
            continue

    # Détection des villes connues
    _detect_ville(text, counters, real_to_placeholder)

    return real_to_placeholder


def anonymize(text: str) -> tuple[str, dict[str, str]]:
    """
    Anonymise les données PII du texte. Le texte structurel, les montants et dates sont conservés.

    Args:
        text: Texte brut extrait du document

    Returns:
        anonymized_text: Texte sûr pour envoi au LLM (Groq ne voit pas les PII)
        mapping: { "[NOM_PROPRE_1]": "AMOUSSA Soultone", ... } pour la dé-anonymisation
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

    mapping = { "[NOM_PROPRE_1]": "AMOUSSA Soultone", "[EMAIL_1]": "koffi@bj", ... }
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
    """
    merged: dict[str, str] = {}
    for doc in docs:
        if doc.is_anonymized and doc.anonymization_map:
            merged.update(doc.anonymization_map)
    return merged
