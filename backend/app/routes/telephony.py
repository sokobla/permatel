"""
Module Téléphonie.

Familles d'endpoints :
  - Ingestion (POST /events/ingest) : appelée par le Core Connector (Phase 12),
    authentification par jeton technique partagé (X-Connector-Token), pas de JWT.
  - Bootstrap config (GET /connectors/config) + heartbeat statut
    (POST /connectors/status) : même trust boundary, consommées par le Core
    Connector.
  - Lecture tenant-scopée (/active-calls, /kpis/*) : @tenant_required.
  - CRUD connecteurs PBX + domaines (/connectors/*) : TENANT-SCOPÉ
    (@tenant_admin_required) — chaque tenant possède et configure son propre
    connecteur, comme SmtpSetting/ImapSetting. Revu depuis la conception
    initiale (Phase 11/12) où un connecteur pouvait être partagé entre
    plusieurs tenants — voir TELEPHONIE_INTEGRATION_PLAN.md.
"""
import logging
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request
from flask_cors import CORS

from app import db, socketio
from app.models import PbxConnector, PbxConnectorDomain, TelephonyEvent
from app.utils.decorators import tenant_admin_required, tenant_required

telephony_bp = Blueprint("telephony", __name__, url_prefix="/api/telephony")
CORS(telephony_bp, supports_credentials=True)

TERMINAL_STATUSES = {"ended", "missed", "abandoned", "technical_failure"}
SYNC_CHANNEL = "telephony:sync"

logger = logging.getLogger(__name__)


def _require_connector_token():
    """Auth partagée par les routes appelées par le Core Connector : jeton
    technique global, pas de JWT (le connecteur n'est pas un utilisateur
    PERMATEL). Retourne une réponse d'erreur si invalide, sinon None."""
    expected_token = current_app.config.get("TELEPHONY_CONNECTOR_TOKEN")
    provided_token = request.headers.get("X-Connector-Token")
    if not expected_token or not provided_token or provided_token != expected_token:
        return jsonify({"error": "Jeton connecteur invalide ou manquant."}), 401
    return None


# ═════════════════════════════════════════════════════════════════════════
#  Redis (signal "Sync" temps réel — filet de secours durable en base)
# ═════════════════════════════════════════════════════════════════════════

_redis_client = None
_redis_checked = False


