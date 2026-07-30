"""
Rendu des modèles d'email personnalisables (Paramètres > Emails).

Le contenu d'un EmailTemplate est fourni par un admin de tenant via un
<textarea> — c'est donc du texte utilisateur qui va être interprété comme un
gabarit Jinja2. Trois barrières, pas une seule :
  1. `SandboxedEnvironment` (pas `jinja2.Template`) : bloque l'introspection
     Python (`__class__`, `__mro__`, etc.) qui permettrait, avec un moteur non
     sandboxé, d'atteindre des objets internes et potentiellement d'exécuter
     du code arbitraire côté serveur.
  2. Whitelist stricte de variables par `template_key` (ALLOWED_VARIABLES) :
     seules les variables listées sont transmises au contexte de rendu, une
     entrée hors liste dans `variables` est silencieusement ignorée plutôt
     que fuitée.
  3. `autoescape=True` : une variable contenant du HTML/JS ne s'injecte pas
     telle quelle dans le corps du mail (XSS via une variable, ex. un nom
     d'utilisateur malveillant).
"""
from email.message import EmailMessage

from flask import current_app
from jinja2 import StrictUndefined
from jinja2.exceptions import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from app.models.email_template import EmailTemplate, TEMPLATE_ONBOARDING_WELCOME, TEMPLATE_PASSWORD_RESET
from app.models.setting import SmtpSetting
from app.utils.mailer import send_via_smtp

# StrictUndefined — indispensable pour que la whitelist de variables (point 2
# ci-dessus) soit réellement appliquée : avec l'Undefined par défaut de
# Jinja2, une variable non fournie s'affiche silencieusement en chaîne vide
# au rendu (aucune exception) — validate_template_content() serait alors
# incapable de détecter/rejeter une variable hors whitelist au PUT.
_ENV = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)

SYSTEM_DEFAULTS = {
    TEMPLATE_ONBOARDING_WELCOME: {
        "subject": "Bienvenue sur {{ tenant_name }}",
        "body_html": (
            "<p>Bonjour {{ prenom }},</p>"
            "<p>Votre compte a été créé sur <strong>{{ tenant_name }}</strong>.</p>"
            "<p>Pour définir votre mot de passe et activer votre accès, cliquez sur le lien "
            "ci-dessous (valable 24 heures) :</p>"
            "<p><a href=\"{{ activation_url }}\">Définir mon mot de passe</a></p>"
            "<p>Passé ce délai, le lien expirera et votre compte sera désactivé — contactez "
            "votre administrateur pour un nouvel envoi.</p>"
            "<p>Plateforme : <a href=\"{{ platform_url }}\">{{ platform_url }}</a></p>"
        ),
    },
    TEMPLATE_PASSWORD_RESET: {
        "subject": "Réinitialisation de votre mot de passe — {{ tenant_name }}",
        "body_html": (
            "<p>Bonjour,</p>"
            "<p>Une réinitialisation de mot de passe a été demandée pour votre compte "
            "{{ tenant_name }}.</p>"
            "<p><a href=\"{{ reset_url }}\">Réinitialiser mon mot de passe</a></p>"
            "<p>Ce lien expire dans 1 heure. Si vous n'êtes pas à l'origine de cette demande, "
            "ignorez cet email — votre mot de passe actuel reste inchangé.</p>"
        ),
    },
}

# Whitelist stricte par clé — voir le point 2 dans le docstring du module.
ALLOWED_VARIABLES = {
    TEMPLATE_ONBOARDING_WELCOME: {"prenom", "nom", "tenant_name", "activation_url", "platform_url"},
    TEMPLATE_PASSWORD_RESET: {"prenom", "tenant_name", "reset_url"},
}


def build_onboarding_url(token: str) -> str:
    base = current_app.config.get("FRONTEND_BASE_URL", "http://localhost:8080").rstrip("/")
    return f"{base}/onboarding?token={token}"


