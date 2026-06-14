from datetime import datetime
import uuid
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model


class Tenant(Base):
    __tablename__ = 'tenants'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False, index=True)
    nom = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


    users = relationship("User", secondary="tenant_users", back_populates="tenants")
    audit_logs = relationship("AuditLog", back_populates="tenant")
    agents_securite = relationship("AgentSecurite", back_populates="tenant")
    contacts = relationship("Contact", back_populates="tenant")
    telephony_events = relationship("TelephonyEvent", back_populates="tenant")

    def __repr__(self):
        return f"<Tenant {self.code} - {self.nom}>"