"""
Blueprint d'authentification PERMATEL.

Endpoints :
  POST  /api/auth/login      — Login username/password → access + refresh tokens
  POST  /api/auth/refresh    — Renouvelle l'access token via le refresh token
  POST  /api/auth/logout     — Révoque les tokens + ferme la session
  GET   /api/auth/me         — Profil de l'utilisateur connecté
  GET   /api/auth/sessions   — Sessions actives de l'utilisateur courant
  POST  /api/auth/select-tenant — Sélectionne un tenant actif et génère de nouveaux tokens
"""
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from flask_cors import CORS
import uuid
from app import db
from app.models.audit_log import AuditAction, AuditLog
from app.models.token_blocklist import TokenBlocklist
from app.models.user import User
from app.models.tenant import Tenant
from app.models.tenant_user import TenantUser
from app.models.user_session import SessionStatus, UserSession
from app.utils.logger import auth_logger

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Appliquer CORS à tout le blueprint pour une gestion centralisée.
# supports_credentials=True est crucial pour que le navigateur envoie les cookies
# ou les headers d'authentification (comme le Bearer token JWT).
CORS(auth_bp, supports_credentials=True)


# ─────────────────────────────────────────────────────────────────────────── #
#  HELPERS PRIVÉS                                                             #
# ─────────────────────────────────────────────────────────────────────────── #

