import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database.db import get_db
from backend.models.user import User
from backend.models.chat_message import ChatMessage
from backend.models.document import Document
from backend.services.auth_service import get_current_user
from backend.services.rag_service import search_documents
from backend.services.anonymization_service import deanonymize, merge_maps_from_docs
from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat IA"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    project_id: str
    message: str
    session_id: str | None = None  # Obligatoire pour les nouvelles conversations


# ── Sessions ─────────────────────────────────────────────────────────────────

@router.get("/sessions/{project_id}")
def list_sessions(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Liste toutes les sessions de chat d'un projet, avec aperçu du premier message."""
    # Récupérer tous les session_id distincts pour ce projet
    rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.project_id == project_id,
            ChatMessage.session_id != None,
        )
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    # Regrouper par session_id
    sessions: dict[str, dict] = {}
    for msg in rows:
        sid = msg.session_id
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "first_message": None,
                "last_message_at": str(msg.created_at),
                "message_count": 0,
            }
        if msg.role == "user" and sessions[sid]["first_message"] is None:
            sessions[sid]["first_message"] = msg.content[:80]
        sessions[sid]["last_message_at"] = str(msg.created_at)
        sessions[sid]["message_count"] += 1

    # Trier par last_message_at décroissant
    sorted_sessions = sorted(
        sessions.values(),
        key=lambda s: s["last_message_at"],
        reverse=True,
    )

    return {"total": len(sorted_sessions), "sessions": sorted_sessions}


@router.post("/sessions/{project_id}")
def create_session(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    """Créer un nouvel identifiant de session."""
    new_session_id = str(uuid.uuid4())
    return {"session_id": new_session_id}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprimer tous les messages d'une session."""
    deleted = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .delete()
    )
    db.commit()
    return {"deleted_messages": deleted, "session_id": session_id}


# ── Historique ────────────────────────────────────────────────────────────────

@router.get("/history/{project_id}")
def get_history(
    project_id: str,
    session_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Historique d'une session. Si session_id absent, retourne les messages legacy (NULL)."""
    query = db.query(ChatMessage).filter(ChatMessage.project_id == project_id)
    if session_id:
        query = query.filter(ChatMessage.session_id == session_id)
    else:
        query = query.filter(ChatMessage.session_id == None)

    messages = query.order_by(ChatMessage.created_at.asc()).all()

    if not messages:
        raise HTTPException(status_code=404, detail="Aucun historique trouvé")

    return {
        "project_id": project_id,
        "session_id": session_id,
        "total_messages": len(messages),
        "historique": [
            {
                "role": m.role,
                "content": m.content,
                "created_at": str(m.created_at),
            }
            for m in messages
        ],
    }


# ── Envoi de message ──────────────────────────────────────────────────────────

@router.post("/message")
def send_message(
    request: MessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id requis. Créez d'abord une session via POST /api/chat/sessions/{project_id}")

    # Charger les 10 derniers messages de cette session pour le contexte
    history_rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.project_id == request.project_id,
            ChatMessage.session_id == request.session_id,
        )
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in history_rows[-10:]]

    # Contexte documentaire RAG
    context_chunks = search_documents(request.project_id, request.message)
    context_text = "\n\n".join(context_chunks) if context_chunks else "Aucun contexte disponible"

    system_prompt = f"""Tu es un assistant expert en pilotage de projets stratégiques.
Tu réponds uniquement en français, de manière claire et structurée.
Appuie tes réponses sur le contexte documentaire fourni.
Si l'information n'est pas dans le contexte, dis-le clairement.

CONTEXTE DOCUMENTAIRE DU PROJET :
{context_text}"""

    messages_groq = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages_groq.append(msg)
    messages_groq.append({"role": "user", "content": request.message})

    from groq import Groq
    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages_groq,
        temperature=0.4,
        max_tokens=2048,
    )
    reponse_text = response.choices[0].message.content

    # Dé-anonymisation : si des documents du projet sont anonymisés,
    # remplacer les placeholders dans la réponse avant stockage et affichage
    project_docs = db.query(Document).filter(
        Document.project_id == request.project_id,
        Document.is_anonymized == True,
    ).all()
    anon_map = merge_maps_from_docs(project_docs)
    if anon_map:
        reponse_text = deanonymize(reponse_text, anon_map)

    # Persister les 2 messages avec session_id
    db.add(ChatMessage(
        project_id=request.project_id,
        session_id=request.session_id,
        role="user",
        content=request.message,
    ))
    db.add(ChatMessage(
        project_id=request.project_id,
        session_id=request.session_id,
        role="assistant",
        content=reponse_text,
    ))
    db.commit()

    return {
        "message_id": str(uuid.uuid4()),
        "project_id": request.project_id,
        "session_id": request.session_id,
        "question": request.message,
        "reponse": reponse_text,
        "sources_utilisees": len(context_chunks),
    }


# ── Reset legacy (rétrocompatibilité) ────────────────────────────────────────

@router.delete("/reset/{project_id}")
def reset_conversation(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(ChatMessage).filter(ChatMessage.project_id == project_id).delete()
    db.commit()
    return {"message": f"Toutes les conversations réinitialisées pour le projet {project_id}"}