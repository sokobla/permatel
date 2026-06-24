"""
Ce fichier de routes gère les opérations CRUD pour les agents de sécurité.
Il implémente la synchronisation automatique d'un enregistrement 'Contact'
pour chaque agent créé ou mis à jour.
"""
import json
from flask_cors import CORS
from flask import Blueprint, request, jsonify, g
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import AgentSecurite, Contact, Prestataire, UserRole
from app.utils.decorators import tenant_required
from app.utils.auth import role_required
from app.routes.contacts import _save_avatar, _delete_avatar
from app.services.agent_kpis import agent_kpis

agents_securite_bp = Blueprint('agents_securite', __name__, url_prefix='/api/agents')


def _parse_kpi_period():
    """Période [from, to] depuis la query (défaut : 30 derniers jours)."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()

    def _p(s, default):
        if not s:
            return default
        try:
            return datetime.fromisoformat(s.replace("Z", ""))
        except ValueError:
            return default

    return _p(request.args.get("from"), now - timedelta(days=30)), _p(request.args.get("to"), now)
CORS(agents_securite_bp, resources={r"/api/agents/*": {"origins": "*"}})

def _sync_agent_contact(agent: AgentSecurite, data: dict):
    """
    Crée ou met à jour le Contact associé pour un AgentSecurite.
    L'instance de l'agent est modifiée et doit être commitée par l'appelant.
    """
    contact = agent.contact or Contact()

    contact.nom = data.get('nom', agent.nom)
    contact.prenom = data.get('prenom', agent.prenom)
    contact.adresse = data.get('adresse', agent.adresse)
    contact.ville = data.get('ville', agent.ville)
    contact.telephone = data.get('telephone', agent.telephone)
    contact.email = data.get('email', agent.email)
    
    if 'avatar_url' in data:
        contact.avatar_url = data['avatar_url']

    contact.type = 'Agent de sécurité'
    contact.fonction = data.get('type_agent', agent.type_agent)

    prestataire_id = data.get('prestataire_id')
    if prestataire_id:
        prestataire = db.session.query(Prestataire).filter_by(id=prestataire_id, tenant_id=g.tenant.id).first()
        if not prestataire:
            raise ValueError("Prestataire non trouvé ou invalide.")
        contact.partner_id = prestataire_id
        contact.tenant_id = None
    else:
        contact.partner_id = None
        contact.tenant_id = g.tenant.id

    agent.contact = contact


def _agent_to_dict(agent: AgentSecurite) -> dict:
    """Sérialise un agent en dictionnaire."""
    return {
        "id": agent.id,
        "matricule": agent.matricule,
        "nom": agent.nom,
        "prenom": agent.prenom,
        "adresse": agent.adresse,
        "ville": agent.ville,
        "telephone": agent.telephone,
        "email": agent.email,
        "type_agent": agent.type_agent,
        "motorise": agent.motorise,
        "is_active": agent.is_active,
        "prestataire_id": str(agent.prestataire_id) if agent.prestataire_id else None,
        "prestataire_nom": agent.prestataire.nom if agent.prestataire else None,
        "contact_id": agent.contact.id if agent.contact else None,
        "avatar_url": agent.contact.avatar_url if agent.contact else None,
        "created_at": agent.created_at.isoformat(),
        "updated_at": agent.updated_at.isoformat(),
    }

@agents_securite_bp.route('', methods=['GET'])
@tenant_required
def list_agents():
    """Liste les agents du tenant avec filtres et pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    search = request.args.get("search", "", type=str).strip()

    query = AgentSecurite.query.filter(AgentSecurite.tenant_id == g.tenant.id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            AgentSecurite.nom.ilike(search_term),
            AgentSecurite.prenom.ilike(search_term),
            AgentSecurite.matricule.ilike(search_term)
        ))

    pagination = query.order_by(AgentSecurite.nom.asc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "agents": [_agent_to_dict(agent) for agent in pagination.items],
        "total": pagination.total,
    }), 200

@agents_securite_bp.route('/<int:agent_id>', methods=['GET'])
@tenant_required
def get_agent(agent_id):
    """Récupère un agent spécifique."""
    agent = AgentSecurite.query.filter_by(id=agent_id, tenant_id=g.tenant.id).first_or_404()
    return jsonify(_agent_to_dict(agent)), 200

@agents_securite_bp.route('', methods=['POST'])
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def create_agent():
    """Crée un nouvel agent et son contact associé."""
    data_str = request.form.get('data')
    if data_str:
        data = json.loads(data_str)
    else:
        data = request.get_json() or {}
        
    avatar_file = request.files.get('avatar')
    
    required_fields = ["matricule", "nom", "prenom"]
    if any(field not in data or not data[field] for field in required_fields):
        return jsonify({"error": f"Les champs {', '.join(required_fields)} sont requis."}), 400

    if AgentSecurite.query.filter_by(tenant_id=g.tenant.id, matricule=data["matricule"]).first():
        return jsonify({"error": "Ce matricule est déjà utilisé dans ce tenant."}), 409

    agent = AgentSecurite(tenant_id=g.tenant.id)
    
    # Mettre à jour les attributs de l'agent
    allowed_fields = [
        "matricule", "nom", "prenom", "adresse", "ville", 
        "telephone", "email", "type_agent", "motorise", "is_active", "prestataire_id"
    ]
    for field in allowed_fields:
        if field in data and hasattr(agent, field):
            val = data[field]
            if field == "prestataire_id" and not val:
                val = None
            setattr(agent, field, val)

    try:
        _sync_agent_contact(agent, data)
        db.session.add(agent)
        db.session.flush() # Génère l'ID du contact avant de sauvegarder l'image
        
        if avatar_file and agent.contact:
            try:
                agent.contact.avatar_url = _save_avatar(avatar_file, agent.contact)
            except ValueError as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 400
                
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 422
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Erreur d'intégrité, le matricule existe peut-être déjà."}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur inattendue: {str(e)}"}), 500

    return jsonify(_agent_to_dict(agent)), 201

