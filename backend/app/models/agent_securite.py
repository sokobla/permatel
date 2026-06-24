from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model

class AgentSecurite(Base):
    __tablename__ = 'agents_securite'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'matricule', name='uq_agents_tenant_matricule'),
        ForeignKeyConstraint(['tenant_id', 'prestataire_id'], ['prestataires.tenant_id', 'prestataires.id'], name='fk_agents_prestataire_tenant', ondelete='SET NULL'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    matricule = Column(String(50), nullable=False, index=True)
    nom = Column(String(100), nullable=False)
    adresse = Column(String(200), nullable=True)
    ville = Column(String(100), nullable=True)
    code_postal = Column(String(20), nullable=True)
    type_agent = Column(String(50), nullable=True)  # Ex: Agent de sécurité, Chef d'équipe, etc.
    prenom = Column(String(100), nullable=False)
    telephone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    motorise = Column(Boolean, default=False, nullable=False)
    avatar_url = Column(String(200), nullable=True)
    qualification = Column(String(100), nullable=True)  # CQP, SSIAP, etc.
    taux_horaire = Column(Numeric(10, 2), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Multi-tenant columns
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    prestataire_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Relations
    demandes_planning_concerne = relationship(
        "DemandePlanning", 
        foreign_keys="DemandePlanning.agent_concerne_id",
        back_populates="agent_concerne"
    )
    demandes_planning_remplacant = relationship(
        "DemandePlanning",
        foreign_keys="DemandePlanning.agent_remplacant_id", 
        back_populates="agent_remplacant"
    )
    tenant = relationship('Tenant', back_populates='agents_securite')
    prestataire = relationship('Prestataire', back_populates='agents_securite')
    contact = relationship('Contact', back_populates='agent_securite', uselist=False, cascade='all, delete-orphan')

    
    def __repr__(self):
        return f"<Agent {self.matricule} - {self.prenom} {self.nom}>"