def _get_client_ip() -> str:
    """Récupère l'IP réelle du client (supporte les reverse proxies)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _get_user_agent() -> str:
    return request.headers.get("User-Agent", "unknown")[:500]


def _revoke_token(jti: str, token_type: str, user_id: int, expires_at: datetime) -> None:
    """Ajoute un JTI à la table token_blocklist (révocation immédiate)."""
    entry = TokenBlocklist(
        jti=jti,
        token_type=token_type,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.session.add(entry)


def _log_audit(user_id: int, event: str, details: dict, tenant_id: uuid.UUID | None = None) -> None:
    """
    Crée une entrée audit_log pour un événement d'authentification.
    """
    try:
        # Hypothèse: Le modèle AuditLog est mis à jour pour inclure tenant_id.
        # La structure ici (table_name, record_id...) peut différer de votre modèle final.
        entry = AuditLog(
            user_id=user_id,
            tenant_id=tenant_id,
            table_name="auth",
            record_id=user_id,
            action=AuditAction.CREATE,
            new_values={"event": event, **details},
        )
        db.session.add(entry)
    except Exception as exc:
        auth_logger.error(f"Échec écriture audit_log : {exc}")


def _check_inactivity(session: UserSession) -> bool:
    """
    Retourne True si la session a dépassé le timeout d'inactivité configuré.
    Met à jour le statut de la session en EXPIRED si c'est le cas.
    """
    timeout = current_app.config.get("SESSION_INACTIVITY_TIMEOUT", 30)
    if not session.last_activity_at:
        return False
    elapsed = (datetime.utcnow() - session.last_activity_at).total_seconds() / 60
    if elapsed > timeout:
        session.status = SessionStatus.EXPIRED
        session.session_end = datetime.utcnow()
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────── #
#  POST /api/auth/login                                                       #
# ─────────────────────────────────────────────────────────────────────────── #

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Authentifie un utilisateur par username + password.

    Body JSON requis :
        {
            "username": "jdupont",
            "password": "motdepasse123"
        }

    Réponse 200 :
        {
            "access_token":  "<jwt_access>",
            "refresh_token": "<jwt_refresh>",
            "session_id":    1,
            "tenants": [
                {"id": "uuid-tenant-1", "code": "CORE", "nom": "Tenant Principal"},
                {"id": "uuid-tenant-2", "code": "CLIENTA", "nom": "Client A"}
            ],
            "active_tenant_id": "uuid-tenant-1",
            "expires_in":    900,
            "user": {
                "id": 1,
                "username": "jdupont",
                "nom": "Dupont",
                "prenom": "Jean",
                "role": "PERMANENCIER",
                "email": "jdupont@permatel.ma",
                "is_active": true,
                "last_login_at": "2026-04-19T14:00:00"
            }
        }

    Erreurs :
        400 — Body manquant ou champs absents
        401 — Identifiants incorrects
        403 — Compte désactivé
    """
    ip         = _get_client_ip()
    user_agent = _get_user_agent()
    body       = request.get_json(silent=True)

    # ── Validation input ─────────────────────────────────────────────────── #
    if not body:
        return jsonify({"error": "Body JSON requis."}), 400

    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        return jsonify({
            "error": "Champs manquants.",
            "detail": "username et password sont obligatoires."
        }), 400
    
    print("------------------------------------")

    # ── Recherche utilisateur ─────────────────────────────────────────────── #
    user = User.query.filter(User.username.ilike(username)).first()

    if not user or not user.check_password(password):
        auth_logger.warning(
            f"LOGIN_FAILED | username={username} | ip={ip}"
        )
        if user:
            _log_audit(user.id, "LOGIN_FAILED", {"ip": ip, "reason": "bad_password"})
            db.session.commit()
        return jsonify({
            "error": "Identifiants incorrects.",
            "detail": "username ou password invalide."
        }), 401

    if not user.is_active:
        auth_logger.warning(
            f"LOGIN_BLOCKED | username={username} | ip={ip} | reason=inactive"
        )
        _log_audit(user.id, "LOGIN_BLOCKED", {"ip": ip, "reason": "account_inactive"})
        db.session.commit()
        return jsonify({
            "error": "Compte désactivé.",
            "detail": "Contactez un administrateur pour réactiver votre compte."
        }), 403

    # ── Création des tokens ───────────────────────────────────────────────── #
    # 1. Récupérer les tenants de l'utilisateur
    user_tenants = TenantUser.query.filter_by(user_id=user.id, is_active=True).join(Tenant).filter(Tenant.is_active==True).all()

    if not user_tenants:
        auth_logger.warning(f"LOGIN_BLOCKED | user_id={user.id} | reason=no_tenant_assigned")
        _log_audit(user.id, "LOGIN_BLOCKED", {"ip": ip, "reason": "no_tenant_assigned"})
        db.session.commit()
        return jsonify({"error": "Aucun tenant n'est assigné à cet utilisateur."}), 403

    tenants_list = [
        {"id": str(ut.tenant.id), "code": ut.tenant.code, "nom": ut.tenant.nom}
        for ut in user_tenants
    ]

    # 2. Déterminer le tenant actif (automatique si un seul tenant)
    active_tenant_id = None
    active_tenant_uuid = None
    if len(tenants_list) == 1:
        active_tenant_id = tenants_list[0]["id"]
        active_tenant_uuid = uuid.UUID(active_tenant_id)

    # 3. Créer les claims et les tokens
    additional_claims = {
        "role":     user.role.value,
        "username": user.username,
        "nom":      user.nom,
        "prenom":   user.prenom,
    }
    if active_tenant_id:
        additional_claims["tid"] = active_tenant_id

    refresh_token = create_refresh_token(
        identity=str(user.id),
        additional_claims=additional_claims,
    )
    refresh_decoded = decode_token(refresh_token)
    refresh_jti     = refresh_decoded["jti"]
    
    # 4. Créer l'access token en incluant le JTI du refresh token
    access_claims = {
        **additional_claims,
        "refresh_jti": refresh_jti,  # Lien vers la session
    }
    access_token  = create_access_token(
        identity=str(user.id),
        additional_claims=access_claims,
    )

    # Décode les tokens pour obtenir exp et autres données
    refresh_exp     = datetime.utcfromtimestamp(refresh_decoded["exp"])

    # Décode l'access token pour l'expires_in en secondes
    access_decoded  = decode_token(access_token)
    access_exp      = datetime.utcfromtimestamp(access_decoded["exp"])
    expires_in      = int((access_exp - datetime.utcnow()).total_seconds())

    # ── Création session ──────────────────────────────────────────────────── #
    session = UserSession(
        user_id          = user.id,
        jti              = refresh_jti,
        active_tenant_id = active_tenant_uuid,
        agent_login      = user.agent_login,
        station_extension= user.station_extension,
        ip_address       = ip,
        user_agent       = user_agent,
        session_start    = datetime.utcnow(),
        last_activity_at = datetime.utcnow(),
        status           = SessionStatus.ACTIVE,
    )
    db.session.add(session)

    # ── Mise à jour last_login_at ─────────────────────────────────────────── #
    user.last_login_at = datetime.utcnow()

    # ── Audit ─────────────────────────────────────────────────────────────── #
    _log_audit(user.id, "LOGIN_SUCCESS", {
        "ip":         ip,
        "user_agent": user_agent,
        "role":       user.role.value
    }, tenant_id=active_tenant_uuid)

    db.session.commit()

    auth_logger.info(
        f"LOGIN_SUCCESS | user_id={user.id} | username={user.username} "
        f"| role={user.role.value} | ip={ip} | session_id={session.id}"
    )

    return jsonify({
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "session_id":    session.id,
        "expires_in":    expires_in,
        "tenants":       tenants_list,
        "active_tenant_id": active_tenant_id,
        "user":          user.to_dict(),
    }), 200


