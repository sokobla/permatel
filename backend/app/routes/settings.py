"""
Paramètres système — SMTP et valeurs de référence (tenant-scopés).

Lecture : tout utilisateur authentifié du tenant actif.
Écriture : ADMIN uniquement.
Le tenant est résolu depuis le claim `tid` du JWT.
"""
import imaplib
import re
import smtplib
import uuid

from flask import Blueprint, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import jwt_required, get_jwt

from app import db
from app.models.setting import SmtpSetting, ReferenceValue
from app.models.sla import SlaPolicy
from app.utils.decorators import tenant_admin_required
from app.utils.crypto import encrypt_secret, decrypt_secret

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")
CORS(settings_bp, supports_credentials=True)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SECURITY_VALUES = {"none", "tls", "ssl"}
IMAP_SECURITY_VALUES = {"none", "ssl", "starttls"}
ALLOWED_FAMILIES = {
    "nature_anomalie", "statut_demande", "moyens_acces",
    "risques_specifiques", "besoins_agents", "type_mission",
    "qualification_agent",
}


def _tenant_uuid():
    """Retourne l'UUID du tenant actif ou (None, réponse d'erreur)."""
    tid = get_jwt().get("tid")
    if not tid:
        return None, (jsonify({"error": "Aucun tenant actif sélectionné."}), 400)
    try:
        return uuid.UUID(tid), None
    except (ValueError, TypeError):
        return None, (jsonify({"error": "Tenant invalide."}), 400)


# ══════════════════════════════════════════════════════════════
#  SMTP
# ══════════════════════════════════════════════════════════════
@settings_bp.get("/smtp")
@jwt_required()
def get_smtp():
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    cfg = SmtpSetting.query.filter_by(tenant_id=tenant_id).first()
    if not cfg:
        # Valeurs par défaut (jamais persistées tant que non sauvegardées)
        return jsonify({
            "host": "", "port": 587, "username": "", "from_address": "",
            "security": "tls", "is_active": True, "has_password": False,
            "updated_at": None,
        }), 200
    return jsonify(cfg.to_dict()), 200


@settings_bp.put("/smtp")
@tenant_admin_required
def put_smtp():
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    data = request.get_json(silent=True) or {}

    host = (data.get("host") or "").strip()
    from_address = (data.get("from_address") or "").strip()
    security = (data.get("security") or "tls").strip().lower()
    try:
        port = int(data.get("port") or 587)
    except (ValueError, TypeError):
        return jsonify({"error": "Port invalide."}), 422

    if not host:
        return jsonify({"error": "Le champ 'host' est obligatoire."}), 422
    if not (0 < port <= 65535):
        return jsonify({"error": "Port hors plage (1-65535)."}), 422
    if not from_address or not EMAIL_RE.match(from_address):
        return jsonify({"error": "Adresse expéditeur invalide."}), 422
    if security not in SECURITY_VALUES:
        return jsonify({"error": f"Chiffrement invalide : {sorted(SECURITY_VALUES)}"}), 422

    cfg = SmtpSetting.query.filter_by(tenant_id=tenant_id).first()
    if not cfg:
        cfg = SmtpSetting(tenant_id=tenant_id)
        db.session.add(cfg)

    cfg.host = host
    cfg.port = port
    cfg.username = (data.get("username") or "").strip() or None
    cfg.from_address = from_address
    cfg.security = security
    cfg.is_active = bool(data.get("is_active", True))
    # Mot de passe : mis à jour seulement s'il est fourni et non vide (chiffré au repos)
    if data.get("password"):
        cfg.password = encrypt_secret(data["password"])

    db.session.commit()
    return jsonify(cfg.to_dict()), 200


@settings_bp.post("/smtp/test")
@tenant_admin_required
def test_smtp():
    """
    Teste la connexion SMTP. Utilise le corps fourni, en complétant le mot de
    passe par celui déjà enregistré s'il n'est pas transmis.
    """
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    saved = SmtpSetting.query.filter_by(tenant_id=tenant_id).first()

    host = (data.get("host") or (saved.host if saved else "") or "").strip()
    from_address = (data.get("from_address") or (saved.from_address if saved else "") or "").strip()
    security = (data.get("security") or (saved.security if saved else "tls")).lower()
    username = (data.get("username") or (saved.username if saved else "")) or None
    password = data.get("password") or decrypt_secret(saved.password if saved else None)
    try:
        port = int(data.get("port") or (saved.port if saved else 587))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Port invalide."}), 422

    if not host or not from_address:
        return jsonify({"ok": False, "error": "Configuration incomplète pour le test."}), 422

    try:
        if security == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.ehlo()
            if security == "tls":
                server.starttls()
                server.ehlo()
        if username and password:
            server.login(username, password)
        server.quit()
        return jsonify({"ok": True, "message": "Connexion SMTP établie avec succès."}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"Échec du test : {exc}"}), 200


