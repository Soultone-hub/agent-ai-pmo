"""
config.py — Paramétrage centralisé de la pipeline.
Modifiez ce fichier pour adapter la pipeline à votre domaine.
"""

from dataclasses import dataclass, field


@dataclass
class DetectorConfig:
    # --- NER ---
    spacy_model: str = "fr_core_news_lg"   # Modèle spaCy à charger
    ner_labels:  list[str] = field(default_factory=lambda: ["PER", "LOC", "ORG"])
    ner_min_score: float = 0.0             # Seuil minimum de confiance NER
                                           # (spaCy ne retourne pas de score direct ;
                                           #  on peut le fixer via Presidio)

    # --- Regex ---
    enable_regex: bool = True
    regex_min_score: float = 0.99          # Les regex sont déterministes → score fixe

    # --- Règles métier custom ---
    enable_rules: bool = True
    custom_keywords: list[str] = field(default_factory=list)
    # Ex : ["patient", "dossier n°", "réf."]


@dataclass
class ResolverConfig:
    # Stratégie de résolution des chevauchements
    # "score"  → garder l'entité avec le score le plus élevé
    # "length" → garder la plus longue
    # "source" → priorité : regex > rule > ner
    strategy: str = "score"

    # Score minimum pour qu'une entité soit retenue
    min_score: float = 0.5

    # Si True, une entité englobante écrase les entités qu'elle contient
    prefer_longest: bool = True


@dataclass
class MapperConfig:
    # Si True, le même texte (insensible à la casse) → même pseudonyme
    case_insensitive: bool = True

    # Format du pseudonyme : "{label}_{n}" → "PERSONNE_1"
    # Vous pouvez surcharger get_pseudo() dans Mapper pour un format custom
    template: str = "{label}_{n}"

    # Délimiteurs autour du pseudonyme dans le texte
    open_tag:  str = "["
    close_tag: str = "]"

    # Chemin vers un fichier JSON de mapping persistant (None = pas de persistance)
    registry_path: str | None = None


@dataclass
class ValidatorConfig:
    # Re-détection post-remplacement pour chercher des entités résiduelles
    enable_redetection: bool = True

    # Score qualité minimum en dessous duquel on émet un avertissement critique
    quality_threshold: float = 0.80

    # Patterns supplémentaires à vérifier après anonymisation
    # (ex : pour s'assurer qu'aucun vrai nom propre ne reste)
    residual_patterns: list[str] = field(default_factory=list)


@dataclass
class PipelineConfig:
    detector:  DetectorConfig  = field(default_factory=DetectorConfig)
    resolver:  ResolverConfig  = field(default_factory=ResolverConfig)
    mapper:    MapperConfig    = field(default_factory=MapperConfig)
    validator: ValidatorConfig = field(default_factory=ValidatorConfig)

    # Encoding attendu pour les textes entrants
    encoding: str = "utf-8"

    # Si True, la pipeline lève une exception en cas de score < quality_threshold
    strict_mode: bool = False
