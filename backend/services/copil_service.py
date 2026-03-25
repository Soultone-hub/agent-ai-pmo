import json
import os
import logging
from backend.services.llm_service import send_to_groq
from backend.services.rag_service import search_documents

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)


def validate_copil(data: dict) -> dict:
    """Valide et normalise la structure COPIL retournée par le LLM."""
    
    types_alertes_valides = {"retard", "budget", "ressource", "risque"}
    priorites_valides = {"critique", "haute", "moyenne", "faible"}
    statuts_valides = {"a_faire", "en_cours", "termine", "bloque"}

    for alerte in data.get("alertes", []):
        if alerte.get("type") not in types_alertes_valides:
            alerte["type"] = "risque"
        if alerte.get("priorite") not in priorites_valides:
            alerte["priorite"] = "moyenne"

    for action in data.get("plan_actions", []):
        if action.get("statut") not in statuts_valides:
            action["statut"] = "a_faire"
        if not action.get("responsable"):
            action["responsable"] = "Non spécifié"
        if not action.get("echeance"):
            action["echeance"] = "Non spécifié"

    if not data.get("etat_avancement"):
        data["etat_avancement"] = "Non spécifié"
    if not data.get("resume_executif"):
        data["resume_executif"] = "Non spécifié"
    if not isinstance(data.get("points_cles"), list):
        data["points_cles"] = []
    if not isinstance(data.get("decisions_attendues"), list):
        data["decisions_attendues"] = []

    return data


def generate_copil(project_id: str, document_text: str) -> dict:
    prompt_path = os.path.join(BASE_DIR, '..', 'prompts', 'copil_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error(f"Fichier prompt introuvable : {prompt_path}")
        return {"error": "Fichier prompt COPIL introuvable"}

    context = search_documents(project_id, "avancement décisions actions jalons planning budget")
    context_text = "\n".join(context) if context else "Aucun contexte disponible"

    doc_preview = (
        document_text[:2000].rsplit(' ', 1)[0] + "..."
        if len(document_text) > 2000
        else document_text
    )

    full_text = f"{doc_preview}\n\nCONTEXTE ADDITIONNEL:\n{context_text}"
    prompt = prompt_template.replace('{document_text}', full_text)

    reponse = send_to_groq(prompt)

    try:
        reponse_clean = reponse.strip()
        if '```json' in reponse_clean:
            reponse_clean = reponse_clean.split('```json')[1].split('```')[0].strip()
        elif '```' in reponse_clean:
            reponse_clean = reponse_clean.split('```')[1].split('```')[0].strip()

        if not reponse_clean:
            return {"error": "Réponse vide du LLM"}

        data = json.loads(reponse_clean)
        return validate_copil(data)

    except json.JSONDecodeError as e:
        logger.error(f"Erreur parsing JSON COPIL pour projet {project_id}: {e}\nRéponse brute: {reponse}")
        return {"error": "Erreur de parsing JSON", "raw": reponse}