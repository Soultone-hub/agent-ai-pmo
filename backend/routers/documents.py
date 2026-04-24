from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.services.parser_service import parse_document
from backend.services.rag_service import index_document
from backend.models.document import Document
from backend.models.user import User
from backend.services.analysis_service import analyze_document, analyze_documents_multi
from backend.services.auth_service import get_current_user
from pydantic import BaseModel
import uuid
import os
import tempfile

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 Mo
MAX_DOCS_PER_PROJECT = 50

@router.post("/upload")
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = [".pdf", ".docx", ".xlsx", ".eml", ".pptx"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext == ".ppt":
        raise HTTPException(
            status_code=400,
            detail="Le format .ppt (PowerPoint ancien) n'est pas supporté. Ouvrez le fichier dans PowerPoint et enregistrez-le en .pptx."
        )
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Format non supporté : {ext}")

    # Lire le contenu en mémoire pour vérifier la taille
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        size_mb = len(content) / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Fichier trop volumineux ({size_mb:.1f} Mo). Maximum autorisé : 10 Mo."
        )

    # Vérifier la limite de documents par projet
    doc_count = db.query(Document).filter(Document.project_id == project_id).count()
    if doc_count >= MAX_DOCS_PER_PROJECT:
        raise HTTPException(
            status_code=400,
            detail=f"Limite atteinte : ce projet contient déjà {doc_count} documents (maximum : {MAX_DOCS_PER_PROJECT})."
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
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
async def analyze_document_endpoint(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    result = analyze_document(str(doc.project_id), str(doc.id), doc.content_text)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return {"document_id": document_id, "analyse": result}

@router.get("/")
def list_documents(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = db.query(Document).filter(Document.project_id == project_id).all()
    return {"documents": [{"id": str(d.id), "filename": d.filename, "uploaded_at": str(d.uploaded_at)} for d in docs]}

@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouve")
    db.delete(doc)
    db.commit()
    return {"message": "Document supprime"}


class MultiAnalyzeRequest(BaseModel):
    project_id: str
    document_ids: list[str]

@router.post("/analyze-multi")
def analyze_multi_endpoint(
    request: MultiAnalyzeRequest,
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

    result = analyze_documents_multi(request.project_id, document_ids, document_texts)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return {"analyse": result}