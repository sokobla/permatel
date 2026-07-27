"""
Module Téléphonie — Phase 11 (fondations backend).

Trois familles d'endpoints :
  - Ingestion (POST /events/ingest) : appelée par le connecteur PBX (Phase 12),
    authentification par jeton technique partagé (X-Connector-Token), pas de JWT.
  - Lecture tenant-scopée (/active-calls, /kpis/*) : @tenant_required, comme le
    reste de l'app.
  - Administration globale des connecteurs PBX (/connectors/*) : un même PBX
    physique peut héberger plusieurs tenants PERMATEL, ce n'est donc PAS une
    ressource tenant-scopée — réservée au super-admin global (role ADMIN),
    même motif que routes/tenants.py.

Le rattachement tenant-scopé d'un domaine PBX (queues supervisées) est exposé
séparément sous /api/settings/telephony (tenant_admin_required).
"""
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import jwt_required

from app import db
from app.models import PbxConnector, PbxDomainTenant, TelephonyEvent, Tenant, UserRole
from app.utils.auth import role_required
from app.utils.decorators import tenant_admin_required, tenant_required

telephony_bp = Blueprint("telephony", __name__, url_prefix="/api/telephony")
CORS(telephony_bp, supports_credentials=True)

TERMINAL_STATUSES = {"ended", "missed", "abandoned", "technical_failure"}


def _require_connector_token():
    """Auth partagée par les routes appelées par le Core Connector (Phase 12) :
    jeton technique global, pas de JWT (le connecteur n'est pas un utilisateur
    PERMATEL). Retourne une réponse d'erreur si invalide, sinon None."""
    from flask import current_app

    expected_token = current_app.config.get("TELEPHONY_CONNECTOR_TOKEN")
    provided_token = request.headers.get("X-Connector-Token")
    if not expected_token or not provided_token or provided_token != expected_token:
        return jsonify({"error": "Jeton connecteur invalide ou manquant."}), 401
    return None


# ═════════════════════════════════════════════════════════════════════════
#  Bootstrap config (connecteur PBX — jeton technique, pas de JWT)
# ═════════════════════════════════════════════════════════════════════════

@telephony_bp.get("/connectors/config")
def connectors_bootstrap_config():
    """
    Config dynamique consommée par le Core Connector (Phase 12) au démarrage
    (et périodiquement) : liste des `pbx_connectors` actifs, identifiants
    déchiffrés inclus, avec leurs rattachements `pbx_domains_tenants`
    (queues supervisées). Le connecteur orchestre un `PBXAdapter` par
    connecteur retourné ici — pas de config statique dupliquée côté
    connecteur, la source de vérité reste l'UI admin PERMATEL (CRUD
    /api/telephony/connectors, Phase 11).

    Auth par jeton technique partagé (même trust boundary que l'ingestion) :
    le connecteur qui peut écrire des événements peut légitimement lire sa
    propre config, y compris les secrets PBX qu'il doit utiliser pour se
    connecter.
    """
    if (err := _require_connector_token()) is not None:
        return err

    connectors = PbxConnector.query.filter_by(is_active=True).all()
    result = []
    for c in connectors:
        data = c.to_dict(include_secrets=True)
        data["domains"] = [
            {
                "pbx_domain": b.pbx_domain,
                "tenant_id": str(b.tenant_id),
                "queue_ids": b.queue_ids or [],
            }
            for b in c.domains
        ]
        result.append(data)
    return jsonify({"connectors": result}), 200


# ═════════════════════════════════════════════════════════════════════════
#  Ingestion (connecteur PBX — jeton technique, pas de JWT)
# ═════════════════════════════════════════════════════════════════════════

