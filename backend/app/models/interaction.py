from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model
import enum

class TypeInteraction(enum.Enum):
    APPEL = "appel"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    NOTE = "note"
    CHANGEMENT_STATUT = "changement_statut"

class Interaction(Base):
    __tablename__ = 'interactions'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id', 'demande_id'], ['demandes.tenant_id', 'demandes.id'], name='fk_interactions_demande_tenant'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    demande_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    type_interaction = Column(SQLEnum(TypeInteraction), nullable=False)
    contenu = Column(Text, nullable=True)
    
    # Pour changement de statut
    ancien_statut = Column(String(50), nullable=True)
    nouveau_statut = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Multi-tenant column (NOT NULL)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False, index=True)
    
    # Relations
    demande = relationship("Demande", back_populates="interactions")
    user = relationship("User", back_populates="interactions")
    
    def __repr__(self):
        return f"<Interaction {self.type_interaction.value} - Demande #{self.demande_id}>"