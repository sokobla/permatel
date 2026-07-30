"""
Expiration des jetons d'onboarding utilisateur PERMATEL.

Contrainte produit explicite : passé 24h sans complétion, le jeton
d'onboarding est révoqué (status=expired) ET le compte utilisateur est
désactivé (is_active=False) — jamais l'un sans l'autre.

Utilisable via la CLI Flask : flask onboarding-sweep

Note de précision : ce sweep tourne périodiquement (cron, ex. */15 min), pas
exactement à la seconde près des 24h — la fenêtre d'imprécision correspond à
l'intervalle du cron, acceptée comme la contrainte réelle plutôt qu'une
exécution "pile à l'heure" jamais garantie.
"""
from datetime import datetime

from app.models.user_token import UserToken, PURPOSE_ONBOARDING, STATUS_PENDING, STATUS_EXPIRED


def sweep_onboarding(db):
    """Expire les jetons d'onboarding `pending` dont expires_at est dépassé,
    désactive le compte utilisateur correspondant. Committe. Retourne un dict
    {"expired": int}."""
    expired_tokens = (
        UserToken.query
        .filter(UserToken.purpose == PURPOSE_ONBOARDING)
        .filter(UserToken.status == STATUS_PENDING)
        .filter(UserToken.expires_at < datetime.utcnow())
        .all()
    )
    for token in expired_tokens:
        token.status = STATUS_EXPIRED
        user = token.user
        user.onboarding_status = STATUS_EXPIRED
        user.is_active = False

    db.session.commit()
    return {"expired": len(expired_tokens)}
