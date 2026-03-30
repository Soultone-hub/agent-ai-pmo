import json
import os
import logging
from backend.services.llm_service import send_to_groq
from backend.services.rag_service import search_in_document, search_in_documents

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)


def validate_risks(data: dict) -> dict:
    """Recalcule et valide les scores/niveaux côté Python."""
    for risk in data.get("risks", []):
        p = max(1, min(5, int(risk.get("probabilite", 1))))
        i = max(1, min(5, int(risk.get("impact", 1))))
        risk["probabilite"] = p
        risk["impact"] = i
        risk["score"] = p * i

        score = risk["score"]
        if score >= 15:
            risk["niveau"] = "critique"
        elif score >= 10:
            risk["niveau"] = "eleve"
        elif score >= 5:
            risk["niveau"] = "modere"
        else:
            risk["niveau"] = "faible"

        categories_valides = {"planning", "budget", "technique", "humain", "externe"}
        if risk.get("categorie") not in categories_valides:
            risk["categorie"] = "externe"

    return data


def extract_risks(project_id: str, document_id: str, document_text: str) -> dict:
    prompt_path = os.path.join(BASE_DIR, '..', 'prompts', 'risk_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error(f"Fichier prompt introuvable : {prompt_path}")
        return {"risks": [], "resume": "Fichier prompt introuvable"}

    # RAG ciblé sur le document cible
    chunks = search_in_document(project_id, document_id, "risques problemes contraintes difficultes")
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
            return {"risks": [], "resume": "Aucun risque identifié"}
        data = json.loads(reponse_clean)
        return validate_risks(data)
    except json.JSONDecodeError as e:
        logger.error(f"Erreur parsing JSON pour projet {project_id}: {e}\nRéponse brute: {reponse}")
        return {"risks": [], "resume": "Erreur de parsing", "raw": reponse}


def extract_risks_multi(project_id: str, document_ids: list, document_texts: list) -> dict:
    """Extraction de risques sur plusieurs documents cibles."""
    prompt_path = os.path.join(BASE_DIR, '..', 'prompts', 'risk_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error(f"Fichier prompt introuvable : {prompt_path}")
        return {"risks": [], "resume": "Fichier prompt introuvable"}

    # RAG sur tous les documents cibles
    chunks = search_in_documents(project_id, document_ids, "risques problemes contraintes difficultes")
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
            return {"risks": [], "resume": "Aucun risque identifié"}
        data = json.loads(reponse_clean)
        return validate_risks(data)
    except json.JSONDecodeError as e:
        logger.error(f"Erreur parsing JSON multi-docs : {e}\nRéponse brute: {reponse}")
        return {"risks": [], "resume": "Erreur de parsing", "raw": reponse}