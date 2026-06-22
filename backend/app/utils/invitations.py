"""Helpers d'invitation : génération/hash de token et envoi d'email."""
import hashlib
import secrets
from email.message import EmailMessage

from flask import current_app

from app.models.setting import SmtpSetting
from app.utils.mailer import send_via_smtp


def generate_token() -> tuple[str, str]:
    """Retourne (token_clair, token_hash). Seul le hash est stocké."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def build_accept_url(token: str) -> str:
    base = current_app.config.get("FRONTEND_BASE_URL", "http://localhost:8080").rstrip("/")
    return f"{base}/accept-invite?token={token}"


def send_invitation_email(tenant, invitation, token: str) -> None:
    """
    Envoie l'email d'invitation via le SMTP du tenant.
    Lève une exception si le SMTP n'est pas configuré ou si l'envoi échoue.
    """
    cfg = SmtpSetting.query.filter_by(tenant_id=tenant.id).first()
    if not cfg or not cfg.host or not cfg.from_address:
        raise RuntimeError("La configuration SMTP du tenant est incomplète (envoi d'invitation impossible).")

    accept_url = build_accept_url(token)
    tenant_name = getattr(tenant, "nom", "") or "votre espace"

    msg = EmailMessage()
    msg["From"] = cfg.from_address
    msg["To"] = invitation.email
    msg["Subject"] = f"Invitation à rejoindre {tenant_name}"
    msg.set_content(
        f"Bonjour,\n\n"
        f"Vous avez été invité(e) à rejoindre l'espace « {tenant_name} » sur PERMATEL.\n\n"
        f"Pour activer votre accès, cliquez sur le lien ci-dessous (valable 48 heures) :\n"
        f"{accept_url}\n\n"
        f"Si vous n'êtes pas concerné(e) par cette invitation, ignorez ce message.\n\n"
        f"— L'équipe {tenant_name}"
    )
    send_via_smtp(cfg, msg)
