import json
import os
import logging
from backend.services.llm_service import send_to_groq
from backend.services.rag_service import search_documents

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

        # Catégorie valide uniquement
        categories_valides = {"planning", "budget", "technique", "humain", "externe"}
        if risk.get("categorie") not in categories_valides:
            risk["categorie"] = "externe"

    return data


def extract_risks(project_id: str, document_text: str) -> dict:
    # Chargement sécurisé du prompt
    prompt_path = os.path.join(BASE_DIR, '..', 'prompts', 'risk_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error(f"Fichier prompt introuvable : {prompt_path}")
        return {"risks": [], "resume": "Fichier prompt introuvable"}

    # Contexte RAG avec fallback
    context = search_documents(project_id, "risques problemes contraintes difficultes")
    context_text = "\n".join(context) if context else "Aucun contexte disponible"

    # Troncature propre
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
            return {"risks": [], "resume": "Aucun risque identifié"}

        data = json.loads(reponse_clean)
        return validate_risks(data)  # ✅ Validation activée

    except json.JSONDecodeError as e:
        logger.error(f"Erreur parsing JSON pour projet {project_id}: {e}\nRéponse brute: {reponse}")
        return {"risks": [], "resume": "Erreur de parsing", "raw": reponse}