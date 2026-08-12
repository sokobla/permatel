"""
Jetons à usage unique rattachés à un utilisateur (onboarding, réinitialisation
de mot de passe). Le jeton clair n'est jamais stocké : seul son hash l'est
(même principe que TenantInvitation.token_hash).

Une seule table pour les deux usages plutôt que deux tables quasi identiques :
la mécanique (générer/hasher/valider/expirer) est strictement la même, seules
la durée de vie et l'effet de bord à l'expiration diffèrent (désactivation du
compte pour l'onboarding uniquement — gérée par le sweep, pas par ce modèle).
"""
from datetime import datetime, timedelta
from app.utils.time import utcnow

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app import db

PURPOSE_ONBOARDING = "onboarding"
PURPOSE_PASSWORD_RESET = "password_reset"

# Durées de vie fixes (décision produit) — l'onboarding a une contrainte
# explicite de 24h ; la réinitialisation suit la convention usuelle du secteur
# (fenêtre courte, le lien est envoyé à une adresse qu'on vérifie tout de
# suite, pas 24h plus tard).
ONBOARDING_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(hours=1)

TTL_BY_PURPOSE = {
    PURPOSE_ONBOARDING: ONBOARDING_TTL,
    PURPOSE_PASSWORD_RESET: PASSWORD_RESET_TTL,
}

# Statuts
STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_REVOKED = "revoked"
STATUS_EXPIRED = "expired"


class UserToken(db.Model):
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(20), nullable=False, index=True)  # PURPOSE_ONBOARDING | PURPOSE_PASSWORD_RESET
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default=STATUS_PENDING, index=True)

    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    # Admin déclencheur pour un onboarding ; toujours NULL pour un reset
    # self-service (personne n'agit "au nom de" l'utilisateur dans ce cas).
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Onboarding uniquement (toujours True pour un reset, ignoré par le sweep
    # qui ne traite que purpose=onboarding). True pour l'invitation initiale
    # (l'utilisateur n'a encore aucun mot de passe utilisable — contrainte
    # produit explicite : 24h puis désactivation, cf. onboarding_sweep.py).
    # False quand un admin renvoie un lien d'onboarding à un utilisateur
    # EXISTANT qui a déjà un compte actif fonctionnel (décision produit du
    # 31/07) : ignorer le lien ne doit jamais désactiver un compte qui
    # marchait déjà — seul le jeton expire, sans effet de bord sur le compte.
    deactivate_on_expiry = Column(Boolean, nullable=False, default=True)

    user = relationship("User", foreign_keys=[user_id])

    def is_valid(self) -> bool:
        return self.status == STATUS_PENDING and self.expires_at > utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "purpose": self.purpose,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
