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

    Ressource GLOBALE, non tenant-scopée : un même PBX physique peut héberger
    plusieurs tenants PERMATEL (voir PbxDomainTenant pour le rattachement).
    CRUD réservé au super-admin global (comme la gestion des tenants).
    `type` est un `String` (pas d'enum Postgres) pour permettre d'ajouter un
    futur type de PBX sans migration.
    """
    __tablename__ = "pbx_connectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # ESL | AMI | TSAPI
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(100), nullable=True)  # AMI notamment (ESL : mot de passe seul)
    password = Column(EncryptedText, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    domains = relationship("PbxDomainTenant", back_populates="connector", cascade="all, delete-orphan")

    def to_dict(self, *, include_secrets=False):
        data = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "has_password": bool(self.password),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_secrets:
            data["password"] = self.password
        return data

    def __repr__(self):
        return f"<PbxConnector {self.name} ({self.type})>"


class PbxDomainTenant(Base):
    """Rattachement d'un domaine PBX (FusionPBX `domain_name`, ou équivalent
    Asterisk) à un tenant PERMATEL, avec les files d'attente supervisées.

    Table tenant-scopée : c'est elle qui permet de router `pbx_domain` (porté
    par chaque événement FreeSWITCH/AMI) vers le bon `tenant_id` côté
    ingestion (`POST /api/telephony/events/ingest`).
    """
    __tablename__ = "pbx_domains_tenants"
    __table_args__ = (
        UniqueConstraint("pbx_connector_id", "pbx_domain", name="uq_pbx_domain_per_connector"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    pbx_connector_id = Column(Integer, ForeignKey("pbx_connectors.id", ondelete="CASCADE"), nullable=False, index=True)
    pbx_domain = Column(String(255), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    queue_ids = Column(JSONB_VARIANT, nullable=True)  # liste de queue_id supervisées pour ce tenant

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    connector = relationship("PbxConnector", back_populates="domains")
    tenant = relationship("Tenant", back_populates="pbx_domains")

    def to_dict(self):
        return {
            "id": self.id,
            "pbx_connector_id": self.pbx_connector_id,
            "pbx_domain": self.pbx_domain,
            "tenant_id": str(self.tenant_id),
            "queue_ids": self.queue_ids or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<PbxDomainTenant {self.pbx_domain} -> tenant={self.tenant_id}>"
