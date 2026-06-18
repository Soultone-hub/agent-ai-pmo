import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.config import settings
from backend.limiter import limiter
from backend.models import user, project, document, analysis, chat_message
from backend.routers import documents, risks, copil, kpi, chat, projects, auth, analyses

logger = logging.getLogger(__name__)

# ── Planificateur de purge RGPD ─────────────────────────────────────────────
# Supprime définitivement les comptes archivés > PURGE_RETENTION_DAYS jours.
# Intégré à l'app (pas de cron externe) ; sûr avec --workers 1 (un seul process).
_PURGE_INTERVAL_SECONDS = 24 * 3600   # une fois par jour
_PURGE_STARTUP_DELAY_SECONDS = 60     # laisser l'app démarrer


def _run_purge_once() -> None:
    """Exécute une passe de purge dans une session DB dédiée (appel bloquant)."""
    from backend.database.db import SessionLocal
    from backend.services.maintenance_service import purge_archived_users
    db = SessionLocal()
    try:
        purge_archived_users(db, retention_days=settings.PURGE_RETENTION_DAYS)
    finally:
        db.close()


async def _purge_loop() -> None:
    await asyncio.sleep(_PURGE_STARTUP_DELAY_SECONDS)
    while True:
        try:
            # Travail SQL bloquant déporté hors de la boucle d'événements
            await asyncio.to_thread(_run_purge_once)
        except Exception as e:
            logger.error("Purge planifiée : erreur — %s", e)
        await asyncio.sleep(_PURGE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if settings.PURGE_SCHEDULER_ENABLED:
        task = asyncio.create_task(_purge_loop())
        logger.info("Planificateur de purge RGPD démarré (rétention %d j).", settings.PURGE_RETENTION_DAYS)
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ── Rate Limiter (protection anti-abus) ─────────────────────────────────────
# Défini dans backend/limiter.py pour éviter les imports circulaires.

app = FastAPI(
    title="Agent IA - Pilotage de Projets Strategiques",
    description="API pour l'assistance intelligente au pilotage de projets",
    version="1.0.0",
    lifespan=lifespan,
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
