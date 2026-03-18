from sqlalchemy import Column, String, Enum, DateTime
from sqlalchemy.dialects.postgresql import UUID
from backend.database.db import Base
import uuid
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum('pmo', 'chef_projet', 'direction', 'consultant', name='user_role'), nullable=False, default='pmo')
    created_at = Column(DateTime, default=datetime.datetime.now)
    