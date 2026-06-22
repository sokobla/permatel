from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app import db
from app.utils.crypto import EncryptedText

Base = db.Model


class Email(Base):
    """
    Message email (canal Mail).

    Phase 1 : flux SORTANT (direction='outbound').
    Les colonnes du flux entrant (imap_uid, received_at, in_reply_to…) sont déjà
    présentes mais nullables pour préparer la Phase 2 (collecte IMAP) sans nouvelle
    migration structurante.
    """
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    direction = Column(String(10), nullable=False, index=True)  # outbound | inbound
    status = Column(String(20), nullable=False, default="sent", index=True)
    # outbound: sent | failed | draft   |   inbound: non_lu | lu | traite | archive | spam

    # En-têtes / contenu
    message_id = Column(String(255), nullable=True, index=True)
    in_reply_to = Column(String(255), nullable=True)
    thread_id = Column(String(255), nullable=True, index=True)
    from_address = Column(String(255), nullable=True)
    to_addresses = Column(Text, nullable=True)   # séparées par des virgules
    cc = Column(Text, nullable=True)
    # Contenu potentiellement porteur de données personnelles → chiffré au repos
    subject = Column(EncryptedText, nullable=True)
    body_text = Column(EncryptedText, nullable=True)
    body_html = Column(EncryptedText, nullable=True)

    # Rattachements métier
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    demande_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # expéditeur / traitant

    # Flux entrant (Phase 2)
    imap_uid = Column(String(64), nullable=True)
    received_at = Column(DateTime, nullable=True)

    # Flux sortant
    sent_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    has_attachments = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "direction": self.direction,
            "status": self.status,
            "from_address": self.from_address,
            "to_addresses": self.to_addresses,
            "cc": self.cc,
            "subject": self.subject,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "contact_id": self.contact_id,
            "demande_id": self.demande_id,
            "user_id": self.user_id,
            "has_attachments": self.has_attachments,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
