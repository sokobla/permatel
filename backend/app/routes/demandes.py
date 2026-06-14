from datetime import datetime
import uuid
from flask import Blueprint, jsonify, request, g
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.demande import (
    Demande, DemandeAnomalie, DemandeCommande, DemandePlanning, DemandeAdmin,
    TypeDemande, StatutDemande, PrioriteDemande,
    NatureAnomalie, EquipementConcerne, TypeCommande, TypeModificationPlanning, CategorieAdmin, TypeDocumentAdmin
)
from app.models.user import User, UserRole
from app.models.client import Client
from app.models.site import Site
from app.models.contact import Contact
from app.models.tenant import Tenant
from app.utils.auth import role_required
from app.utils.decorators import tenant_required


demandes_bp = Blueprint("demandes", __name__, url_prefix="/api/demandes")


def _get_tenant_id_from_claims(claims):
    tenant_id = claims.get("tid")
    if isinstance(tenant_id, str):
        try:
            return uuid.UUID(tenant_id)
        except ValueError:
            return None
    return tenant_id


# ============================================================================
# SÉRIALISATION
# ============================================================================

def _serialize_demande(demande: Demande) -> dict:
    """Sérialise une demande (parent + champs spécifiques selon type)."""
    data = {
        "id": demande.id,
        "numero_ticket": demande.numero_ticket,
        "type_demande": demande.type_demande.value,
        "titre": demande.titre,
        "description": demande.description,
        "statut": demande.statut.value,
        "priorite": demande.priorite.value,
        "client_id": demande.client_id,
        "site_id": demande.site_id,
        "contact_id": demande.contact_id,
        "permanencier_id": demande.permanencier_id,
        "closed_by_id": demande.closed_by_id,
        "sla_deadline": demande.sla_deadline.isoformat() if demande.sla_deadline else None,
        "date_resolution": demande.date_resolution.isoformat() if demande.date_resolution else None,
        "closed_at": demande.closed_at.isoformat() if demande.closed_at else None,
        "is_deleted": demande.is_deleted,
        "deleted_at": demande.deleted_at.isoformat() if demande.deleted_at else None,
        "created_at": demande.created_at.isoformat() if demande.created_at else None,
        "updated_at": demande.updated_at.isoformat() if demande.updated_at else None,
        "tenant_id": str(demande.tenant_id) if demande.tenant_id else None,
    }
    
    # Ajouter champs spécifiques selon type
    if isinstance(demande, DemandeAnomalie):
        data["nature_anomalie"] = demande.nature_anomalie.value if demande.nature_anomalie else None
        data["equipement_concerne"] = demande.equipement_concerne.value if demande.equipement_concerne else None
        data["localisation_precise"] = demande.localisation_precise
        data["impact_securite"] = demande.impact_securite
        data["action_corrective"] = demande.action_corrective
    
    elif isinstance(demande, DemandeCommande):
        data["type_commande"] = demande.type_commande.value if demande.type_commande else None
        data["quantite"] = demande.quantite
        data["budget_estime"] = demande.budget_estime
        data["fournisseur_suggere"] = demande.fournisseur_suggere
        data["date_livraison_souhaitee"] = demande.date_livraison_souhaitee.isoformat() if demande.date_livraison_souhaitee else None
        data["bon_commande"] = demande.bon_commande
    
    elif isinstance(demande, DemandePlanning):
        data["type_modification"] = demande.type_modification.value if demande.type_modification else None
        data["agent_concerne_id"] = demande.agent_concerne_id
        data["agent_remplacant_id"] = demande.agent_remplacant_id
        data["date_debut"] = demande.date_debut.isoformat() if demande.date_debut else None
        data["date_fin"] = demande.date_fin.isoformat() if demande.date_fin else None
        data["motif"] = demande.motif
    
    elif isinstance(demande, DemandeAdmin):
        data["categorie"] = demande.categorie.value if demande.categorie else None
        data["document_type"] = demande.document_type.value if demande.document_type else None
        data["date_echeance"] = demande.date_echeance.isoformat() if demande.date_echeance else None
        data["validation_requise"] = demande.validation_requise
    
    return data


# ============================================================================
# ENDPOINTS
# ============================================================================

