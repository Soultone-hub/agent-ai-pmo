"""
Service de classification automatique des documents PMO.
Utilise le LLM pour identifier la catégorie d'un document parmi une liste prédéfinie.
"""
import json
import logging
from backend.services.llm_service import send_to_groq

logger = logging.getLogger(__name__)

# Liste prédéfinie des catégories PMO
CATEGORIES = {
    "charte_cadrage": {
        "label": "Charte / Note de cadrage",
        "description": "Charte projet, note de cadrage, fiche projet, scope document, vision document",
        "emoji": "📋",
    },
    "planning": {
        "label": "Planning / Rétro-planning",
        "description": "Planning, rétro-planning, Gantt, jalons, PERT, roadmap, calendrier",
        "emoji": "📅",
    },
    "budget": {
        "label": "Budget / Tableau financier",
        "description": "Budget, devis, tableau de bord financier, suivi des coûts, dépenses, facturation",
        "emoji": "💰",
    },
    "rapport_avancement": {
        "label": "Rapport d'avancement",
        "description": "Rapport de statut, reporting, état d'avancement, tableau de bord, bilan",
        "emoji": "📊",
    },
    "compte_rendu": {
        "label": "Compte-rendu / PV COPIL",
        "description": "Compte-rendu de réunion, PV COPIL, minutes, relevé de décisions",
        "emoji": "📝",
    },
    "registre_risques": {
        "label": "Registre des risques",
        "description": "Registre des risques, matrice des risques, analyse SWOT, plan de mitigation",
        "emoji": "⚠️",
    },
    "autre": {
        "label": "Autre",
        "description": "Document non classifiable dans les catégories précédentes",
        "emoji": "📁",
    },
}

# Catégories obligatoires pour un dossier projet complet
REQUIRED_CATEGORIES = [
    "charte_cadrage",
    "planning",
    "budget",
    "rapport_avancement",
    "compte_rendu",
    "registre_risques",
]


def classify_document(filename: str, text_excerpt: str) -> str:
    """
    Classifie un document dans une des catégories PMO prédéfinies.
    Utilise les 1500 premiers caractères du document pour la classification.
    Retourne la clé de catégorie (ex: "charte_cadrage").
    """
    excerpt = text_excerpt[:1500].strip() if text_excerpt else ""

    categories_list = "\n".join([
        f'- "{key}": {info["description"]}'
        for key, info in CATEGORIES.items()
    ])

    prompt = f"""Tu es un expert PMO. Analyse ce document et classe-le dans une seule catégorie.

Nom du fichier : {filename}

Extrait du contenu :
{excerpt}

Catégories disponibles :
{categories_list}

Réponds UNIQUEMENT avec un objet JSON de cette forme exacte :
{{"categorie": "une_des_clés_ci_dessus", "confiance": "haute|moyenne|faible"}}

Ne réponds avec rien d'autre que ce JSON."""

    try:
        response = send_to_groq(
            prompt,
            system_prompt="Tu es un expert en classification de documents de gestion de projet. Réponds uniquement en JSON valide."
        )
        response_clean = response.strip()
        if "```" in response_clean:
            response_clean = response_clean.split("```")[1].split("```")[0].strip()
            if response_clean.startswith("json"):
                response_clean = response_clean[4:].strip()

        data = json.loads(response_clean)
        category = data.get("categorie", "autre")

        if category not in CATEGORIES:
            logger.warning(f"Catégorie inconnue '{category}' retournée par le LLM, fallback 'autre'")
            return "autre"

        logger.info(f"Document '{filename}' classifié : {category} (confiance: {data.get('confiance', '?')})")
        return category

    except Exception as e:
        logger.error(f"Erreur classification document '{filename}': {e}")
        return "autre"


def get_project_checklist(documents: list) -> dict:
    """
    Calcule la checklist de complétude d'un projet à partir de la liste de ses documents.
    Retourne un dict avec l'état de chaque catégorie.
    """
    present_categories = {doc.category for doc in documents if doc.category}

    checklist = {}
    for key, info in CATEGORIES.items():
        if key == "autre":
            continue
        checklist[key] = {
            "label": info["label"],
            "emoji": info["emoji"],
            "present": key in present_categories,
            "required": key in REQUIRED_CATEGORIES,
            "documents": [
                {"id": str(doc.id), "filename": doc.filename}
                for doc in documents
                if doc.category == key
            ],
        }

    required_present = sum(
        1 for key in REQUIRED_CATEGORIES if key in present_categories
    )
    total_required = len(REQUIRED_CATEGORIES)

    return {
        "checklist": checklist,
        "score": required_present,
        "total": total_required,
        "complete": required_present == total_required,
        "pourcentage": round((required_present / total_required) * 100),
    }
