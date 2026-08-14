"""
Accès direct ERP audité pour l'ADMIN global (Phase 6, ODOO_INTEGRATION_PLAN.md §4.4).

Pas une porte dérobée : accès restreint au rôle global ADMIN et TRACÉ (une
ligne AuditLog à chaque consultation), pour que le support PERMATEL puisse
ouvrir l'ERP directement sans passer par le flux applicatif normal.
"""
import uuid

from flask import Blueprint, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.user import UserRole
from app.models.erp import ErpConfig
from app.models.audit_log import AuditLog, AuditAction
from app.utils.auth import role_required

erp_bp = Blueprint("erp", __name__, url_prefix="/api/erp")
CORS(erp_bp, supports_credentials=True)


def _log_erp_audit(user_id: int, tenant_id, event: str, details: dict) -> None:
    """Trace un accès direct ERP — motif `_log_audit` de `routes/auth.py`."""
    try:
        db.session.add(AuditLog(
            user_id=user_id,
            tenant_id=tenant_id,
            table_name="erp",
            record_id=user_id,
            action=AuditAction.CREATE,
            new_values={"event": event, **details},
        ))
    except (TypeError, SQLAlchemyError):
        pass


@erp_bp.get("/direct-access")
@role_required(UserRole.ADMIN)
def get_direct_access():
    tid = get_jwt().get("tid")
    if not tid:
        return jsonify({"error": "Aucun tenant actif sélectionné."}), 400
    try:
        tenant_id = uuid.UUID(tid)
    except (ValueError, TypeError):
        return jsonify({"error": "Tenant invalide."}), 400

    cfg = ErpConfig.query.filter_by(tenant_id=tenant_id).first()
    if not cfg or not cfg.url_erp:
        return jsonify({"error": "Aucun accès direct ERP configuré pour ce tenant."}), 404

    user_id = int(get_jwt_identity())
    _log_erp_audit(user_id, tenant_id, "ERP_DIRECT_ACCESS_VIEWED", {"ip": request.remote_addr})
    db.session.commit()

    return jsonify({
        "url_erp": cfg.url_erp,
        "admin_username": cfg.admin_username,
        "admin_password": cfg.admin_password,
    }), 200
