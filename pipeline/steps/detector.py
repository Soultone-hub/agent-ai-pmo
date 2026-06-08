"""
steps/detector.py — Étape 2 : Détection des entités sensibles.

Trois sources combinées :
  A. NER via spaCy  → PER, LOC, ORG
  B. Regex          → EMAIL, PHONE, IBAN, SIREN, SIRET, NIR, DATE, IP, URL,
                      POSTCODE, CC, IFU, RCCM (identifiants béninois)
  C. Règles métier  → mots-clés contextuels PMO Bénin + sous-région

Améliorations v2 :
  - Téléphones béninois/africains (+229, +225, +221, +228, +226, +237...)
  - IFU (Identifiant Fiscal Unique — Bénin, 13 chiffres)
  - RCCM (Registre de Commerce — format BJ/RCCM/...)
  - Noms propres africains via regex sémantique renforcée
  - Règles contextuelles étendues (secteur PMO)
  - Score NER contextuel basé sur la fréquence des mots-clés environnants
  - Whitelist PMO pour éviter les faux positifs sur les titres de section
"""

import re
import logging
from typing import Callable, TypedDict

from ..models import Entity, EntityLabel
from ..config import DetectorConfig

# Lexique de noms africains (fallback quand spaCy ne les connaît pas)
try:
    from ..african_names import is_african_name, FAMILY_NAMES, GIVEN_NAMES
    _LEXICON_AVAILABLE = True
except ImportError:
    _LEXICON_AVAILABLE = False
    def is_african_name(w: str) -> bool: return False
    FAMILY_NAMES: frozenset[str] = frozenset()
    GIVEN_NAMES:  frozenset[str] = frozenset()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Whitelist PMO — termes techniques à NE PAS anonymiser
# ---------------------------------------------------------------------------

PMO_WHITELIST: set[str] = {
    # Rôles & titres
    "Chef de Projet", "Directeur", "Coordinateur", "Responsable", "Manager",
    "Consultant", "Expert", "Chargé", "Assistant", "Analyste", "Auditeur",
    "Contrôleur", "Superviseur", "PMO", "CTO", "DG", "DAF", "DRH", "DSI",
    "Mr", "Mme", "Dr", "Pr", "Me", "Monsieur", "Madame", "Docteur", "Maître",
    # Organisations génériques
    "BCEAO", "UEMOA", "CEDEAO", "ONU", "PNUD", "BM", "BAD", "FMI",
    "SFI", "AFD", "UE", "USAID", "GIZ",
    # Termes PMO (sections, métriques)
    "Budget", "Planning", "Jalon", "Sprint", "Livrable", "Objectif",
    "Contrainte", "Risque", "KPI", "Indicateur", "Rapport", "Synthèse",
    "Phase", "Étape", "Comité", "COPIL", "CODIR", "CA",
    # Termes géographiques non-PII
    "Bénin", "Afrique", "Ouest", "Nord", "Sud", "Est",
    "FCFA", "CFA", "EUR", "USD",
}

# ---------------------------------------------------------------------------
# Libellés structurels (en-têtes de champ/colonne) — NE sont JAMAIS des PII.
# spaCy a tendance à les classer en PER/ORG/LOC : on les filtre du NER.
# (comparaison insensible à la casse, après strip des ':' et espaces)
# ---------------------------------------------------------------------------

STRUCTURAL_LABELS: frozenset[str] = frozenset({
    "champ", "valeur", "nom", "prénom", "prénoms",
    "nom et prénoms", "nom / prénoms", "nom/prénoms",
    "date", "date de naissance", "date/heure", "lieu de naissance",
    "nationalité", "adresse", "adresse domicile", "adresse ip",
    "téléphone", "téléphone principal", "téléphone secondaire",
    "email", "email professionnel", "email personnel", "adresse email", "courriel",
    "poste", "fonction", "grade", "service", "salaire", "salaire mensuel net",
    "compte", "compte bancaire", "numéro", "numéro cni", "numéro cnss",
    "matricule", "matricule igss", "cni", "cnss", "igss", "ifu", "rccm",
    "motif", "motif consultation", "groupe sanguin",
    "antécédent", "antécédents", "allergie", "allergies",
    "statut", "statut vaccination", "contact", "contact d'urgence",
    "utilisateur", "observations", "observation", "commentaire", "objet",
})

