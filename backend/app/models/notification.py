"""
Notifications PERMATEL — in-app + file d'envoi email.

- Notification          : notif in-app (cloche/centre), par utilisateur, scopée tenant.
- NotificationPreference: préférence par (utilisateur, type) → canaux in_app / email.
- EmailOutbox           : file d'envoi email découplée (dispatch par cron via SMTP tenant).
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    severity = Column(String(10), nullable=False, default="normal")  # low | normal | high
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    entity_type = Column(String(50), nullable=True)   # ex. "demande" / "email"
    entity_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "title": self.title,
            "body": self.body,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NotificationPreference(db.Model):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "type", name="uq_notif_pref"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    in_app = Column(Boolean, nullable=False, default=True)
    email = Column(Boolean, nullable=False, default=False)


class EmailOutbox(db.Model):
    __tablename__ = "email_outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    to_address = Column(String(255), nullable=False)
    subject = Column(String(300), nullable=False)
    body_text = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending | sent | failed
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
