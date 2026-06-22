from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model

class Client(Base):
    __tablename__ = 'clients'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'code_client', name='uq_clients_tenant_code'),
        UniqueConstraint('tenant_id', 'id', name='uq_clients_tenant_id'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String(200), nullable=False)
    logo_url = Column(String(255), nullable=True)
    code_client = Column(String(50), nullable=False, index=True)
    adresse = Column(Text, nullable=True)
    ville = Column(String(100), nullable=True)
    code_postal = Column(String(20), nullable=True)
    telephone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    siret = Column(String(14), nullable=True)
    contact_principal = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Multi-tenant column
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=True, index=True)
    
    # Relations
    sites = relationship("Site", back_populates="client", cascade="all, delete-orphan")
    demandes = relationship("Demande", back_populates="client")
    contacts = relationship("Contact", secondary="contacts_clients", back_populates="clients")
    
    def __repr__(self):
        return f"<Client {self.code_client} - {self.nom}>"