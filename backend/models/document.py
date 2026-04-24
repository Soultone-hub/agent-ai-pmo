from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    doc_type = Column(Enum('rapport', 'cr_reunion', 'planning', 'autre', name='doc_type'), default='autre')
    category = Column(String(50), nullable=True, default="autre")  # Classification IA
    content_text = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.datetime.now)

    analyses = relationship("Analysis", backref="document")