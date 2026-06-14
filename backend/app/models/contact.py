from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model

# Tables d'association N:N
contacts_clients = Table(
    'contacts_clients',
    Base.metadata,
    Column('contact_id', Integer, ForeignKey('contacts.id'), primary_key=True),
    Column('client_id', Integer, ForeignKey('clients.id'), primary_key=True),
    Column('est_principal', Boolean, default=False)
)

contacts_sites = Table(
    'contacts_sites',
    Base.metadata,
    Column('contact_id', Integer, ForeignKey('contacts.id'), primary_key=True),
    Column('site_id', Integer, ForeignKey('sites.id'), primary_key=True),
    Column('est_principal', Boolean, default=False)
)

class Contact(Base):
    __tablename__ = 'contacts'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'id', name='uq_contacts_tenant_id'),
        CheckConstraint(
            "(tenant_id IS NOT NULL OR partner_id IS NOT NULL) "
            "AND NOT (tenant_id IS NOT NULL AND partner_id IS NOT NULL)",
            name='ck_contacts_tenant_or_partner_xor'
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    avatar_url = Column(String(255), nullable=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    adresse = Column(String(200), nullable=False)
    ville = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    fonction = Column(String(100), nullable=True)
    telephone = Column(String(20), nullable=False)
    email = Column(String(100), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    partner_id = Column(UUID(as_uuid=True), ForeignKey('prestataires.id', ondelete='CASCADE'), nullable=True, index=True)
    agent_securite_id = Column(Integer, ForeignKey('agents_securite.id', ondelete='CASCADE'), nullable=True, unique=True)

    # Relations N:N
    clients = relationship("Client", secondary=contacts_clients, back_populates="contacts")
    sites = relationship("Site", secondary=contacts_sites, back_populates="contacts")
    demandes = relationship("Demande", back_populates="contact")

    tenant = relationship("Tenant", back_populates="contacts")
    partner = relationship("Prestataire", back_populates="contacts")
    agent_securite = relationship("AgentSecurite", back_populates="contact", uselist=False)
    
    def __repr__(self):
        return f"<Contact {self.prenom} {self.nom}>"