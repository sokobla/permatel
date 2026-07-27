"""
Anti-brute-force pour /api/auth/login.

Backend Redis (partagé entre tous les workers Gunicorn) quand `REDIS_URL` est
configuré ; à défaut, repli sur un compteur en mémoire par process (comportement
historique — suffisant en dev/tests, mais chaque worker a alors son propre
compteur en production multi-worker).

⚠ En production (Gunicorn multi-worker), `REDIS_URL` DOIT être configuré :
sans Redis, le seuil de verrouillage effectif est dilué par le nombre de
workers puisque chaque worker ne voit que ses propres tentatives.
"""

import logging
import threading
import time
import uuid

try:
    import redis as redis_lib
except ImportError:  # pragma: no cover - redis toujours présent en prod (requirements.txt)
    redis_lib = None

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
# Repli en mémoire : clé -> {"fails": [timestamps...], "locked_until": float|None}
_ATTEMPTS = {}

_redis_client = None
_redis_checked = False


def _cfg(app_config, key, default):
    try:
        return int(app_config.get(key, default))
    except (TypeError, ValueError):
        return default


def _key(username: str, ip: str) -> str:
    return f"{(username or '').strip().lower()}|{ip or 'unknown'}"


def _get_redis(app_config):
    """Retourne un client Redis connecté (mis en cache), ou None si non configuré/indisponible."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    url = app_config.get("REDIS_URL")
    if not url or redis_lib is None:
        _redis_client = None
        return None
    try:
        client = redis_lib.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        _redis_client = client
    except Exception as exc:  # noqa: BLE001 - dégradation volontaire vers le repli mémoire
        logger.warning("Redis anti-brute-force indisponible (%s) — repli sur compteur en mémoire.", exc)
        _redis_client = None
    return _redis_client


# ─────────────────────────────────────────────────────────────────────────────
#  Backend Redis
# ─────────────────────────────────────────────────────────────────────────────

def _redis_check_locked(r, key: str):
    lock_ttl = r.ttl(f"login_lock:{key}")
    if lock_ttl and lock_ttl > 0:
        return True, lock_ttl
    return False, 0


def _redis_register_failure(r, key: str, max_attempts: int, window: int, lockout: int):
    now = time.time()
    fails_key = f"login_fails:{key}"
    lock_key = f"login_lock:{key}"

    pipe = r.pipeline()
    pipe.zadd(fails_key, {f"{now}:{uuid.uuid4().hex}": now})
    pipe.zremrangebyscore(fails_key, 0, now - window)
    pipe.expire(fails_key, window)
    pipe.zcard(fails_key)
    *_, count = pipe.execute()

    if count >= max_attempts:
        r.set(lock_key, "1", ex=lockout)
        return True, lockout
    return False, 0


def _redis_reset(r, key: str):
    r.delete(f"login_fails:{key}", f"login_lock:{key}")


# ─────────────────────────────────────────────────────────────────────────────
#  Repli en mémoire (process unique — dev/tests, ou Redis indisponible)
# ─────────────────────────────────────────────────────────────────────────────

def _memory_check_locked(app_config, username: str, ip: str):
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
        rec["fails"] = [t for t in rec["fails"] if now - t < window]
        if not rec["fails"] and not locked_until:
            _ATTEMPTS.pop(key, None)
        return False, 0


def _memory_register_failure(app_config, username: str, ip: str):
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


def _memory_reset(username: str, ip: str):
    with _LOCK:
        _ATTEMPTS.pop(_key(username, ip), None)


# ─────────────────────────────────────────────────────────────────────────────
#  API publique (identique quel que soit le backend)
# ─────────────────────────────────────────────────────────────────────────────

def check_locked(app_config, username: str, ip: str):
    """Retourne (locked: bool, retry_after_seconds: int)."""
    r = _get_redis(app_config)
    if r is not None:
        try:
            return _redis_check_locked(r, _key(username, ip))
        except redis_lib.RedisError as exc:
            logger.warning("Erreur Redis (check_locked) : %s — repli mémoire.", exc)
    return _memory_check_locked(app_config, username, ip)


def register_failure(app_config, username: str, ip: str):
    """Enregistre un échec. Retourne (locked: bool, retry_after_seconds: int)."""
    r = _get_redis(app_config)
    if r is not None:
        try:
            max_attempts = _cfg(app_config, "LOGIN_MAX_ATTEMPTS", 5)
            window = _cfg(app_config, "LOGIN_WINDOW_MINUTES", 15) * 60
            lockout = _cfg(app_config, "LOGIN_LOCKOUT_MINUTES", 15) * 60
            return _redis_register_failure(r, _key(username, ip), max_attempts, window, lockout)
        except redis_lib.RedisError as exc:
            logger.warning("Erreur Redis (register_failure) : %s — repli mémoire.", exc)
    return _memory_register_failure(app_config, username, ip)


def reset(username: str, ip: str):
    """Réinitialise le compteur après une connexion réussie."""
    from flask import current_app

    r = _get_redis(current_app.config)
    if r is not None:
        try:
            _redis_reset(r, _key(username, ip))
            return
        except redis_lib.RedisError as exc:
            logger.warning("Erreur Redis (reset) : %s — repli mémoire.", exc)
    _memory_reset(username, ip)
