from .user import User, UserRole
from .client import Client
from .site import Site
from .contact import Contact, contacts_clients, contacts_sites
from .agent_securite import AgentSecurite
from .demande import (
    Demande, 
    DemandeAnomalie, 
    DemandeCommande, 
    DemandePlanning, 
    DemandeAdmin,
    TypeDemande,
    StatutDemande,
    PrioriteDemande,
    NatureAnomalie,
    EquipementConcerne,
    TypeCommande,
    TypeModificationPlanning,
    CategorieAdmin,
    TypeDocumentAdmin
)
# Pour rétrocompat avec anciens imports si nécessaire
from .demande import TypeDemande as DemandeType, StatutDemande as DemandeStatut, PrioriteDemande as DemandePriorite
from .interaction import Interaction, TypeInteraction
from .fichier import Fichier
from .audit_log import AuditLog, AuditAction
from .token_blocklist import TokenBlocklist
from .user_session import UserSession, SessionStatus
from .telephony_event import TelephonyEvent, EventType
from .tenant import Tenant
from .tenant_user import TenantUser
from .prestataire import Prestataire


__all__ = [
    # Tenants
    'Tenant', 'TenantUser',
    
    # Users
    'User', 'UserRole',
    
    # Clients & Sites
    'Client', 'Site', 'Contact',
    'contacts_clients', 'contacts_sites',
    
    # Agents
    'AgentSecurite',
    
    # Demandes
    'Demande', 'DemandeAnomalie', 'DemandeCommande', 
    'DemandePlanning', 'DemandeAdmin',
    'TypeDemande', 'StatutDemande', 'PrioriteDemande',
    'NatureAnomalie', 'EquipementConcerne', 'TypeCommande',
    'TypeModificationPlanning', 'CategorieAdmin', 'TypeDocumentAdmin',
    
    # Interactions & Fichiers
    'Interaction', 'TypeInteraction',
    'Fichier',
    
    # Audit & Téléphonie
    'AuditLog', 'AuditAction',
    'TokenBlocklist',
    'UserSession', 'SessionStatus',
    'TelephonyEvent', 'EventType',
    
    # Prestataires
    'Prestataire'
]