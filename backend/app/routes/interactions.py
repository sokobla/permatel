import uuid
from flask import Blueprint, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity

from app import db
from app.models.interaction import Interaction, TypeInteraction
from app.models.demande import Demande
from app.utils.decorators import tenant_required

interactions_bp = Blueprint("interactions", __name__, url_prefix="/api/interactions")
CORS(interactions_bp, resources={r"/api/interactions/*": {"origins": "*"}})


def _get_tenant_id(claims):
    tid = claims.get("tid")
    if isinstance(tid, str):
        try:
            return uuid.UUID(tid)
        except ValueError:
            return None
    return tid


@interactions_bp.post("")
@jwt_required()
@tenant_required
def create_interaction():
    claims    = get_jwt()
    tenant_id = _get_tenant_id(claims)
    user_id   = get_jwt_identity()

    if not tenant_id:
        return jsonify({"error": "Tenant non identifié."}), 400

    data = request.get_json(silent=True) or {}

    demande_id       = data.get("demande_id")
    type_interaction = data.get("type_interaction")
    contenu          = (data.get("contenu") or "").strip()
    contact_id       = data.get("contact_id") or None

    if not demande_id:
        return jsonify({"error": "demande_id est requis."}), 400
    if not type_interaction:
        return jsonify({"error": "type_interaction est requis."}), 400
    if not contenu:
        return jsonify({"error": "contenu est requis."}), 400

    try:
        type_enum = TypeInteraction(type_interaction)
    except ValueError:
        return jsonify({"error": f"type_interaction invalide : {type_interaction}"}), 400

    demande = Demande.query.filter_by(id=demande_id, tenant_id=tenant_id).first()
    if not demande:
        return jsonify({"error": "Demande introuvable."}), 404

    interaction = Interaction(
        demande_id       = demande_id,
        user_id          = user_id,
        tenant_id        = tenant_id,
        type_interaction = type_enum,
        contenu          = contenu,
        contact_id       = contact_id,
    )
    db.session.add(interaction)
    db.session.commit()

    contact_nom = None
    try:
        if interaction.contact:
            contact_nom = f"{interaction.contact.prenom or ''} {interaction.contact.nom or ''}".strip() or None
    except Exception:
        pass

    return jsonify({
        "id":               interaction.id,
        "demande_id":       interaction.demande_id,
        "type_interaction": interaction.type_interaction.value,
        "contenu":          interaction.contenu,
        "contact_id":       interaction.contact_id,
        "contact_nom":      contact_nom,
        "created_at":       interaction.created_at.isoformat(),
    }), 201
