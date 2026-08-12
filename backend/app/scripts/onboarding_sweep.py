"""
Expiration des jetons d'onboarding utilisateur PERMATEL.

Contrainte produit explicite : passé 24h sans complétion, le jeton
d'onboarding est révoqué (status=expired) et, pour une invitation INITIALE
(`token.deactivate_on_expiry=True` — l'utilisateur n'a encore aucun mot de
passe utilisable), le compte est désactivé (is_active=False). Décision
produit du 31/07 : un renvoi vers un utilisateur EXISTANT déjà actif
(`deactivate_on_expiry=False`, cf. `POST /users/<id>/onboarding/send`) ne
désactive JAMAIS le compte à l'expiration — seul le jeton expire, sans
effet de bord sur un compte qui fonctionnait déjà.

Utilisable via la CLI Flask : flask onboarding-sweep

Note de précision : ce sweep tourne périodiquement (cron, ex. */15 min), pas
exactement à la seconde près des 24h — la fenêtre d'imprécision correspond à
l'intervalle du cron, acceptée comme la contrainte réelle plutôt qu'une
exécution "pile à l'heure" jamais garantie.
"""
from datetime import datetime
from app.utils.time import utcnow

from app.models.user_token import UserToken, PURPOSE_ONBOARDING, STATUS_PENDING, STATUS_EXPIRED


def sweep_onboarding(db):
    """Expire les jetons d'onboarding `pending` dont expires_at est dépassé,
    désactive le compte utilisateur correspondant. Committe. Retourne un dict
    {"expired": int}."""
    expired_tokens = (
        UserToken.query
        .filter(UserToken.purpose == PURPOSE_ONBOARDING)
        .filter(UserToken.status == STATUS_PENDING)
        .filter(UserToken.expires_at < utcnow())
        .all()
    )
    for token in expired_tokens:
        token.status = STATUS_EXPIRED
        user = token.user
        user.onboarding_status = STATUS_EXPIRED
        if token.deactivate_on_expiry:
            user.is_active = False

    db.session.commit()
    return {"expired": len(expired_tokens)}
