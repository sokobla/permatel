from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSON as PG_JSON, JSONB
from sqlalchemy.orm import relationship

from app import db
from app.utils.crypto import EncryptedText

Base = db.Model

JSONB_VARIANT = JSONB().with_variant(PG_JSON(), "sqlite")

PBX_TYPES = {"ESL", "AMI", "TSAPI"}


class PbxConnector(Base):
    """Connecteur PBX (FusionPBX/ESL, Asterisk/AMI, futur TSAPI).

    Ressource TENANT-SCOPÉE (revu — initialement globale en Phase 11/12,
    partagée entre tenants via `PbxDomainTenant`). Chaque tenant possède et
    configure son propre connecteur, comme `SmtpSetting`/`ImapSetting` —
    CRUD délégué à l'admin de tenant (`@tenant_admin_required`), plus au
    super-admin global. `type` est un `String` (pas d'enum Postgres) pour
    permettre d'ajouter un futur type de PBX sans migration.
    """
    __tablename__ = "pbx_connectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # ESL | AMI | TSAPI
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(100), nullable=True)  # AMI notamment (ESL : mot de passe seul)
    password = Column(EncryptedText, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # État live rapporté par le Core Connector (heartbeat périodique,
    # POST /api/telephony/connectors/status) — affiché comme sous-ligne
    # "adapter" dans l'UI (Paramètres > Téléphonie).
    is_connected = Column(Boolean, nullable=True)  # None = jamais rapporté
    last_seen_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)

    # Horodatage bumpé par le bouton "Sync" (forcer une reconnexion) — inclus
    # dans le bootstrap config du connecteur comme filet de secours durable
    # si le signal Redis (temps réel) est manqué (connecteur en redémarrage).
    sync_requested_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="pbx_connectors")
    domains = relationship("PbxConnectorDomain", back_populates="connector", cascade="all, delete-orphan")

    def to_dict(self, *, include_secrets=False):
        data = {
            "id": self.id,
            "tenant_id": str(self.tenant_id),
            "name": self.name,
            "type": self.type,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "has_password": bool(self.password),
            "is_active": self.is_active,
            "is_connected": self.is_connected,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "last_error": self.last_error,
            "sync_requested_at": self.sync_requested_at.isoformat() if self.sync_requested_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_secrets:
            data["password"] = self.password
        return data

    def __repr__(self):
        return f"<PbxConnector {self.name} ({self.type}) tenant={self.tenant_id}>"


class PbxConnectorDomain(Base):
    """Domaine PBX (FusionPBX `domain_name`, ou équivalent Asterisk) couvert
    par un `PbxConnector`, avec les files d'attente supervisées.

    Plus de `tenant_id` propre (retiré — hérité implicitement du connecteur
    parent, désormais tenant-scoped) : un connecteur peut couvrir plusieurs
    domaines PBX du même tenant, mais plus être partagé entre tenants.
    C'est cette table qui route `pbx_domain` (porté par chaque événement
    FreeSWITCH/AMI) vers le bon tenant côté ingestion, via son connecteur.
    """
    __tablename__ = "pbx_connector_domains"
    __table_args__ = (
        UniqueConstraint("pbx_connector_id", "pbx_domain", name="uq_pbx_domain_per_connector"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    pbx_connector_id = Column(Integer, ForeignKey("pbx_connectors.id", ondelete="CASCADE"), nullable=False, index=True)
    pbx_domain = Column(String(255), nullable=False, index=True)
    queue_ids = Column(JSONB_VARIANT, nullable=True)  # liste de queue_id supervisées

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    connector = relationship("PbxConnector", back_populates="domains")

    def to_dict(self):
        return {
            "id": self.id,
            "pbx_connector_id": self.pbx_connector_id,
            "pbx_domain": self.pbx_domain,
            "queue_ids": self.queue_ids or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<PbxConnectorDomain {self.pbx_domain} connector={self.pbx_connector_id}>"