# ══════════════════════════════════════════════════════════════
#  IMAP (réception — Phase 2)
# ══════════════════════════════════════════════════════════════
@settings_bp.get("/imap")
@jwt_required()
def get_imap():
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    cfg = SmtpSetting.query.filter_by(tenant_id=tenant_id).first()
    if not cfg:
        return jsonify({
            "imap_host": "", "imap_port": 993, "imap_security": "ssl",
            "imap_username": "", "inbound_enabled": False, "has_imap_password": False,
        }), 200
    return jsonify(cfg.imap_to_dict()), 200


@settings_bp.put("/imap")
@tenant_admin_required
def put_imap():
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    data = request.get_json(silent=True) or {}

    host = (data.get("imap_host") or "").strip()
    security = (data.get("imap_security") or "ssl").strip().lower()
    inbound = bool(data.get("inbound_enabled", False))
    try:
        port = int(data.get("imap_port") or 993)
    except (ValueError, TypeError):
        return jsonify({"error": "Port IMAP invalide."}), 422

    if inbound and not host:
        return jsonify({"error": "L'hôte IMAP est obligatoire pour activer la réception."}), 422
    if host and not (0 < port <= 65535):
        return jsonify({"error": "Port IMAP hors plage (1-65535)."}), 422
    if security not in IMAP_SECURITY_VALUES:
        return jsonify({"error": f"Chiffrement IMAP invalide : {sorted(IMAP_SECURITY_VALUES)}"}), 422

    cfg = SmtpSetting.query.filter_by(tenant_id=tenant_id).first()
    if not cfg:
        cfg = SmtpSetting(tenant_id=tenant_id)
        db.session.add(cfg)

    cfg.imap_host = host or None
    cfg.imap_port = port
    cfg.imap_security = security
    cfg.imap_username = (data.get("imap_username") or "").strip() or None
    cfg.inbound_enabled = inbound
    if data.get("imap_password"):
        cfg.imap_password = encrypt_secret(data["imap_password"])

    db.session.commit()
    return jsonify(cfg.imap_to_dict()), 200


@settings_bp.post("/imap/test")
@tenant_admin_required
def test_imap():
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    saved = SmtpSetting.query.filter_by(tenant_id=tenant_id).first()

    host = (data.get("imap_host") or (saved.imap_host if saved else "") or "").strip()
    security = (data.get("imap_security") or (saved.imap_security if saved else "ssl")).lower()
    username = (data.get("imap_username") or (saved.imap_username if saved else "")) or None
    password = data.get("imap_password") or decrypt_secret(saved.imap_password if saved else None)
    try:
        port = int(data.get("imap_port") or (saved.imap_port if saved else 993))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Port IMAP invalide."}), 422

    if not host:
        return jsonify({"ok": False, "error": "Hôte IMAP manquant."}), 422

    try:
        if security == "ssl":
            client = imaplib.IMAP4_SSL(host, port, timeout=10)
        else:
            client = imaplib.IMAP4(host, port, timeout=10)
            if security == "starttls":
                client.starttls()
        if username and password:
            client.login(username, password)
        client.select("INBOX", readonly=True)
        client.logout()
        return jsonify({"ok": True, "message": "Connexion IMAP établie avec succès."}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"Échec du test IMAP : {exc}"}), 200


# ══════════════════════════════════════════════════════════════
#  VALEURS DE RÉFÉRENCE
# ══════════════════════════════════════════════════════════════
@settings_bp.get("/reference-values")
@jwt_required()
def list_reference_values():
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    family = request.args.get("family")
    query = ReferenceValue.query.filter_by(tenant_id=tenant_id)
    if family:
        if family not in ALLOWED_FAMILIES:
            return jsonify({"error": f"Famille inconnue : {family}"}), 422
        query = query.filter_by(family=family)
    rows = query.order_by(ReferenceValue.family, ReferenceValue.position, ReferenceValue.id).all()
    return jsonify([r.to_dict() for r in rows]), 200


