"""
Blueprint prestataires — PERMATEL
URL prefix : /api/prestataires

Endpoints :
  GET    /api/prestataires                      Liste les prestataires actifs du tenant courant
  GET    /api/prestataires?include_inactive=true Liste tous (actifs + inactifs) — MANAGER+
  GET    /api/prestataires/<uuid>               Detail d'un prestataire
  POST   /api/prestataires                      Creer un prestataire — MANAGER+
  PUT    /api/prestataires/<uuid>               Modifier nom/code d'un prestataire — MANAGER+
  PATCH  /api/prestataires/<uuid>/status        Activer ou desactiver — MANAGER+
                                                La desactivation cascade sur les agents du prestataire.

Regles metier :
  - Isolation tenant stricte : chaque operation filtre sur g.tenant.id
  - Pas de suppression physique : toujours is_active=False (soft delete)
  - UNIQUE(tenant_id, code) : code duplique -> 409
  - Desactivation d'un prestataire -> desactivation de tous ses agents (meme tenant)
  - Acces lecture : tout role authentifie avec tenant actif (@tenant_required)
  - Acces ecriture : MANAGER ou ADMIN (@role_required)
"""

import os
import json
from datetime import datetime
from flask import Blueprint, g, jsonify, request, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from flask_cors import CORS
from app import db
from app.models.prestataire import Prestataire
from app.models.agent_securite import AgentSecurite
from app.models.user import UserRole
from app.utils.decorators import tenant_required
from app.utils.auth import role_required
from app.utils.validators import email_error
from app.utils.logger import get_logger

prestataires_bp = Blueprint("prestataires", __name__, url_prefix="/api/prestataires")

# Appliquer CORS à tout le blueprint. Essentiel pour que le frontend puisse
# appeler ces endpoints sans erreur cross-origin.
CORS(prestataires_bp, supports_credentials=True)

# Logger dedie aux operations prestataires
prestataire_logger = get_logger("permatel.prestataire")


def _save_logo(file, prestataire):
    """Sauvegarde un fichier logo pour un prestataire et retourne l'URL publique."""
    if not file or not file.filename:
        return None

    allowed_extensions_str = current_app.config.get(
        "ALLOWED_AVATAR_EXTENSIONS", ".png,.jpg,.jpeg,.gif,.webp,.svg"
    )
    allowed_extensions = {f".{ext.strip().lstrip('.')}" for ext in allowed_extensions_str.split(",")}
    max_size_mb = int(current_app.config.get("MAX_AVATAR_SIZE_MB", 2))

    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in allowed_extensions:
        raise ValueError(
            "Type de fichier non autorisé. Extensions acceptées : "
            f"{', '.join(allowed_extensions)}"
        )

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > max_size_mb * 1024 * 1024:
        raise ValueError(f"Fichier trop volumineux. Taille max: {max_size_mb}MB.")

    filename = secure_filename(f"prestataire_{prestataire.id}_logo{ext}")
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        raise ValueError("UPLOAD_FOLDER n'est pas configuré dans l'application.")

    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    return f"/uploads/{filename}"


