# pipeline/__init__.py
# Rend le dossier pipeline importable comme package Python
# et expose l'interface publique principale.

from .pipeline import AnonymizationPipeline, AnonymizationQualityError
from .models   import AnonymizationResult, Entity, EntityLabel
from .config   import PipelineConfig

__all__ = [
    "AnonymizationPipeline",
    "AnonymizationQualityError",
    "AnonymizationResult",
    "Entity",
    "EntityLabel",
    "PipelineConfig",
]