@telephony_bp.post("/events/ingest")
def ingest_event():
    """
    Ingestion d'un événement PBX normalisé (voir CDC §5 pour le format).
    Auth : en-tête `X-Connector-Token`, comparé au jeton technique partagé
    configuré côté serveur (TELEPHONY_CONNECTOR_TOKEN) — le connecteur n'est
    pas un utilisateur PERMATEL, aucun token JWT n'a de sens ici.
    Résolution du tenant : via `pbx_domain` -> pbx_domains_tenants.tenant_id.

    Un seul jeton global est volontaire : l'architecture ne prévoit qu'UN
    SEUL process connecteur (Phase 12, `Core Connector`), qui orchestre en
    interne plusieurs `PBXAdapter` concurrents (un par ligne `pbx_connectors`
    — ESL, AMI, TSAPI...). Toutes les requêtes d'ingestion proviennent donc
    du même process quel que soit le PBX/tenant d'origine de l'événement ;
    un jeton par `PbxConnector` n'aurait pas de granularité de révocation
    utile ici (ce serait révoquer une partie du même process, pas un
    déploiement distinct).
    """
    if (err := _require_connector_token()) is not None:
        return err

    data = request.get_json(silent=True) or {}

    pbx_domain = data.get("pbx_domain")
    event_type = data.get("event_type")
    if not pbx_domain or not event_type:
        return jsonify({"error": "Champs 'pbx_domain' et 'event_type' requis."}), 400

    binding = PbxDomainTenant.query.filter_by(pbx_domain=pbx_domain).first()
    if not binding:
        return jsonify({"error": f"Domaine PBX inconnu : '{pbx_domain}'."}), 404

    call = data.get("call") or {}
    agent = data.get("agent") or {}
    queue = data.get("queue") or {}

    created_at = None
    if call.get("created_at"):
        try:
            created_at = datetime.fromisoformat(str(call["created_at"]).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            created_at = None

    event = TelephonyEvent(
        tenant_id=binding.tenant_id,
        pbx_connector_id=binding.pbx_connector_id,
        event_type=event_type,
        call_direction=call.get("direction"),
        call_status=call.get("status"),
        caller_number=call.get("caller"),
        callee_number=call.get("callee"),
        call_uuid=call.get("id"),
        agent_login=agent.get("login"),
        queue_id=queue.get("id"),
        duration=data.get("duration_seconds"),
        recording_url=data.get("recording_url"),
        raw_payload=data,
        created_at=created_at or datetime.utcnow(),
    )
    db.session.add(event)
    db.session.commit()

    return jsonify({"id": event.id, "message": "Événement enregistré."}), 201


# ═════════════════════════════════════════════════════════════════════════
#  Lecture tenant-scopée
# ═════════════════════════════════════════════════════════════════════════

def _parse_period():
    def _parse(dt_str, default):
        if not dt_str:
            return default
        try:
            return datetime.fromisoformat(dt_str.replace("Z", ""))
        except ValueError:
            return default

    now = datetime.utcnow()
    dt_from = _parse(request.args.get("from"), now - timedelta(days=1))
    dt_to = _parse(request.args.get("to"), now)
    return dt_from, dt_to


@telephony_bp.get("/active-calls")
@tenant_required
def active_calls():
    """
    Appels en cours : dernier événement connu par `call_uuid`, dont le statut
    n'est pas terminal. État initial au chargement de la supervision — le
    WebSocket (Phase 11bis) pousse les deltas ensuite.
    """
    latest_ts = (
        db.session.query(
            TelephonyEvent.call_uuid,
            db.func.max(TelephonyEvent.created_at).label("max_created_at"),
        )
        .filter(TelephonyEvent.tenant_id == g.tenant_id, TelephonyEvent.call_uuid.isnot(None))
        .group_by(TelephonyEvent.call_uuid)
        .subquery()
    )
    latest_events = (
        TelephonyEvent.query
        .join(
            latest_ts,
            db.and_(
                TelephonyEvent.call_uuid == latest_ts.c.call_uuid,
                TelephonyEvent.created_at == latest_ts.c.max_created_at,
            ),
        )
        .filter(TelephonyEvent.tenant_id == g.tenant_id)
        .all()
    )
    active = [e.to_dict() for e in latest_events if e.call_status not in TERMINAL_STATUSES]
    return jsonify({"active_calls": active, "total": len(active)}), 200


@telephony_bp.get("/kpis/summary")
@tenant_required
def kpis_summary():
    """Temps moyen de réponse, taux de décroché, volumes — sur la période."""
    dt_from, dt_to = _parse_period()
    events = (
        TelephonyEvent.query.filter(
            TelephonyEvent.tenant_id == g.tenant_id,
            TelephonyEvent.created_at >= dt_from,
            TelephonyEvent.created_at <= dt_to,
            TelephonyEvent.call_uuid.isnot(None),
        ).all()
    )

    by_call = {}
    for e in events:
        by_call.setdefault(e.call_uuid, []).append(e)

    total_calls = 0
    answered_calls = 0
    response_times = []
    for call_uuid, call_events in by_call.items():
        call_events.sort(key=lambda e: e.created_at)
        terminal = next((e for e in call_events if e.call_status in TERMINAL_STATUSES), None)
        if terminal is None:
            continue  # appel encore en cours, pas comptabilisé dans la période close
        total_calls += 1
        first = call_events[0]
        answered = next((e for e in call_events if e.call_status == "answered"), None)
        if answered:
            answered_calls += 1
            response_times.append((answered.created_at - first.created_at).total_seconds())

    avg_response = round(sum(response_times) / len(response_times), 1) if response_times else None
    decroche_rate = round(answered_calls / total_calls * 100, 1) if total_calls else 0

    return jsonify({
        "period": {"from": dt_from.isoformat(), "to": dt_to.isoformat()},
        "total_calls": total_calls,
        "answered_calls": answered_calls,
        "decroche_rate_pct": decroche_rate,
        "avg_response_seconds": avg_response,
    }), 200


@telephony_bp.get("/kpis/queues")
@tenant_required
def kpis_queues():
    """Appels par file d'attente, temps d'attente moyen, taux d'abandon."""
    dt_from, dt_to = _parse_period()
    events = (
        TelephonyEvent.query.filter(
            TelephonyEvent.tenant_id == g.tenant_id,
            TelephonyEvent.created_at >= dt_from,
            TelephonyEvent.created_at <= dt_to,
            TelephonyEvent.call_uuid.isnot(None),
        ).all()
    )

    by_call = {}
    for e in events:
        by_call.setdefault(e.call_uuid, []).append(e)

    per_queue = {}
    for call_uuid, call_events in by_call.items():
        call_events.sort(key=lambda e: e.created_at)
        terminal = next((e for e in call_events if e.call_status in TERMINAL_STATUSES), None)
        if terminal is None:
            continue
        queue_id = next((e.queue_id for e in call_events if e.queue_id), None) or "sans_file"
        bucket = per_queue.setdefault(queue_id, {"total": 0, "abandoned": 0, "wait_times": []})
        bucket["total"] += 1
        if terminal.call_status == "abandoned":
            bucket["abandoned"] += 1
        answered = next((e for e in call_events if e.call_status == "answered"), None)
        if answered:
            bucket["wait_times"].append((answered.created_at - call_events[0].created_at).total_seconds())

    result = []
    for queue_id, bucket in per_queue.items():
        wait_times = bucket["wait_times"]
        result.append({
            "queue_id": queue_id,
            "total_calls": bucket["total"],
            "abandoned_calls": bucket["abandoned"],
            "abandon_rate_pct": round(bucket["abandoned"] / bucket["total"] * 100, 1) if bucket["total"] else 0,
            "avg_wait_seconds": round(sum(wait_times) / len(wait_times), 1) if wait_times else None,
        })

    return jsonify({
        "period": {"from": dt_from.isoformat(), "to": dt_to.isoformat()},
        "queues": result,
    }), 200


@telephony_bp.get("/kpis/agents")
@tenant_required
def kpis_agents():
    """Temps de conversation, appels traités, distribution des statuts par agent."""
    dt_from, dt_to = _parse_period()
    events = (
        TelephonyEvent.query.filter(
            TelephonyEvent.tenant_id == g.tenant_id,
            TelephonyEvent.created_at >= dt_from,
            TelephonyEvent.created_at <= dt_to,
            TelephonyEvent.agent_login.isnot(None),
            TelephonyEvent.call_uuid.isnot(None),
        ).all()
    )

    by_call = {}
    for e in events:
        by_call.setdefault(e.call_uuid, []).append(e)

    per_agent = {}
    for call_uuid, call_events in by_call.items():
        call_events.sort(key=lambda e: e.created_at)
        terminal = next((e for e in call_events if e.call_status in TERMINAL_STATUSES), None)
        if terminal is None:
            continue
        agent_login = next((e.agent_login for e in call_events if e.agent_login), None)
        if not agent_login:
            continue
        bucket = per_agent.setdefault(agent_login, {"calls_handled": 0, "talk_time": 0})
        answered = next((e for e in call_events if e.call_status == "answered"), None)
        if answered:
            bucket["calls_handled"] += 1
            bucket["talk_time"] += terminal.duration or 0

    result = [
        {"agent_login": login, "calls_handled": b["calls_handled"], "talk_time_seconds": b["talk_time"]}
        for login, b in per_agent.items()
    ]
    return jsonify({
        "period": {"from": dt_from.isoformat(), "to": dt_to.isoformat()},
        "agents": result,
    }), 200


# ═════════════════════════════════════════════════════════════════════════
#  Administration globale des connecteurs PBX (super-admin uniquement)
# ═════════════════════════════════════════════════════════════════════════

def _connector_or_404(connector_id):
    return PbxConnector.query.get_or_404(connector_id, description="Connecteur PBX introuvable")


@telephony_bp.get("/connectors")
@jwt_required()
@role_required(UserRole.ADMIN)
def list_connectors():
    connectors = PbxConnector.query.order_by(PbxConnector.name).all()
    return jsonify([c.to_dict() for c in connectors]), 200


@telephony_bp.post("/connectors")
@jwt_required()
@role_required(UserRole.ADMIN)
def create_connector():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    conn_type = (data.get("type") or "").strip().upper()
    host = (data.get("host") or "").strip()
    port = data.get("port")

    if not name or not conn_type or not host or not port:
        return jsonify({"error": "Champs 'name', 'type', 'host' et 'port' requis."}), 400
    try:
        port = int(port)
    except (TypeError, ValueError):
        return jsonify({"error": "Port invalide."}), 400

    connector = PbxConnector(
        name=name,
        type=conn_type,
        host=host,
        port=port,
        username=(data.get("username") or "").strip() or None,
        is_active=bool(data.get("is_active", True)),
    )
    if data.get("password"):
        # Colonne EncryptedText : chiffrement transparent à l'écriture (pas
        # d'appel manuel à encrypt_secret ici — même convention que Email.subject).
        connector.password = data["password"]

    db.session.add(connector)
    db.session.commit()
    return jsonify(connector.to_dict()), 201


@telephony_bp.put("/connectors/<int:connector_id>")
@jwt_required()
@role_required(UserRole.ADMIN)
def update_connector(connector_id):
    connector = _connector_or_404(connector_id)
    data = request.get_json(silent=True) or {}

    if "name" in data:
        connector.name = (data["name"] or "").strip()
    if "type" in data:
        connector.type = (data["type"] or "").strip().upper()
    if "host" in data:
        connector.host = (data["host"] or "").strip()
    if "port" in data:
        try:
            connector.port = int(data["port"])
        except (TypeError, ValueError):
            return jsonify({"error": "Port invalide."}), 400
    if "username" in data:
        connector.username = (data["username"] or "").strip() or None
    if data.get("password"):
        # Colonne EncryptedText : chiffrement transparent à l'écriture (pas
        # d'appel manuel à encrypt_secret ici — même convention que Email.subject).
        connector.password = data["password"]
    if "is_active" in data:
        connector.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify(connector.to_dict()), 200


@telephony_bp.delete("/connectors/<int:connector_id>")
@jwt_required()
@role_required(UserRole.ADMIN)
def delete_connector(connector_id):
    connector = _connector_or_404(connector_id)
    db.session.delete(connector)
    db.session.commit()
    return jsonify({"message": "Connecteur supprimé."}), 200


@telephony_bp.get("/connectors/<int:connector_id>/domains")
@jwt_required()
@role_required(UserRole.ADMIN)
def list_connector_domains(connector_id):
    _connector_or_404(connector_id)
    bindings = PbxDomainTenant.query.filter_by(pbx_connector_id=connector_id).all()
    return jsonify([b.to_dict() for b in bindings]), 200


@telephony_bp.post("/connectors/<int:connector_id>/domains")
@jwt_required()
@role_required(UserRole.ADMIN)
def create_connector_domain(connector_id):
    _connector_or_404(connector_id)
    data = request.get_json(silent=True) or {}

    pbx_domain = (data.get("pbx_domain") or "").strip()
    tenant_id_raw = data.get("tenant_id")
    if not pbx_domain or not tenant_id_raw:
        return jsonify({"error": "Champs 'pbx_domain' et 'tenant_id' requis."}), 400

    # UUID reçu en JSON = str ; la colonne UUID(as_uuid=True) attend un objet
    # uuid.UUID pour le binding SQLAlchemy (cf. bug identique déjà corrigé sur
    # users.py::_parse_tenant_ids — sinon AttributeError: 'str' object has no
    # attribute 'hex' au flush, remontant en 500).
    try:
        tenant_id = uuid.UUID(str(tenant_id_raw))
    except (ValueError, TypeError):
        return jsonify({"error": "Identifiant de tenant invalide."}), 400

    tenant = Tenant.query.filter_by(id=tenant_id, is_active=True).first()
    if not tenant:
        return jsonify({"error": "Tenant introuvable ou inactif."}), 404

    if PbxDomainTenant.query.filter_by(pbx_connector_id=connector_id, pbx_domain=pbx_domain).first():
        return jsonify({"error": "Ce domaine est déjà rattaché à ce connecteur."}), 409

    binding = PbxDomainTenant(
        pbx_connector_id=connector_id,
        pbx_domain=pbx_domain,
        tenant_id=tenant_id,
        queue_ids=data.get("queue_ids") or [],
    )
    db.session.add(binding)
    db.session.commit()
    return jsonify(binding.to_dict()), 201


@telephony_bp.delete("/connectors/<int:connector_id>/domains/<int:binding_id>")
@jwt_required()
@role_required(UserRole.ADMIN)
def delete_connector_domain(connector_id, binding_id):
    binding = PbxDomainTenant.query.filter_by(id=binding_id, pbx_connector_id=connector_id).first_or_404(
        description="Rattachement introuvable"
    )
    db.session.delete(binding)
    db.session.commit()
    return jsonify({"message": "Rattachement supprimé."}), 200


# ═════════════════════════════════════════════════════════════════════════
#  Réglages tenant-scopés (queues supervisées — CDC §2.3)
# ═════════════════════════════════════════════════════════════════════════

@telephony_bp.get("/settings")
@tenant_required
def get_tenant_telephony_settings():
    """Rattachements PBX du tenant actif (lecture seule sauf `queue_ids`)."""
    bindings = PbxDomainTenant.query.filter_by(tenant_id=g.tenant_id).all()
    result = []
    for b in bindings:
        d = b.to_dict()
        d["connector_name"] = b.connector.name if b.connector else None
        d["connector_type"] = b.connector.type if b.connector else None
        result.append(d)
    return jsonify(result), 200


@telephony_bp.put("/settings/<int:binding_id>/queues")
@tenant_admin_required
def update_tenant_queues(binding_id):
    """Édite les files d'attente supervisées pour un rattachement du tenant actif."""
    binding = PbxDomainTenant.query.filter_by(id=binding_id, tenant_id=g.tenant_id).first_or_404(
        description="Rattachement introuvable pour ce tenant"
    )
    data = request.get_json(silent=True) or {}
    queue_ids = data.get("queue_ids")
    if not isinstance(queue_ids, list):
        return jsonify({"error": "'queue_ids' doit être une liste."}), 400

    binding.queue_ids = queue_ids
    db.session.commit()
    return jsonify(binding.to_dict()), 200
