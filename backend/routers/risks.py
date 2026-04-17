from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.services.risk_service import extract_risks, extract_risks_multi
from backend.models.document import Document
from backend.models.analysis import Analysis
from backend.models.user import User
from backend.services.auth_service import get_current_user
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/api/risks", tags=["risques"])

@router.post("/extract")
def extract_project_risks(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouve")

    result = extract_risks(project_id, document_id, doc.content_text)

    analysis = Analysis(
        id=str(uuid.uuid4()),
        project_id=project_id,
        document_id=document_id,
        analysis_type="risks",
        result_json=result,
        model_used="llama-3.3-70b-versatile"
    )
    db.add(analysis)
    db.commit()

    return result

@router.get("/{project_id}")
def get_project_risks(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == "risks"
    ).order_by(Analysis.created_at.desc()).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Aucune analyse de risques trouvee")

    return analysis.result_json


class MultiRiskRequest(BaseModel):
    project_id: str
    document_ids: list[str]

@router.post("/extract-multi")
def extract_risks_multi_endpoint(
    request: MultiRiskRequest,
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

    result = extract_risks_multi(request.project_id, document_ids, document_texts)

    analysis = Analysis(
        id=str(uuid.uuid4()),
        project_id=request.project_id,
        analysis_type="risks",
        result_json=result,
        model_used="llama-3.3-70b-versatile"
    )
    db.add(analysis)
    db.commit()

    return result