def _get_redis():
    """Client Redis mis en cache, ou None si REDIS_URL absent/injoignable.
    Même dégradation gracieuse que login_throttle.py : le signal temps réel
    est un plus, `sync_requested_at` (colonne durable) reste le filet de
    secours consommé par le connecteur à son prochain sondage périodique."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    try:
        import redis as redis_lib
    except ImportError:  # pragma: no cover - redis toujours présent en prod
        _redis_client = None
        return None
    url = current_app.config.get("REDIS_URL")
    if not url:
        _redis_client = None
        return None
    try:
        client = redis_lib.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        _redis_client = client
    except Exception as exc:  # noqa: BLE001 - dégradation volontaire
        logger.warning("Redis indisponible pour le signal Sync (%s) — filet de secours DB seul.", exc)
        _redis_client = None
    return _redis_client


def _publish_sync_signal(connector_id: int):
    r = _get_redis()
    if r is None:
        return
    try:
        r.publish(SYNC_CHANNEL, str(connector_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Échec de publication du signal Sync (connector_id=%s) : %s", connector_id, exc)


# ═════════════════════════════════════════════════════════════════════════
#  Bootstrap config + heartbeat (Core Connector — jeton technique, pas de JWT)
# ═════════════════════════════════════════════════════════════════════════

@telephony_bp.get("/connectors/config")
def connectors_bootstrap_config():
    """
    Config dynamique consommée par le Core Connector au démarrage (et
    périodiquement) : tous les `pbx_connectors` actifs (tous tenants
    confondus — vue globale côté connecteur, même si la ressource est
    tenant-scopée côté administration), identifiants déchiffrés inclus,
    avec leurs domaines rattachés. `sync_requested_at` sert de filet de
    secours au signal Redis temps réel (§ ci-dessus).
    """
    if (err := _require_connector_token()) is not None:
        return err

    connectors = PbxConnector.query.filter_by(is_active=True).all()
    result = []
    for c in connectors:
        data = c.to_dict(include_secrets=True)
        data["domains"] = [
            {"pbx_domain": d.pbx_domain, "queue_ids": d.queue_ids or []}
            for d in c.domains
        ]
        result.append(data)
    return jsonify({"connectors": result}), 200


@telephony_bp.post("/connectors/status")
def connectors_status_heartbeat():
    """
    Heartbeat périodique du Core Connector : état de connexion de chaque
    adapter en cours. Alimente `is_connected`/`last_seen_at`/`last_error`,
    affichés en sous-ligne "adapter" sous chaque connecteur (Paramètres >
    Téléphonie).

    Body : {"connectors": {"<connector_id>": {"connected": bool,
                                                "error": str|null}, ...}}
    """
    if (err := _require_connector_token()) is not None:
        return err

    data = request.get_json(silent=True) or {}
    statuses = data.get("connectors") or {}
    now = datetime.utcnow()

    updated = 0
    for connector_id_str, status in statuses.items():
        try:
            connector_id = int(connector_id_str)
        except (TypeError, ValueError):
            continue
        connector = PbxConnector.query.get(connector_id)
        if not connector:
            continue
        connector.is_connected = bool(status.get("connected"))
        connector.last_seen_at = now
        connector.last_error = status.get("error")
        updated += 1

    db.session.commit()
    return jsonify({"updated": updated}), 200


# ═════════════════════════════════════════════════════════════════════════
#  Ingestion (Core Connector — jeton technique, pas de JWT)
# ═════════════════════════════════════════════════════════════════════════

@telephony_bp.post("/events/ingest")
def ingest_event():
    """
    Ingestion d'un événement PBX normalisé (voir CDC §5 pour le format).
    Résolution du tenant : pbx_domain -> PbxConnectorDomain -> connector.tenant_id.

    Un seul jeton global est volontaire : l'architecture ne prévoit qu'UN
    SEUL process connecteur (Core Connector), qui orchestre en interne
    plusieurs `PBXAdapter` concurrents. Toutes les requêtes d'ingestion
    proviennent donc du même process quel que soit le PBX/tenant d'origine.
    """
    if (err := _require_connector_token()) is not None:
        return err

    data = request.get_json(silent=True) or {}

    pbx_domain = data.get("pbx_domain")
    event_type = data.get("event_type")
    if not pbx_domain or not event_type:
        return jsonify({"error": "Champs 'pbx_domain' et 'event_type' requis."}), 400

    domain = PbxConnectorDomain.query.filter_by(pbx_domain=pbx_domain).first()
    if not domain:
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
        tenant_id=domain.connector.tenant_id,
        pbx_connector_id=domain.pbx_connector_id,
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

    # Diffusion temps réel vers les superviseurs connectés du tenant
    # (namespace /telephony, room = tenant_id — cf. app/sockets/telephony.py).
    # Best-effort : une panne de diffusion ne doit jamais faire échouer
    # l'ingestion elle-même (l'événement reste persisté et consultable après
    # coup dans tous les cas).
    try:
        socketio.emit(
            "telephony_event", event.to_dict(),
            room=str(event.tenant_id), namespace="/telephony",
        )
    except Exception:
        current_app.logger.exception("Échec de diffusion WebSocket de l'événement téléphonie")

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
#  CRUD connecteurs PBX (tenant-scopé — admin de tenant)
# ═════════════════════════════════════════════════════════════════════════

def _connector_or_404(connector_id):
    """Connecteur du tenant actif uniquement — 404 si d'un autre tenant
    (jamais 403 : ne pas révéler l'existence d'un connecteur d'un autre
    tenant, même motif que les autres ressources tenant-scopées)."""
    return PbxConnector.query.filter_by(id=connector_id, tenant_id=g.tenant_id).first_or_404(
        description="Connecteur PBX introuvable"
    )


@telephony_bp.get("/connectors")
@tenant_required
def list_connectors():
    connectors = PbxConnector.query.filter_by(tenant_id=g.tenant_id).order_by(PbxConnector.name).all()
    return jsonify([c.to_dict() for c in connectors]), 200


@telephony_bp.post("/connectors")
@tenant_admin_required
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
        tenant_id=g.tenant_id,
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
@tenant_admin_required
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
        connector.password = data["password"]
    if "is_active" in data:
        connector.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify(connector.to_dict()), 200


@telephony_bp.delete("/connectors/<int:connector_id>")
@tenant_admin_required
def delete_connector(connector_id):
    connector = _connector_or_404(connector_id)
    db.session.delete(connector)
    db.session.commit()
    return jsonify({"message": "Connecteur supprimé."}), 200


@telephony_bp.post("/connectors/<int:connector_id>/sync")
@tenant_admin_required
def sync_connector(connector_id):
    """
    Force une reconnexion de l'adapter PBX correspondant. Signal Redis
    (quasi temps réel si le Core Connector est à l'écoute) + horodatage
    durable `sync_requested_at` (filet de secours, appliqué au plus tard au
    prochain sondage périodique du connecteur — cf. GET /connectors/config).
    """
    connector = _connector_or_404(connector_id)
    connector.sync_requested_at = datetime.utcnow()
    db.session.commit()
    _publish_sync_signal(connector.id)
    return jsonify(connector.to_dict()), 200


@telephony_bp.get("/connectors/<int:connector_id>/domains")
@tenant_required
def list_connector_domains(connector_id):
    _connector_or_404(connector_id)
    domains = PbxConnectorDomain.query.filter_by(pbx_connector_id=connector_id).all()
    return jsonify([d.to_dict() for d in domains]), 200


@telephony_bp.post("/connectors/<int:connector_id>/domains")
@tenant_admin_required
def create_connector_domain(connector_id):
    _connector_or_404(connector_id)
    data = request.get_json(silent=True) or {}

    pbx_domain = (data.get("pbx_domain") or "").strip()
    if not pbx_domain:
        return jsonify({"error": "Le champ 'pbx_domain' est requis."}), 400

    if PbxConnectorDomain.query.filter_by(pbx_connector_id=connector_id, pbx_domain=pbx_domain).first():
        return jsonify({"error": "Ce domaine est déjà rattaché à ce connecteur."}), 409

    queue_ids = data.get("queue_ids")
    if queue_ids is not None and not isinstance(queue_ids, list):
        return jsonify({"error": "'queue_ids' doit être une liste."}), 400

    domain = PbxConnectorDomain(
        pbx_connector_id=connector_id,
        pbx_domain=pbx_domain,
        queue_ids=queue_ids or [],
    )
    db.session.add(domain)
    db.session.commit()
    return jsonify(domain.to_dict()), 201


@telephony_bp.put("/connectors/<int:connector_id>/domains/<int:domain_id>")
@tenant_admin_required
def update_connector_domain(connector_id, domain_id):
    """Édite les files d'attente supervisées d'un domaine PBX rattaché."""
    _connector_or_404(connector_id)
    domain = PbxConnectorDomain.query.filter_by(id=domain_id, pbx_connector_id=connector_id).first_or_404(
        description="Domaine PBX introuvable"
    )
    data = request.get_json(silent=True) or {}
    queue_ids = data.get("queue_ids")
    if not isinstance(queue_ids, list):
        return jsonify({"error": "'queue_ids' doit être une liste."}), 400

    domain.queue_ids = queue_ids
    db.session.commit()
    return jsonify(domain.to_dict()), 200


@telephony_bp.delete("/connectors/<int:connector_id>/domains/<int:domain_id>")
@tenant_admin_required
def delete_connector_domain(connector_id, domain_id):
    _connector_or_404(connector_id)
    domain = PbxConnectorDomain.query.filter_by(id=domain_id, pbx_connector_id=connector_id).first_or_404(
        description="Domaine PBX introuvable"
    )
    db.session.delete(domain)
    db.session.commit()
    return jsonify({"message": "Domaine supprimé."}), 200
