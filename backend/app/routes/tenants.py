# app/blueprints/tenants.py

import os
import re
import json
from werkzeug.utils import secure_filename

from flask import Blueprint, request, jsonify, current_app
from flask_cors import CORS
from flask_jwt_extended import jwt_required, get_jwt
from app import db
from app.models.tenant import Tenant
from app.models.tenant_user import TenantUser
from app.models.user import User, UserRole
from app.utils.logger import tenant_logger
from app.utils.auth import role_required

tenants_bp = Blueprint("tenants", __name__, url_prefix="/api/tenants")

# Appliquer CORS à tout le blueprint. Essentiel pour que le frontend puisse
# appeler ces endpoints sans erreur cross-origin.
CORS(tenants_bp, supports_credentials=True)

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def tenant_to_dict(t, include_users=False):
    data = {
        "id":         str(t.id),
        "code":       t.code,
        "nom":        t.nom,
        "slug":       t.slug,
        "logo_url":   t.logo_url,
        "support_email": t.support_email,
        "is_active":  t.is_active,
        "channels": {
            "telephonie": t.channel_telephonie,
            "email": t.channel_email,
            "chat": t.channel_chat,
        },
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
    if include_users:
        links = TenantUser.query.filter_by(tenant_id=t.id).all()
        data["users"] = [
            {
                "user_id":  lnk.user_id,
                "username": lnk.user.username if lnk.user else None,
                "role":     lnk.membership_role,
                "is_active":    lnk.is_active,
            }
            for lnk in links
        ]
    return data


def _get_caller_id(claims):
    return claims.get("sub") or claims.get("identity")


def _save_logo(file, tenant):
    """Sauvegarde le logo d'un tenant et retourne son URL publique."""
    if not file or not file.filename:
        return None

    allowed_ext = current_app.config.get("ALLOWED_LOGO_EXTENSIONS", ".png,.jpg,.jpeg,.webp")
    allowed = {f".{e.strip().lstrip('.')}" for e in allowed_ext.split(',')}
    max_mb = int(current_app.config.get("MAX_AVATAR_SIZE_MB", 2))

    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in allowed:
        raise ValueError(f"Extension non autorisée. Attendu: {', '.join(allowed)}")

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > max_mb * 1024 * 1024:
        raise ValueError(f"Fichier trop volumineux. Taille max: {max_mb}MB")

    filename = secure_filename(f"tenant_{tenant.id}_logo{ext.lower()}")
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        raise ValueError("UPLOAD_FOLDER n'est pas configuré")
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, filename))
    return f"/uploads/{filename}"


def _delete_logo(tenant):
    """Supprime le fichier logo physique d'un tenant, le cas échéant."""
    if not tenant or not getattr(tenant, 'logo_url', None):
        return
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        return
    file_path = os.path.join(upload_folder, os.path.basename(tenant.logo_url))
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            tenant_logger.error(f"Erreur suppression logo {file_path}: {e}")


def _parse_tenant_request():
    """
    Parse soit du JSON, soit du multipart/form-data contenant une partie 'data'
    (JSON) et une partie 'logo' (fichier).
    Retourne (data, logo_file, error_response | None).
    """
    data = {}
    logo_file = None
    try:
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            payload_str = request.form.get('data')
            data = json.loads(payload_str) if payload_str else {}
            logo_file = request.files.get('logo')
        else:
            data = request.get_json(silent=True) or {}
    except json.JSONDecodeError:
        return None, None, (jsonify({"error": "JSON invalide dans 'data'."}), 400)
    return data, logo_file, None


# ══════════════════════════════════════════════════════════════
#  CRUD TENANT
# ══════════════════════════════════════════════════════════════

# ── GET /api/tenants ──────────────────────────────────────────
@tenants_bp.route("", methods=["GET"])
@jwt_required()
@role_required(UserRole.ADMIN)
def list_tenants():
    """
    Liste tous les tenants.
    Paramètres query optionnels :
      - is_active (bool)   : filtrer par statut is_active/inactive
      - q (str)        : recherche sur nom ou slug
    """
    is_active_param = request.args.get("is_active", default=None)
    search      = request.args.get("q", default="").strip()

    query = Tenant.query

    if is_active_param is not None:
        query = query.filter_by(is_active=(is_active_param.lower() == "true"))

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Tenant.nom.ilike(like), Tenant.slug.ilike(like))
        )

    tenants = query.order_by(Tenant.nom).all()
    return jsonify([tenant_to_dict(t) for t in tenants]), 200