@demandes_bp.get("")
@tenant_required
def list_demandes():
    """Liste toutes les demandes non supprimées pour le tenant actif."""
    claims = get_jwt()
    tenant_id = _get_tenant_id_from_claims(claims)
    if not tenant_id:
        return jsonify({"message": "Aucun tenant actif sélectionné."}), 400

    demandes = Demande.query.filter_by(
        tenant_id=tenant_id,
        is_deleted=False
    ).order_by(Demande.created_at.desc()).all()
    
    return jsonify([_serialize_demande(d) for d in demandes]), 200


@demandes_bp.get("/<int:demande_id>")
@tenant_required
def get_demande(demande_id):
    """Récupère une demande spécifique pour le tenant actif."""
    claims = get_jwt()
    tenant_id = _get_tenant_id_from_claims(claims)
    if not tenant_id:
        return jsonify({"message": "Aucun tenant actif sélectionné."}), 400

    demande = Demande.query.filter_by(
        id=demande_id, tenant_id=tenant_id, is_deleted=False
    ).first()
    if not demande:
        return jsonify({"message": "Demande introuvable"}), 404
    
    return jsonify(_serialize_demande(demande)), 200


@demandes_bp.post("")
@tenant_required
def create_demande():
    """Crée une nouvelle demande pour le tenant actif."""
    claims = get_jwt()
    tenant_id = _get_tenant_id_from_claims(claims)
    user_id = claims.get("sub")
    if not tenant_id:
        return jsonify({"message": "Aucun tenant actif sélectionné."}), 400

    payload = request.get_json(silent=True) or {}
    
    # Validations minimales
    required_fields = ["type_demande", "client_id", "titre"]
    missing_fields = [f for f in required_fields if f not in payload or not payload.get(f)]
    
    if missing_fields:
        return jsonify({
            "message": "Champs obligatoires manquants",
            "missing_fields": missing_fields
        }), 400
    
    # Valider type_demande
    try:
        type_demande = TypeDemande(payload["type_demande"])
    except ValueError:
        return jsonify({
            "message": "type_demande invalide",
            "valid_values": [t.value for t in TypeDemande]
        }), 400
    
    # Valider statut si fourni
    statut = StatutDemande.NOUVELLE
    if "statut" in payload:
        try:
            statut = StatutDemande(payload["statut"])
        except ValueError:
            return jsonify({
                "message": "statut invalide",
                "valid_values": [s.value for s in StatutDemande]
            }), 400
    
    # Valider priorite si fournie
    priorite = PrioriteDemande.NORMALE
    if "priorite" in payload:
        try:
            priorite = PrioriteDemande(payload["priorite"])
        except ValueError:
            return jsonify({
                "message": "priorite invalide",
                "valid_values": [p.value for p in PrioriteDemande]
            }), 400
    
    # Vérifier références (user, client, site, contact)
    permanencier_id = payload.get("permanencier_id", user_id)
    permanencier = User.query.get(permanencier_id)
    if not permanencier:
        return jsonify({"message": "Permanencier introuvable"}), 404
    
    client = Client.query.filter_by(id=payload["client_id"], tenant_id=tenant_id).first()
    if not client:
        return jsonify({"message": f"Client {payload['client_id']} introuvable dans ce tenant"}), 404
    
    site = None
    if payload.get("site_id"):
        site = Site.query.filter_by(id=payload["site_id"], tenant_id=tenant_id).first()
        if not site:
            return jsonify({"message": f"Site {payload['site_id']} introuvable dans ce tenant"}), 404
        if site.client_id != client.id:
            return jsonify({"message": "Le site n'appartient pas au client spécifié"}), 400
    
    contact = None
    if payload.get("contact_id"):
        contact = Contact.query.get(payload["contact_id"])
        if not contact:
            return jsonify({"message": "Contact introuvable"}), 404

    # Dictionnaire des paramètres de base pour toutes les demandes
    base_params = {
        "type_demande": type_demande,
        "client_id": client.id,
        "site_id": site.id if site else None,
        "contact_id": contact.id if contact else None,
        "permanencier_id": permanencier.id,
        "titre": payload["titre"],
        "description": payload.get("description"),
        "statut": statut,
        "priorite": priorite,
        "tenant_id": tenant_id,
    }

    model_map = {
        TypeDemande.ANOMALIE: DemandeAnomalie,
        TypeDemande.COMMANDE: DemandeCommande,
        TypeDemande.PLANNING: DemandePlanning,
        TypeDemande.ADMIN: DemandeAdmin,
    }
    
    try:
        demande_class = model_map[type_demande]
        demande = demande_class(**base_params)
        demande.numero_ticket = "TEMP"  # placeholder to satisfy not-null constraint before flush

        if type_demande == TypeDemande.ANOMALIE:
            if "nature_anomalie" in payload:
                try:
                    demande.nature_anomalie = NatureAnomalie(payload["nature_anomalie"])
                except ValueError:
                    pass
            if "equipement_concerne" in payload:
                try:
                    demande.equipement_concerne = EquipementConcerne(payload["equipement_concerne"])
                except ValueError:
                    pass
            demande.localisation_precise = payload.get("localisation_precise")
            demande.impact_securite = payload.get("impact_securite", False)
            demande.action_corrective = payload.get("action_corrective")
        
        elif type_demande == TypeDemande.COMMANDE:
            if "type_commande" in payload:
                try:
                    demande.type_commande = TypeCommande(payload["type_commande"])
                except ValueError:
                    pass
            demande.quantite = payload.get("quantite")
            demande.budget_estime = payload.get("budget_estime")
            demande.fournisseur_suggere = payload.get("fournisseur_suggere")
            demande.date_livraison_souhaitee = payload.get("date_livraison_souhaitee")
            demande.bon_commande = payload.get("bon_commande")
        
        elif type_demande == TypeDemande.PLANNING:
            if "type_modification" in payload:
                try:
                    demande.type_modification = TypeModificationPlanning(payload["type_modification"])
                except ValueError:
                    pass
            demande.agent_concerne_id = payload.get("agent_concerne_id")
            demande.agent_remplacant_id = payload.get("agent_remplacant_id")
            demande.date_debut = payload.get("date_debut")
            demande.date_fin = payload.get("date_fin")
            demande.motif = payload.get("motif")
        
        elif type_demande == TypeDemande.ADMIN:
            if "categorie" in payload:
                try:
                    demande.categorie = CategorieAdmin(payload["categorie"])
                except ValueError:
                    pass
            if "document_type" in payload:
                try:
                    demande.document_type = TypeDocumentAdmin(payload["document_type"])
                except ValueError:
                    pass
            demande.date_echeance = payload.get("date_echeance")
            demande.validation_requise = payload.get("validation_requise", False)
        
        db.session.add(demande)
        db.session.flush()  # Pour obtenir l'ID avant de générer le numéro de ticket
        
        # Générer numéro ticket final
        demande.numero_ticket = f"{type_demande.value.upper()[:4]}_{demande.id}"
        db.session.commit()
        
        return jsonify(_serialize_demande(demande)), 201
    
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": "Contrainte d'intégrité violée", "error": str(e)}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erreur lors de la création", "error": str(e)}), 500