def build_reset_url(token: str) -> str:
    base = current_app.config.get("FRONTEND_BASE_URL", "http://localhost:8080").rstrip("/")
    return f"{base}/reset-password?token={token}"


def _safe_variables(template_key: str, variables: dict) -> dict:
    allowed = ALLOWED_VARIABLES[template_key]
    return {k: v for k, v in (variables or {}).items() if k in allowed}


def render_template(tenant_id, template_key: str, variables: dict) -> tuple[str, str]:
    """Retourne (subject, body_html) rendus. Charge l'override tenant actif
    s'il existe, sinon SYSTEM_DEFAULTS. Ne transmet au moteur QUE les
    variables listées dans ALLOWED_VARIABLES[template_key]."""
    if template_key not in SYSTEM_DEFAULTS:
        raise ValueError(f"template_key inconnu : {template_key!r}")

    safe_vars = _safe_variables(template_key, variables)

    override = EmailTemplate.query.filter_by(
        tenant_id=tenant_id, template_key=template_key, is_active=True
    ).first()
    subject_src = override.subject if override else SYSTEM_DEFAULTS[template_key]["subject"]
    body_src = override.body_html if override else SYSTEM_DEFAULTS[template_key]["body_html"]

    subject = _ENV.from_string(subject_src).render(**safe_vars)
    body_html = _ENV.from_string(body_src).render(**safe_vars)
    return subject, body_html


def render_raw(template_key: str, subject_src: str, body_src: str, variables: dict) -> tuple[str, str]:
    """Rend un couple (subject, body_html) fourni directement (pas chargé
    depuis la base) — utilisé pour l'aperçu d'un brouillon non encore
    enregistré. Même whitelist de variables que render_template()."""
    safe_vars = _safe_variables(template_key, variables)
    subject = _ENV.from_string(subject_src).render(**safe_vars)
    body_html = _ENV.from_string(body_src).render(**safe_vars)
    return subject, body_html


def validate_template_content(template_key: str, subject: str, body_html: str) -> str | None:
    """Valide qu'un contenu de modèle soumis par un admin est un gabarit
    Jinja2 syntaxiquement correct et ne référence que des variables autorisées
    pour cette clé — retourne un message d'erreur (str) si invalide, sinon
    None. Un template invalide n'est JAMAIS sauvegardé silencieusement."""
    if template_key not in ALLOWED_VARIABLES:
        return f"template_key inconnu : {template_key!r}"

    sample_vars = {name: "x" for name in ALLOWED_VARIABLES[template_key]}
    try:
        _ENV.from_string(subject).render(**sample_vars)
        _ENV.from_string(body_html).render(**sample_vars)
    except TemplateError as exc:
        # Regroupe TemplateSyntaxError (syntaxe invalide), UndefinedError
        # (variable non autorisée référencée) ET SecurityError (tentative
        # d'accès à un attribut non sandboxé, ex. `.__class__.__mro__`) —
        # les trois DOIVENT aboutir à un rejet propre au PUT, jamais à une
        # exception non interceptée (qui remonterait en 500 côté route).
        return f"Gabarit invalide : {exc}"
    return None


def send_templated_email(tenant, template_key: str, variables: dict, to_email: str) -> None:
    """Rend le modèle actif (override tenant ou défaut système) et l'envoie
    via le SMTP du tenant. Lève une exception si le SMTP n'est pas configuré
    ou si l'envoi échoue — à gérer par l'appelant (comme send_invitation_email)."""
    cfg = SmtpSetting.query.filter_by(tenant_id=tenant.id).first()
    if not cfg or not cfg.host or not cfg.from_address:
        raise RuntimeError("La configuration SMTP du tenant est incomplète (envoi d'email impossible).")

    subject, body_html = render_template(tenant.id, template_key, variables)

    msg = EmailMessage()
    msg["From"] = cfg.from_address
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_html, subtype="html")
    send_via_smtp(cfg, msg)
