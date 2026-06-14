# backend/app/routes/sites.py
import os
import json
import logging
from werkzeug.utils import secure_filename
from flask_cors import CORS
from flask import Blueprint, jsonify, request, g, current_app
from sqlalchemy.orm import joinedload
from app.models.site import Site
from app.models.client import Client
from app import db
from app.utils.decorators import tenant_required

logger = logging.getLogger(__name__)
sites_bp = Blueprint("sites", __name__, url_prefix="/api/sites")
CORS(sites_bp, resources={r"/api/sites/*": {"origins": "*"}})

def _save_logo(file, site):
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
    filename = secure_filename(f"site_{site.id}_logo{ext}")
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        raise ValueError("UPLOAD_FOLDER n'est pas configuré")
    os.makedirs(upload_folder, exist_ok=True)
    path = os.path.join(upload_folder, filename)
    file.save(path)
    return f"/uploads/{filename}"

def _delete_logo(site):
    if not site or not getattr(site, 'logo_url', None):
        return
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        return
    filename = os.path.basename(site.logo_url)
    file_path = os.path.join(upload_folder, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            logger.error(f"Erreur suppression logo site {file_path}: {e}")

def _parse_site_request():
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

@sites_bp.get("")
@tenant_required
def list_sites():
    """Liste les sites avec pagination, recherche et filtrage."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_query = request.args.get('search', '', type=str)
    status_filter = request.args.get('status', 'true')

    query = Site.query.options(
        joinedload(Site.client),
        joinedload(Site.contact_principal)
    ).filter(Site.tenant_id == g.tenant_id)

    if status_filter and status_filter.lower() == 'true':
        query = query.filter(Site.is_active == True)
    elif status_filter and status_filter.lower() == 'false':
        query = query.filter(Site.is_active == False)

    print("---------- Debug List des sites -----------")
    print(f" Search query: '{search_query}', Status filter: '{status_filter}'")  # Debug log
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Site.nom.ilike(search_term),
                Site.code_site.ilike(search_term)
            )
        )
        
    # Extraction robuste et infaillible des IDs de client (paramètres uniques, multiples, tableaux ou CSV)
    client_ids = set()
    
    # Parcourt les clés possibles envoyées par les clients HTTP (Axios, Fetch, Postman)
    for key in ['client_id', 'client_id[]']:
        values = request.args.getlist(key)
        for val in values:
            # Ignore les valeurs vides ou les artefacts JavaScript courants
            if not val or val.lower() in ['null', 'undefined']:
                continue
            # Gérer le format séparé par des virgules (ex: "1,2,3")
            for cid in str(val).split(','):
                cid_clean = cid.strip()
                if cid_clean.isdigit():
                    client_ids.add(int(cid_clean))
                
    if client_ids:
        query = query.filter(Site.client_id.in_(list(client_ids)))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    sites = pagination.items
    data = [
        {
            "id": s.id,
            "client_id": s.client_id,
            "client": {"nom": s.client.nom} if s.client else None,
            "nom": s.nom,
            "code_site": s.code_site,
            "adresse": s.adresse,
            "ville": s.ville,
            "code_postal": s.code_postal,
            "telephone": s.telephone,
            "email": s.email,
            "contact_principal_id": s.contact_principal_id,
            "contact_principal": {"nom": f"{s.contact_principal.prenom} {s.contact_principal.nom}"} if s.contact_principal else None,
            "effectif_requis": s.effectif_requis,
            "is_active": s.is_active,
            "logo_url": s.logo_url,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sites
    ]
    return jsonify({
        "sites": data,
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "total_pages": pagination.pages
    }), 200


@sites_bp.get("/<int:site_id>")
@tenant_required
def get_site(site_id):
    """Récupère un site spécifique"""
    site = Site.query.filter_by(id=site_id, tenant_id=g.tenant_id).first_or_404()
    return jsonify({
        "id": site.id,
        "client_id": site.client_id,
        "nom": site.nom,
        "code_site": site.code_site,
        "adresse": site.adresse,
        "ville": site.ville,
        "code_postal": site.code_postal,
        "telephone": site.telephone,
        "email": site.email,
        "contact_principal_id": site.contact_principal_id,
        "latitude": float(site.latitude) if site.latitude is not None else None,
        "longitude": float(site.longitude) if site.longitude is not None else None,
        "effectif_requis": site.effectif_requis,
        "is_active": site.is_active,
        "logo_url": site.logo_url,
        "created_at": site.created_at.isoformat() if site.created_at else None,
        "updated_at": site.updated_at.isoformat() if site.updated_at else None,
    }), 200


@sites_bp.post("")
@tenant_required
def create_site():
    """Crée un nouveau site"""
    data, logo_file, error = _parse_site_request()
    if error:
        return error

    # Validation des champs requis
    required_fields = ["client_id", "nom", "code_site", "adresse", "ville", "code_postal"]
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Le champ '{field}' est requis"}), 400

    # Vérifier que le client existe
    client = Client.query.filter_by(id=data["client_id"], tenant_id=g.tenant_id).first()
    if not client:
        return jsonify({"error": "Le client spécifié n'existe pas"}), 404

    # Vérifier unicité du code_site
    if Site.query.filter_by(tenant_id=g.tenant_id, code_site=data["code_site"]).first():
        return jsonify({"error": "Ce code site existe déjà"}), 409

    try:
        site = Site(
            client_id=data["client_id"],
            tenant_id=g.tenant_id,
            nom=data["nom"],
            code_site=data["code_site"],
        )

        updateable_fields = [
            "adresse", "ville", "code_postal", "telephone", "email",
            "contact_principal_id", "effectif_requis", "latitude", "longitude", "is_active"
        ]
        for field in updateable_fields:
            if field in data:
                setattr(site, field, data.get(field))

        db.session.add(site)
        db.session.flush()

        if logo_file:
            try:
                logo_url = _save_logo(logo_file, site)
                site.logo_url = logo_url
            except ValueError as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 400

        db.session.commit()

        return jsonify({
            "id": site.id,
            "message": "Site créé avec succès"
        }), 201

    except Exception as e:
        logger.error(f"Erreur création site: {e}")
        db.session.rollback()
        return jsonify({"error": "Erreur lors de la création du site"}), 500


@sites_bp.put("/<int:site_id>")
@tenant_required
def update_site(site_id):
    """Met à jour un site existant"""
    site = Site.query.filter_by(id=site_id, tenant_id=g.tenant_id).first_or_404()
    data, logo_file, error = _parse_site_request()
    if error:
        return error

    # Vérifier unicité du code_site si modifié
    if "code_site" in data and data["code_site"] != site.code_site:
        if Site.query.filter(Site.tenant_id == g.tenant_id, Site.code_site == data["code_site"], Site.id != site_id).first():
            return jsonify({"error": "Ce code site existe déjà"}), 409

    # Vérifier que le client existe si modifié
    if "client_id" in data:
        client = Client.query.filter_by(id=data["client_id"], tenant_id=g.tenant_id).first()
        if not client:
            return jsonify({"error": "Le client spécifié n'existe pas"}), 404

    try:
        updateable_fields = [
            "client_id", "nom", "code_site", "adresse", "ville", "code_postal",
            "telephone", "email", "contact_principal_id", "effectif_requis",
            "latitude", "longitude", "is_active"
        ]
        for field in updateable_fields:
            if field in data:
                setattr(site, field, data[field])

        if logo_file:
            try:
                _delete_logo(site)
                site.logo_url = _save_logo(logo_file, site)
            except ValueError as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                logger.error(f"Erreur sauvegarde logo site {site.id}: {e}")
        elif data.get('logo_url') is None and 'logo_url' in data:
            _delete_logo(site)
            site.logo_url = None

        db.session.commit()

        return jsonify({
            "message": "Site mis à jour avec succès"
        }), 200

    except Exception as e:
        logger.error(f"Erreur màj site {site_id}: {e}")
        db.session.rollback()
        return jsonify({"error": "Erreur lors de la mise à jour du site"}), 500


@sites_bp.delete("/<int:site_id>")
@tenant_required
def delete_site(site_id):
    """Supprime un site (soft delete - désactivation)"""
    site = Site.query.filter_by(id=site_id, tenant_id=g.tenant_id).first_or_404()

    try:
        site.is_active = False
        db.session.commit()

        return jsonify({
            "message": "Site désactivé avec succès",
            "id": site.id,
            "is_active": site.is_active,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erreur lors de la suppression du site"}), 500


@sites_bp.patch("/<int:site_id>/toggle")
@tenant_required
def toggle_site_status(site_id):
    """Active/désactive un site"""
    site = Site.query.filter_by(id=site_id, tenant_id=g.tenant_id).first_or_404()

    try:
        site.is_active = not site.is_active
        db.session.commit()

        return jsonify({
            "message": f"Site {'activé' if site.is_active else 'désactivé'} avec succès",
            "id": site.id,
            "is_active": site.is_active,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erreur lors du changement de statut"}), 500


@sites_bp.get("/client/<int:client_id>")
@tenant_required
def list_sites_by_client(client_id):
    """Liste tous les sites d'un client actifs"""
    # Vérifier que le client existe
    client = Client.query.filter_by(id=client_id, tenant_id=g.tenant_id).first_or_404()
    
    sites = Site.query.filter_by(tenant_id=g.tenant_id, client_id=client_id, is_active=True).all()
    data = [
        {
            "id": s.id,
            "client_id": s.client_id,
            "nom": s.nom,
            "code_site": s.code_site,
            "adresse": s.adresse,
            "ville": s.ville,
            "telephone": s.telephone,
            "contact_principal_id": s.contact_principal_id,
            "effectif_requis": s.effectif_requis,
            "is_active": s.is_active,
            "logo_url": s.logo_url,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sites
    ]
    return jsonify(data), 200