# ─────────────────────────────────────────────────────────────────────────── #
#  POST /api/auth/select-tenant                                               #
# ─────────────────────────────────────────────────────────────────────────── #

@auth_bp.route("/select-tenant", methods=["POST"])
@jwt_required()
def select_tenant():
    """
    Permet à un utilisateur de sélectionner un tenant actif et de recevoir de nouveaux tokens.
    Le token JWT fourni doit être un access token valide.

    Body JSON requis :
        { "tenant_id": "uuid-of-the-tenant" }

    Réponse 200 :
        {
            "access_token": "<new_jwt_access>",
            "refresh_token": "<new_jwt_refresh>",
            "active_tenant_id": "uuid-of-the-tenant"
        }
    """
    body = request.get_json(silent=True)
    if not body or "tenant_id" not in body:
        return jsonify({"error": "Le champ 'tenant_id' est requis."}), 400

    tenant_id_str = body["tenant_id"]
    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except (ValueError, TypeError):
        return jsonify({"error": "Format de 'tenant_id' invalide."}), 400

    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    # --- Validation de l'appartenance au tenant ---
    membership = TenantUser.query.filter_by(user_id=user_id, tenant_id=tenant_id, is_active=True).first()
    if not membership or not membership.tenant.is_active:
        return jsonify({"error": "Accès à ce tenant non autorisé ou tenant inactif."}), 403

    # --- Création des nouveaux tokens avec le tenant_id ---
    additional_claims = {
        "role": user.role.value,
        "username": user.username,
        "nom": user.nom,
        "prenom": user.prenom,
        "tid": str(tenant_id)  # Ajout du tenant ID
    }

    new_refresh_token = create_refresh_token(identity=str(user.id), additional_claims=additional_claims)
    new_refresh_jti = decode_token(new_refresh_token)["jti"]

    access_claims = {**additional_claims, "refresh_jti": new_refresh_jti}
    new_access_token = create_access_token(identity=str(user.id), additional_claims=access_claims)

    # --- Mise à jour de la session existante ---
    # On retrouve la session via le refresh_jti du token d'origine
    original_claims = get_jwt()
    refresh_jti_from_original_token = original_claims.get("refresh_jti")
    session = None
    if refresh_jti_from_original_token:
        session = UserSession.query.filter_by(jti=refresh_jti_from_original_token).first()

    if session:
        session.jti = new_refresh_jti  # La session est maintenant liée au nouveau refresh token
        session.active_tenant_id = tenant_id
        session.last_activity_at = datetime.utcnow()

    _log_audit(user_id, "TENANT_SELECTED", {"tenant_id": str(tenant_id)}, tenant_id=tenant_id)
    db.session.commit()

    return jsonify({
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "active_tenant_id": str(tenant_id)
    }), 200


