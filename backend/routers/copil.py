import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.services.copil_service import generate_copil
from backend.models.document import Document
from backend.models.analysis import Analysis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/copil", tags=["COPIL"])


@router.post("/generate")
def generate_copil_report(project_id: str, document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    result = generate_copil(project_id, document_id, doc.content_text)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    analysis = Analysis(
        id=str(uuid.uuid4()),
        project_id=project_id,
        document_id=document_id,
        analysis_type="copil",
        result_json=result,
        model_used="llama-3.3-70b-versatile"
    )
    db.add(analysis)
    db.commit()

    return result


@router.get("/{project_id}")
def get_latest_copil(project_id: str, db: Session = Depends(get_db)):
    analysis = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == "copil"
    ).order_by(Analysis.created_at.desc()).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Aucune synthèse COPIL trouvée pour ce projet")

    return analysis.result_json


@router.get("/{project_id}/historique")
def get_copil_history(project_id: str, db: Session = Depends(get_db)):
    analyses = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == "copil"
    ).order_by(Analysis.created_at.desc()).all()

    return {
        "total": len(analyses),
        "historique": [
            {
                "id": str(a.id),
                "created_at": str(a.created_at),
                "resume_executif": a.result_json.get("resume_executif", "")
            }
            for a in analyses
        ]
    }