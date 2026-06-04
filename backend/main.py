from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.limiter import limiter
from backend.models import user, project, document, analysis, chat_message
from backend.routers import documents, risks, copil, kpi, chat, projects, auth, analyses

# ── Rate Limiter (protection anti-abus) ─────────────────────────────────────
# Défini dans backend/limiter.py pour éviter les imports circulaires.

app = FastAPI(
    title="Agent IA - Pilotage de Projets Strategiques",
    description="API pour l'assistance intelligente au pilotage de projets",
    version="1.0.0"
)

# Monter le limiter sur l'état de l'app + gestionnaire d'erreur 429
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler  # type: ignore[arg-type]
)

from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend React (Vite)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # permet au frontend de lire le nom de fichier d'export
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
