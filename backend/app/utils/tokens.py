"""
Génération/hash de jetons opaques à usage unique — utilisé par les invitations
tenant, l'onboarding utilisateur et la réinitialisation de mot de passe.

Le jeton clair n'est JAMAIS stocké en base, seul son hash SHA-256 l'est
(comparaison lors de la validation, jamais de déchiffrement).
"""
import hashlib
import secrets


def generate_token() -> tuple[str, str]:
    """Retourne (token_clair, token_hash). Seul le hash est stocké."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
