from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum, Boolean, UniqueConstraint, ForeignKeyConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB

# JSONB en PostgreSQL, repli JSON sous SQLite (tests). Comportement runtime
# inchangé en prod (PostgreSQL).
JSONB_VARIANT = JSONB().with_variant(JSON(), "sqlite")
from sqlalchemy.orm import relationship
from app import db
import enum


# ============================================================================
# ENUMS MÉTIER
# ============================================================================

class TypeDemande(enum.Enum):
    ANOMALIE = "anomalie"
    COMMANDE = "commande"
    PLANNING = "planning"
    ADMIN = "admin"


class StatutDemande(enum.Enum):
    NOUVELLE = "nouvelle"
    EN_COURS = "en_cours"
    EN_ATTENTE = "en_attente"
    RESOLUE = "resolue"
    CLOTUREE = "cloturee"
    ANNULEE = "annulee"


class PrioriteDemande(enum.Enum):
    BASSE = "basse"
    NORMALE = "normale"
    HAUTE = "haute"
    URGENTE = "urgente"


class NatureAnomalie(enum.Enum):
    ANJ                        = "anj"
    ABSENCE_JUSTIFIEE          = "absence_justifiee"
    RETARD_PRISE_SERVICE       = "retard_prise_service"
    AGENT_NON_SUR_SITE         = "agent_non_sur_site"
    DOUBLON_PLANNING           = "doublon_planning"
    REMPLACEMENT_PERMUTATION   = "remplacement_permutation"
    MODIFICATION_VACATION      = "modification_vacation"
    PROBLEME_TECHNIQUE         = "probleme_technique"
    SITE_PRESTATAIRE_INJOIGNABLE = "site_prestataire_injoignable"
    BLOCAGE_OUTIL_RH           = "blocage_outil_rh"
    DEMANDE_DE_RENFORT         = "demande_de_renfort"
    ANOMALIE_FACTURATION       = "anomalie_facturation"
    AUTRE                      = "autre"


class TypeCommande(enum.Enum):
    GARDIENNAGE = "gardiennage"
    SURVEILLANCE_MOBILE = "surveillance_mobile"
    RONDES = "rondes"
    INTERVENTION = "intervention"
    FILTRAGE = "filtrage"
    PROTECTION_RAPPROCHEE = "protection_rapprochee"
    ACCUEIL_SECURITE = "accueil_securite"
    AUTRE = "autre"


class TypeModificationPlanning(enum.Enum):
    ABSENCE = "absence"
    CONGE = "conge"
    FORMATION = "formation"
    REUNION = "reunion"
    REMPLACEMENT = "remplacement"
    AUTRE = "autre"


class CategorieAdmin(enum.Enum):
    RESSOURCES_HUMAINES = "ressources_humaines"
    COMPTABILITE = "comptabilite"
    CONTRAT = "contrat"
    POLITIQUE = "politique"
    AUTRE = "autre"


class TypeDocumentAdmin(enum.Enum):
    CONTRAT = "contrat"
    FACTURE = "facture"
    RAPPORT = "rapport"
    DEMANDE_OFFICIELLE = "demande_officielle"
    APPROBATION = "approbation"
    AUTRE = "autre"
    
    

# ============================================================================
# TYPES ENUM SQLALCHEMY NOMMÉS (strict nécessaire pour PostgreSQL/Alembic)
# ============================================================================

type_demande_enum = SQLEnum(TypeDemande, name="type_demande_enum", native_enum=False)
statut_demande_enum = SQLEnum(StatutDemande, name="statut_demande_enum", native_enum=False)
priorite_demande_enum = SQLEnum(PrioriteDemande, name="priorite_demande_enum", native_enum=False)

nature_anomalie_enum = SQLEnum(NatureAnomalie, name="nature_anomalie_enum", native_enum=False)

type_commande_enum = SQLEnum(TypeCommande, name="type_commande_enum", native_enum=False)

type_modification_planning_enum = SQLEnum(
    TypeModificationPlanning,
    name="type_modification_planning_enum", native_enum=False
)

categorie_admin_enum = SQLEnum(CategorieAdmin, name="categorie_admin_enum", native_enum=False)
type_document_admin_enum = SQLEnum(TypeDocumentAdmin, name="type_document_admin_enum", native_enum=False)


# ==========================================================================q==
# MODÈLE PARENT - JOINED TABLE INHERITANCE
# ============================================================================

