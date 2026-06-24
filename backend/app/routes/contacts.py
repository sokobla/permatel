import os
from flask_cors import CORS
from flask import Blueprint, request, jsonify, g, current_app
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename
import json

from app import db
from app.models import Contact, Client, Site, Prestataire, UserRole
from app.utils.decorators import tenant_required
from app.utils.auth import role_required

contacts_bp = Blueprint('contacts', __name__, url_prefix='/api/contacts')
CORS(contacts_bp, resources={r"/api/contacts/*": {"origins": "*"}})

def _save_avatar(file, contact):
    if not file or not file.filename:
        return None

    allowed_extensions_str = current_app.config.get("ALLOWED_AVATAR_EXTENSIONS", ".png,.jpg,.jpeg,.gif,.webp")
    allowed_extensions = {f".{ext.strip().lstrip('.')}" for ext in allowed_extensions_str.split(",")}
    max_size_mb = int(current_app.config.get("MAX_AVATAR_SIZE_MB", 2))

    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in allowed_extensions:
        raise ValueError(f"Extension non autorisée. Attendu: {', '.join(allowed_extensions)}")

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > max_size_mb * 1024 * 1024:
        raise ValueError(f"Fichier trop volumineux. Taille max: {max_size_mb}MB.")

    filename = secure_filename(f"contact_{contact.id}_avatar{ext}")
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    return f"/uploads/{filename}"