@demandes_bp.put("/<int:demande_id>")
@tenant_required
def update_demande(demande_id):
    """Met à jour une demande existante."""
    claims = get_jwt()
    tenant_id = _get_tenant_id_from_claims(claims)
    if not tenant_id:
        return jsonify({"message": "Aucun tenant actif sélectionné."}), 400

    demande = Demande.query.filter_by(
        id=demande_id, tenant_id=tenant_id, is_deleted=False
    ).first_or_404(description="Demande introuvable")
    
    payload = request.get_json(silent=True) or {}
    
    try:
        # Champs génériques
        if "titre" in payload:
            demande.titre = payload["titre"]
        if "description" in payload:
            demande.description = payload["description"]
        
        if "statut" in payload:
            try:
                demande.statut = StatutDemande(payload["statut"])
            except ValueError:
                return jsonify({"message": "statut invalide"}), 400
        
        if "priorite" in payload:
            try:
                demande.priorite = PrioriteDemande(payload["priorite"])
            except ValueError:
                return jsonify({"message": "priorite invalide"}), 400
        
        if "sla_deadline" in payload:
            demande.sla_deadline = payload["sla_deadline"]
        
        # Champs spécifiques selon type
        if isinstance(demande, DemandeAnomalie):
            if "nature_anomalie" in payload:
                try:
                    demande.nature_anomalie = NatureAnomalie(payload["nature_anomalie"])
                except ValueError:
                    pass
            if "equipement_concerne" in payload:
                try:
                    demande.equipement_concerne = EquipementConcerne(payload["equipement_concerne"])
                except ValueError:
                    pass
            if "localisation_precise" in payload:
                demande.localisation_precise = payload["localisation_precise"]
            if "impact_securite" in payload:
                demande.impact_securite = payload["impact_securite"]
            if "action_corrective" in payload:
                demande.action_corrective = payload["action_corrective"]
        
        elif isinstance(demande, DemandeCommande):
            if "type_commande" in payload:
                try:
                    demande.type_commande = TypeCommande(payload["type_commande"])
                except ValueError:
                    pass
            if "quantite" in payload:
                demande.quantite = payload["quantite"]
            if "budget_estime" in payload:
                demande.budget_estime = payload["budget_estime"]
            if "fournisseur_suggere" in payload:
                demande.fournisseur_suggere = payload["fournisseur_suggere"]
            if "date_livraison_souhaitee" in payload:
                demande.date_livraison_souhaitee = payload["date_livraison_souhaitee"]
            if "bon_commande" in payload:
                demande.bon_commande = payload["bon_commande"]
        
        elif isinstance(demande, DemandePlanning):
            if "type_modification" in payload:
                try:
                    demande.type_modification = TypeModificationPlanning(payload["type_modification"])
                except ValueError:
                    pass
            if "agent_concerne_id" in payload:
                demande.agent_concerne_id = payload["agent_concerne_id"]
            if "agent_remplacant_id" in payload:
                demande.agent_remplacant_id = payload["agent_remplacant_id"]
            if "date_debut" in payload:
                demande.date_debut = payload["date_debut"]
            if "date_fin" in payload:
                demande.date_fin = payload["date_fin"]
            if "motif" in payload:
                demande.motif = payload["motif"]
        
        elif isinstance(demande, DemandeAdmin):
            if "categorie" in payload:
                try:
                    demande.categorie = CategorieAdmin(payload["categorie"])
                except ValueError:
                    pass
            if "document_type" in payload:
                try:
                    demande.document_type = TypeDocumentAdmin(payload["document_type"])
                except ValueError:
                    pass
            if "date_echeance" in payload:
                demande.date_echeance = payload["date_echeance"]
            if "validation_requise" in payload:
                demande.validation_requise = payload["validation_requise"]
        
        demande.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify(_serialize_demande(demande)), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Erreur lors de la mise à jour", "error": str(e)}), 500


