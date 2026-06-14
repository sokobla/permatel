import os
import re
from urllib.parse import urlparse

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_REGEX = re.compile(r"^\+?[0-9]{9,15}$")
ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
ALLOWED_URL_SCHEMES = {"http", "https"}
CONTACT_TYPES = {"agent_securite", "autre"}


def is_valid_email(value):
    if not isinstance(value, str):
        return False
    return bool(EMAIL_REGEX.match(value.strip()))


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
