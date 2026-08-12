"""
Modèles d'email personnalisables par tenant (Paramètres > Emails).

Tenant-scopée, comme SmtpSetting/ImapSetting — l'admin de tenant peut
personnaliser le contenu sans passer par l'admin global. Une ligne absente
ou `is_active=False` retombe sur le défaut système
(`app/utils/email_templates.py::SYSTEM_DEFAULTS`) — jamais bloquant.
"""
from datetime import datetime
from app.utils.time import utcnow

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app import db

# Clés de modèle connues — doit rester synchronisé avec SYSTEM_DEFAULTS/
# ALLOWED_VARIABLES dans app/utils/email_templates.py.
TEMPLATE_ONBOARDING_WELCOME = "onboarding_welcome"
TEMPLATE_PASSWORD_RESET = "password_reset"
KNOWN_TEMPLATE_KEYS = {TEMPLATE_ONBOARDING_WELCOME, TEMPLATE_PASSWORD_RESET}


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "template_key", name="uq_email_templates_tenant_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    template_key = Column(String(50), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    body_html = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "template_key": self.template_key,
            "subject": self.subject,
            "body_html": self.body_html,
            "is_active": self.is_active,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
