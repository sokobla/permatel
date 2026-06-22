import os
import re
from urllib.parse import urlparse

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_REGEX = re.compile(r"^\+?[0-9]{9,15}$")
ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
ALLOWED_URL_SCHEMES = {"http", "https"}
CONTACT_TYPES = {"agent_securite", "autre"}

# Politique de mot de passe — NIST 800-63B : on privilégie la LONGUEUR, sans
# règles de composition imposées. Source unique pour TOUS les points d'entrée
# (création, réinitialisation, acceptation d'invitation, CLI super-admin).
PASSWORD_MIN_LENGTH = 12


def is_valid_email(value):
    if not isinstance(value, str):
        return False
    return bool(EMAIL_REGEX.match(value.strip()))


def email_error(value):
    """Message d'erreur si l'email (non vide) est invalide, sinon None."""
    if value and not is_valid_email(value):
        return "Format d'email invalide."
    return None


def password_error(value):
    """Message d'erreur si le mot de passe est trop court, sinon None."""
    if not value or len(value) < PASSWORD_MIN_LENGTH:
        return f"Le mot de passe doit comporter au moins {PASSWORD_MIN_LENGTH} caractères."
    return None


def is_valid_phone(value):
    if not isinstance(value, str):
        return False
    return bool(PHONE_REGEX.match(value.strip()))


def is_valid_avatar_url(value):
    if not isinstance(value, str) or not value.strip():
        return False

    value = value.strip()
    if value.startswith("/uploads/"):
        _, ext = os.path.splitext(value)
        return ext.lower() in ALLOWED_AVATAR_EXTENSIONS

    parsed = urlparse(value)
    if parsed.scheme not in ALLOWED_URL_SCHEMES or not parsed.netloc:
        return False

    _, ext = os.path.splitext(parsed.path)
    return ext.lower() in ALLOWED_AVATAR_EXTENSIONS


def is_valid_contact_type(value):
    if not isinstance(value, str):
        return False
    return value.strip() in CONTACT_TYPES
