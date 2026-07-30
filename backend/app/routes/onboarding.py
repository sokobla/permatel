"""
Complétion publique de l'onboarding utilisateur (aucune authentification).

GET  /api/onboarding/<token>          → détails minimaux (nom, prénom, email) pour pré-remplir le formulaire
POST /api/onboarding/<token>/complete → définit le mot de passe, termine l'onboarding

Miroir de app/routes/invitations.py (même mécanique de résolution jeton/
expiration), mais agit sur un compte déjà existant (créé par un admin) plutôt
que d'en créer un nouveau.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_cors import CORS

from app import db
from app.models.user_token import UserToken, PURPOSE_ONBOARDING, STATUS_PENDING, STATUS_COMPLETED, STATUS_EXPIRED
from app.utils.tokens import hash_token
from app.utils.validators import password_error

onboarding_bp = Blueprint("onboarding", __name__, url_prefix="/api/onboarding")
CORS(onboarding_bp, supports_credentials=True)


def _resolve(token: str):
    """Retourne (user_token, error_tuple). Marque 'expired' si dépassé — même
    principe que invitations.py::_resolve, jamais un message qui distingue
    "n'existe pas" de "expiré" (anti-énumération)."""
    if not token:
        return None, (jsonify({"error": "Jeton manquant."}), 400)
    user_token = UserToken.query.filter_by(
        token_hash=hash_token(token), purpose=PURPOSE_ONBOARDING,
    ).first()
    if not user_token or user_token.status != STATUS_PENDING:
        return None, (jsonify({"error": "Lien d'onboarding invalide ou déjà utilisé."}), 404)
    if user_token.expires_at <= datetime.utcnow():
        user_token.status = STATUS_EXPIRED
        user_token.user.onboarding_status = STATUS_EXPIRED
        db.session.commit()
        return None, (jsonify({"error": "Lien d'onboarding expiré."}), 410)
    return user_token, None


@onboarding_bp.get("/<token>")
def get_onboarding(token):
    user_token, err = _resolve(token)
    if err:
        return err
    user = user_token.user
    return jsonify({
        "email": user.email,
        "nom": user.nom,
        "prenom": user.prenom,
        "expires_at": user_token.expires_at.isoformat(),
    }), 200


@onboarding_bp.post("/<token>/complete")
def complete_onboarding(token):
    user_token, err = _resolve(token)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    pwd_err = password_error(password)
    if pwd_err:
        return jsonify({"error": pwd_err}), 400

    user = user_token.user
    user.set_password(password)
    user_token.status = STATUS_COMPLETED
    user_token.completed_at = datetime.utcnow()
    user.onboarding_status = STATUS_COMPLETED

    db.session.commit()
    return jsonify({"message": "Onboarding terminé. Vous pouvez vous connecter."}), 200
