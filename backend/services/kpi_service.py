import json
import os
import logging
from backend.services.llm_service import send_to_groq
from backend.services.rag_service import search_documents

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)


def validate_kpis(data: dict) -> dict:
    """Valide et normalise la structure KPI retournée par le LLM."""

    categories_valides = {"planning", "budget", "qualite", "ressources", "satisfaction", "technique"}
    statuts_valides = {"vert", "orange", "rouge", "inconnu"}
    tendances_valides = {"hausse", "baisse", "stable", "inconnu"}

    kpis_valides = []
    for i, kpi in enumerate(data.get("kpis", []), start=1):
        if not kpi.get("nom"):
            continue

        if kpi.get("categorie") not in categories_valides:
            kpi["categorie"] = "technique"
        if kpi.get("statut") not in statuts_valides:
            kpi["statut"] = "inconnu"
        if kpi.get("tendance") not in tendances_valides:
            kpi["tendance"] = "inconnu"

        kpi.setdefault("id", f"KPI{i:03d}")
        kpi.setdefault("valeur_actuelle", "Non renseigné")
        kpi.setdefault("valeur_cible", "Non définie")
        kpi.setdefault("unite", "")
        kpi.setdefault("commentaire", "")

        kpis_valides.append(kpi)

    data["kpis"] = kpis_valides

    score = data.get("score_global", {})
    if not isinstance(score, dict):
        score = {}
    score_valeur = max(0, min(100, int(score.get("valeur", 0))))
    data["score_global"] = {
        "valeur": score_valeur,
        "interpretation": score.get("interpretation", "Non spécifié")
    }

    if not data.get("resume"):
        data["resume"] = "Aucune synthèse disponible"

    return data


def extract_kpis(project_id: str, document_text: str) -> dict:
    prompt_path = os.path.join(BASE_DIR, '..', 'prompts', 'kpi_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error(f"Fichier prompt introuvable : {prompt_path}")
        return {"kpis": [], "resume": "Fichier prompt KPI introuvable"}

    context = search_documents(project_id, "indicateurs performance objectifs mesures résultats")
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
            return {"kpis": [], "resume": "Réponse vide du LLM"}

        data = json.loads(reponse_clean)
        return validate_kpis(data)

    except json.JSONDecodeError as e:
        logger.error(f"Erreur parsing JSON KPI pour projet {project_id}: {e}\nRéponse brute: {reponse}")
        return {"kpis": [], "resume": "Erreur de parsing JSON", "raw": reponse}