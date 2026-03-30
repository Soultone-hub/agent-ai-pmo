import json
import os
import logging
from backend.services.llm_service import send_to_groq
from backend.services.rag_service import search_in_document, search_in_documents

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)


def validate_analysis(data: dict) -> dict:
    """Valide et normalise la structure d'analyse documentaire."""
    if not isinstance(data.get("objectifs"), list):
        data["objectifs"] = []
    if not isinstance(data.get("contraintes"), list):
        data["contraintes"] = []
    if not isinstance(data.get("hypotheses"), list):
        data["hypotheses"] = []
    if not isinstance(data.get("parties_prenantes"), list):
        data["parties_prenantes"] = []
    if not isinstance(data.get("points_cles"), list):
        data["points_cles"] = []
    if not data.get("resume"):
        data["resume"] = "Aucun résumé disponible"
    return data


def analyze_document(project_id: str, document_id: str, document_text: str) -> dict:
    prompt_path = os.path.join(BASE_DIR, '..', 'prompts', 'analysis_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error(f"Fichier prompt introuvable : {prompt_path}")
        return {"error": "Fichier prompt analyse introuvable"}

    # RAG ciblé sur le document cible
    chunks = search_in_document(project_id, document_id, "objectifs contraintes hypothèses parties prenantes")
    context_text = "\n".join(chunks) if chunks else "Aucun contexte disponible"

    prompt = prompt_template.replace('{document_text}', context_text)
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
        return validate_analysis(data)
    except json.JSONDecodeError as e:
        logger.error(f"Erreur parsing JSON analyse pour projet {project_id}: {e}\nRéponse brute: {reponse}")
        return {"error": "Erreur de parsing JSON", "raw": reponse}


def analyze_documents_multi(project_id: str, document_ids: list, document_texts: list) -> dict:
    """Analyse documentaire sur plusieurs documents cibles."""
    prompt_path = os.path.join(BASE_DIR, '..', 'prompts', 'analysis_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error(f"Fichier prompt introuvable : {prompt_path}")
        return {"error": "Fichier prompt analyse introuvable"}

    # RAG sur tous les documents cibles
    chunks = search_in_documents(project_id, document_ids, "objectifs contraintes hypothèses parties prenantes")
    context_text = "\n".join(chunks) if chunks else "Aucun contexte disponible"

    prompt = prompt_template.replace('{document_text}', context_text)
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
        return validate_analysis(data)
    except json.JSONDecodeError as e:
        logger.error(f"Erreur parsing JSON analyse multi-docs : {e}\nRéponse brute: {reponse}")
        return {"error": "Erreur de parsing JSON", "raw": reponse}