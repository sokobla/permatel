"""
Acceptation publique des invitations d'onboarding (aucune authentification).

GET  /api/invitations/<token>          → détails minimaux (tenant, email, type de compte)
POST /api/invitations/<token>/accept   → crée le compte (nouveau) ou ajoute l'appartenance (existant)
"""
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_cors import CORS

from app import db
from app.models.user import User, UserRole
from app.models.tenant import Tenant
from app.models.tenant_user import TenantUser
from app.models.tenant_invitation import (
    TenantInvitation, INVITE_PENDING, INVITE_ACCEPTED, INVITE_EXPIRED,
)
from app.utils.invitations import hash_token
from app.utils.validators import password_error

invitations_bp = Blueprint("invitations", __name__, url_prefix="/api/invitations")
CORS(invitations_bp, supports_credentials=True)


def _resolve(token: str):
    """Retourne (invitation, error_tuple). Marque 'expired' si dépassée."""
    if not token:
        return None, (jsonify({"error": "Token manquant."}), 400)
    invitation = TenantInvitation.query.filter_by(token_hash=hash_token(token)).first()
    if not invitation or invitation.status not in (INVITE_PENDING,):
        return None, (jsonify({"error": "Invitation invalide ou déjà utilisée."}), 404)
    if invitation.expires_at <= datetime.utcnow():
        invitation.status = INVITE_EXPIRED
        db.session.commit()
        return None, (jsonify({"error": "Invitation expirée."}), 410)
    return invitation, None


@invitations_bp.get("/<token>")
def get_invitation(token):
    invitation, err = _resolve(token)
    if err:
        return err
    tenant = Tenant.query.get(invitation.tenant_id)
    existing_user = User.query.filter(User.email.ilike(invitation.email)).first()
    return jsonify({
        "email": invitation.email,
        "tenant_name": tenant.nom if tenant else None,
        "role": invitation.role,
        # Un compte existe déjà → l'invité confirme simplement (pas de mot de passe à créer)
        "requires_account": existing_user is None,
        "expires_at": invitation.expires_at.isoformat(),
    }), 200


@invitations_bp.post("/<token>/accept")
def accept_invitation(token):
    invitation, err = _resolve(token)
    if err:
        return err

    tenant = Tenant.query.filter_by(id=invitation.tenant_id, is_active=True).first()
    if not tenant:
        return jsonify({"error": "Tenant introuvable ou inactif."}), 404

    data = request.get_json(silent=True) or {}
    existing_user = User.query.filter(User.email.ilike(invitation.email)).first()

    if existing_user:
        # Compte existant : on ajoute (ou réactive) l'appartenance, sans toucher au rôle global.
        user = existing_user
        membership = TenantUser.query.filter_by(tenant_id=tenant.id, user_id=user.id).first()
        if membership:
            membership.is_active = True
            membership.membership_role = invitation.membership_role
        else:
            db.session.add(TenantUser(
                tenant_id=tenant.id, user_id=user.id,
                membership_role=invitation.membership_role, is_active=True,
            ))
    else:
        # Nouveau compte : nom/prénom/mot de passe requis. username = email.
        nom = (data.get("nom") or "").strip()
        prenom = (data.get("prenom") or "").strip()
        password = data.get("password") or ""
        if not nom or not prenom:
            return jsonify({"error": "Nom et prénom requis."}), 400
        pwd_err = password_error(password)
        if pwd_err:
            return jsonify({"error": pwd_err}), 400

        try:
            role = UserRole(invitation.role)
        except ValueError:
            return jsonify({"error": "Rôle de l'invitation invalide."}), 400

        user = User(
            username=invitation.email,
            email=invitation.email,
            nom=nom,
            prenom=prenom,
            role=role,
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        db.session.add(TenantUser(
            tenant_id=tenant.id, user_id=user.id,
            membership_role=invitation.membership_role, is_active=True,
        ))

    invitation.status = INVITE_ACCEPTED
    invitation.accepted_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "message": "Invitation acceptée. Vous pouvez vous connecter.",
        "email": invitation.email,
    }), 200
