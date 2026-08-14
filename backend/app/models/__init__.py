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
from .telephony_event import TelephonyEvent
from .pbx import PbxConnector, PbxConnectorDomain, PbxPauseCode, PBX_TYPES
from .tenant import Tenant
from .tenant_user import TenantUser, MEMBERSHIP_ADMIN, MEMBERSHIP_MEMBER
from .tenant_invitation import TenantInvitation
from .user_token import UserToken, PURPOSE_ONBOARDING, PURPOSE_PASSWORD_RESET
from .email_template import EmailTemplate, KNOWN_TEMPLATE_KEYS
from .prestataire import Prestataire
from .setting import SmtpSetting, ReferenceValue
from .erp import ErpConfig, ErpSyncQueue
from .sla import SlaPolicy
from .prise_de_service import PriseDeService
from .notification import Notification, NotificationPreference, EmailOutbox
from .email import Email
from .email_attachment import EmailAttachment


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
    'TelephonyEvent',
    'PbxConnector', 'PbxConnectorDomain', 'PbxPauseCode', 'PBX_TYPES',

    # Prestataires
    'Prestataire',

    # Onboarding & modèles d'email
    'UserToken', 'PURPOSE_ONBOARDING', 'PURPOSE_PASSWORD_RESET',
    'EmailTemplate', 'KNOWN_TEMPLATE_KEYS',
]