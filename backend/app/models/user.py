from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app import db
import enum

# Use db.Model as base class for SQLAlchemy 2.0 compatibility
Base = db.Model

class UserRole(enum.Enum):
    PERMANENCIER = "PERMANENCIER"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, index=True)
    telephone = Column(String(20), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    
    # ESL Téléphonie
    agent_login = Column(String(50), nullable=True)
    station_extension = Column(String(20), nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    demandes_assignees = relationship("Demande", foreign_keys="Demande.permanencier_id", back_populates="permanencier")
    demandes_closed = relationship("Demande", foreign_keys="Demande.closed_by_id", back_populates="closed_by")
    interactions = relationship("Interaction", back_populates="user")
    fichiers = relationship("Fichier", back_populates="uploaded_by")
    audit_logs = relationship("AuditLog", back_populates="user")
    user_sessions = relationship("UserSession", back_populates="user")
    tenants = relationship("Tenant", secondary="tenant_users", back_populates="users")
    
    def set_password(self, password: str) -> None:
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256:600000")

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """Retourne une représentation JSON sérialisable de l'utilisateur."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "nom": self.nom,
            "prenom": self.prenom,
            "role": self.role.value,
            "telephone": self.telephone,
            "avatar_url": self.avatar_url,
            "agent_login": self.agent_login,
            "station_extension": self.station_extension,
            "is_active": self.is_active,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f"<User {self.username} - {self.role.value}>"