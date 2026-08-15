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
from app.utils.time import utcnow, utcfromtimestamp

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
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash
import uuid
from app import db
from app.models.audit_log import AuditAction, AuditLog
from app.models.token_blocklist import TokenBlocklist
from app.models.user import User, UserRole
from app.models.tenant import Tenant
from app.models.tenant_user import TenantUser, MEMBERSHIP_ADMIN
from app.models.user_session import SessionStatus, UserSession
from app.models.telephony_event import TelephonyEvent
from app.models.user_token import (
    UserToken, PURPOSE_PASSWORD_RESET, PASSWORD_RESET_TTL,
    STATUS_PENDING, STATUS_COMPLETED, STATUS_EXPIRED,
)
from app.utils.auth import role_required
from app.utils.csv_export import build_csv_response, MAX_EXPORT_ROWS
from app.utils.email_templates import build_reset_url, send_templated_email
from app.utils.geoip import lookup_country_code
from app.utils.logger import auth_logger
from app.utils.login_throttle import check_locked, register_failure, reset as reset_login_throttle
from app.utils.tokens import generate_token, hash_token
from app.utils.validators import password_error
from app.services.tenant_features import tenant_features

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _parse_monitoring_datetime(value):
    """Convertit une string date/datetime en objet datetime Python.
    Accepte : 'YYYY-MM-DD', 'YYYY-MM-DDTHH:MM', 'YYYY-MM-DDTHH:MM:SS'.
    Retourne None si la valeur est absente ou non parseable.
    """
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except (ValueError, TypeError):
            pass
    return None

# Appliquer CORS à tout le blueprint pour une gestion centralisée.
# supports_credentials=True est crucial pour que le navigateur envoie les cookies
# ou les headers d'authentification (comme le Bearer token JWT).
CORS(auth_bp, supports_credentials=True)

# Hash factice utilisé pour égaliser le temps de réponse du login quand
# l'utilisateur n'existe pas (mitigation de l'énumération de comptes par
# canal auxiliaire temporel — vérifier un hash factice coûte le même temps
# qu'une vérification de mot de passe réelle).
_DUMMY_PASSWORD_HASH = generate_password_hash(
    "dummy-password-permatel", method="pbkdf2:sha256:600000"
)


# ─────────────────────────────────────────────────────────────────────────── #
#  HELPERS PRIVÉS                                                             #
# ─────────────────────────────────────────────────────────────────────────── #

def _tenant_brief(t: Tenant) -> dict:
    """Représentation légère d'un tenant pour le frontend (sélection/switch)."""
    return {"id": str(t.id), "code": t.code, "nom": t.nom, "logo_url": t.logo_url}


def _is_tenant_admin(user: User, tenant_id) -> bool:
    """Capacité d'administration du tenant : super-admin global, ou membership 'admin'."""
    if user.role == UserRole.ADMIN:
        return True
    m = TenantUser.query.filter_by(user_id=user.id, tenant_id=tenant_id, is_active=True).first()
    return bool(m and m.membership_role == MEMBERSHIP_ADMIN)


def _accessible_tenants(user: User):
    """
    Tenants accessibles par l'utilisateur :
      - super-admin global (role ADMIN) : tous les tenants actifs ;
      - utilisateur standard : ses appartenances actives (sur tenant actif).
    """
    if user.role == UserRole.ADMIN:
        return Tenant.query.filter_by(is_active=True).order_by(Tenant.nom).all()
    memberships = (
        TenantUser.query.filter_by(user_id=user.id, is_active=True)
        .join(Tenant).filter(Tenant.is_active == True)
        .all()
    )
    return [m.tenant for m in memberships]


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


def _revoke_all_active_sessions(user_id: int) -> list:
    """Invalide immédiatement toutes les sessions ACTIVE d'un utilisateur —
    même mécanique que revoke_session() (blocklist du refresh token, statut
    REVOKED) — déclenchée ici par une réinitialisation de mot de passe plutôt
    qu'une révocation manuelle en Supervision. Un mot de passe qu'on vient de
    réinitialiser (souvent parce qu'il a fuité) ne doit laisser aucune
    session ouverte derrière lui, pas seulement empêcher les futures
    connexions.

    Retourne la liste des `UserSession` révoquées (15/08, ajouté pour que
    l'appelant puisse déclencher le dispatch PBX agent_logout après son
    propre commit — cf. `notify_pbx_agent_logout`). Seul appelant à ce
    jour : `reset_password()`."""
    from datetime import timedelta

    now = utcnow()
    sessions = UserSession.query.filter_by(user_id=user_id, status=SessionStatus.ACTIVE).all()
    for session in sessions:
        if session.jti and not TokenBlocklist.query.filter_by(jti=session.jti).first():
            refresh_exp = now + current_app.config.get("JWT_REFRESH_TOKEN_EXPIRES", timedelta(days=1))
            _revoke_token(jti=session.jti, token_type="refresh", user_id=user_id, expires_at=refresh_exp)
        session.status = SessionStatus.REVOKED
        session.session_end = now
    return sessions


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
    except (TypeError, SQLAlchemyError) as exc:
        auth_logger.error(f"Échec écriture audit_log : {exc}")


