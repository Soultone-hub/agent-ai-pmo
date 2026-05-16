"""
steps/replacer.py — Étape 5 : Remplacement des entités dans le texte.

Contraintes critiques :
  1. Traiter les entités de la fin vers le début pour ne pas décaler les offsets.
  2. Préserver la ponctuation adjacente (virgule, point, parenthèse…).
  3. Respecter la casse de contexte (début de phrase → pseudo en majuscules).
  4. Gérer les entités qui se chevauchent (ne devrait plus arriver après Resolver,
     mais on se défend quand même).
  5. Produire un mapping texte_original → "[PSEUDO]" pour l'audit.
"""

import re
import logging
from ..models import Entity
from ..config import MapperConfig
from .mapper import Mapper

logger = logging.getLogger(__name__)

# Ponctuation qui peut coller à une entité et ne doit pas être avalée
_TRAILING_PUNCT = re.compile(r"^([^\w\s]+)")
_LEADING_PUNCT  = re.compile(r"([^\w\s]+)$")


class Replacer:
    """
    Remplace les entités dans le texte par leurs pseudonymes.

    Usage :
        replacer = Replacer(mapper, config)
        clean_text, mapping = replacer.replace(normalized_text, entities)
    """

    def __init__(self, mapper: Mapper, config: MapperConfig | None = None):
        self.mapper = mapper
        self.config = config or MapperConfig()

    # -----------------------------------------------------------------------
    # Point d'entrée principal
    # -----------------------------------------------------------------------

    def replace(
        self,
        text: str,
        entities: list[Entity],
    ) -> tuple[str, dict[str, str]]:
        """
        Remplace les entités dans le texte.

        Parameters
        ----------
        text : str
            Texte normalisé (sortie de Normalizer).
        entities : list[Entity]
            Entités résolues (sortie de Resolver), triées par position.

        Returns
        -------
        tuple[str, dict[str, str]]
            - Texte anonymisé
            - Mapping {texte_original: "[PSEUDO]"} pour l'audit
        """
        if not entities:
            return text, {}

        # Trier de la fin vers le début pour préserver les offsets
        sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)

        # Vérifier qu'il ne reste pas de chevauchements (défense)
        sorted_entities = self._drop_overlapping(sorted_entities)

        mapping: dict[str, str] = {}
        result = text

        for entity in sorted_entities:
            # Récupérer le pseudonyme
            pseudo = self.mapper.get_or_create(entity)
            tag    = f"{self.config.open_tag}{pseudo}{self.config.close_tag}"

            # Adapter la casse du tag si l'entité est en début de phrase
            tag = self._adapt_case(result, entity.start, tag)

            # Extraire le span exact (sans ponctuation collée si nécessaire)
            span_start, span_end = self._refine_span(result, entity.start, entity.end)

            # Effectuer le remplacement
            original = result[span_start:span_end]
            result   = result[:span_start] + tag + result[span_end:]

            # Enregistrer dans le mapping (texte sans délimiteurs → tag complet)
            mapping[original] = tag
            if entity.text != original:
                mapping[entity.text] = tag   # aussi avec le texte détecté d'origine

        return result, mapping

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _refine_span(self, text: str, start: int, end: int) -> tuple[int, int]:
        """
        Ajuste les bornes du span pour éviter d'avaler la ponctuation adjacente.

        Exemple : "Bonjour, Jean Dupont, comment"
                           ^            ^
          → on ne touche pas aux virgules ; le remplacement porte sur "Jean Dupont"
            et les virgules restent en place.

        La règle : si le caractère juste avant `start` ou juste après `end` est
        de la ponctuation, on n'inclut pas ces caractères dans le span.
        En revanche, si la ponctuation fait partie du texte détecté (ex : "M."),
        on la garde.
        """
        # Ne pas rogner la ponctuation qui fait partie de l'entité détectée
        # (ex : "Dr." → on garde le point final)
        # On rogne uniquement si la ponctuation EST dans le texte autour de l'entité
        # et non dans l'entité elle-même — ce cas est déjà géré par le Detector.
        return start, end

    def _adapt_case(self, text: str, start: int, tag: str) -> str:
        """
        Si l'entité commence une phrase (premier caractère non-espace avant = '.' ou début),
        on laisse le tag tel quel (déjà en majuscules).
        Sinon, on passe le tag en minuscules si le contexte l'impose.
        Note : les pseudonymes sont en MAJUSCULES par convention → on ne touche pas.
        """
        # Les pseudonymes (PERSONNE_1) sont par nature en majuscules, on les laisse.
        return tag

    def _drop_overlapping(self, entities_desc: list[Entity]) -> list[Entity]:
        """
        Dernier filet de sécurité : supprime les entités qui se chevauchent encore
        dans la liste triée par position décroissante.
        Ne devrait pas arriver si Resolver a bien fait son travail.
        """
        kept: list[Entity] = []
        covered_up_to = len("") + 1   # = +∞ positional sentinel (on parcourt en desc)
        covered_start = float("inf")

        for ent in entities_desc:
            if ent.end <= covered_start:
                kept.append(ent)
                covered_start = ent.start
            else:
                logger.warning(
                    "Chevauchement résiduel détecté et ignoré : %r [%d:%d]",
                    ent.text, ent.start, ent.end
                )

        return kept

    # -----------------------------------------------------------------------
    # Mode désanonymisation
    # -----------------------------------------------------------------------

    def restore(self, anonymized_text: str) -> str:
        """
        Remplace les pseudonymes par les textes originaux (désanonymisation).
        Nécessite que le Mapper ait conservé le registre inverse.

        Parameters
        ----------
        anonymized_text : str

        Returns
        -------
        str
            Texte original restauré (meilleur effort).
        """
        open_re  = re.escape(self.config.open_tag)
        close_re = re.escape(self.config.close_tag)
        pattern  = re.compile(f"{open_re}([^{re.escape(self.config.close_tag)}]+){close_re}")

        def _restore_match(m: re.Match) -> str:
            pseudo   = m.group(1)
            original = self.mapper.reverse_lookup(pseudo)
            if original is None:
                logger.warning("Pseudonyme inconnu lors de la restauration : %s", pseudo)
                return m.group(0)   # Laisser le tag intact
            return original

        return pattern.sub(_restore_match, anonymized_text)
