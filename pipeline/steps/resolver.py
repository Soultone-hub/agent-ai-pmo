"""
steps/resolver.py — Étape 3 : Fusion & résolution des entités.

Problèmes traités :
  1. Doublons exacts (même span, même label, sources différentes)
  2. Chevauchements partiels (A commence avant B mais B finit après A)
  3. Inclusions (A est entièrement contenu dans B)
  4. Conflits de label (même span mais labels différents)
  5. Filtrage par score de confiance minimum

Stratégies disponibles (ResolverConfig.strategy) :
  - "score"  → garder l'entité avec le score le plus élevé
  - "length" → garder la plus longue
  - "source" → priorité regex > rule > ner
"""

import logging
from ..models import Entity
from ..config import ResolverConfig

logger = logging.getLogger(__name__)

# Priorité des sources pour la stratégie "source"
SOURCE_PRIORITY: dict[str, int] = {
    "regex": 3,
    "rule":  2,
    "ner":   1,
}


class Resolver:
    """
    Fusionne et résout les conflits entre entités détectées.

    Usage :
        resolver = Resolver(config)
        clean_entities = resolver.resolve(raw_entities)
    """

    def __init__(self, config: ResolverConfig | None = None):
        self.config = config or ResolverConfig()

    # -----------------------------------------------------------------------
    # Point d'entrée principal
    # -----------------------------------------------------------------------

    def resolve(self, entities: list[Entity]) -> list[Entity]:
        """
        Retourne une liste d'entités sans chevauchements ni doublons,
        triée par position dans le texte.

        Parameters
        ----------
        entities : list[Entity]
            Entités brutes de la détection (potentiellement chevauchantes).

        Returns
        -------
        list[Entity]
            Entités résolues, triées par position de début.
        """
        if not entities:
            return []

        # 1. Filtrer par score minimum
        filtered = [e for e in entities if e.score >= self.config.min_score]
        removed = len(entities) - len(filtered)
        if removed:
            logger.debug("%d entité(s) filtrée(s) (score < %.2f).", removed, self.config.min_score)

        # 2. Fusionner les doublons exacts (même span, même label)
        merged = self._merge_exact_duplicates(filtered)

        # 3. Résoudre les chevauchements et inclusions
        resolved = self._resolve_overlaps(merged)

        # 4. Trier par position de début
        resolved.sort(key=lambda e: e.start)

        logger.debug(
            "Résolution : %d entité(s) brutes → %d entité(s) retenues.",
            len(entities), len(resolved)
        )
        return resolved

    # -----------------------------------------------------------------------
    # 1. Fusion des doublons exacts
    # -----------------------------------------------------------------------

    def _merge_exact_duplicates(self, entities: list[Entity]) -> list[Entity]:
        """
        Regroupe les entités qui couvrent exactement le même span.
        Garde l'entité "gagnante" selon la stratégie configurée.
        """
        groups: dict[tuple[int, int, str], list[Entity]] = {}
        for ent in entities:
            key = (ent.start, ent.end, ent.label)
            groups.setdefault(key, []).append(ent)

        merged: list[Entity] = []
        for group in groups.values():
            if len(group) == 1:
                merged.append(group[0])
            else:
                # Utiliser la même clé de tri que pour la résolution des chevauchements
                best = max(group, key=self._sort_key)
                all_sources = list({e.source for e in group})
                best.metadata["all_sources"] = all_sources
                merged.append(best)

        return merged

    # -----------------------------------------------------------------------
    # 2. Résolution des chevauchements
    # -----------------------------------------------------------------------

    def _resolve_overlaps(self, entities: list[Entity]) -> list[Entity]:
        """
        Algorithme glouton :
          - Trier les entités par score (décroissant) puis par longueur (décroissant)
          - Parcourir la liste ; si une entité chevauche une entité déjà retenue,
            l'ignorer (sauf si elle l'englobe totalement et prefer_longest=True).
        """
        # Tri principal : score décroissant, secondaire : longueur décroissante,
        # tertiaire : priorité source décroissante
        # Le premier élément du tri devient "existing" → doit être le meilleur
        sorted_ents = sorted(
            entities,
            key=self._sort_key,
            reverse=True,
        )

        accepted: list[Entity] = []

        for candidate in sorted_ents:
            conflict = self._find_conflict(candidate, accepted)
            if conflict is None:
                accepted.append(candidate)
                continue

            # Il y a un conflit — décider lequel garder
            winner = self._pick_winner(candidate, conflict)
            if winner is candidate:
                accepted.remove(conflict)
                accepted.append(candidate)
            # else : on garde conflict, on ignore candidate

        return accepted

    def _sort_key(self, entity: Entity) -> tuple:
        """
        Clé de tri pour prioriser les entités avant résolution.
        La stratégie "source" met la priorité de source en premier critère,
        puis le score, puis la longueur.
        """
        length = entity.end - entity.start
        src_priority = SOURCE_PRIORITY.get(entity.source, 0)

        if self.config.strategy == "score":
            return (entity.score, length, src_priority)
        elif self.config.strategy == "length":
            return (length, entity.score, src_priority)
        else:  # "source" → source prime, puis score, puis longueur
            return (src_priority, entity.score, length)

    def _find_conflict(self, candidate: Entity, accepted: list[Entity]) -> Entity | None:
        """Retourne la première entité acceptée qui chevauche candidate, ou None."""
        for acc in accepted:
            if candidate.overlaps(acc):
                return acc
        return None

    def _pick_winner(self, candidate: Entity, existing: Entity) -> Entity:
        """
        Choisit entre deux entités qui se chevauchent.
        Retourne l'entité qui doit être conservée.
        """
        # Si l'une englobe totalement l'autre et prefer_longest=True
        if self.config.prefer_longest:
            if existing.contains(candidate):
                return existing
            if candidate.contains(existing):
                return candidate

        # Sinon appliquer la stratégie configurée
        if self.config.strategy == "score":
            return candidate if candidate.score > existing.score else existing
        elif self.config.strategy == "length":
            cand_len = candidate.end - candidate.start
            exist_len = existing.end - existing.start
            return candidate if cand_len > exist_len else existing
        else:  # "source"
            cand_prio  = SOURCE_PRIORITY.get(candidate.source, 0)
            exist_prio = SOURCE_PRIORITY.get(existing.source, 0)
            # La priorité de source est absolue, indépendamment du score
            if cand_prio > exist_prio:
                return candidate
            elif exist_prio > cand_prio:
                return existing
            # Même priorité de source → on compare les scores
            return candidate if candidate.score >= existing.score else existing

    # -----------------------------------------------------------------------
    # Diagnostic
    # -----------------------------------------------------------------------

    def explain(self, before: list[Entity], after: list[Entity]) -> str:
        """
        Retourne un rapport texte comparant avant/après résolution.
        Utile pour le debug et l'audit.
        """
        removed = [e for e in before if e not in after]
        lines = [
            f"Résolution : {len(before)} → {len(after)} entité(s)",
            f"Supprimées : {len(removed)}",
        ]
        for e in removed:
            lines.append(f"  - {e.text!r} ({e.label}, score={e.score:.2f}, src={e.source})")
        lines.append("Retenues :")
        for e in after:
            lines.append(f"  + {e.text!r} ({e.label}, score={e.score:.2f}, src={e.source})")
        return "\n".join(lines)
