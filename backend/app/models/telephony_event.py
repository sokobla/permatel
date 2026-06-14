from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model
import enum

class EventType(enum.Enum):
    CALL_START = "call_start"
    CALL_END = "call_end"
    CALL_TRANSFER = "call_transfer"
    CALL_HOLD = "call_hold"

class TelephonyEvent(Base):
    __tablename__ = 'telephony_events'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id', 'demande_id'], ['demandes.tenant_id', 'demandes.id'], name='fk_telephony_events_demande_tenant', ondelete='SET NULL'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_session_id = Column(Integer, ForeignKey('user_sessions.id'), nullable=False, index=True)
    demande_id = Column(Integer, nullable=True, index=True)
    
    event_type = Column(SQLEnum(EventType), nullable=False)
    caller_number = Column(String(20), nullable=True)
    duration = Column(Integer, nullable=True)  # en secondes
    call_uuid = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Multi-tenant column
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Relations
    user_session = relationship("UserSession", back_populates="telephony_events")
    demande = relationship("Demande", back_populates="telephony_events")
    tenant = relationship('Tenant', back_populates='telephony_events')
    
    def __repr__(self):
        return f"<TelephonyEvent {self.event_type.value} - {self.call_uuid}>"