@settings_bp.post("/reference-values")
@tenant_admin_required
def create_reference_value():
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    family = (data.get("family") or "").strip()
    label = (data.get("label") or "").strip()

    if family not in ALLOWED_FAMILIES:
        return jsonify({"error": f"Famille inconnue : {family}"}), 422
    if not label:
        return jsonify({"error": "Le libellé est obligatoire."}), 422

    exists = ReferenceValue.query.filter_by(
        tenant_id=tenant_id, family=family, label=label
    ).first()
    if exists:
        return jsonify({"error": "Cette valeur existe déjà."}), 409

    code = (data.get("code") or "").strip() or None
    item = ReferenceValue(tenant_id=tenant_id, family=family, label=label, code=code)
    # Le flag discriminant n'a de sens que pour la nature d'anomalie.
    if family == "nature_anomalie" and "is_discriminant" in data:
        item.is_discriminant = bool(data["is_discriminant"])
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@settings_bp.put("/reference-values/<int:value_id>")
@tenant_admin_required
def update_reference_value(value_id):
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    item = ReferenceValue.query.filter_by(id=value_id, tenant_id=tenant_id).first()
    if not item:
        return jsonify({"error": "Valeur introuvable."}), 404
    data = request.get_json(silent=True) or {}

    if "label" in data:
        label = (data["label"] or "").strip()
        if not label:
            return jsonify({"error": "Le libellé ne peut pas être vide."}), 422
        conflict = ReferenceValue.query.filter_by(
            tenant_id=tenant_id, family=item.family, label=label
        ).filter(ReferenceValue.id != value_id).first()
        if conflict:
            return jsonify({"error": "Cette valeur existe déjà."}), 409
        item.label = label
    if "active" in data:
        item.is_active = bool(data["active"])
    if "code" in data:
        item.code = (data["code"] or "").strip() or None
    if "is_discriminant" in data and item.family == "nature_anomalie":
        item.is_discriminant = bool(data["is_discriminant"])
    if "position" in data:
        try:
            item.position = int(data["position"])
        except (ValueError, TypeError):
            return jsonify({"error": "Position invalide."}), 422

    db.session.commit()
    return jsonify(item.to_dict()), 200


@settings_bp.delete("/reference-values/<int:value_id>")
@tenant_admin_required
def delete_reference_value(value_id):
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    item = ReferenceValue.query.filter_by(id=value_id, tenant_id=tenant_id).first()
    if not item:
        return jsonify({"error": "Valeur introuvable."}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Valeur supprimée.", "id": value_id}), 200


# ══════════════════════════════════════════════════════════════
#  POLITIQUES SLA (cibles par priorité × type × client)
# ══════════════════════════════════════════════════════════════
SLA_PRIORITES = {"basse", "normale", "haute", "urgente"}
SLA_TYPES = {"anomalie", "commande", "planning", "admin"}


@settings_bp.get("/sla")
@jwt_required()
def list_sla():
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    rows = SlaPolicy.query.filter_by(tenant_id=tenant_id).order_by(
        SlaPolicy.priorite, SlaPolicy.type_demande, SlaPolicy.client_id
    ).all()
    return jsonify([r.to_dict() for r in rows]), 200


@settings_bp.put("/sla")
@tenant_admin_required
def upsert_sla():
    """Crée ou met à jour une cible SLA pour un périmètre (priorité[, type][, client])."""
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    data = request.get_json(silent=True) or {}

    priorite = (data.get("priorite") or "").strip().lower()
    if priorite not in SLA_PRIORITES:
        return jsonify({"error": f"Priorité invalide : {sorted(SLA_PRIORITES)}"}), 422
    type_demande = (data.get("type_demande") or None)
    if type_demande and type_demande not in SLA_TYPES:
        return jsonify({"error": f"Type invalide : {sorted(SLA_TYPES)}"}), 422
    client_id = data.get("client_id")
    try:
        resp = int(data.get("response_minutes"))
        reso = int(data.get("resolution_minutes"))
    except (TypeError, ValueError):
        return jsonify({"error": "response_minutes et resolution_minutes (entiers) requis."}), 422
    if resp <= 0 or reso <= 0:
        return jsonify({"error": "Les délais doivent être positifs."}), 422
    warning_pct = int(data.get("warning_pct", 80))
    if not (1 <= warning_pct <= 100):
        return jsonify({"error": "warning_pct doit être entre 1 et 100."}), 422
    pause = bool(data.get("pause_on_waiting", True))

    row = SlaPolicy.query.filter_by(
        tenant_id=tenant_id, priorite=priorite, type_demande=type_demande, client_id=client_id
    ).first()
    if not row:
        row = SlaPolicy(tenant_id=tenant_id, priorite=priorite,
                        type_demande=type_demande, client_id=client_id)
        db.session.add(row)
    row.response_minutes = resp
    row.resolution_minutes = reso
    row.warning_pct = warning_pct
    row.pause_on_waiting = pause
    db.session.commit()
    return jsonify(row.to_dict()), 200


@settings_bp.delete("/sla/<int:policy_id>")
@tenant_admin_required
def delete_sla(policy_id):
    tenant_id, err = _tenant_uuid()
    if err:
        return err
    row = SlaPolicy.query.filter_by(id=policy_id, tenant_id=tenant_id).first()
    if not row:
        return jsonify({"error": "Politique SLA introuvable."}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"message": "Politique SLA supprimée.", "id": policy_id}), 200