# ─────────────────────────────────────────────────────────────────────────── #
#  POST /api/auth/refresh                                                     #
# ─────────────────────────────────────────────────────────────────────────── #

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Renouvelle l'access token à partir d'un refresh token valide.
    Met à jour last_activity_at sur la session.
    Vérifie le timeout d'inactivité avant de renouveler.

    Header :
        Authorization: Bearer <refresh_token>

    Réponse 200 :
        {
            "access_token": "<nouveau_jwt>",
            "expires_in": 900
        }

    Erreurs :
        401 — Refresh token invalide, expiré ou révoqué
        403 — Session expirée par inactivité
    """
    claims  = get_jwt()
    user_id = int(get_jwt_identity())
    jti     = claims["jti"]
    ip      = _get_client_ip()

    # ── Vérification session ──────────────────────────────────────────────── #
    session = UserSession.query.filter_by(jti=jti).first()

    if not session:
        auth_logger.warning(
            f"REFRESH_FAILED | user_id={user_id} | jti={jti} | reason=session_not_found"
        )
        return jsonify({
            "error": "Session introuvable.",
            "detail": "Veuillez vous reconnecter."
        }), 401

    if session.status not in (SessionStatus.ACTIVE, SessionStatus.PAUSED):
        auth_logger.warning(
            f"REFRESH_FAILED | user_id={user_id} | session_id={session.id} "
            f"| reason=session_status_{session.status.value}"
        )
        return jsonify({
            "error": "Session terminée.",
            "detail": "Veuillez vous reconnecter."
        }), 401

    # ── Vérification timeout inactivité ──────────────────────────────────── #
    if _check_inactivity(session):
        _log_audit(user_id, "SESSION_EXPIRED_INACTIVITY", { # tenant_id is unknown here
            "session_id":    session.id,
            "ip":            ip,
            "last_activity": (
                session.last_activity_at.isoformat()
                if session.last_activity_at else None
            ),
        })
        db.session.commit()
        auth_logger.info(
            f"SESSION_EXPIRED_INACTIVITY | user_id={user_id} "
            f"| session_id={session.id} | ip={ip}"
        )
        return jsonify({
            "error": "Session expirée par inactivité.",
            "detail": f"Aucune activité depuis plus de "
                      f"{current_app.config.get('SESSION_INACTIVITY_TIMEOUT', 30)} minutes."
        }), 403

    # ── Récupération utilisateur ──────────────────────────────────────────── #
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return jsonify({"error": "Utilisateur introuvable ou désactivé."}), 401

    # ── Nouveau access token ──────────────────────────────────────────────── #
    additional_claims = {
        "role":     user.role.value,
        "username": user.username,
        "nom":      user.nom,
        "prenom":   user.prenom,
    }
    # On propage le tenant_id s'il est dans le refresh token
    if "tid" in claims:
        additional_claims["tid"] = claims["tid"]

    # On lie le nouvel access token à la session via le refresh_jti
    access_claims = {
        **additional_claims,
        "refresh_jti": jti,
    }
    new_access_token = create_access_token(
        identity=str(user.id),
        additional_claims=access_claims,
    )

    access_decoded = decode_token(new_access_token)
    access_exp     = datetime.utcfromtimestamp(access_decoded["exp"])
    expires_in     = int((access_exp - datetime.utcnow()).total_seconds())

    # ── Mise à jour last_activity_at ─────────────────────────────────────── #
    session.last_activity_at = datetime.utcnow()

    tid_from_claims = claims.get("tid")
    tenant_id_for_log = uuid.UUID(tid_from_claims) if tid_from_claims else None

    _log_audit(user_id, "TOKEN_REFRESHED", {"ip": ip, "session_id": session.id}, tenant_id=tenant_id_for_log)
    db.session.commit()

    auth_logger.info(
        f"TOKEN_REFRESHED | user_id={user_id} | session_id={session.id} | ip={ip}"
    )

    return jsonify({
        "access_token": new_access_token,
        "expires_in":   expires_in,
    }), 200


# ─────────────────────────────────────────────────────────────────────────── #
#  POST /api/auth/logout                                                      #
# ─────────────────────────────────────────────────────────────────────────── #

@auth_bp.route("/logout", methods=["POST"])
@jwt_required(verify_type=True)
def logout():
    """
    Révoque l'access token courant + le refresh token associé à la session.
    Ferme la session (status → ENDED).

    Flux d'exécution :
      1. Extraire JTI + claims de l'access token courant
      2. Vérifier que c'est un access token (pas un refresh token)
      3. Révoquer l'access token → TokenBlocklist
      4. Retrouver la session via le JTI du refresh token (stocké dans UserSession.jti)
      5. Révoquer le refresh token → TokenBlocklist
      6. Fermer la session → status=ENDED, session_end=now
      7. Écrire audit_log LOGOUT_SUCCESS
      8. Commit + réponse 200

    Header requis :
        Authorization: Bearer <access_token>

    Réponse 200 :
        { "message": "Déconnexion réussie." }

    Erreurs :
        401 — Token invalide ou expiré (géré automatiquement par @jwt_required)
        422 — Refresh token utilisé au lieu d'access token
    """
    claims  = get_jwt()
    user_id = int(get_jwt_identity())
    jti     = claims["jti"]                               # JTI de l'access token
    refresh_jti = claims.get("refresh_jti")               # JTI du refresh token (pour identifier la session)
    tid_from_claims = claims.get("tid")
    ip      = _get_client_ip()
    now     = datetime.utcnow()

    # Expiration de l'access token (pour stocker dans la blocklist)
    access_exp = datetime.utcfromtimestamp(claims["exp"])

    # ── Étape 1 : Révocation de l'access token ────────────────────────────── #
    # On vérifie qu'il n'est pas déjà révoqué (double-logout)
    already_revoked = TokenBlocklist.query.filter_by(jti=jti).first()
    if not already_revoked:
        _revoke_token(
            jti        = jti,
            token_type = "access",
            user_id    = user_id,
            expires_at = access_exp,
        )

    # ── Étape 2 : Recherche de la session active ──────────────────────────── #
    # Identifier la session par le refresh_jti stocké dans les claims de l'access token
    session = None
    if refresh_jti:
        session = UserSession.query.filter_by(jti=refresh_jti).first()
    
    # Fallback : si pas de refresh_jti (tokens anciens?), chercher la session la plus récente
    if not session:
        session = UserSession.query.filter_by(
            user_id=user_id,
            status=SessionStatus.ACTIVE,
        ).order_by(UserSession.session_start.desc()).first()

        # Fallback : chercher aussi en PAUSED (pause téléphonique ESL)
        if not session:
            session = UserSession.query.filter_by(
                user_id=user_id,
                status=SessionStatus.PAUSED,
            ).order_by(UserSession.session_start.desc()).first()

    # ── Étape 3 : Révocation du refresh token + fermeture session ─────────── #
    if session:
        # Révocation du refresh token via son JTI stocké dans la session
        if session.jti:
            refresh_already_revoked = TokenBlocklist.query.filter_by(
                jti=session.jti
            ).first()
            if not refresh_already_revoked:
                # Le refresh token expire selon la config (JWT_REFRESH_TOKEN_EXPIRES)
                from datetime import timedelta
                refresh_exp = now + current_app.config.get(
                    "JWT_REFRESH_TOKEN_EXPIRES",
                    timedelta(days=7),
                )
                _revoke_token(
                    jti        = session.jti,
                    token_type = "refresh",
                    user_id    = user_id,
                    expires_at = refresh_exp,
                )

        # Fermeture propre de la session
        session.status      = SessionStatus.ENDED
        session.session_end = now

    # ── Étape 4 : Audit log ───────────────────────────────────────────────── #
    tenant_id_for_log = uuid.UUID(tid_from_claims) if tid_from_claims else None
    _log_audit(user_id, "LOGOUT_SUCCESS", {
        "ip":         ip,
        "session_id": session.id if session else None,
        "jti":        jti,
    }, tenant_id=tenant_id_for_log)

    db.session.commit()

    auth_logger.info(
        f"LOGOUT_SUCCESS | user_id={user_id} "
        f"| session_id={session.id if session else 'none'} | ip={ip}"
    )

    return jsonify({"message": "Déconnexion réussie."}), 200


# ─────────────────────────────────────────────────────────────────────────── #
#  GET /api/auth/me                                                           #
# ─────────────────────────────────────────────────────────────────────────── #

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """
    Retourne le profil complet de l'utilisateur authentifié.

    Header :
        Authorization: Bearer <access_token>

    Réponse 200 :
        {
            "id": 1,
            "username": "jdupont",
            "nom": "Dupont",
            "prenom": "Jean",
            "email": "jdupont@permatel.ma",
            "role": "PERMANENCIER",
            "is_active": true,
            "last_login_at": "2026-04-19T14:00:00"
        }

    Erreurs :
        401 — Token invalide ou expiré
        404 — Utilisateur introuvable (ne devrait pas arriver)
    """
    user_id = int(get_jwt_identity())
    user    = User.query.get(user_id)

    if not user:
        return jsonify({"error": "Utilisateur introuvable."}), 404

    return jsonify(user.to_dict()), 200


# ─────────────────────────────────────────────────────────────────────────── #
#  GET /api/auth/sessions                                                     #
# ─────────────────────────────────────────────────────────────────────────── #

@auth_bp.route("/sessions", methods=["GET"])
@jwt_required()
def sessions():
    """
    Retourne la liste des sessions actives de l'utilisateur connecté.
    Utile pour afficher "Appareils connectés" dans l'interface.

    Header :
        Authorization: Bearer <access_token>

    Réponse 200 :
        {
            "sessions": [
                {
                    "id": 1,
                    "status": "ACTIVE",
                    "ip_address": "41.140.x.x",
                    "user_agent": "Mozilla/5.0...",
                    "session_start": "2026-04-19T14:00:00",
                    "last_activity_at": "2026-04-19T14:55:00"
                }
            ],
            "total": 1
        }
    """
    user_id = int(get_jwt_identity())
    active_sessions = UserSession.query.filter(
        UserSession.user_id == user_id,
        UserSession.status.in_([SessionStatus.ACTIVE, SessionStatus.PAUSED]),
    ).order_by(UserSession.session_start.desc()).all()

    return jsonify({
        "sessions": [
            {
                "id":               s.id,
                "status":           s.status.value,
                "ip_address":       s.ip_address,
                "user_agent":       s.user_agent,
                "session_start":    s.session_start.isoformat() if s.session_start else None,
                "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
            }
            for s in active_sessions
        ],
        "total": len(active_sessions),
    }), 200