@demandes_bp.patch("/<int:demande_id>/status")
@tenant_required
def patch_demande_status(demande_id):
    """Met à jour seulement le statut d'une demande."""
    claims = get_jwt()
    tenant_id = _get_tenant_id_from_claims(claims)
    if not tenant_id:
        return jsonify({"message": "Aucun tenant actif sélectionné."}), 400

    demande = Demande.query.filter_by(
        id=demande_id, tenant_id=tenant_id, is_deleted=False
    ).first_or_404(description="Demande introuvable")

    payload = request.get_json(silent=True) or {}
    
    if "statut" not in payload:
        return jsonify({"message": "Le champ 'statut' est requis"}), 400
    
    try:
        demande.statut = StatutDemande(payload["statut"])
    except ValueError:
        return jsonify({
            "message": "statut invalide",
            "valid_values": [s.value for s in StatutDemande]
        }), 400
    
    demande.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify(_serialize_demande(demande)), 200


@demandes_bp.delete("/<int:demande_id>")
@tenant_required
@role_required(UserRole.ADMIN)
def delete_demande(demande_id):
    """Soft delete d'une demande."""
    claims = get_jwt()
    tenant_id = _get_tenant_id_from_claims(claims)
    if not tenant_id:
        return jsonify({"message": "Aucun tenant actif sélectionné."}), 400

    demande = Demande.query.filter_by(
        id=demande_id, tenant_id=tenant_id, is_deleted=False
    ).first_or_404(description="Demande introuvable")

    try:
        demande.is_deleted = True
        demande.deleted_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({"message": "Demande supprimée"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erreur lors de la suppression.", "detail": str(e)}), 500
