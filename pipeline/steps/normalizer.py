"""
steps/normalizer.py — Étape 1 : Normalisation du texte brut.

Objectif : produire un texte propre, homogène, que les détecteurs
(NER, regex) peuvent analyser de façon fiable.

Opérations :
  1. Décodage et nettoyage Unicode (NFC)
  2. Remplacement des caractères de contrôle
  3. Normalisation des espaces (espaces insécables, tabulations…)
  4. Normalisation des sauts de ligne
  5. Correction des encodages cassés (latin-1 interprété UTF-8 = mojibake)
  6. Suppression des caractères non imprimables
  7. Conservation d'un index de correspondance original ↔ normalisé
     (indispensable pour remonter aux offsets d'origine si besoin)
"""

import re
import unicodedata
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Résultat de la normalisation
# ---------------------------------------------------------------------------

@dataclass
class NormalizationResult:
    text: str                         # Texte normalisé
    offset_map: list[int]             # offset_map[i] = position dans le texte original
    changes: list[str]                # Journal des transformations appliquées


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------

class Normalizer:
    """
    Normalise un texte brut avant détection.

    Usage :
        normalizer = Normalizer()
        result = normalizer.normalize(raw_text)
        clean = result.text
    """

    # Caractères de contrôle à supprimer (sauf \n, \r, \t)
    _CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

    # Séquences d'espaces multiples (hors sauts de ligne)
    _MULTI_SPACE_RE = re.compile(r"[^\S\n]{2,}")

    # Sauts de ligne multiples → deux sauts maximum
    _MULTI_NL_RE = re.compile(r"\n{3,}")

    # Tirets typographiques → tiret simple
    _DASHES_RE = re.compile(r"[\u2010-\u2015\u2212]")

    # Guillemets typographiques → ASCII
    _QUOTES_RE = re.compile(r"[\u2018\u2019\u201a\u201b]|[\u201c\u201d\u201e\u201f]")

    # Apostrophes et guillemets spéciaux courants dans les PDF
    _APOS_RE = re.compile(r"[ʼ''′`]")

    def normalize(self, text: str) -> NormalizationResult:
        """
        Applique toutes les transformations et retourne un NormalizationResult.
        """
        changes: list[str] = []
        working = text

        # 1. Correction mojibake basique (latin-1 encodé comme UTF-8 puis mal décodé)
        working, changed = self._fix_mojibake(working)
        if changed:
            changes.append("mojibake_fix")

        # 2. Normalisation Unicode NFC (composition canonique)
        nfc = unicodedata.normalize("NFC", working)
        if nfc != working:
            changes.append("unicode_nfc")
        working = nfc

        # 3. Suppression des caractères de contrôle
        cleaned = self._CONTROL_RE.sub("", working)
        if cleaned != working:
            changes.append("control_chars_removed")
        working = cleaned

        # 4. Normalisation des espaces insécables et autres espaces Unicode
        working, changed = self._normalize_spaces(working)
        if changed:
            changes.append("spaces_normalized")

        # 5. Tirets typographiques → tiret simple ASCII
        result = self._DASHES_RE.sub("-", working)
        if result != working:
            changes.append("dashes_normalized")
        working = result

        # 6. Guillemets typographiques → guillemets ASCII
        result = self._normalize_quotes(working)
        if result != working:
            changes.append("quotes_normalized")
        working = result

        # 7. Tabulations → espace unique
        result = working.replace("\t", " ")
        if result != working:
            changes.append("tabs_to_space")
        working = result

        # 8. Espaces multiples sur une même ligne
        result = self._MULTI_SPACE_RE.sub(" ", working)
        if result != working:
            changes.append("multi_spaces_collapsed")
        working = result

        # 9. Sauts de ligne multiples (3+) → 2 max
        result = self._MULTI_NL_RE.sub("\n\n", working)
        if result != working:
            changes.append("multi_newlines_collapsed")
        working = result

        # 10. Strip global
        working = working.strip()

        # Construction de l'offset map (meilleur effort)
        offset_map = self._build_offset_map(text, working)

        return NormalizationResult(
            text=working,
            offset_map=offset_map,
            changes=changes,
        )

    # -----------------------------------------------------------------------
    # Helpers privés
    # -----------------------------------------------------------------------

    def _fix_mojibake(self, text: str) -> tuple[str, bool]:
        """
        Tente de corriger l'encodage mojibake le plus fréquent :
        texte encodé en UTF-8 mais lu comme latin-1, ou l'inverse.
        Ne modifie le texte que si la correction améliore le taux de caractères valides.
        """
        try:
            fixed = text.encode("latin-1").decode("utf-8")
            # Heuristique : si la version fixée contient moins de caractères
            # de remplacement, c'était bien du mojibake.
            if fixed.count("\ufffd") < text.count("\ufffd"):
                return fixed, True
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        return text, False

    def _normalize_spaces(self, text: str) -> tuple[str, bool]:
        """
        Remplace tous les caractères "espace" Unicode par une espace ASCII ordinaire,
        sauf les sauts de ligne que l'on préserve.
        Espaces concernées : NBSP, espace fine, espace idéographique, etc.
        """
        SPACE_CHARS = (
            "\u00a0"  # NO-BREAK SPACE
            "\u00ad"  # SOFT HYPHEN → on le supprime
            "\u200b"  # ZERO WIDTH SPACE
            "\u200c"  # ZERO WIDTH NON-JOINER
            "\u200d"  # ZERO WIDTH JOINER
            "\u2002"  # EN SPACE
            "\u2003"  # EM SPACE
            "\u2009"  # THIN SPACE
            "\u202f"  # NARROW NO-BREAK SPACE
            "\u3000"  # IDEOGRAPHIC SPACE
            "\ufeff"  # BOM
        )
        result = text
        for ch in SPACE_CHARS:
            if ch in ("\u00ad", "\u200b", "\u200c", "\u200d", "\ufeff"):
                result = result.replace(ch, "")   # suppression pure
            else:
                result = result.replace(ch, " ")  # remplacement par espace
        return result, (result != text)

    def _normalize_quotes(self, text: str) -> str:
        """Unifie les apostrophes et guillemets typographiques vers ASCII."""
        result = self._QUOTES_RE.sub(
            lambda m: '"' if m.group() in '\u201c\u201d\u201e\u201f' else "'",
            text
        )
        result = self._APOS_RE.sub("'", result)
        return result

    def _build_offset_map(self, original: str, normalized: str) -> list[int]:
        """
        Construit un vecteur offset_map tel que :
            offset_map[i] ≈ position approximative du caractère i
                             dans le texte original.

        L'alignement exact caractère-par-caractère est complexe quand des
        caractères sont supprimés ou fusionnés. On utilise ici un alignement
        proportionnel (suffisant pour l'audit ; pour un alignement strict,
        utiliser difflib.SequenceMatcher).
        """
        if not original or not normalized:
            return list(range(len(normalized)))

        ratio = len(original) / max(len(normalized), 1)
        return [min(int(i * ratio), len(original) - 1) for i in range(len(normalized))]
