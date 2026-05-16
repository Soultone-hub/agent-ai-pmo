"""
steps/mapper.py — Étape 4 : Génération et gestion des pseudonymes.

Garanties :
  - Même texte → même pseudonyme (dans une session ET entre sessions si persisted)
  - Pseudonymes uniques par label (PERSONNE_1, PERSONNE_2…)
  - Registre persistable en JSON pour cohérence multi-documents
  - Reversibilité optionnelle (mapping inversé pour désanonymisation)
"""

import json
import logging
from collections import defaultdict
from pathlib import Path

from ..models import Entity, LABEL_FR
from ..config import MapperConfig

logger = logging.getLogger(__name__)


class Mapper:
    """
    Assigne un pseudonyme stable à chaque entité détectée.

    Logique de la clé de registre :
      - Clé = (texte_normalisé, label)
      - Insensible à la casse si config.case_insensitive=True
      - Résistant aux espaces multiples (strip + collapse)

    Usage :
        mapper = Mapper(config)
        pseudo = mapper.get_or_create(entity)
        mapper.save()  # persiste le registre
    """

    def __init__(self, config: MapperConfig | None = None):
        self.config = config or MapperConfig()
        self._counters: dict[str, int] = defaultdict(int)
        self._registry: dict[str, str] = {}      # clé sérialisée → pseudonyme
        self._reverse:  dict[str, str] = {}      # pseudonyme → texte original

        if self.config.registry_path:
            self._load_registry()

    # -----------------------------------------------------------------------
    # Interface principale
    # -----------------------------------------------------------------------

    def get_or_create(self, entity: Entity) -> str:
        """
        Retourne le pseudonyme associé à l'entité.
        En crée un nouveau si l'entité n'a jamais été vue.

        Parameters
        ----------
        entity : Entity

        Returns
        -------
        str
            Pseudonyme formaté selon la config, ex : "PERSONNE_1"
        """
        key = self._make_key(entity.text, entity.label)

        if key not in self._registry:
            pseudo = self._generate_pseudo(entity.label, entity.text)
            self._registry[key] = pseudo
            self._reverse[pseudo] = entity.text
            logger.debug("Nouveau pseudonyme : %r → %s", entity.text, pseudo)

        return self._registry[key]

    def lookup(self, text: str, label: str) -> str | None:
        """Retourne le pseudonyme existant ou None (sans en créer un nouveau)."""
        key = self._make_key(text, label)
        return self._registry.get(key)

    def reverse_lookup(self, pseudo: str) -> str | None:
        """Retourne le texte original associé à un pseudonyme (désanonymisation)."""
        return self._reverse.get(pseudo)

    def all_mappings(self) -> dict[str, str]:
        """Retourne le dictionnaire complet texte original → pseudonyme."""
        return {self._human_key(k): v for k, v in self._registry.items()}

    def stats(self) -> dict[str, int]:
        """Nombre de pseudonymes générés par label."""
        return dict(self._counters)

    # -----------------------------------------------------------------------
    # Génération du pseudonyme
    # -----------------------------------------------------------------------

    def _generate_pseudo(self, label: str, original_text: str) -> str:
        """
        Génère un pseudonyme unique pour un label donné.

        Format par défaut : "{LABEL_FR}_{n}"
          → "PERSONNE_1", "EMAIL_3", "LIEU_2"…

        Peut être surchargé dans une sous-classe pour un format custom.
        """
        self._counters[label] += 1
        n = self._counters[label]
        label_fr = LABEL_FR.get(label, label)
        return self.config.template.format(label=label_fr, n=n)

    # -----------------------------------------------------------------------
    # Clés de registre
    # -----------------------------------------------------------------------

    def _make_key(self, text: str, label: str) -> str:
        """
        Produit une clé de registre normalisée.
        Insensible à la casse si configuré ; résistant aux espaces.
        """
        normalized = " ".join(text.split())   # collapse espaces internes
        if self.config.case_insensitive:
            normalized = normalized.lower()
        return f"{label}::{normalized}"

    def _human_key(self, key: str) -> str:
        """Reconstruit le texte lisible depuis la clé de registre."""
        parts = key.split("::", 1)
        return parts[1] if len(parts) == 2 else key

    # -----------------------------------------------------------------------
    # Persistance JSON
    # -----------------------------------------------------------------------

    def save(self, path: str | None = None) -> None:
        """
        Sauvegarde le registre dans un fichier JSON.

        Parameters
        ----------
        path : str | None
            Chemin cible. Si None, utilise config.registry_path.
            Si aucun des deux n'est défini, lève ValueError.
        """
        target = path or self.config.registry_path
        if not target:
            raise ValueError("Aucun chemin de registre défini (config.registry_path ou paramètre path).")

        data = {
            "registry":  self._registry,
            "reverse":   self._reverse,
            "counters":  dict(self._counters),
        }
        Path(target).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Registre de mapping sauvegardé : %s (%d entrées)", target, len(self._registry))

    def _load_registry(self) -> None:
        """Charge un registre existant depuis le fichier JSON configuré."""
        registry_path = self.config.registry_path
        if not registry_path:
            return
            
        path = Path(registry_path)
        if not path.exists():
            logger.info("Aucun registre existant à %s — démarrage à zéro.", path)
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._registry  = data.get("registry", {})
            self._reverse   = data.get("reverse",  {})
            self._counters  = defaultdict(int, data.get("counters", {}))
            logger.info("Registre chargé : %s (%d entrées).", path, len(self._registry))
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Impossible de charger le registre %s : %s", path, exc)

    # -----------------------------------------------------------------------
    # Utilitaires
    # -----------------------------------------------------------------------

    def reset(self) -> None:
        """Remet le mapper à zéro (efface registre et compteurs)."""
        self._registry.clear()
        self._reverse.clear()
        self._counters.clear()
        logger.info("Mapper réinitialisé.")

    def merge(self, other: "Mapper") -> None:
        """
        Fusionne un autre Mapper dans celui-ci.
        Utile pour combiner des registres provenant de plusieurs documents.
        En cas de conflit, le registre courant a la priorité.
        """
        for key, pseudo in other._registry.items():
            if key not in self._registry:
                self._registry[key] = pseudo
                self._reverse[pseudo] = other._reverse.get(pseudo, "")
        # Recalcule les compteurs
        for label in set(self._counters) | set(other._counters):
            self._counters[label] = max(
                self._counters.get(label, 0),
                other._counters.get(label, 0)
            )
