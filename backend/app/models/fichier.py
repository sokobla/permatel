from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model

class Fichier(Base):
    __tablename__ = 'fichiers'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id', 'demande_id'], ['demandes.tenant_id', 'demandes.id'], name='fk_fichiers_demande_tenant'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    demande_id = Column(Integer, nullable=False, index=True)
    uploaded_by_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    nom_fichier = Column(String(255), nullable=False)
    chemin_fichier = Column(String(500), nullable=False)
    taille = Column(Integer, nullable=True)  # en octets
    type_mime = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Multi-tenant column (NOT NULL)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False, index=True)
    
    # Relations
    demande = relationship("Demande", back_populates="fichiers")
    uploaded_by = relationship("User", back_populates="fichiers")
    
    def __repr__(self):
        return f"<Fichier {self.nom_fichier}>"