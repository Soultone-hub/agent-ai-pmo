import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database.db import get_db
from backend.models.user import User
from backend.models.chat_message import ChatMessage
from backend.services.auth_service import get_current_user
from backend.services.rag_service import search_documents
from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat IA"])


class MessageRequest(BaseModel):
    project_id: str
    message: str


@router.post("/message")
def send_message(
    request: MessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Charger les 10 derniers messages depuis la DB
    history_rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.project_id == request.project_id)
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
        max_tokens=2048
    )

    reponse_text = response.choices[0].message.content

    # Sauvegarder les 2 messages en DB
    db.add(ChatMessage(project_id=request.project_id, role="user", content=request.message))
    db.add(ChatMessage(project_id=request.project_id, role="assistant", content=reponse_text))
    db.commit()

    return {
        "message_id": str(uuid.uuid4()),
        "project_id": request.project_id,
        "question": request.message,
        "reponse": reponse_text,
        "sources_utilisees": len(context_chunks)
    }


@router.get("/history/{project_id}")
def get_history(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    if not messages:
        raise HTTPException(status_code=404, detail="Aucun historique trouvé pour ce projet")
    return {
        "project_id": project_id,
        "total_messages": len(messages),
        "historique": [{"role": m.role, "content": m.content, "created_at": str(m.created_at)} for m in messages]
    }


@router.delete("/reset/{project_id}")
def reset_conversation(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(ChatMessage).filter(ChatMessage.project_id == project_id).delete()
    db.commit()
    return {"message": f"Conversation réinitialisée pour le projet {project_id}"}