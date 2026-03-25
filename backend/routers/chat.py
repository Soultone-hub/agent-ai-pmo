import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database.db import get_db
from backend.services.llm_service import send_to_groq
from backend.services.rag_service import search_documents

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat IA"])

conversations: dict = {}


class MessageRequest(BaseModel):
    project_id: str
    message: str


def get_conversation(project_id: str) -> list:
    if project_id not in conversations:
        conversations[project_id] = []
    return conversations[project_id]


@router.post("/message")
def send_message(request: MessageRequest):
    history = get_conversation(request.project_id)

    context_chunks = search_documents(request.project_id, request.message)
    context_text = "\n\n".join(context_chunks) if context_chunks else "Aucun contexte disponible"

    system_prompt = f"""Tu es un assistant expert en pilotage de projets stratégiques.
Tu réponds uniquement en français, de manière claire et structurée.
Appuie tes réponses sur le contexte documentaire fourni.
Si l'information n'est pas dans le contexte, dis-le clairement.

CONTEXTE DOCUMENTAIRE DU PROJET :
{context_text}"""

    messages_groq = [{"role": "system", "content": system_prompt}]
    for msg in history[-10:]:
        messages_groq.append(msg)
    messages_groq.append({"role": "user", "content": request.message})

    from groq import Groq
    from backend.config import settings
    client = Groq(api_key=settings.GROQ_API_KEY)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages_groq,
        temperature=0.4,
        max_tokens=2048
    )

    reponse_text = response.choices[0].message.content

    history.append({"role": "user", "content": request.message})
    history.append({"role": "assistant", "content": reponse_text})

    return {
        "message_id": str(uuid.uuid4()),
        "project_id": request.project_id,
        "question": request.message,
        "reponse": reponse_text,
        "sources_utilisees": len(context_chunks)
    }


@router.get("/history/{project_id}")
def get_history(project_id: str):
    history = get_conversation(project_id)
    if not history:
        raise HTTPException(status_code=404, detail="Aucun historique trouvé pour ce projet")
    return {
        "project_id": project_id,
        "total_messages": len(history),
        "historique": history
    }


@router.delete("/reset/{project_id}")
def reset_conversation(project_id: str):
    if project_id in conversations:
        conversations[project_id] = []
    return {"message": f"Conversation réinitialisée pour le projet {project_id}"}