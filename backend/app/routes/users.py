import logging
from datetime import datetime
import json
import os
from werkzeug.utils import secure_filename

from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import or_
from flask_cors import CORS
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models import User, UserRole
from app.utils.auth import role_required

users_bp = Blueprint("users", __name__, url_prefix="/api/users")
logger = logging.getLogger(__name__)

# Appliquer CORS à tout le blueprint. Essentiel pour que le frontend puisse
# appeler ces endpoints sans erreur cross-origin.
CORS(users_bp, supports_credentials=True)


def _save_avatar(file, user):
    """Sauvegarde un fichier avatar pour un utilisateur et retourne l'URL publique."""
    if not file or not file.filename:
        return None

    allowed_extensions_str = current_app.config.get(
        "ALLOWED_AVATAR_EXTENSIONS", ".png,.jpg,.jpeg,.gif,.webp"
    )
    allowed_extensions = {f".{ext.strip().lstrip('.')}" for ext in allowed_extensions_str.split(",")}
    max_size_mb = int(current_app.config.get("MAX_AVATAR_SIZE_MB", 2))

    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in allowed_extensions:
        raise ValueError(
            "Type de fichier non autorisé. Extensions acceptées : "
            f"{', '.join(allowed_extensions)}"
        )

    # Vérification de la taille du fichier
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Important: revenir au début du stream avant la sauvegarde
    if file_size > max_size_mb * 1024 * 1024:
        raise ValueError(f"Fichier trop volumineux. Taille max: {max_size_mb}MB.")

    filename = secure_filename(f"user_{user.id}_avatar{ext}")

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        raise ValueError("UPLOAD_FOLDER n'est pas configuré dans l'application.")

    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    # Suppose que UPLOAD_FOLDER est servi statiquement sous /uploads
    return f"/uploads/{filename}"


def _delete_avatar(user):
    """Supprime le fichier avatar d'un utilisateur du système de fichiers."""
    if not user or not hasattr(user, 'avatar_url') or not user.avatar_url:
        return

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        return

    filename = os.path.basename(user.avatar_url)
    file_path = os.path.join(upload_folder, filename)

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            logger.error(f"Erreur lors de la suppression de l'ancien avatar {file_path}: {e}")

def _parse_user_request():
    """
    Parse les données de la requête, gérant JSON et multipart/form-data.
    Retourne un tuple (data, avatar_file, error_response).
    Si le parsing réussit, error_response est None.
    """
    data = {}
    avatar_file = None
    print("Content-Type de la requête :", request.content_type)  # Debug du Content-Type
    print("Données brutes de la requête :", request.data)  # Debug des données brutes
    try:
        if request.content_type.startswith('multipart/form-data'):
            payload_str = request.form.get('data')
            if not payload_str:
                return None, None, (jsonify({"message": "La partie 'data' du formulaire est manquante."}), 400)
            data = json.loads(payload_str)
            avatar_file = request.files.get('avatar')
        else:
            data = request.get_json(silent=True) or {}
    except json.JSONDecodeError:
        return None, None, (jsonify({"message": "Format JSON invalide dans la partie 'data'."}), 400)

    return data, avatar_file, None

def _serialize_tenant(tenant):
    return {
        "id": tenant.id,
        "code": getattr(tenant, "code", None),
        "nom": getattr(tenant, "nom", None),
        "type_tenant": tenant.type_tenant.value if getattr(tenant, "type_tenant", None) else None,
        "is_active": getattr(tenant, "is_active", None),
    }


def _serialize_user(user: User, include_tenants: bool = False) -> dict:
    data = user.to_dict()
    data['status'] = 'active' if user.is_active else 'inactive'

    if include_tenants:
        data["tenants"] = [_serialize_tenant(t) for t in user.tenants]

    return data


def _get_current_user():
    user_id = get_jwt_identity()
    if not user_id:
        return None

    return db.session.get(User, int(user_id))


