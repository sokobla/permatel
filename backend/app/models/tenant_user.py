from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app import db

Base = db.Model


class TenantUser(Base):
    __tablename__ = 'tenant_users'

    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    membership_role = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant", viewonly=True)
    user = relationship("User", viewonly=True)

    def __repr__(self):
        return f"<TenantUser tenant_id={self.tenant_id} user_id={self.user_id}>"