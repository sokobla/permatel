from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model
import enum
import uuid

class SessionStatus(enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

class UserSession(Base):
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    jti = db.Column(db.String(36), unique=True, nullable=True, index=True,
                     default=lambda: str(uuid.uuid4()))
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    
    agent_login = Column(String(50), nullable=True)
    station_extension = Column(String(20), nullable=True)
    
    session_start = Column(DateTime, default=datetime.utcnow, nullable=False)
    session_end = Column(DateTime, nullable=True)
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.ACTIVE, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Multi-tenant column (tenant actif pour la session)
    active_tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=True, index=True)
    
    # Relations
    user = relationship("User", back_populates="user_sessions")
    telephony_events = relationship("TelephonyEvent", back_populates="user_session")
    
    def __repr__(self):
        return f"<UserSession {self.agent_login} - {self.status.value}>"