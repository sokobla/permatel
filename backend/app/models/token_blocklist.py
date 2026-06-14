from datetime import datetime
from app import db


class TokenBlocklist(db.Model):
    """
    Stocke les JTI (JWT ID) des tokens révoqués (access et refresh).
    Vérifiée à chaque requête via le callback @jwt.token_in_blocklist_loader.
    Purger périodiquement les entrées dont expires_at est dépassé.
    """
    __tablename__ = "token_blocklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)
    token_type = db.Column(db.String(10), nullable=False)   # "access" ou "refresh"
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revoked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self) -> str:
        return f"<TokenBlocklist jti={self.jti} type={self.token_type}>"
