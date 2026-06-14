from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model
import enum

class AuditAction(enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

class AuditLog(Base):
    __tablename__ = 'audit_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    table_name = Column(String(50), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    action = Column(SQLEnum(AuditAction), nullable=False)
    
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Multi-tenant column
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Relations
    user = relationship("User", back_populates="audit_logs")
    tenant = relationship('Tenant', back_populates='audit_logs')
    
    def __repr__(self):
        return f"<AuditLog {self.action.value} - {self.table_name}#{self.record_id}>"