# ---------------------------------------------------------------------------
# Lieux béninois courants — pour reclasser en LIEU les toponymes que spaCy
# étiquette à tort en PERSONNE/ORGANISATION (ex : "Cadjèhoun", quartier de Cotonou).
# ---------------------------------------------------------------------------

BENIN_LOCATIONS: frozenset[str] = frozenset({
    # Villes / communes
    "cotonou", "porto-novo", "porto novo", "parakou", "abomey",
    "abomey-calavi", "calavi", "bohicon", "natitingou", "djougou",
    "lokossa", "ouidah", "kandi", "malanville", "savalou", "savè",
    "dassa", "comè", "aplahoué", "pobè", "sakété", "allada", "grand-popo",
    # Quartiers de Cotonou / zones
    "akpakpa", "cadjèhoun", "cadjehoun", "fidjrossè", "fidjrosse",
    "godomey", "gbégamey", "jéricho", "jericho", "zongo", "dantokpa",
    "ganhi", "tokpa", "agla", "fifadji",
    # Départements
    "littoral", "atlantique", "ouémé", "oueme", "plateau", "mono",
    "couffo", "zou", "collines", "borgou", "alibori", "atacora", "donga",
})

# Abréviations françaises courantes — un "abrév.mot" n'est PAS un identifiant.
_USER_ABBREV_BLACKLIST: frozenset[str] = frozenset({
    "cf", "ex", "art", "fig", "cad", "etc", "p", "pp", "vol",
    "no", "av", "bd", "ch", "al", "op", "loc", "cf",
})

# Extensions de fichiers et TLD — un "mot.pdf" ou "site.com" n'est PAS un identifiant.
_USER_EXT_TLD_BLACKLIST: frozenset[str] = frozenset({
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "eml", "txt", "csv",
    "png", "jpg", "jpeg", "gif", "svg", "bmp", "zip", "rar", "exe",
    "html", "htm", "php", "json", "xml", "md", "log",
    "com", "org", "net", "fr", "bj", "ci", "sn", "tg", "bf", "cm",
    "gouv", "edu", "int", "info", "io",
})

# ---------------------------------------------------------------------------
# Catalogue de patterns regex — v2
# ---------------------------------------------------------------------------

