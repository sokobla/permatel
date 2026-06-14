"""
Décorateurs et helpers d'authentification JWT pour PERMATEL.
"""
from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.models.user import User, UserRole


def role_required(*roles: UserRole):
    """
    Décorateur : vérifie que l'utilisateur authentifié possède l'un des rôles requis.

    Usage :
        @role_required(UserRole.MANAGER, UserRole.ADMIN)
        def ma_route():
            ...
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_role = claims.get("role")
            allowed = [r.value for r in roles]
            if user_role not in allowed:
                return jsonify({
                    "error": "Accès refusé",
                    "message": f"Rôle requis : {', '.join(allowed)}. Votre rôle : {user_role}."
                }), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_current_user() -> User | None:
    """
    Retourne l'objet User correspondant à l'identity du JWT courant.
    À utiliser dans une route protégée par @jwt_required().
    """
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return User.query.get(user_id)


def get_active_session_jti() -> str | None:
    """Retourne le JTI du token courant depuis les claims JWT."""
    claims = get_jwt()
    return claims.get("jti")