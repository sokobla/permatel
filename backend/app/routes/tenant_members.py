"""
Gestion du roster d'un tenant par son administrateur (délégation).

Toutes les routes sont tenant-scopées (claim `tid`) et réservées à l'admin de
tenant ou au super-admin global (`tenant_admin_required`). L'onboarding de
nouveaux comptes se fait par invitation (acceptation obligatoire, TTL 48h).

Garde-fous (Modèle 1 — rôle global) :
  - un admin de tenant ne peut PAS attribuer le rôle global ADMIN ;
  - il agit uniquement sur les appartenances de SON tenant actif ;
  - il ne modifie jamais le rôle global d'un utilisateur existant partagé.
"""
from datetime import datetime

from flask import Blueprint, g, jsonify, request
from flask_cors import CORS

from app import db
from app.models.user import User, UserRole
from app.models.tenant_user import TenantUser, MEMBERSHIP_ADMIN, MEMBERSHIP_MEMBER
from app.models.tenant_invitation import (
    TenantInvitation, INVITATION_TTL, INVITE_PENDING, INVITE_REVOKED,
)
from app.utils.decorators import tenant_admin_required, tenant_required
from app.utils.invitations import generate_token, send_invitation_email
from app.services.tenant_features import tenant_features

tenant_members_bp = Blueprint("tenant_members", __name__, url_prefix="/api/tenant")
CORS(tenant_members_bp, supports_credentials=True)


@tenant_members_bp.get("/features")
@tenant_required
def get_tenant_features():
    """Disponibilités fonctionnelles du tenant actif (lecture, tout utilisateur)."""
    return jsonify(tenant_features(g.tenant)), 200

# Rôles globaux attribuables par délégation (jamais ADMIN).
DELEGABLE_ROLES = {UserRole.MANAGER.value, UserRole.PERMANENCIER.value}
MEMBERSHIP_ROLES = {MEMBERSHIP_ADMIN, MEMBERSHIP_MEMBER}


def _member_payload(membership: TenantUser) -> dict:
    u = membership.user
    return {
        "user_id": u.id,
        "email": u.email,
        "username": u.username,
        "nom": u.nom,
        "prenom": u.prenom,
        "role": u.role.value if u.role else None,          # rôle fonctionnel global
        "membership_role": membership.membership_role,      # capacité dans le tenant
        "is_active": membership.is_active,
        "user_is_active": u.is_active,
    }


# ── Roster ────────────────────────────────────────────────────────────────── #

@tenant_members_bp.get("/members")
@tenant_admin_required
def list_members():
    memberships = (
        TenantUser.query.filter_by(tenant_id=g.tenant_id)
        .join(User, TenantUser.user_id == User.id)
        .order_by(User.nom.asc())
        .all()
    )
    return jsonify({"members": [_member_payload(m) for m in memberships],
                    "total": len(memberships)}), 200


@tenant_members_bp.patch("/members/<int:user_id>")
@tenant_admin_required
def update_member(user_id):
    """Met à jour l'appartenance : is_active et/ou membership_role (PAS le rôle global)."""
    if user_id == g.user.id:
        return jsonify({"error": "Vous ne pouvez pas modifier votre propre appartenance."}), 400

    membership = TenantUser.query.filter_by(tenant_id=g.tenant_id, user_id=user_id).first()
    if not membership:
        return jsonify({"error": "Membre introuvable dans ce tenant."}), 404

    data = request.get_json(silent=True) or {}

    if "membership_role" in data:
        mr = data["membership_role"]
        if mr not in MEMBERSHIP_ROLES:
            return jsonify({"error": "membership_role invalide."}), 400
        membership.membership_role = mr

    if "is_active" in data:
        membership.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify({"message": "Appartenance mise à jour.", "member": _member_payload(membership)}), 200