REGEX_PATTERNS: list[tuple[str, str, int]] = [

    # ── Email ─────────────────────────────────────────────────────────────
    ("EMAIL",
     r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
     re.IGNORECASE),

    # ── URL ───────────────────────────────────────────────────────────────
    ("URL",
     r"https?://[^\s<>\"']+|www\.[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}[^\s<>\"']*",
     re.IGNORECASE),

    # ── IBAN (tous pays) — tolère les espaces de groupage ─────────────────
    # Ex : "BJ66 BJ060 10001 23456789012 54" ou "FR76 3000 4000 03..."
    # On capture l'IBAN entier en une seule entité (espaces internes inclus)
    # pour éviter qu'il soit fragmenté en plusieurs faux positifs.
    ("IBAN",
     r"\b[A-Z]{2}\d{2}(?:[  ]?[A-Z0-9]){10,30}\b",
     0),

    # ── Nom d'utilisateur système (initiale.nom / prénom.nom) ─────────────
    # Ex : "kf.gbedje", "b.alassane" — identifiants directs de personnes
    # dans les journaux d'accès. Validé dans _validate_match (anti-fichiers/TLD).
    ("USER",
     r"\b[a-zA-Z]{1,3}\.[a-zA-Z][a-zA-Z\-]{2,}\b",
     0),

    # ── Matricule / identifiant administratif structuré ───────────────────
    # Ex : "BEN/MSP/2024/04521", "BJ-1985-082234-K", "CNSS-BJ-0043219-2"
    # Validé dans _validate_match (≥3 chiffres + ≥1 lettre).
    ("MATRICULE",
     r"\b[A-Z]{2,}[\-/](?:[A-Z0-9]+[\-/])*[A-Z0-9]+\b",
     0),

    # ── SIRET (14 chiffres) ───────────────────────────────────────────────
    ("SIRET",
     r"\b\d{3}[\s.\-]?\d{3}[\s.\-]?\d{3}[\s.\-]?\d{5}\b",
     0),

    # ── SIREN (9 chiffres) ────────────────────────────────────────────────
    ("SIREN",
     r"\b\d{3}[\s.\-]?\d{3}[\s.\-]?\d{3}\b",
     0),

    # ── IFU béninois (13 chiffres) ────────────────────────────────────────
    ("IFU",
     r"\b\d{13}\b",
     0),

    # ── RCCM béninois ────────────────────────────────────────────────────
    # Format : RB/COT/2021/B/1234 ou BJ/RCCM/COT/2021/B/1234
    ("RCCM",
     r"\b(?:BJ/RCCM/|RB/)[A-Z]{2,4}/\d{4}/[A-Z]/\d{2,6}\b",
     re.IGNORECASE),

    # ── NIR — sécurité sociale français ──────────────────────────────────
    ("NIR",
     r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}(?:[\s.\-]?\d{2})?\b",
     0),

    # ── Carte bancaire (Luhn vérifié dans _validate_match) ────────────────
    ("CC",
     r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
     0),

    # ── Adresse IP v4 ─────────────────────────────────────────────────────
    ("IP",
     r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b",
     0),

    # ── Téléphones — France + Bénin + sous-région Afrique de l'Ouest ─────
    # France : 06 12 34 56 78 / +33 6 12 34 56 78
    # Bénin  : +229 01 23 45 67 / 97 12 34 56
    # CI     : +225 07 12 34 56 78
    # Sénégal: +221 77 123 45 67
    # Togo   : +228 90 12 34 56
    # Burkina: +226 70 12 34 56
    # Cameroun: +237 6 12 34 56 78
    ("PHONE",
     r"""
     (?:
       (?:\+33|0033|0)[1-9](?:[\s.\-]{0,2}\d{2}){4}            # France
       |
       (?:\+229|00229)[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}  # Bénin international
       |
       (?:\+225|00225)[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}  # Côte d'Ivoire
       |
       (?:\+221|00221)[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{3}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}  # Sénégal
       |
       (?:\+228|00228)[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}  # Togo
       |
       (?:\+226|00226)[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}  # Burkina
       |
       (?:\+237|00237)[\s.\-]{0,2}\d{1,2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}  # Cameroun
       |
       \b(?:9[0-9]|6[0-9]|0[1-9])[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}\b  # Local Bénin (8 chiffres)
     )
     """,
     re.VERBOSE),

    # ── Code postal français ──────────────────────────────────────────────
    ("POSTCODE",
     r"\b(?:0[1-9]|[1-8]\d|9[0-5])\d{3}\b",
     0),

    # ── Date ──────────────────────────────────────────────────────────────
    # PAS de détection inconditionnelle des dates : dans un contexte PMO la
    # plupart des dates ne sont PAS des données personnelles (jalons, échéances,
    # COPIL, planning) et les masquer dégraderait les analyses du LLM.
    # Seules les dates dans un contexte PERSONNEL sont masquées via une règle
    # contextuelle (voir CONTEXTUAL_RULES : "né le", "date de naissance"…).

    # ── Noms propres africains hors spaCy (SUPPRIMÉ car trop de faux positifs) ──
    # Remplacé par le lexique african_names.py et les règles contextuelles.
]


# ---------------------------------------------------------------------------
# Type des règles contextuelles
# ---------------------------------------------------------------------------

class ContextualRule(TypedDict):
    label:    str
    keywords: list[str]
    pattern:  str
    window:   int
    score:    float


# ---------------------------------------------------------------------------
# Motif de date réutilisable (formats FR, ISO, textuels) — sans flag VERBOSE
# car utilisé via re.search() dans les règles contextuelles.
# ---------------------------------------------------------------------------

_DATE_VALUE = (
    r"(?i)(?:"
    r"\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}"                         # 12/03/1990
    r"|\d{4}[\/\-.]\d{2}[\/\-.]\d{2}"                              # 1990-03-12
    r"|\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|"
    r"août|septembre|octobre|novembre|décembre)\s+\d{2,4}"        # 12 mars 1990
    r")"
)


# ---------------------------------------------------------------------------
# Règles métier contextuelles — v2 (secteur PMO Bénin)
# ---------------------------------------------------------------------------

