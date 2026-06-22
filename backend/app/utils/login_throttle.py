"""
Anti-brute-force pour /api/auth/login — sans dépendance externe.

Compteur en mémoire par clé (username + IP) avec fenêtre glissante et
verrouillage temporaire après trop d'échecs.

⚠ Portée : process unique. En déploiement multi-worker (gunicorn -w N), chaque
worker a son propre compteur ; pour une protection stricte en production,
remplacer le backend par Redis (même interface : is_locked / register_failure /
reset). Suffisant pour un déploiement mono-process et déjà efficace en mitigation.
"""

import threading
import time

_LOCK = threading.Lock()
# clé -> {"fails": [timestamps...], "locked_until": float|None}
_ATTEMPTS = {}


def _cfg(app_config, key, default):
    try:
        return int(app_config.get(key, default))
    except (TypeError, ValueError):
        return default


def _key(username: str, ip: str) -> str:
    return f"{(username or '').strip().lower()}|{ip or 'unknown'}"


def check_locked(app_config, username: str, ip: str):
    """
    Retourne (locked: bool, retry_after_seconds: int).
    Purge au passage les échecs hors fenêtre.
    """
    window = _cfg(app_config, "LOGIN_WINDOW_MINUTES", 15) * 60
    now = time.time()
    key = _key(username, ip)
    with _LOCK:
        rec = _ATTEMPTS.get(key)
        if not rec:
            return False, 0
        locked_until = rec.get("locked_until")
        if locked_until and locked_until > now:
            return True, int(locked_until - now)
        # Fenêtre expirée : nettoyage
        rec["fails"] = [t for t in rec["fails"] if now - t < window]
        if not rec["fails"] and not locked_until:
            _ATTEMPTS.pop(key, None)
        return False, 0


def register_failure(app_config, username: str, ip: str):
    """
    Enregistre un échec. Retourne (locked: bool, retry_after_seconds: int)
    si le seuil est atteint et que le verrou vient d'être posé.
    """
    max_attempts = _cfg(app_config, "LOGIN_MAX_ATTEMPTS", 5)
    window = _cfg(app_config, "LOGIN_WINDOW_MINUTES", 15) * 60
    lockout = _cfg(app_config, "LOGIN_LOCKOUT_MINUTES", 15) * 60
    now = time.time()
    key = _key(username, ip)
    with _LOCK:
        rec = _ATTEMPTS.setdefault(key, {"fails": [], "locked_until": None})
        rec["fails"] = [t for t in rec["fails"] if now - t < window]
        rec["fails"].append(now)
        if len(rec["fails"]) >= max_attempts:
            rec["locked_until"] = now + lockout
            return True, lockout
        return False, 0


def reset(username: str, ip: str):
    """Réinitialise le compteur après une connexion réussie."""
    with _LOCK:
        _ATTEMPTS.pop(_key(username, ip), None)
