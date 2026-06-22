import uuid
from functools import wraps

from flask import g, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.models import Tenant, TenantUser
from app.models.tenant_user import MEMBERSHIP_ADMIN
from app.models.user import User, UserRole
from app.utils.logger import auth_logger


def _load_tenant_context():
    """
    Résout et charge le contexte de tenant dans `flask.g`.

    Pose : g.user, g.tenant, g.tenant_id, g.is_super_admin, g.tenant_membership
    (None pour le super-admin sans appartenance), g.is_tenant_admin.

    Retourne None si OK, sinon un tuple (response, status) à renvoyer.
    Règle de codes : 401 (pas de contexte / user inactif) · 400 (tid malformé) ·
    403 (RBAC intra-tenant : pas membre) · 404 (tenant inexistant/inactif).
    """
    verify_jwt_in_request()
    claims = get_jwt()

    tenant_id_str = claims.get("tid")
    if not tenant_id_str:
        auth_logger.warning("TENANT_REQUIRED_FAIL | reason=no_tid_in_jwt")
        return jsonify({
            "error": "Accès non autorisé",
            "message": "Aucun tenant actif n'est sélectionné dans le token."
        }), 401

    user_id = int(get_jwt_identity())
    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except (ValueError, TypeError):
        auth_logger.error(f"TENANT_REQUIRED_FAIL | user_id={user_id} | reason=invalid_tid_format | tid='{tenant_id_str}'")
        return jsonify({"error": "Format du tenant ID invalide dans le token."}), 400

    is_super_admin = claims.get("role") == UserRole.ADMIN.value

    if is_super_admin:
        tenant = Tenant.query.filter_by(id=tenant_id, is_active=True).first()
        if not tenant:
            auth_logger.warning(f"TENANT_REQUIRED_FAIL | user_id={user_id} | tenant_id={tenant_id} | reason=tenant_not_found (admin)")
            return jsonify({"error": "Tenant introuvable ou inactif."}), 404
        user = User.query.get(user_id)
        if not user or not user.is_active:
            return jsonify({"error": "Utilisateur introuvable ou désactivé."}), 401
        g.user = user
        g.tenant = tenant
        g.tenant_id = tenant_id
        g.is_super_admin = True
        g.tenant_membership = None
        g.is_tenant_admin = True  # le super-admin administre tous les tenants
        return None

    membership = TenantUser.query.join(Tenant).filter(
        TenantUser.user_id == user_id,
        TenantUser.tenant_id == tenant_id,
        TenantUser.is_active == True,
        Tenant.is_active == True
    ).first()

    if not membership:
        auth_logger.warning(f"TENANT_REQUIRED_FAIL | user_id={user_id} | tenant_id={tenant_id} | reason=not_a_member")
        return jsonify({
            "error": "Accès refusé",
            "message": "Vous n'êtes pas autorisé à accéder aux ressources de ce tenant."
        }), 403

    g.user = membership.user
    g.tenant = membership.tenant
    g.tenant_id = tenant_id
    g.is_super_admin = False
    g.tenant_membership = membership
    g.is_tenant_admin = membership.membership_role == MEMBERSHIP_ADMIN
    return None


def tenant_required(fn):
    """Route nécessitant un contexte de tenant actif (cf. _load_tenant_context)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        err = _load_tenant_context()
        if err is not None:
            return err
        return fn(*args, **kwargs)
    return wrapper


def tenant_admin_required(fn):
    """
    Route d'administration du tenant : exige un contexte de tenant valide ET
    la capacité d'administration (super-admin global, ou membership_role='admin'
    pour le tenant actif). Sinon 403.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        err = _load_tenant_context()
        if err is not None:
            return err
        if not getattr(g, "is_tenant_admin", False):
            return jsonify({
                "error": "Accès refusé",
                "message": "Cette action requiert le rôle d'administrateur du tenant."
            }), 403
        return fn(*args, **kwargs)
    return wrapper