def _delete_avatar(contact):
    if not contact or not getattr(contact, 'avatar_url', None):
        return
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    filename = os.path.basename(contact.avatar_url)
    file_path = os.path.join(upload_folder, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

def _contact_to_dict(contact: Contact) -> dict:
    """Sérialise un contact en dictionnaire."""
    return {
        "id": contact.id,
        "avatar_url": contact.avatar_url,
        "nom": contact.nom,
        "prenom": contact.prenom,
        "adresse": contact.adresse,
        "ville": contact.ville,
        "telephone": contact.telephone,
        "email": contact.email,
        "type": contact.type,
        "agent_securite_id": contact.agent_securite_id,
        "fonction": contact.fonction,
        "notes": contact.notes,
        "tenant_id": str(contact.tenant_id) if contact.tenant_id else None,
        "prestataire_id": str(contact.partner_id) if contact.partner_id else None,
        "prestataire": contact.partner.nom if contact.partner else None,
        "clients": [{"id": client.id, "nom": client.nom} for client in contact.clients],
        "sites": [{"id": site.id, "nom": site.nom} for site in contact.sites],
        "created_at": contact.created_at.isoformat(),
        "updated_at": contact.updated_at.isoformat(),
    }

@contacts_bp.route('/grouped', methods=['GET'])
@tenant_required
def list_grouped_contacts():
    """Retourne les contacts groupés par type pour les listes déroulantes de contact principal."""
    query = Contact.query.join(
        Prestataire, Contact.partner_id == Prestataire.id, isouter=True
    ).filter(
        or_(Contact.tenant_id == g.tenant.id, Prestataire.tenant_id == g.tenant.id)
    ).all()
    
    grouped = {
        "Tenant": [],
        "Client": [],
        "Prestataire": [],
        "Agent de sécurité": []
    }
    
    for c in query:
        if c.type in grouped:
            grouped[c.type].append({"id": c.id, "nom": f"{c.nom} {c.prenom}".strip()})
            
    return jsonify(grouped), 200

@contacts_bp.route('', methods=['GET'])
@tenant_required
def list_contacts():
    """
    Liste les contacts du tenant avec filtres et pagination.
    Filtres supportés: nom, prenom, telephone, ville, type, prestataire_id, client_id, site_id.
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    
    # Filtres
    search_query = request.args.get("search", type=str)
    status_filter = request.args.get("status", type=str)

    # La requête de base cible les contacts du tenant ou ceux liés à un prestataire du tenant.
    query = Contact.query.options(
        joinedload(Contact.partner),
        joinedload(Contact.clients),
        joinedload(Contact.sites)
    ).join(Prestataire, Contact.partner_id == Prestataire.id, isouter=True).filter(
        or_(Contact.tenant_id == g.tenant.id, Prestataire.tenant_id == g.tenant.id)
    )

    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            or_(
                Contact.nom.ilike(search_term),
                Contact.prenom.ilike(search_term),
                Contact.email.ilike(search_term),
                Contact.telephone.ilike(search_term),
                Contact.ville.ilike(search_term),
                Contact.fonction.ilike(search_term)
            )
        )

    if status_filter:
        if status_filter.lower() == 'true':
            query = query.filter(Prestataire.is_active == True)
        elif status_filter.lower() == 'false':
            query = query.filter(Prestataire.is_active == False)

    # Filtres contextuels robustes
    client_ids_raw = request.args.getlist('client_id') + request.args.getlist('client_id[]')
    if client_ids_raw:
        client_ids = {int(cid.strip()) for val in client_ids_raw for cid in str(val).split(',') if cid.strip().isdigit()}
        if client_ids:
            query = query.join(Contact.clients).filter(Client.id.in_(client_ids))

    prestataire_ids_raw = request.args.getlist('prestataire_id') + request.args.getlist('prestataire_id[]')
    if prestataire_ids_raw:
        # Gère les UUIDs et les IDs numériques
        prestataire_ids = {pid.strip() for val in prestataire_ids_raw for pid in str(val).split(',') if pid.strip()}
        if prestataire_ids:
            query = query.filter(Contact.partner_id.in_(prestataire_ids))
            
    site_ids_raw = request.args.getlist('site_id') + request.args.getlist('site_id[]')
    if site_ids_raw:
        site_ids = {int(sid.strip()) for val in site_ids_raw for sid in str(val).split(',') if sid.strip().isdigit()}
        if site_ids:
            query = query.join(Contact.sites).filter(Site.id.in_(site_ids))

    pagination = query.distinct().order_by(Contact.nom.asc(), Contact.prenom.asc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "contacts": [_contact_to_dict(contact) for contact in pagination.items],
        "total": pagination.total,
    }), 200


@contacts_bp.route('', methods=['POST'])
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def create_contact():
    """Crée un nouveau contact (Tenant, Client ou Prestataire)."""
    
    # Extraction du payload JSON depuis le multipart/form-data ou le body direct
    data_str = request.form.get('data')
    if data_str:
        data = json.loads(data_str)
    else:
        data = request.get_json() or {}
        
    avatar_file = request.files.get('avatar')

    contact_type = data.get('type')
    if contact_type == 'Agent de sécurité':
        return jsonify({"error": "La création des contacts de type 'Agent de sécurité' doit se faire via le module Agents."}), 403

    contact = Contact(
        nom=data.get('nom'),
        prenom=data.get('prenom'),
        adresse=data.get('adresse'),
        ville=data.get('ville'),
        telephone=data.get('telephone'),
        email=data.get('email'),
        fonction=data.get('fonction'),
        type=contact_type,
        notes=data.get('notes')
    )

    if contact_type == 'Prestataire':
        prestataire_id = data.get('prestataire_id')
        if not prestataire_id:
            return jsonify({"error": "Le champ Prestataire est requis pour ce type de contact."}), 422
        prestataire = Prestataire.query.filter_by(id=prestataire_id, tenant_id=g.tenant.id).first_or_404()
        contact.partner_id = prestataire_id

    elif contact_type == 'Client':
        client_ids = data.get('client_ids', [])
        if not client_ids:
            return jsonify({"error": "Le champ Client est requis pour ce type de contact."}), 422
        
        contact.tenant_id = g.tenant.id
        contact.clients = Client.query.filter(Client.id.in_(client_ids), Client.tenant_id == g.tenant.id).all()
        
        site_ids = data.get('site_ids', [])
        if site_ids:
            contact.sites = Site.query.filter(Site.id.in_(site_ids), Site.tenant_id == g.tenant.id).all()

    elif contact_type == 'Tenant':
        contact.tenant_id = g.tenant.id

    try:
        db.session.add(contact)
        db.session.flush() # Génère l'ID du contact avant sauvegarde de l'image
        
        if avatar_file:
            try:
                contact.avatar_url = _save_avatar(avatar_file, contact)
            except ValueError as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 400
                
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur lors de la création: {str(e)}"}), 500

    return jsonify(_contact_to_dict(contact)), 201


@contacts_bp.route('/<int:contact_id>', methods=['PUT'])
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def update_contact(contact_id):
    """Met à jour un contact (sauf type 'Agent de sécurité')."""
    
    # Récupérer le contact en s'assurant qu'il appartient au tenant
    contact = Contact.query.join(
        Prestataire, Contact.partner_id == Prestataire.id, isouter=True
    ).filter(
        Contact.id == contact_id,
        or_(Contact.tenant_id == g.tenant.id, Prestataire.tenant_id == g.tenant.id)
    ).first_or_404()

    if contact.type == 'Agent de sécurité':
        return jsonify({"error": "La modification des contacts de type 'Agent de sécurité' doit se faire via le module Agents."}), 403

    # Adaptation pour supporter multipart/form-data contenant un payload 'data' en JSON
    data_str = request.form.get('data')
    if data_str:
        data = json.loads(data_str)
    else:
        data = request.get_json() or {}
        
    avatar_file = request.files.get('avatar')
    
    # Mise à jour des champs simples (sauf avatar_url)
    for field in ['nom', 'prenom', 'adresse', 'ville', 'telephone', 'email', 'fonction', 'notes']:
        if field in data:
            setattr(contact, field, data[field])
            
    if avatar_file:
        try:
            _delete_avatar(contact)
            contact.avatar_url = _save_avatar(avatar_file, contact)
        except ValueError as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 400
    elif data.get('avatar_url') is None and 'avatar_url' in data:
        _delete_avatar(contact)
        contact.avatar_url = None

    contact_type = data.get('type', contact.type)
    contact.type = contact_type

    # Logique métier en fonction du type
    if contact_type == 'Prestataire':
        prestataire_id = data.get('prestataire_id')
        if not prestataire_id:
            return jsonify({"error": "Le champ Prestataire est requis pour ce type de contact."}), 422
        
        prestataire = Prestataire.query.filter_by(id=prestataire_id, tenant_id=g.tenant.id).first_or_404()
            
        contact.partner_id = prestataire_id
        contact.tenant_id = None # Règle XOR
        contact.clients.clear()
        contact.sites.clear()

    elif contact_type == 'Client':
        client_ids = data.get('client_ids', [])
        if not client_ids:
            return jsonify({"error": "Le champ Client est requis pour ce type de contact."}), 422

        contact.tenant_id = g.tenant.id
        contact.partner_id = None # Règle XOR

        contact.clients = Client.query.filter(Client.id.in_(client_ids), Client.tenant_id == g.tenant.id).all()
        if len(contact.clients) != len(client_ids):
            return jsonify({"error": "Un ou plusieurs clients sont invalides."}), 422

        site_ids = data.get('site_ids', [])
        contact.sites = Site.query.filter(Site.id.in_(site_ids), Site.tenant_id == g.tenant.id).all() if site_ids else []
        if site_ids and len(contact.sites) != len(site_ids):
            return jsonify({"error": "Un ou plusieurs sites sont invalides."}), 422

    elif contact_type == 'Tenant':
        contact.tenant_id = g.tenant.id
        contact.partner_id = None # Règle XOR
        contact.clients.clear()
        contact.sites.clear()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur lors de la mise à jour: {str(e)}"}), 500

    return jsonify(_contact_to_dict(contact)), 200

@contacts_bp.route('/<int:contact_id>', methods=['DELETE'])
@tenant_required
@role_required(UserRole.ADMIN)
def delete_contact(contact_id):
    """Supprime un contact (sauf type 'Agent de sécurité')."""
    contact = Contact.query.join(
        Prestataire, Contact.partner_id == Prestataire.id, isouter=True
    ).filter(
        Contact.id == contact_id,
        or_(Contact.tenant_id == g.tenant.id, Prestataire.tenant_id == g.tenant.id)
    ).first_or_404()

    if contact.type == 'Agent de sécurité':
        return jsonify({"error": "La suppression des contacts de type 'Agent de sécurité' doit se faire via le module Agents."}), 403

    try:
        _delete_avatar(contact)
        db.session.delete(contact)
        db.session.commit()
        return jsonify({"message": "Contact supprimé avec succès."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur lors de la suppression: {str(e)}"}), 500