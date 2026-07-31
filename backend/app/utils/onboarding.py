"""Déclenchement/renvoi de l'email d'onboarding utilisateur (compte créé par
un admin, sans mot de passe fourni directement). Partagé par la création
(users.py::create_user) et le renvoi (users.py::resend_onboarding) pour ne
pas dupliquer la mécanique jeton+email."""
from datetime import datetime

from flask import current_app

from app import db
from app.models.user_token import UserToken, PURPOSE_ONBOARDING, ONBOARDING_TTL, STATUS_PENDING, STATUS_REVOKED
from app.utils.email_templates import build_onboarding_url, send_templated_email
from app.utils.tokens import generate_token


def trigger_onboarding(user, tenant, created_by_user_id, deactivate_on_expiry: bool = True) -> None:
    """Révoque tout jeton onboarding `pending` existant pour cet utilisateur,
    en crée un nouveau, envoie l'email. Lève une exception si l'envoi échoue
    (SMTP non configuré ou en erreur) — à gérer par l'appelant, qui doit
    rollback la transaction plutôt que de laisser un jeton créé sans email
    envoyé.

    `deactivate_on_expiry=False` (décision produit du 31/07) : à utiliser
    quand on renvoie un lien d'onboarding à un utilisateur EXISTANT qui a
    déjà un compte actif fonctionnel (`users.py::send_onboarding_existing`)
    — ignorer ce lien ne doit jamais désactiver un compte qui marchait déjà,
    contrairement à l'invitation initiale (`create_user`/`resend_onboarding`,
    où l'utilisateur n'a encore aucun mot de passe utilisable)."""
    existing = UserToken.query.filter_by(
        user_id=user.id, purpose=PURPOSE_ONBOARDING, status=STATUS_PENDING,
    ).all()
    for t in existing:
        t.status = STATUS_REVOKED

    raw, token_hash = generate_token()
    token = UserToken(
        user_id=user.id, purpose=PURPOSE_ONBOARDING, token_hash=token_hash,
        status=STATUS_PENDING, expires_at=datetime.utcnow() + ONBOARDING_TTL,
        created_by_user_id=created_by_user_id, deactivate_on_expiry=deactivate_on_expiry,
    )
    db.session.add(token)
    db.session.flush()

    platform_url = current_app.config.get("FRONTEND_BASE_URL", "http://localhost:8080").rstrip("/")
    send_templated_email(
        tenant, "onboarding_welcome",
        {
            "prenom": user.prenom,
            "nom": user.nom,
            "tenant_name": getattr(tenant, "nom", "") or "votre espace",
            "activation_url": build_onboarding_url(raw),
            "platform_url": platform_url,
        },
        user.email,
    )
    user.onboarding_status = STATUS_PENDING
