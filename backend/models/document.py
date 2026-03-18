from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.database.db import Base
import uuid
import datetime

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    doc_type = Column(Enum('rapport', 'cr_reunion', 'planning', 'autre', name='doc_type'), default='autre')
    content_text = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.datetime.now)

    analyses = relationship("Analysis", backref="document")