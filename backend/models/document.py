from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database.db import Base
import uuid
import datetime

# Catégories prédéfinies pour la checklist PMO
DOCUMENT_CATEGORIES = [
    "charte_cadrage",     # Charte / Note de cadrage
    "planning",           # Planning / Rétro-planning / Gantt
    "budget",             # Budget / Tableau financier
    "rapport_avancement", # Rapport d'avancement / Statut
    "compte_rendu",       # Compte-rendu / PV COPIL
    "registre_risques",   # Registre des risques
    "autre",              # Autre / Non classifié
]

class Document(Base):
    __tablename__ = "documents"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id       = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename         = Column(String(255), nullable=False)
    category         = Column(String(50), nullable=True, default="autre")
    content_text     = Column(Text)
    # ── Anonymisation ──────────────────────────────────────────
    is_anonymized    = Column(Boolean, default=False, nullable=False)
    anonymization_map = Column(JSONB, nullable=True)   # {"[EMAIL_1]": "jean@acme.fr", ...}
    uploaded_at      = Column(DateTime, default=datetime.datetime.now)

    analyses = relationship("Analysis", backref="document")