import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.services.kpi_service import extract_kpis
from backend.models.document import Document
from backend.models.analysis import Analysis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/kpi", tags=["KPI"])


@router.post("/extract")
def extract_project_kpis(project_id: str, document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    result = extract_kpis(project_id, document_id, doc.content_text)

    if not result.get("kpis"):
        raise HTTPException(status_code=422, detail="Aucun KPI identifiable dans ce document")

    analysis = Analysis(
        id=str(uuid.uuid4()),
        project_id=project_id,
        document_id=document_id,
        analysis_type="kpi",
        result_json=result,
        model_used="llama-3.3-70b-versatile"
    )
    db.add(analysis)
    db.commit()

    return result


@router.get("/{project_id}")
def get_latest_kpis(project_id: str, db: Session = Depends(get_db)):
    analysis = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == "kpi"
    ).order_by(Analysis.created_at.desc()).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Aucune analyse KPI trouvée pour ce projet")

    return analysis.result_json


@router.get("/{project_id}/score")
def get_project_score(project_id: str, db: Session = Depends(get_db)):
    analysis = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == "kpi"
    ).order_by(Analysis.created_at.desc()).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Aucune analyse KPI trouvée pour ce projet")

    score = analysis.result_json.get("score_global", {})
    return {
        "project_id": project_id,
        "score": score.get("valeur", 0),
        "interpretation": score.get("interpretation", "Non spécifié"),
        "generated_at": str(analysis.created_at)
    }


@router.get("/{project_id}/historique")
def get_kpi_history(project_id: str, db: Session = Depends(get_db)):
    analyses = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == "kpi"
    ).order_by(Analysis.created_at.desc()).all()

    return {
        "total": len(analyses),
        "historique": [
            {
                "id": str(a.id),
                "created_at": str(a.created_at),
                "score_global": a.result_json.get("score_global", {}).get("valeur", 0),
                "nb_kpis": len(a.result_json.get("kpis", []))
            }
            for a in analyses
        ]
    }