CONTEXTUAL_RULES: list[ContextualRule] = [

    # ── Dates PERSONNELLES uniquement (naissance, décès, embauche…) ────────
    # Les dates "projet" (jalons, échéances, COPIL) ne sont PAS masquées.
    {
        "label":    "DATE",
        "keywords": [
            "né le", "née le", "ne le", "nee le", "né(e) le",
            "date de naissance", "naissance le", "naissance :", "naissance:",
            "décédé le", "décédée le", "date de décès", "décès le", "deces le",
            "embauché le", "embauchée le", "date d'embauche", "embauche le",
            "recruté le", "recrutée le", "date de recrutement", "recrutement le",
            "engagé le", "engagée le", "entré en fonction le",
            "marié le", "mariée le", "date de mariage",
            "diagnostiqué le", "diagnostiquée le", "hospitalisé le",
            "hospitalisée le", "admis le", "admise le",
        ],
        "pattern":  _DATE_VALUE,
        "window":   45,
        "score":    0.95,
    },

    # ── Personnes mentionnées après un titre de civilité ──────────────────
    {
        "label":    "PER",
        "keywords": ["m. ", "mme ", "dr ", "dr. ", "pr ", "pr. ", "me ", "me. ",
                     "monsieur ", "madame ", "docteur ", "maître ", "mr ", "mr. "],
        "pattern":  r"[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜŸŒÆ][a-zà-ÿœæ\-]+(?:\s+[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜŸŒÆ][a-zà-ÿœæ\-]+)*",
        "window":   60,
        "score":    0.90,
    },

    # ── Personnes après "patient :", "nom :", "signataire :", etc. ─────────
    {
        "label":    "PER",
        "keywords": ["patient :", "patient:", "nom :", "nom:", "prénom :", "prénom:",
                     "assuré :", "titulaire :", "signataire :", "responsable :",
                     "chef de projet :", "contact :", "interlocuteur :"],
        "pattern":  r"[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜŸŒÆ][a-zà-ÿœæ\-]+(?:\s+[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜŸŒÆ][a-zà-ÿœæ\-]+)*",
        "window":   80,
        "score":    0.85,
    },

    # ── Adresses ──────────────────────────────────────────────────────────
    {
        "label":    "LOC",
        "keywords": ["adresse :", "adresse:", "domicilié à", "résidant à",
                     "situé à", "sis à", "quartier ", "arrondissement ",
                     "commune de ", "ville de "],
        "pattern":  r".{5,120}",
        "window":   150,
        "score":    0.75,
    },

    # ── Téléphone après libellé ────────────────────────────────────────────
    {
        "label":    "PHONE",
        "keywords": ["tél :", "tél.", "tel :", "téléphone :", "mobile :",
                     "portable :", "cel :", "gsm :", "whatsapp :"],
        "pattern":  r"[\d\s\+\-\.]{7,20}",
        "window":   45,
        "score":    0.88,
    },

    # ── IFU après libellé ─────────────────────────────────────────────────
    {
        "label":    "IFU",
        "keywords": ["ifu :", "ifu:", "identifiant fiscal", "n° ifu", "numéro ifu",
                     "n°fiscal", "fiscal unique"],
        "pattern":  r"\d{11,13}",
        "window":   50,
        "score":    0.95,
    },

    # ── RCCM après libellé ────────────────────────────────────────────────
    {
        "label":    "RCCM",
        "keywords": ["rccm :", "rccm:", "registre de commerce", "n° rccm",
                     "numéro rccm", "immatriculée sous"],
        "pattern":  r"[A-Z0-9\/\-]{5,30}",
        "window":   60,
        "score":    0.92,
    },

    # ── Noms propres après "rédigé par", "préparé par", "validé par" ──────
    {
        "label":    "PER",
        "keywords": ["rédigé par", "préparé par", "validé par", "approuvé par",
                     "signé par", "établi par", "visa de", "certifié par"],
        "pattern":  r"[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜŸŒÆ][a-zà-ÿœæ\-]+(?:\s+[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜŸŒÆ][a-zà-ÿœæ\-]+)*",
        "window":   80,
        "score":    0.88,
    },
]


# ---------------------------------------------------------------------------
# Listes noires pour les noms propres africains (faux positifs courants)
# ---------------------------------------------------------------------------

