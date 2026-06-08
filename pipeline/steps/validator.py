"""
steps/validator.py — Étape 6 : Validation de la qualité d'anonymisation.

Contrôles effectués :
  1. Re-détection résiduelle — relancer le détecteur sur le texte anonymisé
     pour trouver des entités qui auraient échappé au premier passage.
  2. Contrôle des patterns de fuite — vérifier que des données structurées
     connues (email, tel, IBAN…) ne subsistent pas après remplacement.
  3. Score de couverture — ratio d'entités trouvées qui ont bien été remplacées.
  4. Contrôle de cohérence du mapping — chaque entité référencée dans le
     mapping est bien absente du texte final.
  5. Score global — agrégation pondérée → valeur [0, 1].

Score de sortie :
  1.00 = parfait (aucune fuite détectée)
  < 0.80 = problème significatif → avertissement critique
  0.00 = le texte n'a pas du tout été anonymisé
"""

import re
import logging
from ..models import Entity
from ..config import ValidatorConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Patterns de fuite à contrôler après anonymisation
# Ces patterns détectent des données structurelles résiduelles.
# Ils sont intentionnellement plus larges que ceux du Detector.
# ---------------------------------------------------------------------------

LEAK_PATTERNS: list[tuple[str, str]] = [
    ("EMAIL_LEAK",   r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    ("IBAN_LEAK",    r"\b[A-Z]{2}\d{2}(?:[  ]?[A-Z0-9]){10,30}\b"),
    ("NIR_LEAK",     r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}(?:[\s.\-]?\d{2})?\b"),
    ("CC_LEAK",      r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"),
    # Téléphones : France + Bénin + sous-région Afrique de l'Ouest
    ("PHONE_LEAK",   r"(?:\+33|0033|0)[1-9](?:[\s.\-]{0,2}\d{2}){4}|"
                     r"(?:\+229|00229)[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}|"
                     r"(?:\+225|00225|\+221|00221|\+228|00228|\+226|00226|\+237|00237)[\s.\-]{0,2}\d[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}[\s.\-]{0,2}\d{2}"),
    # Identifiants fiscaux béninois
    ("IFU_LEAK",     r"\b\d{13}\b"),
    ("RCCM_LEAK",    r"\b(?:BJ/RCCM/|RB/)[A-Z]{2,4}/\d{4}/[A-Z]/\d{2,6}\b"),
]


class ValidationReport:
    """Rapport détaillé issu de la validation."""

    def __init__(self):
        self.score: float = 1.0
        self.warnings: list[str] = []
        self.residual_entities: list[dict] = []   # Entités non anonymisées détectées
        self.leak_matches: list[dict] = []         # Patterns de fuite trouvés
        self.checks_passed: list[str] = []
        self.checks_failed: list[str] = []

    def add_warning(self, message: str):
        self.warnings.append(message)
        logger.warning("[Validator] %s", message)

    def penalty(self, amount: float, reason: str):
        """Applique une pénalité au score et enregistre la raison."""
        self.score = max(0.0, self.score - amount)
        self.checks_failed.append(reason)
        logger.debug("[Validator] Pénalité %.2f : %s (score → %.2f)", amount, reason, self.score)

    def ok(self, check_name: str):
        self.checks_passed.append(check_name)

    def summary(self) -> str:
        lines = [f"Score de validation : {self.score:.0%}"]
        if self.checks_passed:
            lines.append(f"Contrôles OK ({len(self.checks_passed)}) : " + ", ".join(self.checks_passed))
        if self.checks_failed:
            lines.append(f"Contrôles KO ({len(self.checks_failed)}) : " + ", ".join(self.checks_failed))
        for w in self.warnings:
            lines.append(f"  ⚠  {w}")
        return "\n".join(lines)


class Validator:
    """
    Valide la qualité d'un texte anonymisé.

    Usage :
        validator = Validator(config)
        report = validator.validate(
            clean_text,
            entities,     # entités détectées à l'étape 2
            mapping,      # mapping produit par le Replacer
        )
        print(report.summary())
    """

    def __init__(self, config: ValidatorConfig | None = None):
        self.config = config or ValidatorConfig()
        self._leak_compiled = [
            (label, re.compile(pattern, re.IGNORECASE))
            for label, pattern in LEAK_PATTERNS
        ]
        # Patterns custom fournis dans la config
        for i, pattern in enumerate(self.config.residual_patterns):
            try:
                self._leak_compiled.append((f"CUSTOM_{i}", re.compile(pattern)))
            except re.error as exc:
                logger.error("Pattern custom invalide : %s — %s", pattern, exc)

    # -----------------------------------------------------------------------
    # Point d'entrée principal
    # -----------------------------------------------------------------------

    def validate(
        self,
        clean_text: str,
        entities: list[Entity],
        mapping: dict[str, str],
    ) -> ValidationReport:
        """
        Effectue tous les contrôles et retourne un ValidationReport.

        Parameters
        ----------
        clean_text : str
            Texte après anonymisation (sortie du Replacer).
        entities : list[Entity]
            Entités détectées et normalement remplacées.
        mapping : dict[str, str]
            Mapping {texte_original: tag} produit par le Replacer.

        Returns
        -------
        ValidationReport
        """
        report = ValidationReport()

        # 1. Vérifier que les entités sont absentes du texte final
        self._check_entity_absence(clean_text, entities, mapping, report)

        # 2. Chercher des patterns de fuite structurelle
        self._check_leak_patterns(clean_text, report)

        # 3. Vérifier la cohérence du mapping
        self._check_mapping_consistency(clean_text, mapping, report)

        # 4. Re-détection via spaCy (optionnelle)
        if self.config.enable_redetection:
            self._check_redetection(clean_text, report)

        # 5. Avertissement global si score bas
        if report.score < self.config.quality_threshold:
            report.add_warning(
                f"Score de qualité insuffisant ({report.score:.0%} < "
                f"{self.config.quality_threshold:.0%}). "
                "Des données personnelles pourraient subsister."
            )

        logger.info(
            "Validation terminée — score : %.2f | %d avertissement(s)",
            report.score, len(report.warnings)
        )
        return report

    # -----------------------------------------------------------------------
    # Contrôle 1 : Absence des entités dans le texte final
    # -----------------------------------------------------------------------

    def _check_entity_absence(
        self,
        text: str,
        entities: list[Entity],
        mapping: dict[str, str],
        report: ValidationReport,
    ):
        """
        Vérifie que chaque entité détectée ne figure plus dans le texte final
        (sauf si elle est légitime d'apparaître — ex : noms de villes dans un
        texte où seules les personnes sont anonymisées).
        """
        leaks: list[Entity] = []

        for entity in entities:
            # Le texte original doit être absent du texte nettoyé
            if entity.text in text:
                # Vérifier que ce n'est pas une coïncidence avec une autre occurrence
                # légitime (ex : un prénom commun comme "Marie" dans "Marie-Antoinette")
                # Recherche exacte par boundaries de mots
                pattern = r"(?<![A-ZÀ-Ÿa-zà-ÿ])" + re.escape(entity.text) + r"(?![A-ZÀ-Ÿa-zà-ÿ])"
                if re.search(pattern, text):
                    leaks.append(entity)
                    report.residual_entities.append({
                        "text":  entity.text,
                        "label": entity.label,
                        "score": entity.score,
                    })

        if leaks:
            names = ", ".join(f"{e.text!r}" for e in leaks[:5])
            suffix = f" (et {len(leaks) - 5} autres)" if len(leaks) > 5 else ""
            penalty = min(0.5, 0.10 * len(leaks))
            report.penalty(penalty, f"entités_résiduelles({len(leaks)})")
            report.add_warning(
                f"{len(leaks)} entité(s) non anonymisée(s) : {names}{suffix}"
            )
        else:
            report.ok("absence_entités")

    # -----------------------------------------------------------------------
    # Contrôle 2 : Patterns de fuite structurelle
    # -----------------------------------------------------------------------

    def _check_leak_patterns(self, text: str, report: ValidationReport):
        """
        Recherche des données structurelles (email, IBAN…) encore présentes
        dans le texte. Ces patterns sont plus larges que ceux du Detector
        pour maximiser la détection des fuites.
        """
        total_leaks = 0

        for label, pattern in self._leak_compiled:
            matches = list(pattern.finditer(text))
            for m in matches:
                report.leak_matches.append({
                    "label": label,
                    "text":  m.group(),
                    "start": m.start(),
                    "end":   m.end(),
                })
                total_leaks += 1
                report.add_warning(
                    f"Fuite de données détectée ({label}) : {m.group()!r} "
                    f"[pos {m.start()}:{m.end()}]"
                )

        if total_leaks == 0:
            report.ok("patterns_de_fuite")
        else:
            penalty = min(0.60, 0.15 * total_leaks)
            report.penalty(penalty, f"patterns_de_fuite({total_leaks})")

    # -----------------------------------------------------------------------
    # Contrôle 3 : Cohérence du mapping
    # -----------------------------------------------------------------------

    def _check_mapping_consistency(
        self,
        text: str,
        mapping: dict[str, str],
        report: ValidationReport,
    ):
        """
        Pour chaque entrée du mapping :
          - La valeur (le tag) doit être présente dans le texte final.
          - La clé (le texte original) ne doit pas l'être.
        """
        inconsistencies = 0

        for original, tag in mapping.items():
            # Le tag doit apparaître dans le texte anonymisé
            if tag not in text:
                logger.debug(
                    "Tag absent du texte final (peut être normal si entité dupliquée) : %s",
                    tag
                )
                # Pas de pénalité ici — un tag peut ne pas apparaître si
                # l'entité était dupliquée et une seule occurrence a été remplacée.

            # Le texte original ne doit pas apparaître
            if original and original in text:
                inconsistencies += 1

        if inconsistencies:
            report.penalty(0.05 * inconsistencies, f"mapping_incohérent({inconsistencies})")
            report.add_warning(
                f"{inconsistencies} incohérence(s) dans le mapping "
                "(texte original encore présent malgré le tag)."
            )
        else:
            report.ok("cohérence_mapping")

    # -----------------------------------------------------------------------
    # Contrôle 4 : Re-détection NER (optionnelle)
    # -----------------------------------------------------------------------

    def _check_redetection(self, text: str, report: ValidationReport):
        """
        Re-exécute une détection NER légère sur le texte anonymisé pour
        détecter des entités résiduelles que les patterns n'auraient pas trouvées.
        On ignore les entités qui sont des faux positifs connus (noms communs…).
        """
        try:
            import spacy
            nlp = spacy.load("fr_core_news_sm")   # Modèle léger pour la validation
            doc = nlp(text)
            residuals = [
                ent for ent in doc.ents
                if ent.label_ in {"PER", "LOC", "ORG"}
                # Exclure les pseudonymes eux-mêmes qui ressembleraient à des entités
                and not ent.text.startswith("[")
            ]
            if residuals:
                names = ", ".join(f"{e.text!r}" for e in residuals[:5])
                report.add_warning(
                    f"Re-détection NER : {len(residuals)} entité(s) potentiellement "
                    f"résiduelles : {names}"
                )
                report.penalty(min(0.20, 0.05 * len(residuals)), f"re-détection_NER({len(residuals)})")
                report.residual_entities.extend([
                    {"text": e.text, "label": e.label_, "score": None, "source": "redetection"}
                    for e in residuals
                ])
            else:
                report.ok("re-détection_NER")
        except Exception as exc:
            logger.debug("Re-détection NER ignorée (modèle non disponible) : %s", exc)
            # Pas de pénalité si le modèle n'est pas dispo