@users_bp.get("")
@jwt_required()
@role_required(UserRole.ADMIN)
def list_users():
    # Récupération des paramètres de requête avec des valeurs par défaut
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    search = request.args.get('search', '', type=str).strip()
    status = request.args.get('status', '', type=str)
    sort_by = request.args.get('sort_by', 'id', type=str)
    sort_order = request.args.get('sort_order', 'asc', type=str)

    query = User.query

    # Filtre de recherche sur plusieurs champs
    if search:
        search_term = f"%{search}%"
        search_filters = [
            User.username.ilike(search_term),
            User.nom.ilike(search_term),
            User.prenom.ilike(search_term),
            User.email.ilike(search_term),
        ]
        if search.isdigit():
            search_filters.append(User.id == int(search))
        query = query.filter(or_(*search_filters))

    # Filtre par statut
    if status == 'active':
        query = query.filter(User.is_active.is_(True))
    elif status == 'inactive':
        query = query.filter(User.is_active.is_(False))
    elif status:
        # Si un statut est fourni mais n'est pas supporté (ex: 'suspended'),
        # on s'assure qu'aucun résultat n'est retourné.
        query = query.filter(False)

    # Tri
    sort_column = getattr(User, sort_by, None)
    if sort_column is None:
        sort_column = User.id  # Colonne de tri par défaut
    
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())

    # Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "users": [_serialize_user(user, include_tenants=True) for user in pagination.items],
        "total": pagination.total,
    }), 200


@users_bp.get("/<int:user_id>")
@jwt_required()
@role_required(UserRole.ADMIN)
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 404

    return jsonify(_serialize_user(user, include_tenants=True)), 200


