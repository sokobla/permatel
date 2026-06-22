from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, NUMERIC
from sqlalchemy.orm import relationship
from app import db

Base = db.Model

class Site(Base):
    __tablename__ = 'sites'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'code_site', name='uq_sites_tenant_code'),
        UniqueConstraint('tenant_id', 'id', name='uq_sites_tenant_id'),
        ForeignKeyConstraint(['tenant_id', 'client_id'], ['clients.tenant_id', 'clients.id'], name='fk_sites_client_tenant'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, nullable=False, index=True)
    nom = Column(String(200), nullable=False)
    code_site = Column(String(50), nullable=False, index=True)
    logo_url = Column(String(255), nullable=True)
    adresse = Column(Text, nullable=True)
    ville = Column(String(100), nullable=True)
    code_postal = Column(String(20), nullable=True)
    telephone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    type_site = Column(String(50), nullable=True)
    contact_principal_id = Column(Integer, ForeignKey('contacts.id'), nullable=True)
    effectif_requis = Column(Integer, nullable=True)
    latitude = Column(NUMERIC(10, 7), nullable=True)
    longitude = Column(NUMERIC(10, 7), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Multi-tenant column
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=True, index=True)
    
    # Relations
    client = relationship("Client", back_populates="sites")
    demandes = relationship("Demande", back_populates="site")
    contacts = relationship("Contact", secondary="contacts_sites", back_populates="sites")
    contact_principal = relationship("Contact")
    
    def __repr__(self):
        return f"<Site {self.code_site} - {self.nom}>"