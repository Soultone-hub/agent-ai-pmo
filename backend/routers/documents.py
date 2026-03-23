from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.services.parser_service import parse_document
from backend.services.rag_service import index_document
from backend.services.llm_service import send_to_groq
from backend.models.document import Document
import uuid
import os
import tempfile

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post("/upload")
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    allowed = [".pdf", ".docx", ".xlsx", ".eml"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Format non supporte : {ext}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        text = parse_document(tmp_path)
        document_id = str(uuid.uuid4())
        nb_chunks = index_document(project_id, document_id, text)

        doc = Document(
            id=document_id,
            project_id=project_id,
            filename=file.filename,
            content_text=text
        )
        db.add(doc)
        db.commit()

        return {"document_id": document_id, "filename": file.filename, "nb_chunks": nb_chunks}
    finally:
        os.unlink(tmp_path)

@router.post("/analyze")
async def analyze_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouve")

    prompt_template = open('backend/prompts/analysis_prompt.txt').read()
    prompt = prompt_template.replace('{document_text}', doc.content_text[:3000])
    reponse = send_to_groq(prompt)

    return {"document_id": document_id, "analyse": reponse}

@router.get("/")
def list_documents(project_id: str, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.project_id == project_id).all()
    return {"documents": [{"id": str(d.id), "filename": d.filename, "uploaded_at": str(d.uploaded_at)} for d in docs]}

@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouve")
    db.delete(doc)
    db.commit()
    return {"message": "Document supprime"}