def _check_inactivity(session: UserSession) -> bool:
    """
    Retourne True si la session a dépassé le timeout d'inactivité configuré.
    Met à jour le statut de la session en EXPIRED si c'est le cas.
    """
    timeout = current_app.config.get("SESSION_INACTIVITY_TIMEOUT", 30)
    if not session.last_activity_at:
        return False
    elapsed = (utcnow() - session.last_activity_at).total_seconds() / 60
    if elapsed > timeout:
        session.status = SessionStatus.EXPIRED
        session.session_end = utcnow()
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

    # ── Anti-brute-force : verrouillage temporaire ────────────────────────── #
    locked, retry_after = check_locked(current_app.config, username, ip)
    if locked:
        auth_logger.warning(
            f"LOGIN_LOCKED | username={username} | ip={ip} | retry_after={retry_after}s"
        )
        resp = jsonify({
            "error": "Trop de tentatives échouées.",
            "detail": f"Compte temporairement verrouillé. Réessayez dans {retry_after // 60 + 1} minute(s).",
            "retry_after": retry_after,
        })
        resp.headers["Retry-After"] = str(retry_after)
        return resp, 429

    # ── Recherche utilisateur (par username OU email — username = email) ───── #
    # Comparaison exacte insensible à la casse (pas de ilike() sur une entrée
    # utilisateur non échappée : %/_ y seraient interprétés comme des jokers SQL).
    username_lower = username.lower()
    user = User.query.filter(
        db.or_(
            func.lower(User.username) == username_lower,
            func.lower(User.email) == username_lower,
        )
    ).first()

    if user:
        password_valid = user.check_password(password)
    else:
        # Vérification à temps constant : exécute quand même un hachage pour
        # que la réponse ne soit pas mesurablement plus rapide qu'en cas de
        # mauvais mot de passe sur un compte existant.
        check_password_hash(_DUMMY_PASSWORD_HASH, password)
        password_valid = False

    if not user or not password_valid:
        locked_now, _retry = register_failure(current_app.config, username, ip)
        auth_logger.warning(
            f"LOGIN_FAILED | username={username} | ip={ip}"
        )
        if user:
            _log_audit(user.id, "LOGIN_FAILED", {"ip": ip, "reason": "bad_password"})
            if locked_now:
                _log_audit(user.id, "LOGIN_LOCKED", {"ip": ip})
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

    # Authentification réussie : réinitialiser le compteur d'échecs
    reset_login_throttle(username, ip)

    # ── Création des tokens ───────────────────────────────────────────────── #
    # 1. Récupérer les tenants accessibles (admin = tous ; standard = appartenances)
    is_super_admin = user.role == UserRole.ADMIN
    accessible = _accessible_tenants(user)

    # Un utilisateur standard sans aucun tenant ne peut pas entrer.
    # (Le super-admin global, lui, accède à la plateforme même sans appartenance.)
    if not accessible and not is_super_admin:
        auth_logger.warning(f"LOGIN_BLOCKED | user_id={user.id} | reason=no_tenant_assigned")
        _log_audit(user.id, "LOGIN_BLOCKED", {"ip": ip, "reason": "no_tenant_assigned"})
        db.session.commit()
        return jsonify({"error": "Aucun tenant n'est assigné à cet utilisateur."}), 403

    tenants_list = [_tenant_brief(t) for t in accessible]

    # 2. Déterminer le tenant actif :
    #    - standard avec 1 seul tenant → sélection automatique (bypass de l'écran) ;
    #    - standard avec ≥2 tenants → sélection requise côté client ;
    #    - super-admin → jamais d'auto-sélection (doit choisir son contexte de travail).
    active_tenant_id = None
    active_tenant_uuid = None
    if not is_super_admin and len(tenants_list) == 1:
        active_tenant_id = tenants_list[0]["id"]
        active_tenant_uuid = uuid.UUID(active_tenant_id)

    # 3. Créer les claims et les tokens
    additional_claims = {
        "role":     user.role.value,
        "username": user.username,
        "nom":      user.nom,
        "prenom":   user.prenom,
    }
    is_tenant_admin_resp = is_super_admin
    if active_tenant_id:
        additional_claims["tid"] = active_tenant_id
        is_tenant_admin_resp = _is_tenant_admin(user, active_tenant_uuid)
        additional_claims["tenant_admin"] = is_tenant_admin_resp

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
    refresh_exp     = utcfromtimestamp(refresh_decoded["exp"])

    # Décode l'access token pour l'expires_in en secondes
    access_decoded  = decode_token(access_token)
    access_exp      = utcfromtimestamp(access_decoded["exp"])
    expires_in      = int((access_exp - utcnow()).total_seconds())

    # ── Création session ──────────────────────────────────────────────────── #
    session = UserSession(
        user_id          = user.id,
        jti              = refresh_jti,
        active_tenant_id = active_tenant_uuid,
        agent_login      = user.agent_login,
        station_extension= user.station_extension,
        ip_address       = ip,
        user_agent       = user_agent,
        session_start    = utcnow(),
        last_activity_at = utcnow(),
        status           = SessionStatus.ACTIVE,
    )
    db.session.add(session)

    # ── Mise à jour last_login_at ─────────────────────────────────────────── #
    user.last_login_at = utcnow()

    # ── Audit ─────────────────────────────────────────────────────────────── #
    _log_audit(user.id, "LOGIN_SUCCESS", {
        "ip":         ip,
        "user_agent": user_agent,
        "role":       user.role.value
    }, tenant_id=active_tenant_uuid)

    db.session.commit()

    # Exécution à distance ESL (13/08) : au login PERMATEL, si l'utilisateur
    # est un agent connu côté téléphonie, déclenche le job "agent_login"
    # (statut FusionPBX "On Break" + pause_code="0" par défaut, cf.
    # ESLAdapter.execute_job). `user.agent_login` déjà chargé sur l'objet ORM
    # (utilisé ligne 383), aucune requête supplémentaire. Best-effort : ne
    # doit jamais faire échouer le login lui-même.
    if user.agent_login and active_tenant_uuid:
        try:
            from app.routes.telephony import _dispatch_pbx_job, _record_and_broadcast_agent_status_event
            _dispatch_pbx_job(active_tenant_uuid, "agent_login", user.agent_login)
            # Persiste/diffuse tout de suite (correctif 14/08, même motif
            # que set_my_agent_status) : sinon le statut "On Break" implicite
            # du login n'apparaît nulle part tant que le round-trip
            # connecteur/PBX n'a pas confirmé. `session` = l'objet tout juste
            # créé ci-dessus (ligne ~379) : synchronise UserSession.status en
            # parallèle (PAUSED, cf. suivi des temps de login/pause du 14/08).
            _record_and_broadcast_agent_status_event(
                active_tenant_uuid, user.agent_login, "On Break", "0", session=session,
            )
        except Exception:  # noqa: BLE001
            auth_logger.warning(
                f"agent_login PBX dispatch échoué | user_id={user.id} | agent_login={user.agent_login}",
                exc_info=True,
            )

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
        "is_global_admin": is_super_admin,
        "is_tenant_admin": is_tenant_admin_resp,
        "features":      tenant_features(db.session.get(Tenant, active_tenant_uuid)) if active_tenant_uuid else None,
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
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return jsonify({"error": "Utilisateur introuvable ou désactivé."}), 401

    # --- Autorisation sur le tenant cible ---
    if user.role == UserRole.ADMIN:
        # Super-admin : tout tenant actif, sans appartenance.
        tenant = Tenant.query.filter_by(id=tenant_id, is_active=True).first()
        if not tenant:
            return jsonify({"error": "Tenant introuvable ou inactif."}), 404
    else:
        membership = TenantUser.query.filter_by(user_id=user_id, tenant_id=tenant_id, is_active=True).first()
        if not membership or not membership.tenant.is_active:
            return jsonify({"error": "Accès à ce tenant non autorisé ou tenant inactif."}), 403

    # --- Création des nouveaux tokens avec le tenant_id ---
    tenant_admin = _is_tenant_admin(user, tenant_id)
    additional_claims = {
        "role": user.role.value,
        "username": user.username,
        "nom": user.nom,
        "prenom": user.prenom,
        "tid": str(tenant_id),  # Ajout du tenant ID
        "tenant_admin": tenant_admin,
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
        session.last_activity_at = utcnow()

    _log_audit(user_id, "TENANT_SELECTED", {"tenant_id": str(tenant_id)}, tenant_id=tenant_id)
    db.session.commit()

    return jsonify({
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "active_tenant_id": str(tenant_id),
        "is_tenant_admin": tenant_admin,
        "features": tenant_features(db.session.get(Tenant, tenant_id)),
    }), 200


# ─────────────────────────────────────────────────────────────────────────── #
#  GET /api/auth/tenants  (liste des tenants accessibles — pour switch/sélection) #
# ─────────────────────────────────────────────────────────────────────────── #

@auth_bp.route("/tenants", methods=["GET"])
@jwt_required()
def my_tenants():
    """
    Liste les tenants accessibles par l'utilisateur courant.
      - super-admin global : tous les tenants actifs ;
      - utilisateur standard : ses appartenances actives.

    Réponse 200 : { "tenants": [...], "is_global_admin": bool }
    """
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return jsonify({"error": "Utilisateur introuvable ou désactivé."}), 401

    tenants = _accessible_tenants(user)
    return jsonify({
        "tenants": [_tenant_brief(t) for t in tenants],
        "is_global_admin": user.role == UserRole.ADMIN,
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
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return jsonify({"error": "Utilisateur introuvable ou désactivé."}), 401

    # ── Nouveau access token ──────────────────────────────────────────────── #
    additional_claims = {
        "role":     user.role.value,
        "username": user.username,
        "nom":      user.nom,
        "prenom":   user.prenom,
    }
    # On propage le tenant_id (et la capacité d'admin tenant) s'ils sont dans le refresh token
    if "tid" in claims:
        additional_claims["tid"] = claims["tid"]
    if "tenant_admin" in claims:
        additional_claims["tenant_admin"] = claims["tenant_admin"]

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
    access_exp     = utcfromtimestamp(access_decoded["exp"])
    expires_in     = int((access_exp - utcnow()).total_seconds())

    # ── Mise à jour last_activity_at ─────────────────────────────────────── #
    session.last_activity_at = utcnow()

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
    now     = utcnow()

    # Expiration de l'access token (pour stocker dans la blocklist)
    access_exp = utcfromtimestamp(claims["exp"])

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
                    timedelta(days=1),
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

    # Exécution à distance ESL (13/08) : au logout PERMATEL, si la session
    # fermée porte un agent PBX, déclenche le job "agent_logout" (statut
    # FusionPBX "Logged Out"). `session.agent_login` déjà chargé sur l'objet
    # `UserSession` en cours de fermeture — pas de requête `User`
    # supplémentaire. Best-effort : ne doit jamais faire échouer le logout.
    if session and session.agent_login and tenant_id_for_log:
        try:
            from app.routes.telephony import _dispatch_pbx_job, _record_and_broadcast_agent_status_event
            _dispatch_pbx_job(tenant_id_for_log, "agent_logout", session.agent_login)
            # Correctif 14/08, même motif qu'au login : persiste/diffuse
            # tout de suite sans attendre la confirmation PBX. `session` est
            # déjà ENDED à ce point (statut posé plus haut, avant le commit)
            # — no-op sur .status côté _record_and_broadcast_agent_status_event,
            # mais stamp quand même user_session_id sur l'événement pour
            # l'historique (suivi des temps de login/pause du 14/08).
            _record_and_broadcast_agent_status_event(
                tenant_id_for_log, session.agent_login, "Logged Out", session=session,
            )
        except Exception:  # noqa: BLE001
            auth_logger.warning(
                f"agent_logout PBX dispatch échoué | user_id={user_id} | agent_login={session.agent_login}",
                exc_info=True,
            )

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
    user    = db.session.get(User, user_id)

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


# ─────────────────────────────────────────────────────────────────────────── #
#  GET /api/auth/sessions/monitoring   (supervision — STAFF, tenant-scoped)    #
# ─────────────────────────────────────────────────────────────────────────── #

def _session_status_durations(session, now=None):
    """Minutes actif/pause/déconnecté-PBX pour une session (14/08, suivi des
    temps de login/pause) — reconstruites à partir de l'historique
    `TelephonyEvent(user_session_id=session.id, event_type=
    'CALLCENTER_AGENT_STATE_CHANGE')`, désormais alimenté en parallèle de
    `UserSession.status` (cf. `_record_and_broadcast_agent_status_event`,
    `app/routes/telephony.py`). Chaque intervalle est imputé au statut de
    l'événement qui l'OUVRE ; le segment final est borné à
    `session.session_end` (session terminée) ou `now` (session encore
    ouverte). Bucketing aligné sur `_normalize_agent_presence`
    (`app/routes/telephony.py:1364`) : Available→actif, On Break→pause,
    Logged Out/statut inconnu→déconnecté. Sans historique d'événements
    (session antérieure à ce chantier, ou jamais passée par un changement de
    statut explicite), toute la durée de la session est comptée comme
    active — comportement historique inchangé, pour ne pas fausser
    rétroactivement les sessions déjà closes."""
    from app.routes.telephony import _AGENT_PRESENCE_AWAY, _AGENT_PRESENCE_ONLINE

    now = now or utcnow()
    end = session.session_end or now
    totals = {"active_min": 0.0, "pause_min": 0.0, "offline_min": 0.0}
    if not session.session_start or end <= session.session_start:
        return totals

    events = (
        TelephonyEvent.query
        .filter_by(user_session_id=session.id, event_type="CALLCENTER_AGENT_STATE_CHANGE")
        .order_by(TelephonyEvent.created_at)
        .all()
    )
    if not events:
        totals["active_min"] = (end - session.session_start).total_seconds() / 60
        return totals

    def _bucket(raw_status):
        key = (raw_status or "").strip().lower()
        if key in _AGENT_PRESENCE_ONLINE:
            return "active_min"
        if key in _AGENT_PRESENCE_AWAY:
            return "pause_min"
        return "offline_min"

    # Segment avant le premier événement connu — normalement quasi nul :
    # login() crée son événement "On Break" dans la même transaction que la
    # session (cf. app/routes/auth.py::login()). Compté actif par défaut,
    # cohérent avec le repli "sans historique" ci-dessus.
    cursor = session.session_start
    current_bucket = "active_min"
    for event in events:
        ts = min(event.created_at, end)
        if ts > cursor:
            totals[current_bucket] += (ts - cursor).total_seconds() / 60
        cursor = ts
        current_bucket = _bucket(event.agent_status)
        if cursor >= end:
            break

    if cursor < end:
        totals[current_bucket] += (end - cursor).total_seconds() / 60

    return totals


def _filtered_sessions_query(tenant_uuid):
    scope = request.args.get("status", "live")
    query = UserSession.query.filter(UserSession.active_tenant_id == tenant_uuid)
    if scope != "all":
        query = query.filter(
            UserSession.status.in_([SessionStatus.ACTIVE, SessionStatus.PAUSED])
        )
    if from_val := request.args.get("from"):
        if dt_from := _parse_monitoring_datetime(from_val):
            query = query.filter(UserSession.session_start >= dt_from)
    if to_val := request.args.get("to"):
        if dt_to := _parse_monitoring_datetime(to_val):
            query = query.filter(UserSession.session_start <= dt_to)
    return query.order_by(UserSession.last_activity_at.desc().nullslast())


def _serialize_session_row(s, caller_refresh_jti):
    u = s.user
    durations = _session_status_durations(s)
    return {
        "id":               s.id,
        "user_id":          s.user_id,
        "username":         u.username if u else None,
        "full_name":        f"{(u.prenom or '').strip()} {(u.nom or '').strip()}".strip() if u else None,
        "role":             u.role.value if u and u.role else None,
        "status":           s.status.value,
        "ip_address":       s.ip_address,
        # Drapeau pays (14/08) — lookup GeoIP local, jamais exporté en CSV
        # (cf. export_sessions_monitoring_csv, header volontairement inchangé).
        "country_code":     lookup_country_code(s.ip_address, current_app.config.get("GEOIP_DB_PATH")),
        "user_agent":       s.user_agent,
        "agent_login":      s.agent_login,
        "station_extension": s.station_extension,
        "session_start":    s.session_start.isoformat() if s.session_start else None,
        "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
        "session_end":      s.session_end.isoformat() if s.session_end else None,
        "is_current":       bool(caller_refresh_jti and s.jti == caller_refresh_jti),
        # Suivi des temps de login/pause (14/08) — calcul live pour une
        # session encore ouverte (borné à l'instant présent).
        "active_minutes":   round(durations["active_min"], 1),
        "pause_minutes":    round(durations["pause_min"], 1),
    }


@auth_bp.route("/sessions/monitoring", methods=["GET"])
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def sessions_monitoring():
    """
    Liste les sessions du TENANT ACTIF (claim `tid`) pour la supervision.
    Le tenant doit toujours être spécifié dans le token.

    Query optionnels :
      - status : 'live' (défaut, ACTIVE+PAUSED) | 'all'
      - from / to : bornes sur session_start
    """
    claims = get_jwt()
    tid = claims.get("tid")
    if not tid:
        return jsonify({"error": "Aucun tenant actif sélectionné."}), 400
    try:
        tenant_uuid = uuid.UUID(tid)
    except (ValueError, TypeError):
        return jsonify({"error": "Tenant invalide."}), 400

    caller_refresh_jti = claims.get("refresh_jti")
    sessions_list = _filtered_sessions_query(tenant_uuid).all()
    payload = [_serialize_session_row(s, caller_refresh_jti) for s in sessions_list]

    return jsonify({"sessions": payload, "total": len(payload), "tenant_id": tid}), 200


@auth_bp.route("/sessions/monitoring/export", methods=["GET"])
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def export_sessions_monitoring_csv():
    """Export CSV des sessions du tenant actif (mêmes filtres que /monitoring)."""
    claims = get_jwt()
    tid = claims.get("tid")
    if not tid:
        return jsonify({"error": "Aucun tenant actif sélectionné."}), 400
    try:
        tenant_uuid = uuid.UUID(tid)
    except (ValueError, TypeError):
        return jsonify({"error": "Tenant invalide."}), 400

    caller_refresh_jti = claims.get("refresh_jti")
    sessions_list = _filtered_sessions_query(tenant_uuid).limit(MAX_EXPORT_ROWS).all()
    rows_data = [_serialize_session_row(s, caller_refresh_jti) for s in sessions_list]

    header = [
        "username", "full_name", "role", "status", "ip_address", "user_agent",
        "agent_login", "station_extension", "session_start", "last_activity_at", "session_end",
        "active_minutes", "pause_minutes",
    ]
    csv_rows = [
        [
            r["username"], r["full_name"], r["role"], r["status"], r["ip_address"], r["user_agent"],
            r["agent_login"], r["station_extension"], r["session_start"], r["last_activity_at"], r["session_end"],
            r["active_minutes"], r["pause_minutes"],
        ]
        for r in rows_data
    ]

    filename = f"sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return build_csv_response(header, csv_rows, filename)


# ─────────────────────────────────────────────────────────────────────────── #
#  DELETE /api/auth/sessions/<id>   (révocation à distance)                    #
# ─────────────────────────────────────────────────────────────────────────── #

@auth_bp.route("/sessions/<int:session_id>", methods=["DELETE"])
@jwt_required()
def revoke_session(session_id):
    """
    Révoque une session : blocklist son refresh token, statut REVOKED.

    Autorisé si :
      - l'appelant est le propriétaire de la session, OU
      - l'appelant est ADMIN/MANAGER et la session appartient à son tenant actif.

    Note : l'access token de la session reste valide jusqu'à son expiration
    (≤ 15 min) — seul le refresh token est immédiatement invalidé.
    """
    from datetime import timedelta

    claims    = get_jwt()
    caller_id = int(get_jwt_identity())
    caller_role = claims.get("role")
    tid       = claims.get("tid")
    ip        = _get_client_ip()
    now       = utcnow()

    session = db.session.get(UserSession, session_id)
    if not session:
        return jsonify({"error": "Session introuvable."}), 404

    is_owner = session.user_id == caller_id
    is_staff = caller_role in (UserRole.ADMIN.value, UserRole.MANAGER.value)
    same_tenant = tid and str(session.active_tenant_id) == str(tid)

    if not (is_owner or (is_staff and same_tenant)):
        return jsonify({"error": "Accès refusé à cette session."}), 403

    if session.status in (SessionStatus.ENDED, SessionStatus.REVOKED, SessionStatus.EXPIRED):
        return jsonify({"message": "Session déjà terminée.", "status": session.status.value}), 200

    # Révocation du refresh token associé
    if session.jti and not TokenBlocklist.query.filter_by(jti=session.jti).first():
        refresh_exp = now + current_app.config.get("JWT_REFRESH_TOKEN_EXPIRES", timedelta(days=1))
        _revoke_token(
            jti=session.jti,
            token_type="refresh",
            user_id=session.user_id,
            expires_at=refresh_exp,
        )

    session.status = SessionStatus.REVOKED
    session.session_end = now

    tenant_for_log = None
    if session.active_tenant_id:
        tenant_for_log = session.active_tenant_id
    _log_audit(caller_id, "SESSION_REVOKED", {
        "ip": ip,
        "session_id": session.id,
        "target_user_id": session.user_id,
        "by_staff": is_staff and not is_owner,
    }, tenant_id=tenant_for_log)

    db.session.commit()
    auth_logger.info(
        f"SESSION_REVOKED | by_user={caller_id} | session_id={session.id} "
        f"| target_user={session.user_id} | ip={ip}"
    )

    # Exécution à distance ESL (15/08) : une session révoquée (admin ou
    # propriétaire) doit aussi déconnecter l'agent côté PBX — jusqu'ici
    # seul logout() déclenchait ce job. Best-effort, après le commit.
    if session.agent_login and session.active_tenant_id:
        from app.routes.telephony import notify_pbx_agent_logout
        notify_pbx_agent_logout(
            session.active_tenant_id, session.agent_login,
            session=session, context="revoke_session",
        )

    return jsonify({"message": "Session révoquée.", "session_id": session.id}), 200


# ─────────────────────────────────────────────────────────────────────────── #
#  GET /api/auth/sessions/stats   (KPI supervision — STAFF, tenant-scoped)     #
# ─────────────────────────────────────────────────────────────────────────── #

@auth_bp.route("/sessions/stats", methods=["GET"])
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def sessions_stats():
    """
    KPI de suivi des sessions.
    - ADMIN   : agrégation sur TOUS les tenants.
    - MANAGER : restreint au tenant actif (claim `tid`).
    Query : ?from=ISO&to=ISO&user_id=<id> (défaut période : 30 derniers jours).
    """
    from datetime import timedelta
    from statistics import median

    claims = get_jwt()
    role = claims.get("role")
    is_admin = role == UserRole.ADMIN.value
    tid = claims.get("tid")

    tenant_uuid = None
    if not is_admin:
        # MANAGER : tenant obligatoire
        if not tid:
            return jsonify({"error": "Aucun tenant actif sélectionné."}), 400
        try:
            tenant_uuid = uuid.UUID(tid)
        except (ValueError, TypeError):
            return jsonify({"error": "Tenant invalide."}), 400

    now = utcnow()

    def _parse(dt_str, default):
        if not dt_str:
            return default
        try:
            return datetime.fromisoformat(dt_str.replace("Z", ""))
        except ValueError:
            return default

    dt_from = _parse(request.args.get("from"), now - timedelta(days=30))
    dt_to = _parse(request.args.get("to"), now)
    user_filter = request.args.get("user_id", type=int)

    # ── Sessions (ADMIN: tous tenants ; MANAGER: tenant actif) ────────────── #
    sessions_q = UserSession.query
    if tenant_uuid is not None:
        sessions_q = sessions_q.filter(UserSession.active_tenant_id == tenant_uuid)
    if user_filter:
        sessions_q = sessions_q.filter(UserSession.user_id == user_filter)
    sessions = sessions_q.all()
    in_period = [s for s in sessions if s.session_start and dt_from <= s.session_start <= dt_to]

    active_sessions = [s for s in sessions if s.status == SessionStatus.ACTIVE]
    paused_sessions = [s for s in sessions if s.status == SessionStatus.PAUSED]

    # A. Temps réel
    active_now = len(active_sessions)
    unique_users_connected = len({s.user_id for s in active_sessions})
    paused_now = len(paused_sessions)

    # A.3 Pic de sessions simultanées sur la période (balayage d'intervalles)
    events = []
    for s in in_period:
        start = s.session_start
        end = s.session_end or now
        events.append((start, 1))
        events.append((end, -1))
    events.sort(key=lambda e: (e[0], -e[1]))
    cur = peak = 0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    peak_concurrent = peak

    # B.7 Durées des sessions terminées dans la période
    durations_min = [
        (s.session_end - s.session_start).total_seconds() / 60
        for s in sessions
        if s.session_end and s.session_start and dt_from <= s.session_end <= dt_to
    ]
    avg_duration = round(sum(durations_min) / len(durations_min), 1) if durations_min else 0
    median_duration = round(median(durations_min), 1) if durations_min else 0
    total_online_min = round(sum(durations_min), 1) if durations_min else 0

    # Suivi des temps de login/pause (14/08) — mêmes sessions que
    # `durations_min` ci-dessus (terminées dans la période), décomposées en
    # temps actif/pause via `_session_status_durations`.
    status_durations = [
        _session_status_durations(s)
        for s in sessions
        if s.session_end and s.session_start and dt_from <= s.session_end <= dt_to
    ]
    total_active_min = round(sum(d["active_min"] for d in status_durations), 1)
    total_pause_min = round(sum(d["pause_min"] for d in status_durations), 1)

    # D.14 Répartition par rôle (sessions actives)
    by_role = {}
    for s in active_sessions:
        r = s.user.role.value if s.user and s.user.role else "inconnu"
        by_role[r] = by_role.get(r, 0) + 1

    # D.15 Raisons de fin (sessions de la période)
    end_reasons = {"ended": 0, "expired": 0, "revoked": 0, "active": 0, "paused": 0}
    for s in in_period:
        k = s.status.value
        if k in end_reasons:
            end_reasons[k] += 1

    # ── Événements d'audit (tenant + période) ─────────────────────────────── #
    logs_q = AuditLog.query.filter(
        AuditLog.table_name == "auth",
        AuditLog.created_at >= dt_from,
        AuditLog.created_at <= dt_to,
    )
    if tenant_uuid is not None:
        logs_q = logs_q.filter(AuditLog.tenant_id == tenant_uuid)
    if user_filter:
        logs_q = logs_q.filter(AuditLog.user_id == user_filter)
    logs = logs_q.all()

    def _event(l):
        return (l.new_values or {}).get("event")

    login_success = [l for l in logs if _event(l) == "LOGIN_SUCCESS"]
    login_failed = [l for l in logs if _event(l) == "LOGIN_FAILED"]
    login_locked = [l for l in logs if _event(l) == "LOGIN_LOCKED"]
    expired_inact = [l for l in logs if _event(l) == "SESSION_EXPIRED_INACTIVITY"]
    revoked_evt = [l for l in logs if _event(l) == "SESSION_REVOKED"]

    # B.5/B.6 Séries par jour
    logins_per_day = {}
    unique_users_per_day = {}
    hour_hist = {h: 0 for h in range(24)}
    for l in login_success:
        day = l.created_at.strftime("%Y-%m-%d")
        logins_per_day[day] = logins_per_day.get(day, 0) + 1
        unique_users_per_day.setdefault(day, set()).add(l.user_id)
        hour_hist[l.created_at.hour] += 1
    logins_series = [{"date": d, "count": c} for d, c in sorted(logins_per_day.items())]
    unique_series = [
        {"date": d, "count": len(s)} for d, s in sorted(unique_users_per_day.items())
    ]
    peak_hours = [{"hour": h, "count": hour_hist[h]} for h in range(24)]

    # C.9 Taux d'échec
    total_attempts = len(login_success) + len(login_failed)
    failure_rate = round(len(login_failed) / total_attempts * 100, 1) if total_attempts else 0

    # C.13 Top IP par tentatives échouées
    ip_fail = {}
    for l in login_failed:
        ip_addr = (l.new_values or {}).get("ip") or "inconnue"
        ip_fail[ip_addr] = ip_fail.get(ip_addr, 0) + 1
    top_failed_ips = sorted(
        [{"ip": k, "count": v} for k, v in ip_fail.items()],
        key=lambda x: x["count"], reverse=True,
    )[:5]

    return jsonify({
        "period": {"from": dt_from.isoformat(), "to": dt_to.isoformat()},
        "realtime": {
            "active_now": active_now,
            "unique_users_connected": unique_users_connected,
            "peak_concurrent": peak_concurrent,
            "paused_now": paused_now,
        },
        "activity": {
            "logins_total": len(login_success),
            "logins_per_day": logins_series,
            "unique_users_per_day": unique_series,
            "avg_duration_min": avg_duration,
            "median_duration_min": median_duration,
            "total_online_min": total_online_min,
            "total_active_min": total_active_min,
            "total_pause_min": total_pause_min,
            "peak_hours": peak_hours,
        },
        "security": {
            "failure_rate_pct": failure_rate,
            "login_failed_total": len(login_failed),
            "lockouts": len(login_locked),
            "expired_inactivity": len(expired_inact),
            "revoked": len(revoked_evt),
            "top_failed_ips": top_failed_ips,
        },
        "distribution": {
            "by_role": by_role,
            "end_reasons": end_reasons,
        },
    }), 200


# ═════════════════════════════════════════════════════════════════════════
#  Mot de passe oublié — self-service, aucune authentification requise
# ═════════════════════════════════════════════════════════════════════════

@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """
    Déclenche l'envoi d'un email de réinitialisation de mot de passe.

    Retourne TOUJOURS 200 avec le même message, que l'email corresponde à un
    compte actif ou non (anti-énumération) — ne jamais laisser une réponse
    distinguer "cet email existe" de "cet email n'existe pas".
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    generic_response = (jsonify({
        "message": "Si un compte existe pour cette adresse, un email de réinitialisation a été envoyé."
    }), 200)

    if not email:
        return generic_response

    user = User.query.filter(User.email.ilike(email), User.is_active.is_(True)).first()
    if not user or not user.tenants:
        return generic_response

    tenant = user.tenants[0]
    raw, token_hash = generate_token()
    reset_token = UserToken(
        user_id=user.id, purpose=PURPOSE_PASSWORD_RESET, token_hash=token_hash,
        status=STATUS_PENDING, expires_at=utcnow() + PASSWORD_RESET_TTL,
    )
    db.session.add(reset_token)
    db.session.flush()

    try:
        send_templated_email(
            tenant, "password_reset",
            {
                "prenom": user.prenom,
                "tenant_name": getattr(tenant, "nom", "") or "votre espace",
                "reset_url": build_reset_url(raw),
            },
            user.email,
        )
    except Exception:  # noqa: BLE001
        # Ne jamais révéler un échec d'envoi (fuiterait "cet email existe"
        # via une différence de comportement) — journalisé, pas remonté.
        db.session.rollback()
        auth_logger.exception("Échec de l'envoi de l'email de réinitialisation de mot de passe.")
        return generic_response

    db.session.commit()
    return generic_response


def _resolve_reset_token(token: str):
    """Miroir de onboarding.py::_resolve — jamais un message qui distingue
    "n'existe pas" de "expiré" (anti-énumération)."""
    if not token:
        return None, (jsonify({"error": "Jeton manquant."}), 400)
    reset_token = UserToken.query.filter_by(
        token_hash=hash_token(token), purpose=PURPOSE_PASSWORD_RESET,
    ).first()
    if not reset_token or reset_token.status != STATUS_PENDING:
        return None, (jsonify({"error": "Lien de réinitialisation invalide ou déjà utilisé."}), 404)
    if reset_token.expires_at <= utcnow():
        reset_token.status = STATUS_EXPIRED
        db.session.commit()
        return None, (jsonify({"error": "Lien de réinitialisation expiré."}), 410)
    return reset_token, None


@auth_bp.route("/reset-password/<token>", methods=["GET"])
def check_reset_token(token):
    """Validation seule (pas de données à pré-remplir, contrairement à
    l'onboarding) — permet au frontend d'afficher le formulaire ou un état
    d'erreur avant que l'utilisateur ne saisisse quoi que ce soit."""
    _reset_token, err = _resolve_reset_token(token)
    if err:
        return err
    return jsonify({"valid": True}), 200


@auth_bp.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    reset_token, err = _resolve_reset_token(token)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    pwd_err = password_error(password)
    if pwd_err:
        return jsonify({"error": pwd_err}), 400

    user = reset_token.user
    user.set_password(password)
    reset_token.status = STATUS_COMPLETED
    reset_token.completed_at = utcnow()

    # Un mot de passe qu'on vient de réinitialiser ne doit laisser aucune
    # session déjà ouverte valide — décision produit actée explicitement.
    revoked_sessions = _revoke_all_active_sessions(user.id)

    db.session.commit()
    auth_logger.info(f"PASSWORD_RESET_COMPLETED | user_id={user.id}")

    # Exécution à distance ESL (15/08) : chaque session révoquée ici (une
    # par appareil connecté) doit aussi déconnecter l'agent côté PBX.
    # Best-effort, après le commit — un échec sur une session n'empêche pas
    # de traiter les suivantes.
    if revoked_sessions:
        from app.routes.telephony import notify_pbx_agent_logout
        for s in revoked_sessions:
            if s.agent_login and s.active_tenant_id:
                notify_pbx_agent_logout(
                    s.active_tenant_id, s.agent_login,
                    session=s, context="reset_password",
                )

    return jsonify({"message": "Mot de passe réinitialisé. Vous pouvez vous connecter."}), 200