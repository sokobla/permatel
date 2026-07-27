from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, JSON as PG_JSON, JSONB
from sqlalchemy.orm import relationship
from app import db

Base = db.Model

JSONB_VARIANT = JSONB().with_variant(PG_JSON(), "sqlite")

# event_type / call_direction / call_status sont des String (pas d'enum
# Postgres) : le module Téléphonie doit pouvoir accueillir de nouveaux types
# d'événements (ESL, puis AMI en phase 2) sans migration de schéma. Valeurs
# attendues aujourd'hui, validées côté application (routes/telephony.py) :
#   event_type     : CHANNEL_CREATE | CHANNEL_PROGRESS_MEDIA | CHANNEL_ANSWER
#                     | CHANNEL_HANGUP_COMPLETE | CALLCENTER_QUEUE_ENTER
#                     | CALLCENTER_AGENT_STATE_CHANGE
#   call_direction  : inbound | outbound
#   call_status     : ringing | early_media | answered | missed | abandoned
#                     | technical_failure | on_hold | ended


class TelephonyEvent(Base):
    __tablename__ = 'telephony_events'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id', 'demande_id'], ['demandes.tenant_id', 'demandes.id'], name='fk_telephony_events_demande_tenant', ondelete='SET NULL'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_session_id = Column(Integer, ForeignKey('user_sessions.id'), nullable=True, index=True)
    demande_id = Column(Integer, nullable=True, index=True)
    pbx_connector_id = Column(Integer, ForeignKey('pbx_connectors.id', ondelete='SET NULL'), nullable=True, index=True)

    event_type = Column(String(50), nullable=False)
    call_direction = Column(String(10), nullable=True)  # inbound | outbound
    call_status = Column(String(30), nullable=True)
    caller_number = Column(String(20), nullable=True)
    callee_number = Column(String(20), nullable=True)
    agent_login = Column(String(50), nullable=True, index=True)
    queue_id = Column(String(100), nullable=True, index=True)
    duration = Column(Integer, nullable=True)  # en secondes
    call_uuid = Column(String(100), nullable=True, index=True)
    recording_url = Column(String(500), nullable=True)
    raw_payload = Column(JSONB_VARIANT, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Multi-tenant column
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)

    # Relations
    user_session = relationship("UserSession", back_populates="telephony_events")
    demande = relationship("Demande", back_populates="telephony_events")
    tenant = relationship('Tenant', back_populates='telephony_events')
    pbx_connector = relationship("PbxConnector")

    def to_dict(self):
        return {
            "id": self.id,
            "pbx_connector_id": self.pbx_connector_id,
            "event_type": self.event_type,
            "call_direction": self.call_direction,
            "call_status": self.call_status,
            "caller": self.caller_number,
            "callee": self.callee_number,
            "agent_login": self.agent_login,
            "queue_id": self.queue_id,
            "duration": self.duration,
            "call_uuid": self.call_uuid,
            "recording_url": self.recording_url,
            "demande_id": self.demande_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<TelephonyEvent {self.event_type} - {self.call_uuid}>"
