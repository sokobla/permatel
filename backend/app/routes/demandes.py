from datetime import datetime
import uuid
from flask_cors import CORS
from flask import Blueprint, jsonify, request, g
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.demande import (
    Demande, DemandeAnomalie, DemandeCommande, DemandePlanning, DemandeAdmin,
    TypeDemande, StatutDemande, PrioriteDemande,
    NatureAnomalie, TypeCommande, TypeModificationPlanning, CategorieAdmin, TypeDocumentAdmin
)
from app.models.user import User, UserRole
from app.models.client import Client
from app.models.site import Site
from app.models.contact import Contact
from app.models.tenant import Tenant
from app.utils.auth import role_required
from app.utils.decorators import tenant_required
from app.services.sla import apply_sla, on_status_change, sla_state


demandes_bp = Blueprint("demandes", __name__, url_prefix="/api/demandes")
CORS(demandes_bp, resources={r"/api/demandes/*": {"origins": "*"}})

def _parse_datetime(value):
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

def _agent_avatar(agent) -> str | None:
    """Retourne l'avatar_url d'un AgentSecurite : préfère le contact lié, sinon le champ propre."""
    if not agent:
        return None
    try:
        if agent.contact and agent.contact.avatar_url:
            return agent.contact.avatar_url
    except Exception:
        pass
    return getattr(agent, "avatar_url", None)


