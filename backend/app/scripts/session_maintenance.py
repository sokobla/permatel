"""
Maintenance des sessions PERMATEL.

Deux opérations idempotentes, sûres à rejouer :
  1. Expiration des sessions ACTIVE inactives depuis plus de
     SESSION_INACTIVITY_TIMEOUT minutes  -> status=EXPIRED, session_end=now.
     (Les sessions PAUSED — pause téléphonique ESL — ne sont PAS touchées.)
  2. Purge des entrées de token_blocklist dont expires_at est dépassé
     (le token est de toute façon expiré côté JWT, l'entrée ne sert plus).

Utilisable :
  - via la CLI Flask :   flask sessions-sweep
  - via le script cron :  python -m app.scripts.session_maintenance  (ou scripts/sessions_sweep.py)
"""

from datetime import datetime, timedelta

from flask import current_app

from app.models.user_session import UserSession, SessionStatus
from app.models.token_blocklist import TokenBlocklist


def expire_inactive_sessions(db, timeout_minutes=None):
    """Passe en EXPIRED les sessions ACTIVE inactives au-delà du timeout."""
    if timeout_minutes is None:
        timeout_minutes = int(current_app.config.get("SESSION_INACTIVITY_TIMEOUT", 30))

    cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    now = datetime.utcnow()

    stale = (
        UserSession.query
        .filter(UserSession.status == SessionStatus.ACTIVE)
        .filter(UserSession.last_activity_at.isnot(None))
        .filter(UserSession.last_activity_at < cutoff)
        .all()
    )
    for s in stale:
        s.status = SessionStatus.EXPIRED
        s.session_end = now

    return len(stale)


def purge_expired_blocklist(db):
    """Supprime les JTI révoqués dont l'expiration JWT est dépassée."""
    deleted = (
        TokenBlocklist.query
        .filter(TokenBlocklist.expires_at < datetime.utcnow())
        .delete(synchronize_session=False)
    )
    return deleted or 0


def sweep_sessions(db, timeout_minutes=None):
    """
    Exécute les deux opérations de maintenance et committe.
    Retourne un dict de comptes : {expired, purged}.
    """
    expired = expire_inactive_sessions(db, timeout_minutes=timeout_minutes)
    purged = purge_expired_blocklist(db)
    db.session.commit()
    return {"expired": expired, "purged": purged}
