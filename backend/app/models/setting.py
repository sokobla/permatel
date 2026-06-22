from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID

from app import db

Base = db.Model


class SmtpSetting(Base):
    """
    Configuration SMTP par tenant (une ligne par tenant).
    Le mot de passe n'est jamais renvoyé par l'API (champ write-only).
    """
    __tablename__ = "smtp_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    host = Column(String(255), nullable=True)
    port = Column(Integer, default=587, nullable=False)
    username = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)  # chiffré au repos
    from_address = Column(String(255), nullable=True)
    security = Column(String(10), default="tls", nullable=False)  # none | tls | ssl
    is_active = Column(Boolean, default=True, nullable=False)

    # ── Réception (IMAP) — Phase 2 ──────────────────────────────────────────
    imap_host = Column(String(255), nullable=True)
    imap_port = Column(Integer, default=993, nullable=False)
    imap_security = Column(String(10), default="ssl", nullable=False)  # none | ssl | starttls
    imap_username = Column(String(255), nullable=True)
    imap_password = Column(String(255), nullable=True)  # chiffré au repos
    inbound_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self, include_password=False):
        data = {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "from_address": self.from_address,
            "security": self.security,
            "is_active": self.is_active,
            "has_password": bool(self.password),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_password:
            data["password"] = self.password
        return data

    def imap_to_dict(self):
        return {
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "imap_security": self.imap_security,
            "imap_username": self.imap_username,
            "inbound_enabled": self.inbound_enabled,
            "has_imap_password": bool(self.imap_password),
        }


class ReferenceValue(Base):
    """
    Valeur de référence éditable (listes des formulaires métier), par tenant.
    `family` regroupe les valeurs : nature_anomalie, statut_demande,
    moyens_acces, risques_specifiques, besoins_agents, type_mission.
    """
    __tablename__ = "reference_values"
    __table_args__ = (
        UniqueConstraint("tenant_id", "family", "label", name="uq_refval_tenant_family_label"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    family = Column(String(50), nullable=False, index=True)
    label = Column(String(150), nullable=False)
    # Code stable (clé d'enum côté backend) pour les familles couplées à la logique
    # métier. NULL pour les familles à libellés libres (moyens d'accès, risques…).
    code = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    # Nature « discriminante » (famille nature_anomalie) : pénalise le KPI
    # « Incidents agent » et le score agent. Paramétrable par tenant.
    is_discriminant = Column(Boolean, default=False, nullable=False)
    position = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "family": self.family,
            "label": self.label,
            "code": self.code,
            "active": self.is_active,
            "is_discriminant": self.is_discriminant,
            "position": self.position,
        }