def _serialize_demande(demande: Demande) -> dict:
    """Sérialise une demande (parent + champs spécifiques selon type)."""
    # Labels dénormalisés (évite des requêtes supplémentaires côté client)
    client_nom = None
    client_logo_url = None
    try:
        if demande.client:
            client_nom     = demande.client.nom
            client_logo_url = demande.client.logo_url
    except Exception:
        pass

    site_nom = None
    site_logo_url = None
    try:
        if demande.site:
            site_nom     = demande.site.nom
            site_logo_url = demande.site.logo_url
    except Exception:
        pass

    contact_nom = None
    contact_avatar_url = None
    try:
        if demande.contact:
            c = demande.contact
            contact_nom        = f"{c.prenom or ''} {c.nom or ''}".strip() or None
            contact_avatar_url = c.avatar_url
    except Exception:
        pass

    permanencier_nom = None
    permanencier_avatar_url = None
    try:
        if demande.permanencier:
            p = demande.permanencier
            permanencier_nom        = f"{p.prenom or ''} {p.nom or ''}".strip() or None
            permanencier_avatar_url = p.avatar_url
    except Exception:
        pass

    created_by_nom  = None
    created_by_role = None
    try:
        if demande.created_by:
            u = demande.created_by
            created_by_nom  = f"{u.prenom or ''} {u.nom or ''}".strip() or None
            created_by_role = u.role.value if hasattr(u, 'role') and u.role else None
    except Exception:
        pass

    updated_by_nom = None
    try:
        if demande.updated_by:
            u = demande.updated_by
            updated_by_nom = f"{u.prenom or ''} {u.nom or ''}".strip() or None
    except Exception:
        pass

    data = {
        "id": demande.id,
        "numero_ticket": demande.numero_ticket,
        "client_nom": client_nom,
        "client_logo_url": client_logo_url,
        "site_nom": site_nom,
        "site_logo_url": site_logo_url,
        "permanencier_nom": permanencier_nom,
        "permanencier_avatar_url": permanencier_avatar_url,
        "type_demande": demande.type_demande.value,
        "titre": demande.titre,
        "description": demande.description,
        "adresse_intervention": demande.adresse_intervention,
        "statut": demande.statut.value,
        "priorite": demande.priorite.value,
        "client_id": demande.client_id,
        "site_id": demande.site_id,
        "contact_id": demande.contact_id,
        "contact_nom": contact_nom,
        "contact_avatar_url": contact_avatar_url,
        "permanencier_id": demande.permanencier_id,
        "closed_by_id": demande.closed_by_id,
        "created_by_id":   demande.created_by_id,
        "created_by_nom":  created_by_nom,
        "created_by_role": created_by_role,
        "updated_by_id": demande.updated_by_id,
        "updated_by_nom": updated_by_nom,
        "sla_deadline": demande.sla_deadline.isoformat() if demande.sla_deadline else None,
        "sla_response_deadline": demande.sla_response_deadline.isoformat() if demande.sla_response_deadline else None,
        "prise_en_charge_at": demande.prise_en_charge_at.isoformat() if demande.prise_en_charge_at else None,
        "sla": sla_state(demande),
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
        data["equipement_concerne"] = demande.equipement_concerne
        data["localisation_precise"] = demande.localisation_precise
        data["impact_securite"] = demande.impact_securite
        data["action_corrective"] = demande.action_corrective
        data["agent_concerne_id"] = demande.agent_concerne_id
        agent = demande.agent_concerne
        data["agent_concerne_label"] = (
            " ".join(filter(None, [agent.prenom, agent.nom])) if agent else None
        )
        data["agent_concerne_avatar_url"] = _agent_avatar(agent)

    elif isinstance(demande, DemandeCommande):
        data["type_commande"] = demande.type_commande.value if demande.type_commande else None
        data["quantite"] = demande.quantite
        data["budget_estime"] = demande.budget_estime
        data["fournisseur_suggere"] = demande.fournisseur_suggere
        data["date_livraison_souhaitee"] = demande.date_livraison_souhaitee.isoformat() if demande.date_livraison_souhaitee else None
        data["bon_commande"] = demande.bon_commande
        data["moyens_acces"] = demande.moyens_acces or []
        data["equipements_site"] = demande.equipements_site or []
        data["risques_specifiques"] = demande.risques_specifiques or []
        data["besoins_agents"] = demande.besoins_agents or []
    
    elif isinstance(demande, DemandePlanning):
        data["type_modification"] = demande.type_modification.value if demande.type_modification else None
        data["agent_concerne_id"] = demande.agent_concerne_id
        data["agent_remplacant_id"] = demande.agent_remplacant_id
        data["date_debut"] = demande.date_debut.isoformat() if demande.date_debut else None
        data["date_fin"] = demande.date_fin.isoformat() if demande.date_fin else None
        data["motif"] = demande.motif
        agent_c = demande.agent_concerne
        data["agent_concerne_label"] = (
            " ".join(filter(None, [agent_c.prenom, agent_c.nom])) if agent_c else None
        )
        data["agent_concerne_avatar_url"] = _agent_avatar(agent_c)
        agent_r = demande.agent_remplacant
        data["agent_remplacant_label"] = (
            " ".join(filter(None, [agent_r.prenom, agent_r.nom])) if agent_r else None
        )
        data["agent_remplacant_avatar_url"] = _agent_avatar(agent_r)
    
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

    query = Demande.query.filter_by(tenant_id=tenant_id, is_deleted=False)

    if contact_id := request.args.get("contact_id", type=int):
        query = query.filter(Demande.contact_id == contact_id)
    if client_id := request.args.get("client_id", type=int):
        query = query.filter(Demande.client_id == client_id)
    if type_val := request.args.get("type_demande"):
        try:
            query = query.filter(Demande.type_demande == TypeDemande(type_val))
        except ValueError:
            pass
    if statut_val := request.args.get("statut"):
        try:
            query = query.filter(Demande.statut == StatutDemande(statut_val))
        except ValueError:
            pass

    demandes = query.order_by(Demande.created_at.desc()).all()
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
        "adresse_intervention": payload.get("adresse_intervention"),
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
            demande.equipement_concerne = payload.get("equipement_concerne")
            demande.localisation_precise = payload.get("localisation_precise")
            demande.impact_securite = payload.get("impact_securite", False)
            demande.action_corrective = payload.get("action_corrective")
            demande.agent_concerne_id = payload.get("agent_concerne_id") or None
        
        elif type_demande == TypeDemande.COMMANDE:
            if "type_commande" in payload:
                try:
                    demande.type_commande = TypeCommande(payload["type_commande"])
                except ValueError:
                    pass
            demande.quantite = payload.get("quantite")
            demande.budget_estime = payload.get("budget_estime")
            demande.fournisseur_suggere = payload.get("fournisseur_suggere")
            demande.date_livraison_souhaitee = _parse_datetime(payload.get("date_livraison_souhaitee"))
            demande.bon_commande = payload.get("bon_commande")
            demande.moyens_acces = payload.get("moyens_acces") or []
            demande.equipements_site = payload.get("equipements_site") or []
            demande.risques_specifiques = payload.get("risques_specifiques") or []
            demande.besoins_agents = payload.get("besoins_agents") or []
        
        elif type_demande == TypeDemande.PLANNING:
            if "type_modification" in payload:
                try:
                    demande.type_modification = TypeModificationPlanning(payload["type_modification"])
                except ValueError:
                    pass
            demande.agent_concerne_id = payload.get("agent_concerne_id")
            demande.agent_remplacant_id = payload.get("agent_remplacant_id")
            demande.date_debut = _parse_datetime(payload.get("date_debut"))
            demande.date_fin = _parse_datetime(payload.get("date_fin"))
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
            demande.date_echeance = _parse_datetime(payload.get("date_echeance"))
            demande.validation_requise = payload.get("validation_requise", False)
        
        demande.created_by_id = user_id

        db.session.add(demande)
        db.session.flush()  # Pour obtenir l'ID avant de générer le numéro de ticket

        # Générer numéro ticket final
        demande.numero_ticket = f"{type_demande.value.upper()[:4]}_{demande.id}"
        # SLA : échéances calculées depuis created_at + politique du tenant
        apply_sla(demande)
        on_status_change(demande, demande.statut)   # prise en charge si créée hors "nouvelle"
        db.session.commit()

        # ── Notifications (non bloquant) ───────────────────────────────────
        try:
            from app.services.notifications import notify, tenant_members
            members = tenant_members(g.tenant_id)
            notify(g.tenant_id, members, "demande.created",
                   title=f"Nouvelle demande — {demande.numero_ticket}",
                   body=f"{demande.titre} (priorité {demande.priorite.value}).",
                   entity_type="demande", entity_id=demande.id)
            assignee = User.query.get(demande.permanencier_id) if demande.permanencier_id else None
            if assignee:
                notify(g.tenant_id, [assignee], "demande.assigned",
                       title=f"Demande qui vous est assignée — {demande.numero_ticket}",
                       body=demande.titre, entity_type="demande", entity_id=demande.id)
            db.session.commit()
        except Exception:  # noqa: BLE001
            db.session.rollback()

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
    user_id = claims.get("sub")
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
            # Horodatages de cycle de vie (prise en charge / résolution / clôture)
            on_status_change(demande, demande.statut)

        if "priorite" in payload:
            try:
                demande.priorite = PrioriteDemande(payload["priorite"])
            except ValueError:
                return jsonify({"message": "priorite invalide"}), 400
            # Recalcule les échéances SLA (pas de surcharge manuelle)
            apply_sla(demande)
        
        # Champs spécifiques selon type
        if isinstance(demande, DemandeAnomalie):
            if "nature_anomalie" in payload:
                try:
                    demande.nature_anomalie = NatureAnomalie(payload["nature_anomalie"])
                except ValueError:
                    pass
            if "equipement_concerne" in payload:
                demande.equipement_concerne = payload["equipement_concerne"]
            if "localisation_precise" in payload:
                demande.localisation_precise = payload["localisation_precise"]
            if "impact_securite" in payload:
                demande.impact_securite = payload["impact_securite"]
            if "action_corrective" in payload:
                demande.action_corrective = payload["action_corrective"]
            if "agent_concerne_id" in payload:
                demande.agent_concerne_id = payload["agent_concerne_id"] or None
        
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
                demande.date_livraison_souhaitee = _parse_datetime(payload["date_livraison_souhaitee"])
            if "bon_commande" in payload:
                demande.bon_commande = payload["bon_commande"]
            if "moyens_acces" in payload:
                demande.moyens_acces = payload["moyens_acces"] or []
            if "equipements_site" in payload:
                demande.equipements_site = payload["equipements_site"] or []
            if "risques_specifiques" in payload:
                demande.risques_specifiques = payload["risques_specifiques"] or []
            if "besoins_agents" in payload:
                demande.besoins_agents = payload["besoins_agents"] or []
        
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
                demande.date_debut = _parse_datetime(payload["date_debut"])
            if "date_fin" in payload:
                demande.date_fin = _parse_datetime(payload["date_fin"])
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
                demande.date_echeance = _parse_datetime(payload["date_echeance"])
            if "validation_requise" in payload:
                demande.validation_requise = payload["validation_requise"]
        
        demande.updated_at = datetime.utcnow()
        demande.updated_by_id = user_id
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


@demandes_bp.patch("/<int:demande_id>/pec")
@tenant_required
def pec_demande(demande_id):
    """Prise en charge : passe le statut à en_cours et assigne le permanencier courant."""
    claims = get_jwt()
    tenant_id = _get_tenant_id_from_claims(claims)
    user_id = claims.get("sub")
    if not tenant_id:
        return jsonify({"message": "Aucun tenant actif sélectionné."}), 400

    demande = Demande.query.filter_by(
        id=demande_id, tenant_id=tenant_id, is_deleted=False
    ).first_or_404(description="Demande introuvable")

    demande.statut = StatutDemande.EN_COURS
    if user_id:
        try:
            demande.permanencier_id = int(user_id)
        except (ValueError, TypeError):
            pass
    demande.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(_serialize_demande(demande)), 200


@demandes_bp.get("/<int:demande_id>/interactions")
@tenant_required
def get_demande_interactions(demande_id):
    """Liste les interactions d'une demande, triées de la plus récente à la plus ancienne."""
    from app.models.interaction import Interaction
    claims = get_jwt()
    tenant_id = _get_tenant_id_from_claims(claims)
    if not tenant_id:
        return jsonify({"message": "Aucun tenant actif sélectionné."}), 400

    Demande.query.filter_by(
        id=demande_id, tenant_id=tenant_id, is_deleted=False
    ).first_or_404(description="Demande introuvable")

    interactions = (
        Interaction.query
        .filter_by(demande_id=demande_id, tenant_id=tenant_id)
        .order_by(Interaction.created_at.desc())
        .all()
    )

    result = []
    for i in interactions:
        user_nom = None
        try:
            if i.user:
                user_nom = f"{i.user.prenom or ''} {i.user.nom or ''}".strip() or None
        except Exception:
            pass
        contact_nom = None
        try:
            if i.contact:
                contact_nom = f"{i.contact.prenom or ''} {i.contact.nom or ''}".strip() or None
        except Exception:
            pass

        result.append({
            "id": i.id,
            "type_interaction": i.type_interaction.value,
            "contenu": i.contenu,
            "ancien_statut": i.ancien_statut,
            "nouveau_statut": i.nouveau_statut,
            "user_id": i.user_id,
            "user_nom": user_nom,
            "contact_id": i.contact_id,
            "contact_nom": contact_nom,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        })

    return jsonify(result), 200


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
