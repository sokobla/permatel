"""
Gestion des modèles d'email par tenant (Paramètres > Emails).

Délégué à l'admin de tenant (@tenant_admin_required), même principe que
SMTP/IMAP/valeurs de référence — pas réservé à l'admin global.
"""
from flask import Blueprint, g, jsonify, request
from flask_cors import CORS

from app import db
from app.models.email_template import EmailTemplate, KNOWN_TEMPLATE_KEYS
from app.utils.decorators import tenant_admin_required
from app.utils.email_templates import ALLOWED_VARIABLES, SYSTEM_DEFAULTS, render_raw, validate_template_content

email_templates_bp = Blueprint("email_templates", __name__, url_prefix="/api/tenant/email-templates")
CORS(email_templates_bp, supports_credentials=True)

# Contexte d'exemple utilisé pour l'aperçu — jamais envoyé réellement.
PREVIEW_SAMPLE_VARIABLES = {
    "prenom": "Jean",
    "nom": "Dupont",
    "tenant_name": "Votre espace",
    "activation_url": "https://exemple.permatel.local/onboarding?token=apercu",
    "reset_url": "https://exemple.permatel.local/reset-password?token=apercu",
    "platform_url": "https://exemple.permatel.local",
}


def _template_payload(template_key: str) -> dict:
    override = EmailTemplate.query.filter_by(
        tenant_id=g.tenant_id, template_key=template_key, is_active=True
    ).first()
    source = override or SYSTEM_DEFAULTS[template_key]
    return {
        "template_key": template_key,
        "subject": source.subject if override else source["subject"],
        "body_html": source.body_html if override else source["body_html"],
        "is_customized": override is not None,
        "available_variables": sorted(ALLOWED_VARIABLES[template_key]),
        "updated_at": override.updated_at.isoformat() if override and override.updated_at else None,
    }


@email_templates_bp.get("")
@tenant_admin_required
def list_templates():
    return jsonify({"templates": [_template_payload(key) for key in sorted(KNOWN_TEMPLATE_KEYS)]}), 200


@email_templates_bp.get("/<template_key>")
@tenant_admin_required
def get_template(template_key):
    if template_key not in KNOWN_TEMPLATE_KEYS:
        return jsonify({"error": "Modèle d'email inconnu."}), 404
    return jsonify(_template_payload(template_key)), 200


@email_templates_bp.put("/<template_key>")
@tenant_admin_required
def update_template(template_key):
    if template_key not in KNOWN_TEMPLATE_KEYS:
        return jsonify({"error": "Modèle d'email inconnu."}), 404

    data = request.get_json(silent=True) or {}
    subject = (data.get("subject") or "").strip()
    body_html = (data.get("body_html") or "").strip()
    if not subject or not body_html:
        return jsonify({"error": "Objet et corps requis."}), 400

    error = validate_template_content(template_key, subject, body_html)
    if error:
        return jsonify({"error": error}), 400

    override = EmailTemplate.query.filter_by(tenant_id=g.tenant_id, template_key=template_key).first()
    if override:
        override.subject = subject
        override.body_html = body_html
        override.is_active = True
        override.updated_by_user_id = g.user.id
    else:
        override = EmailTemplate(
            tenant_id=g.tenant_id, template_key=template_key,
            subject=subject, body_html=body_html,
            is_active=True, updated_by_user_id=g.user.id,
        )
        db.session.add(override)

    db.session.commit()
    return jsonify({"message": "Modèle enregistré.", "template": _template_payload(template_key)}), 200


@email_templates_bp.post("/<template_key>/reset")
@tenant_admin_required
def reset_template(template_key):
    if template_key not in KNOWN_TEMPLATE_KEYS:
        return jsonify({"error": "Modèle d'email inconnu."}), 404

    override = EmailTemplate.query.filter_by(tenant_id=g.tenant_id, template_key=template_key).first()
    if override:
        override.is_active = False
        db.session.commit()
    return jsonify({"message": "Modèle réinitialisé au défaut.", "template": _template_payload(template_key)}), 200


@email_templates_bp.post("/<template_key>/preview")
@tenant_admin_required
def preview_template(template_key):
    if template_key not in KNOWN_TEMPLATE_KEYS:
        return jsonify({"error": "Modèle d'email inconnu."}), 404

    data = request.get_json(silent=True) or {}
    # Permet de prévisualiser un brouillon non encore enregistré (subject/
    # body_html soumis dans la requête) ; sinon prévisualise le modèle actif.
    subject_src = data.get("subject")
    body_src = data.get("body_html")
    if subject_src is None or body_src is None:
        payload = _template_payload(template_key)
        subject_src = payload["subject"]
        body_src = payload["body_html"]
    else:
        error = validate_template_content(template_key, subject_src, body_src)
        if error:
            return jsonify({"error": error}), 400

    rendered_subject, rendered_body = render_raw(template_key, subject_src, body_src, PREVIEW_SAMPLE_VARIABLES)
    return jsonify({"subject": rendered_subject, "body_html": rendered_body}), 200
