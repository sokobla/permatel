"""
Invitations d'onboarding utilisateur (par tenant).

Un admin de tenant (ou le super-admin) invite une adresse email à rejoindre un
tenant. Le token clair n'est jamais stocké : seul son hash l'est. L'invitation
est à usage unique et expire au bout de 48h (non configurable).
"""
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app import db

# Durée de validité fixe d'une invitation (non configurable — décision produit).
INVITATION_TTL = timedelta(hours=48)

# Statuts
INVITE_PENDING = "pending"
INVITE_ACCEPTED = "accepted"
INVITE_REVOKED = "revoked"
INVITE_EXPIRED = "expired"


class TenantInvitation(db.Model):
    __tablename__ = "tenant_invitations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(120), nullable=False, index=True)
    # Rôle fonctionnel global à attribuer (contraint côté route : jamais ADMIN via délégation)
    role = Column(String(20), nullable=False)
    # Capacité dans le tenant : 'admin' | 'member'
    membership_role = Column(String(50), nullable=False, default="member")
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default=INVITE_PENDING, index=True)
    invited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    accepted_at = Column(DateTime, nullable=True)

    def is_valid(self) -> bool:
        return self.status == INVITE_PENDING and self.expires_at > datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": str(self.tenant_id),
            "email": self.email,
            "role": self.role,
            "membership_role": self.membership_role,
            "status": self.status,
            "invited_by_user_id": self.invited_by_user_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
        }