@agents_securite_bp.route('/<int:agent_id>', methods=['PUT', 'PATCH', 'POST'])
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def update_agent(agent_id):
    """Met à jour un agent et son contact associé."""
    agent = AgentSecurite.query.filter_by(id=agent_id, tenant_id=g.tenant.id).first_or_404()
    
    data_str = request.form.get('data')
    if data_str:
        data = json.loads(data_str)
    else:
        data = request.get_json() or {}
        
    avatar_file = request.files.get('avatar')

    if "matricule" in data and data["matricule"] != agent.matricule:
        if AgentSecurite.query.filter(AgentSecurite.tenant_id == g.tenant.id, AgentSecurite.matricule == data["matricule"], AgentSecurite.id != agent_id).first():
            return jsonify({"error": "Ce matricule est déjà utilisé."}), 409

    # Mettre à jour les attributs de l'agent
    allowed_fields = [
        "matricule", "nom", "prenom", "adresse", "ville", 
        "telephone", "email", "type_agent", "motorise", "is_active", "prestataire_id"
    ]
    for field in allowed_fields:
        if field in data and hasattr(agent, field):
            val = data[field]
            if field == "prestataire_id" and not val:
                val = None
            setattr(agent, field, val)

    try:
        _sync_agent_contact(agent, data)
        db.session.flush() # Génère l'ID du contact s'il vient d'être créé
        
        if avatar_file and agent.contact:
            try:
                _delete_avatar(agent.contact)
                agent.contact.avatar_url = _save_avatar(avatar_file, agent.contact)
            except ValueError as e:
                db.session.rollback()
                return jsonify({"error": str(e)}), 400
        elif data.get('avatar_url') is None and 'avatar_url' in data and agent.contact:
            _delete_avatar(agent.contact)
            agent.contact.avatar_url = None
            
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur inattendue: {str(e)}"}), 500

    return jsonify(_agent_to_dict(agent)), 200

@agents_securite_bp.route('/<int:agent_id>', methods=['DELETE'])
@tenant_required
@role_required(UserRole.ADMIN)
def delete_agent(agent_id):
    """Supprime un agent et son contact associé (suppression physique)."""
    agent = AgentSecurite.query.filter_by(id=agent_id, tenant_id=g.tenant.id).first_or_404()

    try:
        if agent.contact:
            _delete_avatar(agent.contact)
        # La suppression du contact est gérée par la cascade 'delete-orphan'
        db.session.delete(agent)
        db.session.commit()
        return jsonify({"message": "Agent et contact associé supprimés avec succès."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur lors de la suppression: {str(e)}"}), 500


# ── KPI agents (Anomalies / Incidents agent / Score) ─────────────────────────
@agents_securite_bp.get('/stats')
@tenant_required
def agents_stats():
    """Répartition des agents actifs par qualification (type_agent) pour le tenant."""
    from sqlalchemy import func
    rows = (
        db.session.query(
            AgentSecurite.type_agent,
            func.count(AgentSecurite.id).label('count')
        )
        .filter(
            AgentSecurite.tenant_id == g.tenant.id,
            AgentSecurite.is_active.is_(True),
        )
        .group_by(AgentSecurite.type_agent)
        .order_by(func.count(AgentSecurite.id).desc())
        .all()
    )
    return jsonify([
        {"qualification": r.type_agent or "Non renseigné", "count": r.count}
        for r in rows
    ]), 200


@agents_securite_bp.get('/<int:agent_id>/kpis')
@tenant_required
def agent_kpis_endpoint(agent_id):
    """KPI d'un agent sur la période du filtre (?from&to, défaut 30j)."""
    agent = AgentSecurite.query.filter_by(id=agent_id, tenant_id=g.tenant.id).first_or_404()
    dt_from, dt_to = _parse_kpi_period()
    data = agent_kpis(g.tenant.id, agent.id, dt_from, dt_to)
    data["period"] = {"from": dt_from.isoformat(), "to": dt_to.isoformat()}
    return jsonify(data), 200


@agents_securite_bp.get('/kpis')
@tenant_required
@role_required(UserRole.ADMIN, UserRole.MANAGER)
def agents_kpis_list():
    """KPI agrégés de tous les agents actifs du tenant (tableau de bord)."""
    dt_from, dt_to = _parse_kpi_period()
    agents = AgentSecurite.query.filter_by(tenant_id=g.tenant.id, is_active=True).all()
    rows = []
    for a in agents:
        k = agent_kpis(g.tenant.id, a.id, dt_from, dt_to)
        k["matricule"] = a.matricule
        k["nom"] = f"{a.prenom} {a.nom}".strip()
        k["type_agent"] = a.type_agent
        rows.append(k)
    rows.sort(key=lambda r: (r["score"], -r["incidents"]))  # plus à risque en tête
    return jsonify({"agents": rows, "period": {"from": dt_from.isoformat(), "to": dt_to.isoformat()}}), 200