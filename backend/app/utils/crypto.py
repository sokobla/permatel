"""
Chiffrement réversible de secrets applicatifs (ex. mot de passe SMTP).

Utilise Fernet (AES-128 CBC + HMAC). La clé est dérivée de
SETTINGS_ENCRYPTION_KEY (ou, à défaut, JWT_SECRET_KEY) par SHA-256.

Les valeurs chiffrées sont préfixées par `enc::` pour distinguer les anciennes
valeurs en clair (rétro-compatibilité / migration douce).
"""
import base64
import hashlib

from flask import current_app
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import TypeDecorator, Text

_PREFIX = "enc::"


def fernet_from_secret(secret: str) -> Fernet:
    """Construit un Fernet à partir d'un secret arbitraire (même dérivation SHA-256)."""
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def _fernet():
    secret = (
        current_app.config.get("SETTINGS_ENCRYPTION_KEY")
        or current_app.config.get("JWT_SECRET_KEY")
        or "change-me"
    )
    return fernet_from_secret(secret)


def decrypt_secret_with(value, fernet):
    """Déchiffre une chaîne avec un Fernet donné (ex. ancienne clé). Legacy clair inchangé."""
    if not value:
        return value
    if not value.startswith(_PREFIX):
        return value
    try:
        return fernet.decrypt(value[len(_PREFIX):].encode()).decode()
    except InvalidToken:
        return None


def decrypt_bytes_with(data, fernet):
    """Déchiffre des octets avec un Fernet donné. Legacy (sans préfixe) inchangé."""
    if not data or not data.startswith(_BIN_PREFIX):
        return data
    try:
        return fernet.decrypt(data[len(_BIN_PREFIX):])
    except InvalidToken:
        return data


def encrypt_secret(plain):
    """Chiffre une chaîne. Renvoie None/'' tels quels, idempotent si déjà chiffré."""
    if not plain:
        return plain
    if isinstance(plain, str) and plain.startswith(_PREFIX):
        return plain
    token = _fernet().encrypt(plain.encode()).decode()
    return _PREFIX + token


def decrypt_secret(value):
    """Déchiffre une valeur. Renvoie les anciennes valeurs en clair inchangées."""
    if not value:
        return value
    if not value.startswith(_PREFIX):
        return value  # legacy : stocké en clair avant chiffrement
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode()).decode()
    except InvalidToken:
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Chiffrement de fichiers (pièces jointes)
# ─────────────────────────────────────────────────────────────────────────────
_BIN_PREFIX = b"ENC1"


def encrypt_bytes(data: bytes) -> bytes:
    """Chiffre des octets (préfixe de détection ENC1)."""
    if data is None:
        return data
    return _BIN_PREFIX + _fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    """Déchiffre des octets ; renvoie tels quels les fichiers legacy en clair."""
    if not data or not data.startswith(_BIN_PREFIX):
        return data
    try:
        return _fernet().decrypt(data[len(_BIN_PREFIX):])
    except InvalidToken:
        return data


# ─────────────────────────────────────────────────────────────────────────────
#  Type SQLAlchemy : colonne texte chiffrée au repos (transparent)
# ─────────────────────────────────────────────────────────────────────────────
class EncryptedText(TypeDecorator):
    """Colonne Text chiffrée à l'écriture, déchiffrée à la lecture (Fernet)."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_secret(value) if value is not None else value

    def process_result_value(self, value, dialect):
        return decrypt_secret(value) if value is not None else value