@users_bp.post("")
@jwt_required()
@role_required(UserRole.ADMIN)
def create_user():
    data, avatar_file, error = _parse_user_request()

    if error:
        return error
    required_fields = ["username", "email", "nom", "prenom", "role", "password"]
    missing_fields = [field for field in required_fields if not data.get(field)]

    if missing_fields:
        return jsonify({
            "message": "Champs obligatoires manquants",
            "missing_fields": missing_fields
        }), 400

    username = data["username"].strip()
    email = data["email"].strip().lower()
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Nom d'utilisateur déjà utilisé"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email déjà utilisé"}), 409

    try:
        role = UserRole(data["role"])
    except ValueError:
        return jsonify({"message": "Rôle invalide"}), 400

    user = User(
        username=username,
        email=email,
        nom=data["nom"].strip(),
        prenom=data["prenom"].strip(),
        role=role,
        telephone=data.get("telephone"),
        agent_login=data.get("agent_login"),
        station_extension=data.get("station_extension"),
        is_active=data.get("is_active", True),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    user.set_password(data["password"])

    db.session.add(user)
    db.session.flush()  # Obtenir user.id pour le nom de fichier de l'avatar

    if avatar_file:
        try:
            avatar_url = _save_avatar(avatar_file, user)
            user.avatar_url = avatar_url
        except ValueError as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erreur lors de la sauvegarde de l'avatar pour la création d'utilisateur : {e}")
            return jsonify({"message": "Erreur interne lors de la sauvegarde de l'avatar."}), 500

    tenant_ids = data.get("tenant_ids", [])
    if tenant_ids:
        # Hypothèse: la relation User.tenants est déjà fonctionnelle via secondary=tenant_users
        from app.models import Tenant
        tenants = Tenant.query.filter(Tenant.id.in_(tenant_ids)).all()
        user.tenants = tenants

    db.session.commit()

    return jsonify({
        "message": "Utilisateur créé",
        "user": _serialize_user(user, include_tenants=True)
    }), 201


@users_bp.put("/<int:user_id>")
@jwt_required()
@role_required(UserRole.ADMIN)
def update_user(user_id):
    """Mise à jour d'un utilisateur. Réservé aux ADMIN."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 404

    data, avatar_file, error = _parse_user_request()
    if error:
        return error
    if "username" in data:
        username = data["username"].strip()
        existing = User.query.filter(User.username == username, User.id != user.id).first()
        if existing:
            return jsonify({"message": "Nom d'utilisateur déjà utilisé"}), 409
        user.username = username

    if "email" in data:
        email = data["email"].strip().lower()
        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            return jsonify({"message": "Email déjà utilisé"}), 409
        user.email = email

    if "nom" in data:
        user.nom = data["nom"].strip()

    if "prenom" in data:
        user.prenom = data["prenom"].strip()

    if "telephone" in data:
        user.telephone = data["telephone"]

    if "agent_login" in data:
        user.agent_login = data["agent_login"]

    if "station_extension" in data:
        user.station_extension = data["station_extension"]

    if "is_active" in data:
        user.is_active = bool(data["is_active"])

    if "role" in data:
        try:
            user.role = UserRole(data["role"])
        except ValueError:
            return jsonify({"message": "Rôle invalide"}), 400

    if avatar_file:
        try:
            # Un nouvel avatar est uploadé, on supprime l'ancien d'abord.
            _delete_avatar(user)
            avatar_url = _save_avatar(avatar_file, user)
            user.avatar_url = avatar_url
        except ValueError as e:
            # Les autres modifications sont valides, mais on informe l'utilisateur de l'erreur d'upload.
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'avatar pour l'utilisateur {user.id}: {e}")
    elif data.get('avatar_url') is None and 'avatar_url' in data:
        # Le frontend a envoyé 'avatar_url: null', signalant une suppression.
        _delete_avatar(user)
        user.avatar_url = None

    if "tenant_ids" in data:
        from app.models import Tenant
        tenant_ids = data.get("tenant_ids") or []
        tenants = Tenant.query.filter(Tenant.id.in_(tenant_ids)).all() if tenant_ids else []
        user.tenants = tenants

    user.updated_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        "message": "Utilisateur mis à jour",
        "user": _serialize_user(user, include_tenants=True)
    }), 200


@users_bp.patch("/<int:user_id>/status")
@jwt_required()
@role_required(UserRole.ADMIN)
def update_user_status(user_id):
    """Activation / désactivation d'un compte. Réservé aux ADMIN."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 404

    payload = request.get_json(silent=True) or {}

    if "is_active" not in payload:
        return jsonify({"message": "Le champ is_active est requis"}), 400

    user.is_active = bool(payload["is_active"])
    user.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "message": "Statut utilisateur mis à jour",
        "user": _serialize_user(user, include_tenants=True)
    }), 200


@users_bp.patch("/<int:user_id>/password")
@jwt_required()
def update_password(user_id):
    current_user = _get_current_user()
    if not current_user:
        return jsonify({"message": "Utilisateur authentifié introuvable"}), 401

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 404

    if current_user.id != user.id and current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Action non autorisée"}), 403

    payload = request.get_json(silent=True) or {}
    new_password = payload.get("new_password")
    old_password = payload.get("old_password")

    if not new_password or len(new_password) < 8:
        return jsonify({"message": "Le nouveau mot de passe doit contenir au moins 8 caractères"}), 400

    if current_user.role != UserRole.ADMIN or current_user.id == user.id:
        if not old_password or not user.check_password(old_password):
            return jsonify({"message": "Ancien mot de passe incorrect"}), 401

    user.set_password(new_password)
    user.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"message": "Mot de passe mis à jour avec succès"}), 200


@users_bp.delete("/<int:user_id>")
@jwt_required()
@role_required(UserRole.ADMIN)
def delete_user(user_id):
    current_user = _get_current_user()
    if not current_user:
        return jsonify({"message": "Utilisateur authentifié introuvable"}), 401

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 404

    if current_user.id == user.id:
        return jsonify({"message": "Suppression de son propre compte interdite"}), 400

    _delete_avatar(user)

    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "Utilisateur supprimé"}), 200