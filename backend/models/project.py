from sqlalchemy import Column, String, Enum, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database.db import Base
import uuid
import datetime

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(Enum('active', 'archived', name='project_status'), default='active')
    created_at = Column(DateTime, default=datetime.datetime.now)

    owner = relationship("User", backref="projects")
    documents = relationship("Document", backref="project")
    analyses = relationship("Analysis", backref="project")