# ── GET /api/tenants/<id> ─────────────────────────────────────
@tenants_bp.route("/<uuid:tenant_id>", methods=["GET"])
@jwt_required()
@role_required(UserRole.ADMIN)
def get_tenant(tenant_id):
    """
    Détail d'un tenant.
    Paramètre query optionnel :
      - include_users (bool) : inclure la liste des utilisateurs rattachés
    """
    include_users = request.args.get("include_users", "false").lower() == "true"
    tenant = Tenant.query.get_or_404(tenant_id)
    return jsonify(tenant_to_dict(tenant, include_users=include_users)), 200


# ── POST /api/tenants ─────────────────────────────────────────
@tenants_bp.route("", methods=["POST"])
@jwt_required()
@role_required(UserRole.ADMIN)
def create_tenant():
    """
    Créer un nouveau tenant.
    Body JSON obligatoire : { "nom": "...", "slug": "..." }
    Body JSON optionnel   : { "is_active": true }
    """
    data, logo_file, err = _parse_tenant_request()
    if err:
        return err
    claims = get_jwt()
    caller = _get_caller_id(claims)

    nom  = (data.get("nom")  or "").strip()
    slug = (data.get("slug") or "").strip().lower()
    code = (data.get("code") or "").strip().upper()

    # ── Validations ──
    if not nom:
        return jsonify({"error": "Le champ 'nom' est obligatoire."}), 422
    if not slug:
        return jsonify({"error": "Le champ 'slug' est obligatoire."}), 422
    if not code:
        return jsonify({"error": "Le champ 'code' est obligatoire."}), 422

    # Slug : lettres, chiffres et tirets uniquement
    import re
    if not re.match(r"^[a-z0-9\-]+$", slug):
        return jsonify({
            "error": "Le slug ne peut contenir que des lettres minuscules, chiffres et tirets."
        }), 422

    if Tenant.query.filter_by(slug=slug).first():
        return jsonify({"error": f"Le slug '{slug}' est déjà utilisé."}), 409

    if Tenant.query.filter_by(code=code).first():
        return jsonify({"error": f"Le code '{code}' est déjà utilisé."}), 409

    tenant = Tenant(
        nom=nom,
        slug=slug,
        code=code,
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(tenant)
    db.session.flush()  # obtenir tenant.id pour nommer le fichier logo

    if logo_file:
        try:
            tenant.logo_url = _save_logo(logo_file, tenant)
        except ValueError as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 422

    # Amorce les valeurs de référence par défaut pour le nouveau tenant
    try:
        from app.scripts.seeding import seed_reference_values
        seed_reference_values(db, tenant.id)
    except Exception as exc:  # noqa: BLE001
        tenant_logger.warning(f"CREATE_TENANT | seed valeurs de référence échoué : {exc}")

    db.session.commit()

    tenant_logger.info(f"CREATE_TENANT | caller={caller} | Tenant {tenant.id} créé : {nom} ({slug})")
    return jsonify(tenant_to_dict(tenant)), 201


# ── PUT /api/tenants/<id> ─────────────────────────────────────
@tenants_bp.route("/<uuid:tenant_id>", methods=["PUT"])
@jwt_required()
@role_required(UserRole.ADMIN)
def update_tenant(tenant_id):
    """
    Mettre à jour un tenant (mise à jour partielle acceptée).
    """
    tenant = Tenant.query.get_or_404(tenant_id)
    data, logo_file, err = _parse_tenant_request()
    if err:
        return err
    claims = get_jwt()
    caller = _get_caller_id(claims)

    if "nom" in data:
        nom = data["nom"].strip()
        if not nom:
            return jsonify({"error": "'nom' ne peut pas être vide."}), 422
        tenant.nom = nom

    if "code" in data:
        new_code = (data["code"] or "").strip().upper()
        if not new_code:
            return jsonify({"error": "'code' ne peut pas être vide."}), 422
        conflict = Tenant.query.filter_by(code=new_code).first()
        if conflict and conflict.id != tenant_id:
            return jsonify({"error": f"Le code '{new_code}' est déjà utilisé."}), 409
        tenant.code = new_code

    if "slug" in data:
        import re
        new_slug = data["slug"].strip().lower()
        if not re.match(r"^[a-z0-9\-]+$", new_slug):
            return jsonify({
                "error": "Slug invalide (lettres minuscules, chiffres, tirets uniquement)."
            }), 422
        conflict = Tenant.query.filter_by(slug=new_slug).first()
        if conflict and conflict.id != tenant_id:
            return jsonify({"error": f"Le slug '{new_slug}' est déjà utilisé."}), 409
        tenant.slug = new_slug

    if "support_email" in data:
        se = (data.get("support_email") or "").strip()
        if se and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", se):
            return jsonify({"error": "Email support invalide."}), 422
        tenant.support_email = se or None

    if "is_active" in data:
        tenant.is_active = bool(data["is_active"])

    # Canaux métier (pilotage admin global). Désactiver un canal ne purge aucune
    # configuration existante (réversible).
    channels = data.get("channels") or {}
    for key, attr in (("telephonie", "channel_telephonie"),
                      ("email", "channel_email"),
                      ("chat", "channel_chat")):
        if key in channels:
            setattr(tenant, attr, bool(channels[key]))

    # Gestion du logo : nouveau fichier remplace l'ancien ; logo_url=null le supprime
    if logo_file:
        try:
            _delete_logo(tenant)
            tenant.logo_url = _save_logo(logo_file, tenant)
        except ValueError as e:
            return jsonify({"error": str(e)}), 422
    elif "logo_url" in data and data.get("logo_url") is None:
        _delete_logo(tenant)
        tenant.logo_url = None

    tenant.updated_at = db.func.now()  # Met à jour la date de modification
    db.session.commit()
    tenant_logger.info(f"UPDATE_TENANT | caller={caller} | Tenant {tenant_id} mis à jour")
    return jsonify(tenant_to_dict(tenant)), 200


# ── DELETE /api/tenants/<id> ──────────────────────────────────
@tenants_bp.route("/<uuid:tenant_id>", methods=["DELETE"])
@jwt_required()
@role_required(UserRole.ADMIN)
def delete_tenant(tenant_id):
    """
    Suppression physique d'un tenant.
    Bloqué si des utilisateurs sont encore rattachés.
    """
    tenant = Tenant.query.get_or_404(tenant_id)
    claims = get_jwt()
    caller = _get_caller_id(claims)

    nb_users = TenantUser.query.filter_by(tenant_id=tenant_id).count()
    if nb_users > 0:
        return jsonify({
            "error": (
                f"Impossible de supprimer ce tenant : "
                f"{nb_users} utilisateur(s) y sont encore rattachés."
            )
        }), 409

    _delete_logo(tenant)
    db.session.delete(tenant)
    db.session.commit()
    tenant_logger.info(f"DELETE_TENANT | caller={caller} | Tenant {tenant_id} supprimé")
    return jsonify({"message": f"Tenant {tenant_id} supprimé avec succès."}), 200


# ══════════════════════════════════════════════════════════════
#  GESTION DES UTILISATEURS D'UN TENANT
# ══════════════════════════════════════════════════════════════

ROLES_VALIDES = {"admin", "manager", "permanencier"}


# ── GET /api/tenants/<id>/users ───────────────────────────────
@tenants_bp.route("/<uuid:tenant_id>/users", methods=["GET"])
@jwt_required()
@role_required(UserRole.ADMIN)
def list_tenant_users(tenant_id):
    """Liste les utilisateurs rattachés à un tenant."""
    Tenant.query.get_or_404(tenant_id)

    links = (
        TenantUser.query
        .filter_by(tenant_id=tenant_id)
        .join(TenantUser.user)
        .order_by(User.username)
        .all()
    )

    return jsonify([
        {
            "user_id":  lnk.user_id,
            "username": lnk.user.username if lnk.user else None,
            "email":    lnk.user.email    if lnk.user else None,
            "role":     lnk.membership_role,
            "is_active":    lnk.is_active,
        }
        for lnk in links
    ]), 200


# ── POST /api/tenants/<id>/users ──────────────────────────────
@tenants_bp.route("/<uuid:tenant_id>/users", methods=["POST"])
@jwt_required()
@role_required(UserRole.ADMIN)
def add_user_to_tenant(tenant_id):
    """Rattacher un utilisateur à un tenant. Réservé aux ADMIN."""
    """
    Rattacher un utilisateur existant à un tenant.
    Body JSON : { "user_id": 3, "role": "manager" }
    """
    Tenant.query.get_or_404(tenant_id)
    data   = request.get_json(silent=True) or {}
    claims = get_jwt()
    caller = _get_caller_id(claims)

    target_user_id = data.get("user_id")
    role           = data.get("role", "permanencier")

    if not target_user_id:
        return jsonify({"error": "'user_id' est obligatoire."}), 422

    if role not in ROLES_VALIDES:
        return jsonify({"error": f"Rôle invalide. Valeurs acceptées : {sorted(ROLES_VALIDES)}"}), 422

    if not User.query.get(target_user_id):
        return jsonify({"error": f"Utilisateur {target_user_id} introuvable."}), 404

    existing = TenantUser.query.filter_by(
        tenant_id=tenant_id, user_id=target_user_id
    ).first()
    if existing:
        return jsonify({"error": "Cet utilisateur est déjà rattaché à ce tenant."}), 409

    link = TenantUser(
        tenant_id=tenant_id,
        user_id=target_user_id,
        membership_role=role,
        is_active=True,
    )
    db.session.add(link)
    db.session.commit()
    tenant_logger.info(f"ADD_USER_TENANT | caller={caller} | User {target_user_id} → Tenant {tenant_id} (rôle: {role})")

    return jsonify({
        "message":   "Utilisateur rattaché au tenant.",
        "tenant_id": str(tenant_id),
        "user_id":   target_user_id,
        "role":      role,
    }), 201


# ── PUT /api/tenants/<id>/users/<user_id> ─────────────────────
@tenants_bp.route("/<uuid:tenant_id>/users/<int:user_id>", methods=["PUT"])
@jwt_required()
@role_required(UserRole.ADMIN)
def update_tenant_user(tenant_id, user_id):
    """Modifier le rôle ou le statut d'un membre. Réservé aux ADMIN."""
    """
    Modifier le rôle ou le statut d'un utilisateur dans un tenant.
    Body JSON : { "role": "manager", "is_active": false }
    """
    Tenant.query.get_or_404(tenant_id)
    link = TenantUser.query.filter_by(
        tenant_id=tenant_id, user_id=user_id
    ).first_or_404()

    data   = request.get_json(silent=True) or {}
    claims = get_jwt()
    caller = _get_caller_id(claims)

    if "role" in data:
        if data["role"] not in ROLES_VALIDES:
            return jsonify({"error": f"Rôle invalide : {sorted(ROLES_VALIDES)}"}), 422
        link.membership_role = data["role"]

    if "is_active" in data:
        link.is_active = bool(data["is_active"])

    db.session.commit()
    tenant_logger.info(f"UPDATE_USER_TENANT | caller={caller} | User {user_id} dans Tenant {tenant_id} mis à jour")

    return jsonify({
        "tenant_id": str(tenant_id),
        "user_id":   user_id,
        "role":      link.membership_role,
        "is_active":     link.is_active,
    }), 200


# ── DELETE /api/tenants/<id>/users/<user_id> ──────────────────
@tenants_bp.route("/<uuid:tenant_id>/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
@role_required(UserRole.ADMIN)
def remove_user_from_tenant(tenant_id, user_id):
    """Détacher un utilisateur d'un tenant. Réservé aux ADMIN."""
    """Détacher un utilisateur d'un tenant."""
    Tenant.query.get_or_404(tenant_id)
    link = TenantUser.query.filter_by(
        tenant_id=tenant_id, user_id=user_id
    ).first_or_404()

    claims = get_jwt()
    caller = _get_caller_id(claims)

    db.session.delete(link)
    db.session.commit()
    tenant_logger.info(f"REMOVE_USER_TENANT | caller={caller} | User {user_id} du Tenant {tenant_id}")

    return jsonify({"message": f"Utilisateur {user_id} retire du tenant."}), 200
