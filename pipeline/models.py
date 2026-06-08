"""
models.py — Structures de données partagées dans toute la pipeline.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Types d'entités supportés
# ---------------------------------------------------------------------------

class EntityLabel(str, Enum):
    # Entités nommées (NER)
    PER  = "PER"   # Personne physique
    LOC  = "LOC"   # Lieu géographique
    ORG  = "ORG"   # Organisation / entreprise

    # Données structurées (regex)
    EMAIL   = "EMAIL"
    PHONE   = "PHONE"
    IBAN    = "IBAN"
    SIREN   = "SIREN"
    SIRET   = "SIRET"
    NIR     = "NIR"       # Numéro de sécurité sociale français
    DATE    = "DATE"
    IP      = "IP"
    URL     = "URL"
    POSTCODE = "POSTCODE"
    CC      = "CC"        # Numéro de carte bancaire

    # Identifiants métier (Bénin / Afrique de l'Ouest)
    IFU     = "IFU"      # Identifiant Fiscal Unique (13 chiffres)
    RCCM    = "RCCM"     # Registre de Commerce et du Crédit Mobilier

    # Identifiants personnels structurés
    USER      = "USER"       # Nom d'utilisateur système (initiale.nom / prénom.nom)
    MATRICULE = "MATRICULE"  # Matricule / identifiant administratif (CNI, CNSS…)

    # Entités métier custom
    CUSTOM  = "CUSTOM"


# Noms français pour les pseudonymes générés
LABEL_FR: dict[str, str] = {
    "PER":      "PERSONNE",
    "LOC":      "LIEU",
    "ORG":      "ORGANISATION",
    "EMAIL":    "EMAIL",
    "PHONE":    "TELEPHONE",
    "IBAN":     "IBAN",
    "SIREN":    "SIREN",
    "SIRET":    "SIRET",
    "NIR":      "NIR",
    "DATE":     "DATE",
    "IP":       "IP",
    "URL":      "URL",
    "POSTCODE": "CODE_POSTAL",
    "CC":       "CARTE_BANCAIRE",
    "IFU":      "IFU",
    "RCCM":     "RCCM",
    "USER":      "UTILISATEUR",
    "MATRICULE": "MATRICULE",
    "CUSTOM":   "ENTITE",
}


# ---------------------------------------------------------------------------
# Entité détectée
# ---------------------------------------------------------------------------

@dataclass
class Entity:
    text: str               # Texte brut détecté : "Jean Dupont"
    label: str              # Label : "PER", "EMAIL", …
    start: int              # Offset début dans le texte normalisé
    end: int                # Offset fin (exclusif)
    score: float            # Score de confiance [0, 1]
    source: str             # "ner" | "regex" | "rule"
    context: str = ""       # Fenêtre de contexte (utile pour debug/audit)
    metadata: dict = field(default_factory=dict)  # Infos complémentaires libres

    # -----------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"Entity(text={self.text!r}, label={self.label}, "
            f"span=[{self.start}:{self.end}], score={self.score:.2f}, src={self.source})"
        )

    def overlaps(self, other: "Entity") -> bool:
        """Retourne True si les deux entités se chevauchent (même si partiellement)."""
        return self.start < other.end and other.start < self.end

    def contains(self, other: "Entity") -> bool:
        """Retourne True si self englobe totalement other."""
        return self.start <= other.start and self.end >= other.end


# ---------------------------------------------------------------------------
# Résultat complet de la pipeline
# ---------------------------------------------------------------------------

@dataclass
class AnonymizationResult:
    original_text:   str
    normalized_text: str                      # Texte après normalisation
    clean_text:      str                      # Texte final anonymisé
    entities:        list[Entity]             # Entités retenues après résolution
    mapping:         dict[str, str]           # "Jean Dupont" → "[PERSONNE_1]"
    score:           float                    # Score qualité global [0, 1]
    warnings:        list[str] = field(default_factory=list)
    stats:           dict = field(default_factory=dict)

    # -----------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "clean_text": self.clean_text,
            "mapping": self.mapping,
            "score": round(self.score, 4),
            "stats": self.stats,
            "warnings": self.warnings,
            "entities": [
                {
                    "text":   e.text,
                    "label":  e.label,
                    "start":  e.start,
                    "end":    e.end,
                    "score":  round(e.score, 4),
                    "source": e.source,
                }
                for e in self.entities
            ],
        }

    def summary(self) -> str:
        lines = [
            f"Score qualité : {self.score:.0%}",
            f"Entités anonymisées : {len(self.entities)}",
        ]
        by_label: dict[str, int] = {}
        for e in self.entities:
            by_label[e.label] = by_label.get(e.label, 0) + 1
        for label, count in sorted(by_label.items()):
            lines.append(f"  {label}: {count}")
        if self.warnings:
            lines.append("Avertissements :")
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")
        return "\n".join(lines)
