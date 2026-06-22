# backend/app/routes/clients.py
import logging
import json
import os
from werkzeug.utils import secure_filename

from flask import Blueprint, jsonify, request, g, current_app
from flask_cors import CORS
from app.models.client import Client
from app.models.user import UserRole
from app import db
from app.utils.decorators import tenant_required
from app.utils.auth import role_required

logger = logging.getLogger(__name__)


def _save_logo(file, client):
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

    filename = secure_filename(f"client_{client.id}_logo{ext}")
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        raise ValueError("UPLOAD_FOLDER n'est pas configuré")
    os.makedirs(upload_folder, exist_ok=True)
    path = os.path.join(upload_folder, filename)
    file.save(path)
    return f"/uploads/{filename}"


def _delete_logo(client):
    if not client or not getattr(client, 'logo_url', None):
        return
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        return
    filename = os.path.basename(client.logo_url)
    file_path = os.path.join(upload_folder, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            logger.error(f"Erreur suppression logo {file_path}: {e}")


def _parse_client_request():
    """Parse JSON ou multipart/form-data contenant 'data' (JSON) et 'logo' fichier."""
    data = {}
    logo_file = None
    try:
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            payload_str = request.form.get('data')
            if not payload_str:
                return None, None, (jsonify({"error": "La partie 'data' du formulaire est manquante."}), 400)
            data = json.loads(payload_str)
            logo_file = request.files.get('logo')
        else:
            data = request.get_json(silent=True) or {}
    except json.JSONDecodeError:
        return None, None, (jsonify({"error": "JSON invalide dans 'data'"}), 400)
    return data, logo_file, None

clients_bp = Blueprint("clients", __name__, url_prefix="/api/clients")

CORS(clients_bp, resources={r"/api/clients/*": {"origins": "*"}})

@clients_bp.get("")
@tenant_required
def list_clients():
    """Liste les clients avec pagination, recherche et filtrage."""
    tenant_id = getattr(g, 'tenant_id', None)
    if not tenant_id:
        return jsonify({"error": "Contexte de tenant non trouvé. Veuillez sélectionner un tenant."}), 400

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_query = request.args.get('search', '', type=str)
    status_filter = request.args.get('status', '', type=str)

    query = Client.query.filter_by(tenant_id=tenant_id)

    if status_filter:
        if status_filter.lower() == 'true':
            query = query.filter_by(is_active=True)
        elif status_filter.lower() == 'false':
            query = query.filter_by(is_active=False)

    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Client.nom.ilike(search_term),
                Client.code_client.ilike(search_term),
                Client.email.ilike(search_term)
            )
        )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    clients = pagination.items

    data = [
        {
            "id": c.id,
            "nom": c.nom,
            "code_client": c.code_client,
            "adresse": c.adresse,
            "ville": c.ville,
            "code_postal": c.code_postal,
            "telephone": c.telephone,
            "email": c.email,
            "siret": c.siret,
            "contact_principal": c.contact_principal,
            "is_active": c.is_active,
            "logo_url": c.logo_url,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in clients
    ]
    return jsonify({
        "clients": data,
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "total_pages": pagination.pages
    }), 200


@clients_bp.get("/<int:client_id>")
@tenant_required
def get_client(client_id):
    """Récupère un client spécifique"""
    client = Client.query.filter_by(id=client_id, tenant_id=g.tenant_id).first_or_404()
    return jsonify({
        "id": client.id,
        "nom": client.nom,
        "code_client": client.code_client,
        "adresse": client.adresse,
        "ville": client.ville,
        "code_postal": client.code_postal,
        "telephone": client.telephone,
        "email": client.email,
        "contact_principal": client.contact_principal,
        "is_active": client.is_active,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }), 200


@clients_bp.post("")
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def create_client():
    """Crée un nouveau client; supporte multipart/form-data avec 'data' JSON et 'logo' fichier."""
    data, logo_file, error = _parse_client_request()
    if error:
        return error

    # Validation des champs requis
    required_fields = ["nom", "code_client"]
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Le champ '{field}' est requis"}), 400

    # Vérifier unicité du code_client
    if Client.query.filter_by(tenant_id=g.tenant_id, code_client=data["code_client"]).first():
        return jsonify({"error": "Ce code client existe déjà"}), 409

    try:
        client = Client(
            tenant_id=g.tenant_id,
            nom=data["nom"],
            code_client=data["code_client"],
        )
        
        update_fields = ["adresse", "telephone", "email", "contact_principal", "ville", "code_postal", "siret"]
        for field in update_fields:
            if field in data:
                setattr(client, field, data.get(field))
                
        db.session.add(client)
        db.session.flush()

        if logo_file:
            try:
                logo_url = _save_logo(logo_file, client)
                client.logo_url = logo_url
            except ValueError as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                db.session.rollback()
                logger.error(f"Erreur lors de la sauvegarde du logo: {e}")
                return jsonify({"error": "Erreur interne lors de la sauvegarde du logo."}), 500

        db.session.commit()

        return jsonify({
            "id": client.id,
            "nom": client.nom,
            "code_client": client.code_client,
            "adresse": client.adresse,
            "ville": client.ville,
            "code_postal": client.code_postal,
            "telephone": client.telephone,
            "email": client.email,
            "contact_principal": client.contact_principal,
            "is_active": client.is_active,
            "logo_url": client.logo_url,
            "created_at": client.created_at.isoformat() if client.created_at else None,
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erreur lors de la création du client"}), 500


@clients_bp.put("/<int:client_id>")
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def update_client(client_id):
    """Met à jour un client existant"""
    client = Client.query.filter_by(id=client_id, tenant_id=g.tenant_id).first_or_404()
    data, logo_file, error = _parse_client_request()
    if error:
        return error

    # Vérifier unicité du code_client si modifié
    if "code_client" in data and data["code_client"] != client.code_client:
        if Client.query.filter_by(tenant_id=g.tenant_id, code_client=data["code_client"]).first():
            return jsonify({"error": "Ce code client existe déjà"}), 409

    try:
        # Mise à jour des champs de manière dynamique
        updateable_fields = ["nom", "code_client", "adresse", "telephone", "email", "contact_principal", "ville", "code_postal", "siret"]
        for field in updateable_fields:
            if field in data:
                setattr(client, field, data[field])

        if logo_file:
            try:
                _delete_logo(client)
                logo_url = _save_logo(logo_file, client)
                client.logo_url = logo_url
            except ValueError as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                logger.error(f"Erreur sauvegarde logo client {client.id}: {e}")

        elif data.get('logo_url') is None and 'logo_url' in data:
            # Frontend a explicitement demandé la suppression
            _delete_logo(client)
            client.logo_url = None

        db.session.commit()

        return jsonify({
            "id": client.id,
            "nom": client.nom,
            "code_client": client.code_client,
            "adresse": client.adresse,
            "ville": client.ville,
            "code_postal": client.code_postal,
            "telephone": client.telephone,
            "email": client.email,
            "contact_principal": client.contact_principal,
            "is_active": client.is_active,
            "logo_url": client.logo_url,
            "updated_at": client.updated_at.isoformat() if client.updated_at else None,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erreur lors de la mise à jour du client"}), 500


@clients_bp.delete("/<int:client_id>")
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def delete_client(client_id):
    """Supprime un client (soft delete - désactivation en cascade)"""
    client = Client.query.filter_by(id=client_id, tenant_id=g.tenant_id).first_or_404()

    try:
        client.is_active = False
        
        # Désactivation en cascade : on désactive aussi tous les sites liés à ce client
        for site in client.sites:
            site.is_active = False
            
        db.session.commit()

        return jsonify({"message": "Client et ses sites désactivés avec succès"}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la désactivation du client {client_id}: {e}")
        return jsonify({"error": "Erreur lors de la suppression du client", "details": str(e)}), 500


@clients_bp.patch("/<int:client_id>/status")
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def toggle_client_status(client_id):
    """Active ou désactive un client (avec effet cascade sur les sites)"""
    client = Client.query.filter_by(id=client_id, tenant_id=g.tenant_id).first_or_404()
    payload = request.get_json() or {}

    if "is_active" not in payload:
        return jsonify({"error": "Le champ 'is_active' est requis"}), 400

    if not isinstance(payload["is_active"], bool):
        return jsonify({"error": "Le champ 'is_active' doit être un booléen"}), 400

    try:
        client.is_active = payload["is_active"]
        
        # Effet cascade : on applique le statut à tous les sites liés au client
        for site in client.sites:
            site.is_active = client.is_active
            
        db.session.commit()

        status_text = "activé" if client.is_active else "désactivé"
        return jsonify({
            "message": f"Client {status_text} avec succès",
            "is_active": client.is_active
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erreur lors de la modification du statut"}), 500