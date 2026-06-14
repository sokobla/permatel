import uuid
from functools import wraps

from flask import g, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.models import Tenant, TenantUser
from app.utils.logger import auth_logger


def tenant_required(fn):
    """
    Décorateur pour les routes nécessitant un contexte de tenant actif.

    Ce décorateur vérifie que :
    1. Un token JWT valide est présent.
    2. Le token contient un claim 'tid' (tenant ID).
    3. L'utilisateur (identifié par 'sub') est bien un membre actif du tenant ('tid').

    Si tout est valide, il charge `g.user` et `g.tenant` pour un accès facile
    dans la vue.

    Sinon, il retourne une erreur 401, 403 ou 400.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            claims = get_jwt()

            tenant_id_str = claims.get("tid")
            if not tenant_id_str:
                auth_logger.warning("TENANT_REQUIRED_FAIL | reason=no_tid_in_jwt")
                return jsonify({
                    "error": "Accès non autorisé",
                    "message": "Aucun tenant actif n'est sélectionné dans le token."
                }), 401  # 401 Unauthorized car le token est incomplet pour cette ressource

            user_id = int(get_jwt_identity())

            try:
                tenant_id = uuid.UUID(tenant_id_str)
            except (ValueError, TypeError):
                auth_logger.error(f"TENANT_REQUIRED_FAIL | user_id={user_id} | reason=invalid_tid_format | tid='{tenant_id_str}'")
                return jsonify({"error": "Format du tenant ID invalide dans le token."}), 400

            # Vérification la plus importante : l'utilisateur appartient-il au tenant ?
            # On joint sur Tenant pour s'assurer que le tenant lui-même est actif.
            membership = TenantUser.query.join(Tenant).filter(
                TenantUser.user_id == user_id,
                TenantUser.tenant_id == tenant_id,
                TenantUser.is_active == True,
                Tenant.is_active == True
            ).first()

            if not membership:
                auth_logger.warning(f"TENANT_REQUIRED_FAIL | user_id={user_id} | tenant_id={tenant_id} | reason=not_a_member")
                return jsonify({
                    "error": "Accès refusé",
                    "message": "Vous n'êtes pas autorisé à accéder aux ressources de ce tenant."
                }), 403  # 403 Forbidden car l'utilisateur est authentifié mais n'a pas les droits

            # Charger le contexte dans flask.g pour la vue
            g.user = membership.user
            g.tenant = membership.tenant
            g.tenant_id = tenant_id

        except Exception as e:
            # Gère les erreurs de flask_jwt_extended (token expiré, invalide, etc.)
            # qui lèvent des exceptions spécifiques. La réponse est déjà formatée par l'extension.
            raise e

        return fn(*args, **kwargs)
    return wrapper