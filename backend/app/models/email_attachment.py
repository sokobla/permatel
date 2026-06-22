from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app import db

Base = db.Model


class EmailAttachment(Base):
    """Pièce jointe d'un email (sortant en Phase 1, entrant en Phase 2)."""
    __tablename__ = "email_attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(120), nullable=True)
    size = Column(Integer, nullable=True)
    storage_path = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "email_id": self.email_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
        }
