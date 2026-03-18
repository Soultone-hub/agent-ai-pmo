from sqlalchemy import Column, String, Enum, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database.db import Base
import uuid
import datetime

class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    analysis_type = Column(Enum('document', 'risks', 'copil', 'kpi', name='analysis_type'), nullable=False)
    result_json = Column(JSONB)
    model_used = Column(String(100))
    created_at = Column(DateTime, default=datetime.datetime.now)