class Demande(db.Model):
    """
    Classe parent pour toutes les demandes.
    Utilise Joined Table Inheritance (JTI) pour les sous-classes.
    """
    __tablename__ = 'demandes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Polymorphisme: discriminator
    type_discriminator = Column(String(50), nullable=False, index=True)
    __mapper_args__ = {
        'polymorphic_identity': 'demande',
        'polymorphic_on': type_discriminator
    }
    
    # Identifiants et type métier
    numero_ticket = Column(String(50), nullable=False, index=True)
    type_demande = Column(type_demande_enum, nullable=False, index=True)
    
    # Relations métier
    client_id = Column(Integer, nullable=False, index=True)
    site_id = Column(Integer, nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey('contacts.id'), nullable=True, index=True)
    
    # Affectation
    permanencier_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    closed_by_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    updated_by_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    
    # Contenu
    titre = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    adresse_intervention = Column(String(300), nullable=True)
    
    # Workflow
    statut = Column(statut_demande_enum, default=StatutDemande.NOUVELLE, nullable=False, index=True)
    priorite = Column(priorite_demande_enum, default=PrioriteDemande.NORMALE, nullable=False)
    
    # SLA et résolution
    sla_deadline = Column(DateTime, nullable=True)          # échéance de RÉSOLUTION
    sla_response_deadline = Column(DateTime, nullable=True)  # échéance de PRISE EN CHARGE
    prise_en_charge_at = Column(DateTime, nullable=True)     # 1ère sortie du statut "nouvelle"
    sla_warning_notified = Column(Boolean, default=False, nullable=False)  # anti-doublon alerte SLA
    sla_breach_notified = Column(Boolean, default=False, nullable=False)
    date_resolution = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Multi-tenant (NOT NULL)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False, index=True)
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'id', name='uq_demandes_tenant_id'),
        UniqueConstraint('tenant_id', 'numero_ticket', name='uq_demandes_tenant_numero'),
        ForeignKeyConstraint(['tenant_id', 'client_id'], ['clients.tenant_id', 'clients.id'], 
                           name='fk_demandes_client_tenant'),
        ForeignKeyConstraint(['tenant_id', 'site_id'], ['sites.tenant_id', 'sites.id'], 
                           name='fk_demandes_site_tenant'),
    )
    
    # Relations ORM
    client = relationship("Client", back_populates="demandes")
    site = relationship("Site", back_populates="demandes")
    contact = relationship("Contact", back_populates="demandes")
    permanencier = relationship("User", foreign_keys=[permanencier_id], back_populates="demandes_assignees")
    closed_by = relationship("User", foreign_keys=[closed_by_id], back_populates="demandes_closed")
    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])
    interactions = relationship("Interaction", back_populates="demande", cascade="all, delete-orphan")
    fichiers = relationship("Fichier", back_populates="demande", cascade="all, delete-orphan")
    telephony_events = relationship("TelephonyEvent", back_populates="demande")


# ============================================================================
# SOUS-CLASSES - JOINED TABLE INHERITANCE
# ============================================================================

class DemandeAnomalie(Demande):
    """Demande spécialisée pour signalement d'anomalies/incidents."""
    __tablename__ = 'demandes_anomalies'
    
    id = Column(Integer, ForeignKey('demandes.id'), primary_key=True)
    
    __mapper_args__ = {
        'polymorphic_identity': 'anomalie',
    }
    
    nature_anomalie = Column(nature_anomalie_enum, nullable=True)
    equipement_concerne = Column(String(200), nullable=True)
    localisation_precise = Column(Text, nullable=True)
    impact_securite = Column(Boolean, default=False, nullable=False)
    action_corrective = Column(Text, nullable=True)
    agent_concerne_id = Column(Integer, ForeignKey('agents_securite.id'), nullable=True, index=True)

    agent_concerne = relationship("AgentSecurite", foreign_keys=[agent_concerne_id])


class DemandeCommande(Demande):
    """Demande spécialisée pour commandes de biens/services."""
    __tablename__ = 'demandes_commandes'
    
    id = Column(Integer, ForeignKey('demandes.id'), primary_key=True)
    
    __mapper_args__ = {
        'polymorphic_identity': 'commande',
    }
    
    type_commande = Column(type_commande_enum, nullable=True)
    quantite = Column(Integer, nullable=True)
    budget_estime = Column(String(50), nullable=True)
    fournisseur_suggere = Column(String(200), nullable=True)
    date_livraison_souhaitee = Column(DateTime, nullable=True)
    bon_commande = Column(String(100), nullable=True)
    # Données opérationnelles structurées (listes)
    moyens_acces = Column(JSONB_VARIANT, nullable=True)
    equipements_site = Column(JSONB_VARIANT, nullable=True)
    risques_specifiques = Column(JSONB_VARIANT, nullable=True)
    besoins_agents = Column(JSONB_VARIANT, nullable=True)


class DemandePlanning(Demande):
    """Demande spécialisée pour modifications de planning/absences."""
    __tablename__ = 'demandes_plannings'
    
    id = Column(Integer, ForeignKey('demandes.id'), primary_key=True)
    
    __mapper_args__ = {
        'polymorphic_identity': 'planning',
    }
    
    type_modification = Column(type_modification_planning_enum, nullable=True)
    agent_concerne_id = Column(Integer, ForeignKey('agents_securite.id'), nullable=True, index=True)
    date_debut = Column(DateTime, nullable=True)
    date_fin = Column(DateTime, nullable=True)
    motif = Column(Text, nullable=True)
    agent_remplacant_id = Column(Integer, ForeignKey('agents_securite.id'), nullable=True, index=True)
    
    # Relations pour les agents
    agent_concerne = relationship("AgentSecurite", foreign_keys=[agent_concerne_id], back_populates="demandes_planning_concerne")
    agent_remplacant = relationship("AgentSecurite", foreign_keys=[agent_remplacant_id], back_populates="demandes_planning_remplacant")


class DemandeAdmin(Demande):
    """Demande spécialisée pour tâches administratives."""
    __tablename__ = 'demandes_admin'
    
    id = Column(Integer, ForeignKey('demandes.id'), primary_key=True)
    
    __mapper_args__ = {
        'polymorphic_identity': 'admin',
    }
    
    categorie = Column(categorie_admin_enum, nullable=True)
    document_type = Column(type_document_admin_enum, nullable=True)
    date_echeance = Column(DateTime, nullable=True)
    validation_requise = Column(Boolean, default=False, nullable=False)
