from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import documents, risks, copil, kpi, chat

app = FastAPI(
    title="Agent IA - Pilotage de Projets Strategiques",
    description="API pour l'assistance intelligente au pilotage de projets",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(risks.router)
app.include_router(copil.router)
app.include_router(kpi.router)
app.include_router(chat.router)

@app.get("/")
def root():
    return {"message": "Agent IA PMO operationnel"}

@app.get("/health")
def health():
    return {"status": "ok"}