_PER_BLACKLIST_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(Budget|Planning|Phase|Étape|Rapport|Synthèse|Comité|"
               r"COPIL|CODIR|Bénin|Afrique|Nord|Sud|Est|Ouest|"
               r"Total|Montant|Solde|Exercice|Trimestre|Semestre|"
               r"Annexe|Article|Section|Chapitre|Tableau|Figure|"
               r"Objectif|Contrainte|Risque|Livrable|Jalon|Sprint)$",
               re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Detector principal — v2
# ---------------------------------------------------------------------------

class Detector:
    """
    Détecte les entités sensibles dans un texte normalisé.
    Version 2 avec support étendu Bénin + sous-région.

    Paramètres
    ----------
    config : DetectorConfig
    custom_rules : list[dict], optionnel
    """

    # Mots-clés PMO qui boost le score NER si trouvés dans le contexte
    _PMO_CONTEXT_BOOST_KEYWORDS = [
        "signe", "approuvé", "rédigé", "contact", "responsable",
        "chef", "directeur", "dr ", "m. ", "mme ", "mr ",
    ]

    def __init__(
        self,
        config: DetectorConfig | None = None,
        custom_rules: list[ContextualRule] | None = None,
    ):
        self.config = config or DetectorConfig()
        self._nlp = None
        self._compiled_regex: list[tuple[str, re.Pattern, float]] = []
        self._rules: list[ContextualRule] = CONTEXTUAL_RULES + (custom_rules or [])

        self._compile_regex()

    # -----------------------------------------------------------------------
    # Chargement NER spaCy (lazy)
    # -----------------------------------------------------------------------

    def _load_nlp(self):
        if self._nlp is not None:
            return
        try:
            import spacy
            self._nlp = spacy.load(self.config.spacy_model)
            logger.info("Modèle spaCy '%s' chargé.", self.config.spacy_model)
        except Exception as exc:
            logger.warning(
                "Impossible de charger '%s' : %s. NER désactivé.",
                self.config.spacy_model, exc
            )
            self._nlp = False

    # -----------------------------------------------------------------------
    # Compilation regex
    # -----------------------------------------------------------------------

    def _compile_regex(self):
        for label, pattern, flags in REGEX_PATTERNS:
            try:
                compiled = re.compile(pattern, flags)
                self._compiled_regex.append((label, compiled, self.config.regex_min_score))
            except re.error as exc:
                logger.error("Pattern regex invalide pour %s : %s", label, exc)

    # -----------------------------------------------------------------------
    # Point d'entrée
    # -----------------------------------------------------------------------

    def detect(self, text: str) -> list[Entity]:
        entities: list[Entity] = []

        # A. NER spaCy
        entities.extend(self._detect_ner(text))

        # B. Lexique de noms africains (complète le NER)
        if _LEXICON_AVAILABLE:
            entities.extend(self._detect_lexicon(text))

        # C. Regex
        if self.config.enable_regex:
            entities.extend(self._detect_regex(text))

        # D. Règles contextuelles
        if self.config.enable_rules:
            entities.extend(self._detect_rules(text))

        # Écrêtage : une entité ne doit pas franchir un saut de ligne. spaCy
        # fusionne parfois une valeur et le libellé de la ligne suivante
        # (ex : "Gbèdji Kokou Fernand\nDate de naissance"). On tronque à la 1re ligne.
        entities = [c for e in entities if (c := self._clip_at_newline(e)) is not None]

        # Filtre final : retirer les libellés structurels (en-têtes de champ)
        # quelle que soit la source (NER, lexique ou règle).
        entities = [e for e in entities if not self._is_structural(e)]

        logger.debug("Détection brute : %d entité(s).", len(entities))
        return entities

    @staticmethod
    def _clip_at_newline(entity: Entity) -> Entity | None:
        """Tronque l'entité au premier saut de ligne. Retourne None si trop courte."""
        nl = entity.text.find("\n")
        if nl == -1:
            return entity
        clipped = entity.text[:nl].rstrip()
        if len(clipped.strip()) <= 1:
            return None
        entity.text = clipped
        entity.end = entity.start + len(clipped)
        return entity

    @staticmethod
    def _is_structural(entity: Entity) -> bool:
        """True si l'entité est un libellé structurel (jamais une donnée PII)."""
        if entity.label not in ("PER", "LOC", "ORG"):
            return False
        norm = " ".join(entity.text.split()).lower().strip(" :")
        return norm in STRUCTURAL_LABELS

    # -----------------------------------------------------------------------
    # B. Lexique de noms africains
    # -----------------------------------------------------------------------

    def _detect_lexicon(self, text: str) -> list[Entity]:
        """
        Recherche dans le texte tous les tokens qui correspondent à un nom
        du lexique africain, puis tente de reconstruire le nom complet
        (prénom + NOM ou NOM + prénom).
        Score élevé (0.92) car le lexique est une source fiable.
        """
        entities: list[Entity] = []

        # Tokenisation simple sur les limites de mots
        token_pattern = re.compile(
            r"[A-ZÀ-Ÿ][a-zà-ÿœæ\-]+|[A-ZÀ-Ÿ]{2,}",
            re.UNICODE
        )

        tokens = list(token_pattern.finditer(text))

        i = 0
        while i < len(tokens):
            tok = tokens[i]
            word = tok.group()

            if is_african_name(word):
                # Essayer de construire un nom composé avec le token suivant
                if i + 1 < len(tokens):
                    next_tok  = tokens[i + 1]
                    next_word = next_tok.group()
                    gap       = text[tok.end():next_tok.start()]

                    # Accepter un espace simple ou un tiret comme séparateur
                    if gap in (" ", "-", "\u00a0") and is_african_name(next_word):
                        # Nom composé connu dans le lexique
                        full_text  = text[tok.start():next_tok.end()]
                        context    = self._extract_context(text, tok.start(), next_tok.end())
                        entities.append(Entity(
                            text=full_text,
                            label="PER",
                            start=tok.start(),
                            end=next_tok.end(),
                            score=0.92,
                            source="lexicon",
                            context=context,
                        ))
                        i += 2
                        continue

                    # Un seul mot du lexique + mot suivant non-lexique → peut être
                    # "NOM Prénom" ou "Prénom NOM" : on vérifie si le suivant
                    # commence par une majuscule (heuristique)
                    if gap == " " and next_word[0].isupper() and len(next_word) >= 2:
                        full_text = text[tok.start():next_tok.end()]
                        context   = self._extract_context(text, tok.start(), next_tok.end())
                        # Score légèrement réduit car le deuxième élément n'est pas confirmé
                        entities.append(Entity(
                            text=full_text,
                            label="PER",
                            start=tok.start(),
                            end=next_tok.end(),
                            score=0.85,
                            source="lexicon",
                            context=context,
                        ))
                        i += 2
                        continue

                # Mot seul du lexique → score plus bas (prénom isolé, moins certain)
                context = self._extract_context(text, tok.start(), tok.end())
                entities.append(Entity(
                    text=word,
                    label="PER",
                    start=tok.start(),
                    end=tok.end(),
                    score=0.75,
                    source="lexicon",
                    context=context,
                ))

            i += 1

        return entities

    # -----------------------------------------------------------------------
    # C. NER spaCy avec boost contextuel
    # -----------------------------------------------------------------------

    def _detect_ner(self, text: str) -> list[Entity]:
        self._load_nlp()
        if not self._nlp:
            return []

        entities: list[Entity] = []
        try:
            doc = self._nlp(text)
        except Exception as exc:
            logger.error("Erreur spaCy : %s", exc)
            return []

        for ent in doc.ents:
            if ent.label_ not in self.config.ner_labels:
                continue

            # Forme normalisée du texte (sans casse, sans ':' ni espaces parasites)
            norm = " ".join(ent.text.split()).lower().strip(" :")

            # Libellés structurels (en-têtes de champ/colonne) → jamais des PII
            if norm in STRUCTURAL_LABELS:
                continue

            label = ent.label_

            # Toponymes béninois mal classés en PER/ORG → forcer LIEU
            if norm in BENIN_LOCATIONS:
                label = "LOC"

            # Score de base NER + boost contextuel
            context = self._extract_context(text, ent.start_char, ent.end_char, window=40)
            score = self._compute_ner_score(ent.text, context)

            # Filtre whitelist sur les LOC et ORG
            if label in ("LOC", "ORG") and ent.text in PMO_WHITELIST:
                continue

            # Filtre blacklist sur les PER (termes PMO courants : Budget, Phase…)
            if label == "PER" and self._is_per_blacklisted(ent.text):
                continue

            # Ignorer les personnes composées d'une seule lettre (ex: "M" dans "Mr.")
            if label == "PER" and len(ent.text.strip()) <= 1:
                continue

            entities.append(Entity(
                text=ent.text,
                label=label,
                start=ent.start_char,
                end=ent.end_char,
                score=score,
                source="ner",
                context=context,
            ))

        return entities

    def _compute_ner_score(self, ent_text: str, context: str) -> float:
        """Score NER de base 0.75, boosté jusqu'à 0.95 si contexte PMO détecté."""
        base = 0.75
        ctx_lower = context.lower()
        boost = sum(
            0.04 for kw in self._PMO_CONTEXT_BOOST_KEYWORDS
            if kw in ctx_lower
        )
        return min(base + boost, 0.95)

    # -----------------------------------------------------------------------
    # B. Regex
    # -----------------------------------------------------------------------

    def _detect_regex(self, text: str) -> list[Entity]:
        entities: list[Entity] = []

        for label, pattern, score in self._compiled_regex:
            for match in pattern.finditer(text):
                raw = match.group()

                # Validation complémentaire
                if not self._validate_match(label, raw, text, match.start()):
                    continue

                # Filtre blacklist sur les PER regex
                if label == "PER" and self._is_per_blacklisted(raw):
                    continue

                context = self._extract_context(text, match.start(), match.end(), window=25)

                # Score légèrement réduit pour les PER regex (moins fiable que NER)
                effective_score = 0.78 if label == "PER" else score

                entities.append(Entity(
                    text=raw,
                    label=label,
                    start=match.start(),
                    end=match.end(),
                    score=effective_score,
                    source="regex",
                    context=context,
                    metadata={"groups": match.groups()},
                ))

        return entities

    # -----------------------------------------------------------------------
    # C. Règles contextuelles
    # -----------------------------------------------------------------------

    def _detect_rules(self, text: str) -> list[Entity]:
        entities: list[Entity] = []

        for rule in self._rules:
            # Préparer le regex pour les mots-clés (avec frontière de mot)
            kws = sorted(rule["keywords"], key=len, reverse=True)
            # On échappe le mot clé, mais on gère l'espace éventuel à la fin.
            # IMPORTANT : si le mot-clé se termine par une lettre/chiffre (ex : "pr",
            # "me", "dr"), on exige une frontière de mot APRÈS, sinon il matcherait
            # à l'intérieur de mots ordinaires ("pr"→"principal", "me"→"mensuel").
            escaped_kws = []
            for kw in kws:
                stripped = kw.strip()
                escaped = re.escape(stripped)
                if stripped[-1:].isalnum():
                    escaped += r"\b"
                escaped_kws.append(escaped + r"\s*")
            pattern_str = r"(?i)\b(?:" + "|".join(escaped_kws) + r")"
            kw_regex = re.compile(pattern_str)

            for match in kw_regex.finditer(text):
                keyword_found = match.group()
                search_start = match.end()
                search_end   = min(search_start + rule["window"], len(text))
                window_text  = text[search_start:search_end].strip()

                m = re.search(rule["pattern"], window_text)
                if m:
                    matched_text = m.group().strip()

                    # Filtre blacklist
                    if rule["label"] == "PER" and self._is_per_blacklisted(matched_text):
                        continue

                    # Filtre trop court
                    if len(matched_text) < 2:
                        continue

                    # On retrouve la position absolue exacte
                    abs_start = search_start + (window_text.index(matched_text) if matched_text in window_text else m.start())
                    abs_end   = abs_start + len(matched_text)
                    context   = self._extract_context(text, abs_start, abs_end, window=30)

                    entities.append(Entity(
                        text=matched_text,
                        label=rule["label"],
                        start=abs_start,
                        end=abs_end,
                        score=rule["score"],
                        source="rule",
                        context=context,
                        metadata={"trigger_keyword": keyword_found},
                    ))

        return entities

    # -----------------------------------------------------------------------
    # Validation complémentaire
    # -----------------------------------------------------------------------

    def _validate_match(self, label: str, text: str, full_text: str, start: int) -> bool:
        if label == "CC":
            return self._luhn_check(re.sub(r"[\s\-]", "", text))

        if label == "POSTCODE":
            code = re.sub(r"\s", "", text)
            if not (len(code) == 5 and code.isdigit()):
                return False
            # Rejeter si le code fait partie d'un identifiant plus large
            # (ex : "BEN/MSP/2024/04521" → 04521 n'est pas un code postal)
            if start > 0 and full_text[start - 1] in "/-":
                return False
            return True

        if label == "IBAN":
            cleaned = re.sub(r"[\s ]", "", text).upper()
            # IBAN béninois : on masque sur la structure (BJ + 2 chiffres + ...)
            # sans exiger le checksum mod-97 — les IBAN de test/saisis manuellement
            # échouent souvent le mod-97 et ne doivent surtout pas fuiter.
            if cleaned.startswith("BJ"):
                return 20 <= len(cleaned) <= 34
            return self._iban_check(cleaned)

        if label == "USER":
            parts = text.split(".")
            if len(parts) != 2:
                return False
            first, second = parts[0].lower(), parts[1].lower()
            # Exclure les abréviations FR ("cf.note") et les fichiers/TLD ("doc.xlsx", "site.com")
            if first in _USER_ABBREV_BLACKLIST:
                return False
            if second in _USER_EXT_TLD_BLACKLIST:
                return False
            return True

        if label == "MATRICULE":
            # Un matricule administratif mêle lettres et chiffres (≥3 chiffres)
            digits = sum(c.isdigit() for c in text)
            has_alpha = any(c.isalpha() for c in text)
            return digits >= 3 and has_alpha

        if label == "SIREN":
            cleaned = re.sub(r"[\s.\-]", "", text)
            return len(cleaned) == 9

        if label == "IFU":
            cleaned = re.sub(r"[\s.\-]", "", text)
            # IFU béninois = 13 chiffres, ne doit pas être une date ou un montant
            if len(cleaned) != 13:
                return False
            # Heuristique : éviter les montants financiers (commencent rarement par 0)
            return cleaned[0] != "0"

        if label == "PHONE":
            # Un numéro de téléphone a au moins 8 chiffres significatifs
            digits_only = re.sub(r"\D", "", text)
            return len(digits_only) >= 8

        if label == "PER":
            # Le pattern PER regex exige au moins un mot tout-en-majuscules
            words = text.split()
            has_full_upper = any(
                w.upper() == w and len(re.sub(r"[^A-ZÀÂÄÉÈÊËÎÏÔÙÛÜŸŒÆ]", "", w)) >= 2
                for w in words
            )
            return has_full_upper

        return True

    @staticmethod
    def _is_per_blacklisted(text: str) -> bool:
        """Retourne True si le texte est un terme PMO courant (faux positif)."""
        for pat in _PER_BLACKLIST_PATTERNS:
            if pat.match(text.strip()):
                return True
        # Vérification dans la whitelist globale
        return text.strip() in PMO_WHITELIST

    @staticmethod
    def _luhn_check(number: str) -> bool:
        try:
            digits = [int(d) for d in reversed(number) if d.isdigit()]
            if len(digits) < 13:
                return False
            total = 0
            for i, d in enumerate(digits):
                if i % 2 == 1:
                    d *= 2
                    if d > 9:
                        d -= 9
                total += d
            return total % 10 == 0
        except ValueError:
            return False

    @staticmethod
    def _iban_check(iban: str) -> bool:
        try:
            iban = re.sub(r"\s", "", iban).upper()
            if len(iban) < 15:
                return False
            rearranged = iban[4:] + iban[:4]
            numeric = "".join(
                str(ord(c) - 55) if c.isalpha() else c
                for c in rearranged
            )
            return int(numeric) % 97 == 1
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _extract_context(text: str, start: int, end: int, window: int = 30) -> str:
        ctx_start = max(0, start - window)
        ctx_end   = min(len(text), end + window)
        snippet   = text[ctx_start:ctx_end]
        rel_start = start - ctx_start
        rel_end   = end   - ctx_start
        return snippet[:rel_start] + "«" + snippet[rel_start:rel_end] + "»" + snippet[rel_end:]
