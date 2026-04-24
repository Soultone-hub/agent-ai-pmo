from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.models.analysis import Analysis
from backend.models.user import User
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


@router.get("/project/{project_id}")
def list_project_analyses(
    project_id: str,
    type: str = Query(default="document", description="Type d'analyse : document, risks, kpi, copil"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Liste toutes les analyses d'un projet, filtrées par type, avec résumé."""
    analyses = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == type,
    ).order_by(Analysis.created_at.desc()).all()

    def _summarize(a):
        r = a.result_json or {}
        entry = {
            "id": str(a.id),
            "created_at": str(a.created_at),
        }
        if type == "document":
            entry["nb_objectifs"]      = len(r.get("objectifs", []))
            entry["nb_contraintes"]    = len(r.get("contraintes", []))
            entry["nb_points_cles"]    = len(r.get("points_cles", []))
            entry["resume"]            = (r.get("resume") or "")[:120]
        elif type == "risks":
            risks = r.get("risks", [])
            entry["nb_risques"]        = len(risks)
            entry["nb_critiques"]      = sum(1 for x in risks if x.get("niveau") == "critique")
            entry["resume"]            = (r.get("resume") or "")[:120]
        elif type == "kpi":
            entry["nb_kpis"]           = len(r.get("kpis", []))
            entry["score_global"]      = r.get("score_global", {}).get("valeur", 0)
        elif type == "copil":
            entry["resume_executif"]   = (r.get("resume_executif") or "")[:120]
        return entry

    return {
        "total": len(analyses),
        "historique": [_summarize(a) for a in analyses],
    }


@router.get("/project/{project_id}/latest")
def get_latest_analysis(
    project_id: str,
    type: str = Query(default="document"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne la dernière analyse d'un projet pour un type donné."""
    analysis = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == type,
    ).order_by(Analysis.created_at.desc()).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Aucune analyse trouvée")

    return {
        "id": str(analysis.id),
        "type": analysis.analysis_type,
        "created_at": str(analysis.created_at),
        "result": analysis.result_json,
    }


@router.get("/{analysis_id}")
def get_analysis_by_id(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Charge le résultat complet d'une analyse spécifique par son ID."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analyse non trouvée")

    return {
        "id": str(analysis.id),
        "type": analysis.analysis_type,
        "created_at": str(analysis.created_at),
        "result": analysis.result_json,
    }
