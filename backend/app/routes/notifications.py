"""
API notifications — scopée tenant actif + utilisateur courant (g.user).
"""
from datetime import datetime

from flask import Blueprint, g, jsonify, request
from flask_cors import CORS

from app import db
from app.models.notification import Notification, NotificationPreference
from app.utils.decorators import tenant_required

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")
CORS(notifications_bp, supports_credentials=True)


@notifications_bp.get("")
@tenant_required
def list_notifications():
    status = request.args.get("status")  # "unread" | None
    limit = min(request.args.get("limit", default=30, type=int), 100)
    q = Notification.query.filter_by(tenant_id=g.tenant_id, user_id=g.user.id)
    if status == "unread":
        q = q.filter_by(is_read=False)
    items = q.order_by(Notification.created_at.desc()).limit(limit).all()
    unread = Notification.query.filter_by(
        tenant_id=g.tenant_id, user_id=g.user.id, is_read=False
    ).count()
    return jsonify({"notifications": [n.to_dict() for n in items], "unread_count": unread}), 200


@notifications_bp.get("/unread-count")
@tenant_required
def unread_count():
    n = Notification.query.filter_by(
        tenant_id=g.tenant_id, user_id=g.user.id, is_read=False
    ).count()
    return jsonify({"unread_count": n}), 200


@notifications_bp.post("/<int:notif_id>/read")
@tenant_required
def mark_read(notif_id):
    n = Notification.query.filter_by(id=notif_id, tenant_id=g.tenant_id, user_id=g.user.id).first()
    if not n:
        return jsonify({"error": "Notification introuvable."}), 404
    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.utcnow()
        db.session.commit()
    return jsonify({"message": "Marquée comme lue.", "id": notif_id}), 200


@notifications_bp.post("/read-all")
@tenant_required
def mark_all_read():
    now = datetime.utcnow()
    updated = Notification.query.filter_by(
        tenant_id=g.tenant_id, user_id=g.user.id, is_read=False
    ).update({"is_read": True, "read_at": now})
    db.session.commit()
    return jsonify({"message": "Tout marqué comme lu.", "updated": updated}), 200


@notifications_bp.get("/preferences")
@tenant_required
def get_preferences():
    rows = NotificationPreference.query.filter_by(tenant_id=g.tenant_id, user_id=g.user.id).all()
    return jsonify([
        {"type": r.type, "in_app": r.in_app, "email": r.email} for r in rows
    ]), 200


@notifications_bp.put("/preferences")
@tenant_required
def set_preference():
    data = request.get_json(silent=True) or {}
    type_ = (data.get("type") or "").strip()
    if not type_:
        return jsonify({"error": "Le champ 'type' est requis."}), 400
    row = NotificationPreference.query.filter_by(
        tenant_id=g.tenant_id, user_id=g.user.id, type=type_
    ).first()
    if not row:
        row = NotificationPreference(tenant_id=g.tenant_id, user_id=g.user.id, type=type_)
        db.session.add(row)
    if "in_app" in data:
        row.in_app = bool(data["in_app"])
    if "email" in data:
        row.email = bool(data["email"])
    db.session.commit()
    return jsonify({"type": row.type, "in_app": row.in_app, "email": row.email}), 200
