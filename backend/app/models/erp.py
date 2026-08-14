"""
Fondations ERP (Phase 6, cf. ODOO_INTEGRATION_PLAN.md §3.B et §5).

Nommage volontairement générique `Erp*`/`erp_*`, pas `Odoo*` — l'instance
ERP réellement branchée (Odoo 18 Community aujourd'hui) n'est pas figée
dans le nom du code, cf. §2.3 du plan.
"""
from datetime import datetime
from app.utils.time import utcnow

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app import db
from app.utils.crypto import EncryptedText

Base = db.Model


class ErpConfig(Base):
    """
    Configuration ERP par tenant (une ligne par tenant, motif SmtpSetting).

    Instance ERP partagée entre tenants (§2.3) : ce modèle ne stocke donc
    PAS des identifiants de connexion différents par tenant pour l'usage
    applicatif courant — seulement le `company_id` (res.company) ERP cible
    pour scoper les appels XML-RPC de ce tenant.

    Les 3 champs url_erp/admin_username/admin_password servent UNIQUEMENT
    à l'accès direct ERP audité pour l'ADMIN global (§4.4) — pas à la
    synchronisation applicative courante (qui utilise l'URL/DB partagée
    résolue depuis la config app, jamais depuis ces colonnes tenant).
    Chiffrées au repos via EncryptedText (transparent, motif déjà en place
    sur Email.subject/body_text) — pas le pattern manuel encrypt_secret()/
    decrypt_secret() utilisé par SmtpSetting, cf. CLAUDE.md.
    """
    __tablename__ = "erp_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    company_id = Column(Integer, nullable=True)

    # Accès direct ERP audité (§4.4) — ADMIN global uniquement.
    url_erp = Column(EncryptedText, nullable=True)
    admin_username = Column(EncryptedText, nullable=True)
    admin_password = Column(EncryptedText, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def to_dict(self, include_secrets=False):
        data = {
            "company_id": self.company_id,
            "has_admin_password": bool(self.admin_password),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_secrets:
            data["url_erp"] = self.url_erp
            data["admin_username"] = self.admin_username
            data["admin_password"] = self.admin_password
        return data


class ErpSyncQueue(Base):
    """
    File de retry pour la synchronisation ERP (§2.1, §2.4).

    Une tentative synchrone à timeout court est faite après le commit
    d'une action PERMATEL ; en cas d'échec/timeout, une ligne est insérée
    ici et reprise par `flask erp-sync-dispatch` (cron).

    `locked_at`/`locked_until` : verrouillage court pour qu'un run de
    dispatch qui prend du retard ne se fasse pas doubler par le suivant
    (§2.4) — absent d'EmailOutbox (dispatch simple/mono-worker) mais
    requis ici, la sync ERP pouvant être plus lente (XML-RPC).
    """
    __tablename__ = "erp_sync_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    flux = Column(String(50), nullable=False)  # ex. "partner_create" — pas d'Enum natif
    payload = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    # pending | in_flight | done | failed
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "flux": self.flux,
            "status": self.status,
            "attempts": self.attempts,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
