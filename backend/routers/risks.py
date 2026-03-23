from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.services.risk_service import extract_risks
from backend.services.parser_service import parse_document
from backend.models.document import Document
from backend.models.analysis import Analysis
import uuid
import json

router = APIRouter(prefix="/api/risks", tags=["risques"])

@router.post("/extract")
def extract_project_risks(project_id: str, document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouve")

    result = extract_risks(project_id, doc.content_text)

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
def get_project_risks(project_id: str, db: Session = Depends(get_db)):
    analysis = db.query(Analysis).filter(
        Analysis.project_id == project_id,
        Analysis.analysis_type == "risks"
    ).order_by(Analysis.created_at.desc()).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Aucune analyse de risques trouvee")

    return analysis.result_json