def _delete_logo(prestataire):
    """Supprime le fichier logo d'un prestataire."""
    if not prestataire or not hasattr(prestataire, 'logo_url') or not prestataire.logo_url:
        return

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    if not upload_folder:
        return

    filename = os.path.basename(prestataire.logo_url)
    file_path = os.path.join(upload_folder, filename)

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            prestataire_logger.error(f"Erreur lors de la suppression de l'ancien logo {file_path}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER PRIVE
# ─────────────────────────────────────────────────────────────────────────────

def _prestataire_to_dict(p: Prestataire, include_agents_count: bool = True) -> dict:
    """
    Serialise un Prestataire en dictionnaire JSON.
    include_agents_count : ajoute le nombre d'agents actifs rattaches.
    """
    result = {
        "id":         str(p.id),
        "tenant_id":  str(p.tenant_id),
        "code":       p.code,
        "nom":        p.nom,
        "adresse":    p.adresse,
        "ville":      p.ville,
        "telephone":  p.telephone,
        "email":      p.email,
        "logo_url":   p.logo_url,
        "is_active":  p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
    if include_agents_count:
        # Compte uniquement les agents actifs pour ne pas biaiser l'affichage
        result["agents_actifs_count"] = AgentSecurite.query.filter_by(
            prestataire_id=p.id,
            tenant_id=p.tenant_id,
            is_active=True,
        ).count()
    return result


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/prestataires
# ─────────────────────────────────────────────────────────────────────────────

@prestataires_bp.get("")
@tenant_required
def list_prestataires():
    """
    Liste les prestataires du tenant actif.

    Query param :
      include_inactive=true  — inclut les prestataires inactifs (MANAGER+ uniquement)

    Reponse 200 : { prestataires: [...], total: N }
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    search = request.args.get('search', '', type=str).strip()
    status = request.args.get('status', '', type=str)
    sort_by = request.args.get('sort_by', 'nom', type=str)
    sort_order = request.args.get('sort_order', 'asc', type=str)

    query = Prestataire.query.filter_by(tenant_id=g.tenant.id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            Prestataire.nom.ilike(search_term),
            Prestataire.code.ilike(search_term)
        ))

    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)

    sort_column = getattr(Prestataire, sort_by, None)
    if sort_column is None:
        sort_column = Prestataire.nom
    
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "prestataires": [_prestataire_to_dict(p) for p in pagination.items],
        "total": pagination.total,
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/prestataires/<uuid:prestataire_id>
# ─────────────────────────────────────────────────────────────────────────────

@prestataires_bp.get("/<uuid:prestataire_id>")
@tenant_required
def get_prestataire(prestataire_id):
    """
    Detail d'un prestataire du tenant courant.

    Reponse 200 : { id, tenant_id, code, nom, is_active, created_at, agents_actifs_count }
    Erreurs :
      404 — prestataire introuvable ou n'appartient pas au tenant courant
    """
    # Filtre systematique sur tenant_id pour garantir l'isolation
    p = Prestataire.query.filter_by(
        id=prestataire_id,
        tenant_id=g.tenant.id,
    ).first_or_404(description="Prestataire introuvable.")

    return jsonify(_prestataire_to_dict(p)), 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/prestataires
# ─────────────────────────────────────────────────────────────────────────────

@prestataires_bp.post("")
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def create_prestataire():
    """
    Cree un prestataire pour le tenant courant.

    Body JSON :
      { "nom", "adresse", "ville", "telephone" } (requis)
      { "code", "email", "is_active" } (optionnel)

    Reponse 201 : prestataire cree
    Erreurs :
      400 — champ requis manquant
      409 — code deja utilise dans ce tenant
    """
    logo_file = None
    try:
        if request.content_type.startswith('multipart/form-data'):
            payload = json.loads(request.form.get('data', '{}'))
            logo_file = request.files.get('logo')
        else:
            payload = request.get_json(silent=True) or {}
    except json.JSONDecodeError:
        return jsonify({"error": "Format JSON invalide dans la partie 'data'."}), 400

    # ── Validation ────────────────────────────────────────────────────────── #
    required_fields = ["nom", "adresse", "ville", "telephone"]
    missing = [f for f in required_fields if not payload.get(f)]
    if missing:
        return jsonify({"error": f"Champs requis manquants : {', '.join(missing)}"}), 400

    nom = payload["nom"].strip()
    adresse = payload["adresse"].strip()
    ville = payload["ville"].strip()
    telephone = payload["telephone"].strip()
    email = (payload.get("email") or "").strip() or None
    err = email_error(email)
    if err:
        return jsonify({"error": err}), 400

    code = (payload.get("code") or "").strip() or None

    if code:
        doublon = Prestataire.query.filter_by(
            tenant_id=g.tenant.id, code=code
        ).first()
        if doublon:
            return jsonify({
                "error": "Code deja utilise.",
                "detail": f"Un prestataire avec le code '{code}' existe deja dans ce tenant."
            }), 409

    # ── Creation ──────────────────────────────────────────────────────────── #
    try:
        p = Prestataire(
            tenant_id = g.tenant.id,
            nom       = nom,
            adresse   = adresse,
            ville     = ville,
            telephone = telephone,
            email     = email,
            code      = code,
            is_active = payload.get("is_active", True),
        )
        db.session.add(p)
        db.session.flush() # Pour obtenir p.id

        if logo_file:
            try:
                logo_url = _save_logo(logo_file, p)
                p.logo_url = logo_url
            except ValueError as e:
                db.session.rollback()
                return jsonify({"message": str(e)}), 400

        db.session.commit()

        prestataire_logger.info(
            f"PRESTATAIRE_CREATED | tenant={g.tenant.id} | id={p.id} | nom={p.nom} | user={g.user.id}"
        )
        return jsonify(_prestataire_to_dict(p, include_agents_count=False)), 201

    except Exception as exc:
        db.session.rollback()
        prestataire_logger.error(f"PRESTATAIRE_CREATE_ERROR | tenant={g.tenant.id} | err={exc}")
        return jsonify({"error": "Erreur lors de la creation du prestataire."}), 500


# ─────────────────────────────────────────────────────────────────────────────
# PUT /api/prestataires/<uuid:prestataire_id>
# ─────────────────────────────────────────────────────────────────────────────

@prestataires_bp.route("/<uuid:prestataire_id>", methods=["PUT", "POST"])
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def update_prestataire(prestataire_id):
    """
    Modifie le nom et/ou le code d'un prestataire.
    Pour activer/desactiver, utiliser PATCH /<id>/status.

    Body JSON : { "nom": "...", "code": "..." }

    Reponse 200 : prestataire mis a jour
    Erreurs :
      400 — nom vide si fourni
      404 — prestataire introuvable
      409 — code deja utilise par un autre prestataire du meme tenant
    """
    p = Prestataire.query.filter_by(
        id=prestataire_id,
        tenant_id=g.tenant.id,
    ).first_or_404(description="Prestataire introuvable.")

    logo_file = None
    try:
        if request.content_type.startswith('multipart/form-data'):
            payload = json.loads(request.form.get('data', '{}'))
            logo_file = request.files.get('logo')
        else:
            payload = request.get_json(silent=True) or {}
    except json.JSONDecodeError:
        return jsonify({"error": "Format JSON invalide dans la partie 'data'."}), 400

    # ── Validation ────────────────────────────────────────────────────────── #
    if "nom" in payload:
        nom = (payload["nom"] or "").strip()
        if not nom:
            return jsonify({"error": "Le champ 'nom' ne peut pas etre vide."}), 400
        p.nom = nom
    if "adresse" in payload: p.adresse = payload["adresse"]
    if "ville" in payload: p.ville = payload["ville"]
    if "telephone" in payload: p.telephone = payload["telephone"]
    if "email" in payload:
        email = (payload["email"] or "").strip() or None
        err = email_error(email)
        if err:
            return jsonify({"error": err}), 400
        p.email = email

    if "code" in payload:
        code = (payload["code"] or "").strip() or None
        if code and code != p.code:
            doublon = Prestataire.query.filter(
                Prestataire.tenant_id == g.tenant.id,
                Prestataire.code == code,
                Prestataire.id != p.id,         # Exclure le prestataire courant
            ).first()
            if doublon:
                return jsonify({
                    "error": "Code deja utilise.",
                    "detail": f"Un prestataire avec le code '{code}' existe deja dans ce tenant."
                }), 409
        p.code = code

    if logo_file:
        _delete_logo(p)
        try:
            p.logo_url = _save_logo(logo_file, p)
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
    elif 'logo_url' in payload and payload['logo_url'] is None:
        _delete_logo(p)
        p.logo_url = None

    # ── Persistance ───────────────────────────────────────────────────────── #
    try:
        db.session.commit()
        prestataire_logger.info(
            f"PRESTATAIRE_UPDATED | tenant={g.tenant.id} | id={p.id} | user={g.user.id}"
        )
        return jsonify(_prestataire_to_dict(p)), 200

    except Exception as exc:
        db.session.rollback()
        prestataire_logger.error(f"PRESTATAIRE_UPDATE_ERROR | id={p.id} | err={exc}")
        return jsonify({"error": "Erreur lors de la mise a jour du prestataire."}), 500


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/prestataires/<uuid:prestataire_id>/status
# ─────────────────────────────────────────────────────────────────────────────

@prestataires_bp.patch("/<uuid:prestataire_id>/status")
@tenant_required
@role_required(UserRole.MANAGER, UserRole.ADMIN)
def update_prestataire_status(prestataire_id):
    """
    Active ou desactive un prestataire.

    REGLE METIER — desactivation en cascade :
      Si is_active=False, tous les agents de securite rattaches a ce prestataire
      (meme tenant) sont egalement desactives. Cette operation est irreversible
      cote agents : la reactivation du prestataire ne reactive PAS automatiquement
      ses agents (action intentionnelle requise).

    Body JSON : { "is_active": true|false }

    Reponse 200 :
      { "id", "nom", "is_active", "agents_desactives": N }
      agents_desactives : nombre d'agents desactives en cascade (0 si activation)

    Erreurs :
      400 — champ is_active manquant ou invalide
      404 — prestataire introuvable
    """
    p = Prestataire.query.filter_by(
        id=prestataire_id,
        tenant_id=g.tenant.id,
    ).first_or_404(description="Prestataire introuvable.")

    payload = request.get_json(silent=True) or {}

    # ── Validation ────────────────────────────────────────────────────────── #
    if "is_active" not in payload:
        return jsonify({"error": "Le champ 'is_active' est requis."}), 400

    if not isinstance(payload["is_active"], bool):
        return jsonify({"error": "Le champ 'is_active' doit etre un booleen (true/false)."}), 400

    nouvel_etat = payload["is_active"]

    # ── Application ───────────────────────────────────────────────────────── #
    try:
        agents_desactives = 0
        p.is_active = nouvel_etat

        if not nouvel_etat:
            # REGLE METIER : desactivation du prestataire -> cascade sur ses agents actifs
            # On cible uniquement les agents actifs pour ne pas toucher deux fois les deja-inactifs
            agents_actifs = AgentSecurite.query.filter_by(
                prestataire_id = prestataire_id,
                tenant_id      = g.tenant.id,
                is_active      = True,
            ).all()

            for agent in agents_actifs:
                agent.is_active   = False
                agent.updated_at  = datetime.utcnow()

            agents_desactives = len(agents_actifs)

            if agents_desactives:
                prestataire_logger.info(
                    f"PRESTATAIRE_CASCADE_DEACTIVATION | tenant={g.tenant.id} "
                    f"| prestataire_id={prestataire_id} | agents_desactives={agents_desactives} "
                    f"| user={g.user.id}"
                )

        db.session.commit()

        etat_label = "active" if nouvel_etat else "desactive"
        prestataire_logger.info(
            f"PRESTATAIRE_STATUS_CHANGED | tenant={g.tenant.id} | id={p.id} "
            f"| is_active={nouvel_etat} | user={g.user.id}"
        )

        return jsonify({
            "id":                str(p.id),
            "nom":               p.nom,
            "is_active":         p.is_active,
            "agents_desactives": agents_desactives,
            "message":           f"Prestataire {etat_label} avec succes."
                                 + (f" {agents_desactives} agent(s) desactive(s) en cascade."
                                    if agents_desactives else ""),
        }), 200

    except Exception as exc:
        db.session.rollback()
        prestataire_logger.error(
            f"PRESTATAIRE_STATUS_ERROR | id={prestataire_id} | err={exc}"
        )
        return jsonify({"error": "Erreur lors de la modification du statut."}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Methodes non autorisees (protection explicite contre DELETE physique)
# ─────────────────────────────────────────────────────────────────────────────

@prestataires_bp.delete("/<uuid:prestataire_id>")
@tenant_required
def delete_prestataire_forbidden(prestataire_id):
    """
    La suppression physique des prestataires est interdite.
    Utiliser PATCH /<id>/status avec { "is_active": false } pour desactiver.
    """
    return jsonify({
        "error": "Suppression physique non autorisee.",
        "detail": "Utilisez PATCH /api/prestataires/{id}/status pour desactiver un prestataire.",
    }), 405