@tenant_members_bp.delete("/members/<int:user_id>")
@tenant_admin_required
def remove_member(user_id):
    """Retire l'appartenance au tenant (ne supprime pas le compte global)."""
    if user_id == g.user.id:
        return jsonify({"error": "Vous ne pouvez pas vous retirer vous-même."}), 400

    membership = TenantUser.query.filter_by(tenant_id=g.tenant_id, user_id=user_id).first()
    if not membership:
        return jsonify({"error": "Membre introuvable dans ce tenant."}), 404

    db.session.delete(membership)
    db.session.commit()
    return jsonify({"message": "Membre retiré du tenant."}), 200


# ── Invitations ──────────────────────────────────────────────────────────── #

@tenant_members_bp.get("/invitations")
@tenant_admin_required
def list_invitations():
    invites = (
        TenantInvitation.query.filter_by(tenant_id=g.tenant_id)
        .order_by(TenantInvitation.created_at.desc())
        .all()
    )
    return jsonify({"invitations": [i.to_dict() for i in invites], "total": len(invites)}), 200


@tenant_members_bp.post("/invitations")
@tenant_admin_required
def create_invitation():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    role = data.get("role")
    membership_role = data.get("membership_role", MEMBERSHIP_MEMBER)

    if not email or "@" not in email:
        return jsonify({"error": "Adresse email valide requise."}), 400
    if role not in DELEGABLE_ROLES:
        return jsonify({"error": f"Rôle invalide. Autorisés : {', '.join(sorted(DELEGABLE_ROLES))}."}), 400
    if membership_role not in MEMBERSHIP_ROLES:
        return jsonify({"error": "membership_role invalide."}), 400

    # Déjà membre actif ?
    existing_user = User.query.filter(User.email.ilike(email)).first()
    if existing_user:
        m = TenantUser.query.filter_by(tenant_id=g.tenant_id, user_id=existing_user.id, is_active=True).first()
        if m:
            return jsonify({"error": "Cet utilisateur est déjà membre du tenant."}), 409

    # Invitation pending déjà existante ?
    pending = TenantInvitation.query.filter_by(
        tenant_id=g.tenant_id, email=email, status=INVITE_PENDING
    ).first()
    if pending and pending.is_valid():
        return jsonify({"error": "Une invitation est déjà en attente pour cet email."}), 409

    token, token_hash = generate_token()
    invitation = TenantInvitation(
        tenant_id=g.tenant_id,
        email=email,
        role=role,
        membership_role=membership_role,
        token_hash=token_hash,
        status=INVITE_PENDING,
        invited_by_user_id=g.user.id,
        expires_at=datetime.utcnow() + INVITATION_TTL,
    )
    db.session.add(invitation)
    db.session.flush()

    try:
        send_invitation_email(g.tenant, invitation, token)
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Échec de l'envoi de l'invitation : {exc}"}), 502

    db.session.commit()
    return jsonify({"message": "Invitation envoyée.", "invitation": invitation.to_dict()}), 201


@tenant_members_bp.post("/invitations/<int:invite_id>/resend")
@tenant_admin_required
def resend_invitation(invite_id):
    invitation = TenantInvitation.query.filter_by(id=invite_id, tenant_id=g.tenant_id).first()
    if not invitation:
        return jsonify({"error": "Invitation introuvable."}), 404
    if invitation.status != INVITE_PENDING:
        return jsonify({"error": "Seule une invitation en attente peut être relancée."}), 400

    token, token_hash = generate_token()
    invitation.token_hash = token_hash
    invitation.expires_at = datetime.utcnow() + INVITATION_TTL

    try:
        send_invitation_email(g.tenant, invitation, token)
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Échec de l'envoi : {exc}"}), 502

    db.session.commit()
    return jsonify({"message": "Invitation relancée.", "invitation": invitation.to_dict()}), 200


@tenant_members_bp.delete("/invitations/<int:invite_id>")
@tenant_admin_required
def revoke_invitation(invite_id):
    invitation = TenantInvitation.query.filter_by(id=invite_id, tenant_id=g.tenant_id).first()
    if not invitation:
        return jsonify({"error": "Invitation introuvable."}), 404
    invitation.status = INVITE_REVOKED
    db.session.commit()
    return jsonify({"message": "Invitation révoquée."}), 200
