"""
pipeline.py — Orchestrateur de la pipeline d'anonymisation.

Usage minimal :
    from pipeline import AnonymizationPipeline
    pipeline = AnonymizationPipeline()
    result = pipeline.run("Jean Dupont, né le 12/03/1985, habite Paris.")
    print(result.clean_text)
    print(result.summary())

Usage avancé (config custom + persistance du mapping) :
    from pipeline import AnonymizationPipeline
    from .config import PipelineConfig, MapperConfig

    config = PipelineConfig(
        mapper=MapperConfig(registry_path="mapping.json"),
    )
    pipeline = AnonymizationPipeline(config=config)

    for doc in documents:
        result = pipeline.run(doc)
        pipeline.save_mapping()   # persiste après chaque document
"""

import json
import logging
from pathlib import Path

from .models import AnonymizationResult
from .config import PipelineConfig
from .steps.normalizer import Normalizer
from .steps.detector   import Detector
from .steps.resolver   import Resolver
from .steps.mapper     import Mapper
from .steps.replacer   import Replacer
from .steps.validator  import Validator

logger = logging.getLogger(__name__)


class AnonymizationPipeline:
    """
    Pipeline complète d'anonymisation en 6 étapes.

    Paramètres
    ----------
    config : PipelineConfig, optionnel
        Configuration globale. Utilise les valeurs par défaut si non fournie.
    shared_mapper : Mapper, optionnel
        Mapper partagé entre plusieurs instances ou documents.
        Utile pour garantir la cohérence des pseudonymes sur un corpus.
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        shared_mapper: Mapper | None = None,
    ):
        self.config = config or PipelineConfig()

        # Instanciation des étapes
        self.normalizer = Normalizer()
        self.detector   = Detector(config=self.config.detector)
        self.resolver   = Resolver(config=self.config.resolver)
        self.mapper     = shared_mapper or Mapper(config=self.config.mapper)
        self.replacer   = Replacer(mapper=self.mapper, config=self.config.mapper)
        self.validator  = Validator(config=self.config.validator)

        logger.info("Pipeline d'anonymisation initialisée.")

    # -----------------------------------------------------------------------
    # Point d'entrée principal
    # -----------------------------------------------------------------------

    def run(self, text: str) -> AnonymizationResult:
        """
        Anonymise un texte brut et retourne un AnonymizationResult complet.

        Parameters
        ----------
        text : str
            Texte brut à anonymiser.

        Returns
        -------
        AnonymizationResult
        """
        logger.info("Début d'anonymisation — %d caractère(s).", len(text))

        # ── Étape 1 : Normalisation ─────────────────────────────────────────
        norm_result = self.normalizer.normalize(text)
        normalized  = norm_result.text
        logger.debug("Normalisation : %s", norm_result.changes)

        # ── Étape 2 : Détection ─────────────────────────────────────────────
        raw_entities = self.detector.detect(normalized)
        logger.debug("Détection : %d entité(s) brute(s).", len(raw_entities))

        # ── Étape 3 : Fusion & résolution ────────────────────────────────────
        entities = self.resolver.resolve(raw_entities)
        logger.debug("Résolution : %d entité(s) retenue(s).", len(entities))

        # ── Étapes 4 + 5 : Mapping + Remplacement ────────────────────────────
        # (le Replacer appelle le Mapper pour chaque entité — les deux sont couplés)
        clean_text, mapping = self.replacer.replace(normalized, entities)
        logger.debug("Remplacement : %d substitution(s).", len(mapping))

        # ── Étape 6 : Validation ────────────────────────────────────────────
        report = self.validator.validate(clean_text, entities, mapping)

        # ── Mode strict ─────────────────────────────────────────────────────
        if self.config.strict_mode and report.score < self.config.validator.quality_threshold:
            raise AnonymizationQualityError(
                f"Score de qualité insuffisant : {report.score:.0%}. "
                f"Avertissements : {report.warnings}"
            )

        # ── Statistiques ─────────────────────────────────────────────────────
        stats = self._build_stats(text, normalized, entities, mapping, report)

        logger.info(
            "Anonymisation terminée — score : %.2f | %d entité(s) | %d avertissement(s).",
            report.score, len(entities), len(report.warnings)
        )

        return AnonymizationResult(
            original_text   = text,
            normalized_text = normalized,
            clean_text      = clean_text,
            entities        = entities,
            mapping         = mapping,
            score           = report.score,
            warnings        = report.warnings,
            stats           = stats,
        )

    # -----------------------------------------------------------------------
    # Traitement par lot
    # -----------------------------------------------------------------------

    def run_batch(self, texts: list[str]) -> list[AnonymizationResult]:
        """
        Anonymise une liste de textes en partageant le même registre de mapping.
        Garantit la cohérence des pseudonymes sur tout le corpus.

        Parameters
        ----------
        texts : list[str]

        Returns
        -------
        list[AnonymizationResult]
        """
        results = []
        for i, text in enumerate(texts):
            logger.info("Traitement document %d/%d.", i + 1, len(texts))
            results.append(self.run(text))
        return results

    # -----------------------------------------------------------------------
    # Désanonymisation
    # -----------------------------------------------------------------------

    def restore(self, anonymized_text: str) -> str:
        """
        Tente de restaurer le texte original à partir d'un texte anonymisé.
        Nécessite que le registre du Mapper soit disponible.

        Parameters
        ----------
        anonymized_text : str

        Returns
        -------
        str
            Texte avec les pseudonymes remplacés par les valeurs originales.
        """
        return self.replacer.restore(anonymized_text)

    # -----------------------------------------------------------------------
    # Persistance
    # -----------------------------------------------------------------------

    def save_mapping(self, path: str | None = None) -> None:
        """Sauvegarde le registre de mapping."""
        self.mapper.save(path)

    def export_result(self, result: AnonymizationResult, path: str) -> None:
        """Exporte un résultat complet en JSON."""
        Path(path).write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info("Résultat exporté : %s", path)

    # -----------------------------------------------------------------------
    # Statistiques internes
    # -----------------------------------------------------------------------

    def _build_stats(
        self,
        original: str,
        normalized: str,
        entities: list,
        mapping: dict,
        report,
    ) -> dict:
        by_label: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for e in entities:
            by_label[e.label]   = by_label.get(e.label, 0) + 1
            by_source[e.source] = by_source.get(e.source, 0) + 1

        return {
            "original_length":   len(original),
            "normalized_length": len(normalized),
            "entities_total":    len(entities),
            "entities_by_label": by_label,
            "entities_by_source": by_source,
            "substitutions":     len(mapping),
            "validation_score":  round(report.score, 4),
            "leaks_detected":    len(report.leak_matches),
            "warnings_count":    len(report.warnings),
        }


# ---------------------------------------------------------------------------
# Exception custom
# ---------------------------------------------------------------------------

class AnonymizationQualityError(Exception):
    """Levée en mode strict quand le score de qualité est insuffisant."""
    pass
