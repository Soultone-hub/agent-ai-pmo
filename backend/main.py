from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.models import user, project, document, analysis, chat_message
from backend.routers import documents, risks, copil, kpi, chat, projects, auth, analyses

app = FastAPI(
    title="Agent IA - Pilotage de Projets Strategiques",
    description="API pour l'assistance intelligente au pilotage de projets",
    version="1.0.0"
)

from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend React (Vite)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optimisation : Compression GZip pour réduire le poids des transferts (très utile pour l'envoi des documents RAG)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(risks.router)
app.include_router(copil.router)
app.include_router(kpi.router)
app.include_router(chat.router)
app.include_router(projects.router)
app.include_router(analyses.router)

@app.get("/")
def root():
    return {"message": "Agent IA PMO operationnel"}

@app.get("/health")
def health():
    return {"status": "ok"}
