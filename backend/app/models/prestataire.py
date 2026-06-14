from datetime import datetime
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model


class Prestataire(Base):
    __tablename__ = 'prestataires'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'code', name='uq_prestataires_tenant_code'),
        UniqueConstraint('tenant_id', 'id', name='uq_prestataires_tenant_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False, index=True)
    code = Column(String(50), nullable=True)
    nom = Column(String(200), nullable=False)
    adresse = Column(Text, nullable=True)
    ville = Column(String(100), nullable=True)
    telephone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    logo_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    agents_securite = relationship("AgentSecurite", back_populates="prestataire", overlaps="agents_securite,tenant")
    contacts = relationship("Contact", back_populates="partner")

    def __repr__(self):
        return f"<Prestataire {self.code} - {self.nom}>"