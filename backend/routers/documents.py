from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.services.parser_service import parse_document
from backend.services.rag_service import index_document
from backend.models.document import Document
from backend.models.user import User
from backend.services.analysis_service import analyze_document, analyze_documents_multi
from backend.services.classification_service import classify_document, get_project_checklist
from backend.services.auth_service import get_current_user
from backend.services.anonymization_service import anonymize, get_anonymization_summary
from pydantic import BaseModel
import uuid
import os
import tempfile

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024   # 20 Mo
MAX_DOCS_PER_PROJECT = 50

@router.post("/upload")
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    anonymize_doc: bool = Query(default=False, alias="anonymize", description="Anonymiser les données personnelles (RGPD) avant indexation"),
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

    # Vérifier la taille
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        size_mb = len(content) / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Fichier trop volumineux ({size_mb:.1f} Mo). Maximum autorisé : 20 Mo."
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
        # 1. Parser le document
        text = parse_document(tmp_path)
        document_id = str(uuid.uuid4())

        # 2. Anonymisation PII avant tout envoi au LLM ou indexation
        anon_map: dict = {}
        text_for_index = text
        if anonymize_doc:
            text_for_index, anon_map = anonymize(text)

        # 3. Indexer dans ChromaDB (RAG) — le texte indexé est anonymisé si demandé
        nb_chunks = index_document(project_id, document_id, text_for_index)

        # 4. Classifier automatiquement la catégorie PMO
        category = classify_document(file.filename, text_for_index)

        # 5. Persister en base — content_text stocke le texte anonymisé
        doc = Document(
            id=document_id,
            project_id=project_id,
            filename=file.filename,
            content_text=text_for_index,       # anonymisé si demandé
            category=category,
            is_anonymized=anonymize_doc,
            anonymization_map=anon_map if anonymize_doc else None,
        )
        db.add(doc)
        db.commit()

        response = {
            "document_id": document_id,
            "filename": file.filename,
            "nb_chunks": nb_chunks,
            "category": category,
            "is_anonymized": anonymize_doc,
        }
        if anonymize_doc and anon_map:
            response["anonymization_summary"] = get_anonymization_summary(anon_map)

        return response
    finally:
        os.unlink(tmp_path)


@router.get("/checklist/{project_id}")
def get_checklist(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne la checklist de complétude documentaire du projet."""
    docs = db.query(Document).filter(Document.project_id == project_id).all()
    return get_project_checklist(docs)


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
    return {
        "documents": [
            {
                "id": str(d.id),
                "filename": d.filename,
                "category": d.category,
                "is_anonymized": d.is_anonymized,
                "uploaded_at": str(d.uploaded_at),
            }
            for d in docs
        ]
    }


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    db.delete(doc)
    db.commit()
    return {"message": "Document supprimé"}


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