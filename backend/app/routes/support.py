"""
Contacter le support — endpoint PUBLIC (utilisable depuis LoginView, pré-auth).

Le destinataire est l'`support_email` du tenant résolu (à partir de l'email de
l'émetteur), avec repli sur la config système SUPPORT_EMAIL. L'envoi utilise le
SMTP du tenant. En cas d'impossibilité d'envoi, la réponse reste positive
(la demande est journalisée côté serveur) afin de ne pas exposer la config et de
garantir une UX claire.
"""
import re
from email.message import EmailMessage

from flask import Blueprint, jsonify, request, current_app
from flask_cors import CORS

from app.models.user import User
from app.models.contact import Contact
from app.models.tenant import Tenant
from app.models.setting import SmtpSetting
from app.utils.mailer import send_via_smtp
from app.utils.logger import auth_logger

support_bp = Blueprint("support", __name__, url_prefix="/api/support")
CORS(support_bp, supports_credentials=True)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
OBJETS = {"identifiant_oublie": "Identifiant oublié",
          "mot_de_passe_oublie": "Mot de passe oublié", "autre": "Autre"}


def _resolve_tenant(email):
    """Devine le tenant à partir de l'email de l'émetteur (user puis contact)."""
    if email:
        user = User.query.filter(User.email.ilike(email)).first()
        if user and user.tenants:
            return next((t for t in user.tenants if t.support_email), user.tenants[0])
        contact = Contact.query.filter(Contact.email.ilike(email)).first()
        if contact and contact.tenant_id:
            t = Tenant.query.get(contact.tenant_id)
            if t:
                return t
    return Tenant.query.filter(Tenant.support_email.isnot(None)).first()


@support_bp.post("")
def contact_support():
    data = request.get_json(silent=True) or {}
    nom = (data.get("nom") or "").strip()
    prenom = (data.get("prenom") or "").strip()
    email = (data.get("email") or "").strip()
    entreprise = (data.get("entreprise") or "").strip()
    objet = OBJETS.get(data.get("objet"), "Autre")
    message = (data.get("message") or "").strip()

    if not nom or not email or not message:
        return jsonify({"error": "Nom, email et message sont obligatoires."}), 422
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Email invalide."}), 422

    tenant = _resolve_tenant(email)
    recipient = (tenant.support_email if tenant else None) or current_app.config.get("SUPPORT_EMAIL")
    cfg = SmtpSetting.query.filter_by(tenant_id=tenant.id).first() if tenant else None

    body = (
        f"Nouvelle demande de support\n\n"
        f"Objet : {objet}\n"
        f"Nom : {prenom} {nom}\n"
        f"Email : {email}\n"
        f"Entreprise : {entreprise or '—'}\n\n"
        f"Message :\n{message}\n"
    )

    delivered = False
    if recipient and cfg and cfg.host and cfg.from_address:
        try:
            msg = EmailMessage()
            msg["From"] = cfg.from_address
            msg["To"] = recipient
            msg["Reply-To"] = email
            msg["Subject"] = f"[Support] {objet} — {prenom} {nom}".strip()
            msg.set_content(body)
            send_via_smtp(cfg, msg)
            delivered = True
        except Exception as exc:  # noqa: BLE001
            auth_logger.warning(f"SUPPORT_SEND_FAILED | to={recipient} | {exc}")
    else:
        auth_logger.warning(
            f"SUPPORT_REQUEST_UNROUTED | from={email} | recipient={recipient} | smtp={bool(cfg)}"
        )

    # Réponse toujours positive (pas d'exposition de config pré-auth)
    return jsonify({"ok": True, "delivered": delivered}), 200
