import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.services.copil_service import generate_copil, generate_copil_multi
from backend.models.document import Document
from backend.models.analysis import Analysis
from backend.models.user import User
from backend.services.auth_service import get_current_user
from backend.services.anonymization_service import deanonymize_result, merge_maps_from_docs
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/copil", tags=["COPIL"])


@router.post("/generate")
def generate_copil_report(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    result = generate_copil(project_id, document_id, doc.content_text)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    # Dé-anonymisation du rapport COPIL (noms des participants, entreprises, etc.)
    anon_map = merge_maps_from_docs([doc])
    if anon_map:
        result = deanonymize_result(result, anon_map)

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
def get_latest_copil(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == "copil"
    ).order_by(Analysis.created_at.desc()).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Aucune synthèse COPIL trouvée pour ce projet")

    return analysis.result_json


@router.get("/{project_id}/historique")
def get_copil_history(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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


class MultiCopilRequest(BaseModel):
    project_id: str
    document_ids: list[str]


@router.post("/generate-multi")
def generate_copil_multi_endpoint(
    request: MultiCopilRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = db.query(Document).filter(
        Document.id.in_(request.document_ids)
    ).all()

    if not docs:
        raise HTTPException(status_code=404, detail="Aucun document trouvé")

    document_ids = [str(d.id) for d in docs]
    document_texts = [d.content_text for d in docs]

    result = generate_copil_multi(request.project_id, document_ids, document_texts)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    anon_map = merge_maps_from_docs(docs)
    if anon_map:
        result = deanonymize_result(result, anon_map)

    analysis = Analysis(
        id=str(uuid.uuid4()),
        project_id=request.project_id,
        analysis_type="copil",
        result_json=result,
        model_used="llama-3.3-70b-versatile"
    )
    db.add(analysis)
    db.commit()

    return result