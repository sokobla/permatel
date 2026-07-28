"""
Module Téléphonie.

Familles d'endpoints :
  - Ingestion ESL (POST /events/ingest) : appelée par le Core Connector
    (Phase 12), authentification par jeton technique partagé
    (X-Connector-Token), pas de JWT.
  - Ingestion CDR (POST /cdr/ingest/<token>, Phase 14) : appelée directement
    par FusionPBX (mod_json_cdr), sans passer par le Core Connector — un
    jeton PAR CONNECTEUR (généré/régénéré depuis l'UI) résout directement le
    connecteur, plus une restriction IP optionnelle (`authorized_ip`).
    Canal complémentaire à l'ESL live : un résumé de fin d'appel, jamais
    d'événement "en cours" (une call CDR n'apparaît donc jamais dans
    /active-calls).
  - Bootstrap config (GET /connectors/config) + heartbeat statut
    (POST /connectors/status) : même trust boundary que l'ingestion ESL,
    consommées par le Core Connector.
  - Lecture tenant-scopée (/active-calls, /kpis/*, /calls, /recordings) :
    @tenant_required.
  - CRUD connecteurs PBX + domaines (/connectors/*) : TENANT-SCOPÉ
    (@tenant_admin_required) — chaque tenant possède et configure son propre
    connecteur, comme SmtpSetting/ImapSetting. Revu depuis la conception
    initiale (Phase 11/12) où un connecteur pouvait être partagé entre
    plusieurs tenants — voir TELEPHONIE_INTEGRATION_PLAN.md.
"""
import csv
import hashlib
import hmac
import io
import json
import logging
import secrets
import zipfile
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests
from flask import Blueprint, Response, current_app, g, jsonify, request
from flask_cors import CORS

from app import db, socketio
from app.models import PbxConnector, PbxConnectorDomain, TelephonyEvent
from app.utils.decorators import tenant_admin_required, tenant_required

telephony_bp = Blueprint("telephony", __name__, url_prefix="/api/telephony")
CORS(telephony_bp, supports_credentials=True)

TERMINAL_STATUSES = {"ended", "missed", "abandoned", "technical_failure"}
SYNC_CHANNEL = "telephony:sync"

logger = logging.getLogger(__name__)


def _get_client_ip() -> str:
    """Dupliqué depuis app/routes/auth.py (petite fonction, pas de module
    utilitaire commun pour l'instant) — support reverse proxy (X-Forwarded-For)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


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
        agent_status=agent.get("status"),
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
#  Ingestion CDR (FusionPBX mod_json_cdr — Phase 14, jeton par connecteur)
# ═════════════════════════════════════════════════════════════════════════

def _hash_webhook_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


# Dupliqué depuis connector/normalizer.py (packages séparés, pas de module
# partagé entre connector/ et backend/) — garder synchronisé si la liste
# évolue côté ESL.
_CDR_TECHNICAL_FAILURE_CAUSES = {
    "NORMAL_TEMPORARY_FAILURE", "RECOVERY_ON_TIMER_EXPIRE", "DESTINATION_OUT_OF_ORDER",
    "NETWORK_OUT_OF_ORDER", "SWITCH_CONGESTION", "INCOMPATIBLE_DESTINATION",
}
_CDR_MISSED_CAUSES = {"NO_ANSWER", "USER_BUSY", "USER_NOT_REGISTERED", "CALL_REJECTED", "NO_USER_RESPONSE"}


def _cdr_terminal_status(hangup_cause: str, was_answered: bool) -> str:
    cause = (hangup_cause or "").upper()
    if cause in _CDR_TECHNICAL_FAILURE_CAUSES:
        return "technical_failure"
    if was_answered:
        return "ended"
    if cause in _CDR_MISSED_CAUSES:
        return "missed"
    return "abandoned"


def _cdr_epoch_to_dt(raw):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return datetime.utcfromtimestamp(value) if value else None


@telephony_bp.post("/cdr/ingest/<token>")
def cdr_ingest(token):
    """
    Webhook CDR — FusionPBX (mod_json_cdr) POSTe un résumé JSON à la fin de
    chaque appel. Contrairement à /events/ingest (jeton global, appelé par
    notre propre Core Connector), le jeton ici est PAR CONNECTEUR et résout
    directement le tenant, sans jamais transiter par le Core Connector.

    ⚠️ Non confirmé contre un flux FusionPBX réel avant mise en prod : le
    format exact du corps (JSON brut vs. `application/x-www-form-urlencoded`
    avec un champ `cdr=<json>`, comportement historique de mod_xml_cdr) et
    les noms de variables `cc_queue`/`cc_agent` (files/agents, absents des
    variables CDR standard, best-effort si présents).
    """
    connector = PbxConnector.query.filter_by(
        cdr_webhook_token_hash=_hash_webhook_token(token)
    ).first()
    if connector is None or connector.cdr_webhook_token_hash is None or not hmac.compare_digest(
        connector.cdr_webhook_token_hash, _hash_webhook_token(token)
    ):
        return jsonify({"error": "Jeton webhook CDR invalide."}), 404

    if connector.authorized_ip:
        allowed_ips = {ip.strip() for ip in connector.authorized_ip.split(",") if ip.strip()}
        client_ip = _get_client_ip()
        if allowed_ips and client_ip not in allowed_ips:
            logger.warning(
                "CDR webhook refusé : IP %s non autorisée pour le connecteur id=%s", client_ip, connector.id,
            )
            return jsonify({"error": "Adresse IP non autorisée."}), 403

    # Confirmé sur trafic FusionPBX réel (28/07) : le corps est POSTé en
    # Content-Type application/x-www-form-urlencoded (comportement par
    # défaut de libcurl avec POSTFIELDS, pas une vraie soumission de
    # formulaire) — le JSON brut se retrouve décodé par Werkzeug comme une
    # clé ou une valeur du formulaire, selon que le JSON contient ou non un
    # '=' littéral (s'il n'y en a aucun, tout le corps devient une clé
    # unique à valeur vide plutôt qu'une paire clé=valeur). On scanne donc
    # les clés ET les valeurs du formulaire décodé à la recherche d'un objet
    # JSON valide, en plus des tentatives corps-JSON-brut (au cas où un
    # autre PBX/config poste vraiment du JSON avec le bon Content-Type).
    payload = request.get_json(silent=True, force=True)
    if payload is None:
        for candidate_str in (*request.form.keys(), *request.form.values()):
            try:
                candidate = json.loads(candidate_str)
            except (TypeError, ValueError):
                continue
            if isinstance(candidate, dict):
                payload = candidate
                break
    if payload is None:
        try:
            payload = json.loads(request.get_data(as_text=True) or "")
        except (TypeError, ValueError):
            payload = None
    if not isinstance(payload, dict):
        logger.warning(
            "CDR webhook : corps illisible pour le connecteur id=%s "
            "(Content-Type=%r, %d octets, clés formulaire=%r)",
            connector.id, request.content_type, request.content_length or 0,
            list(request.form.keys())[:5],
        )
        return jsonify({"error": "Corps CDR JSON invalide ou absent."}), 400

    variables = payload.get("variables") or {}
    call_uuid = (
        variables.get("uuid") or variables.get("call_uuid") or payload.get("uuid")
        or request.args.get("uuid")
    )
    if not call_uuid:
        return jsonify({"error": "UUID d'appel introuvable dans le CDR."}), 400

    start_at = _cdr_epoch_to_dt(variables.get("start_epoch"))
    answer_at = _cdr_epoch_to_dt(variables.get("answer_epoch"))
    end_at = _cdr_epoch_to_dt(variables.get("end_epoch")) or datetime.utcnow()
    try:
        billsec = int(variables["billsec"]) if variables.get("billsec") is not None else None
    except (TypeError, ValueError):
        billsec = None
    was_answered = bool(answer_at) and bool(billsec)

    caller = variables.get("caller_id_number") or variables.get("effective_caller_id_number")
    callee = variables.get("destination_number")
    direction = variables.get("direction")
    queue_id = variables.get("cc_queue")  # best-effort, non confirmé
    agent_login = variables.get("cc_agent")  # best-effort, non confirmé
    recording_url = variables.get("record_file_path") or variables.get("recording_follow_transfer")

    events = []
    if start_at:
        events.append(TelephonyEvent(
            tenant_id=connector.tenant_id, pbx_connector_id=connector.id,
            event_type="CDR_RECORD_START", call_direction=direction, call_status="ringing",
            caller_number=caller, callee_number=callee, agent_login=agent_login, queue_id=queue_id,
            call_uuid=call_uuid, created_at=start_at, raw_payload=payload,
        ))
    if answer_at and was_answered:
        events.append(TelephonyEvent(
            tenant_id=connector.tenant_id, pbx_connector_id=connector.id,
            event_type="CDR_RECORD_ANSWER", call_direction=direction, call_status="answered",
            caller_number=caller, callee_number=callee, agent_login=agent_login, queue_id=queue_id,
            call_uuid=call_uuid, created_at=answer_at, raw_payload=payload,
        ))
    events.append(TelephonyEvent(
        tenant_id=connector.tenant_id, pbx_connector_id=connector.id,
        event_type="CDR_RECORD_END", call_direction=direction,
        call_status=_cdr_terminal_status(variables.get("hangup_cause"), was_answered),
        caller_number=caller, callee_number=callee, agent_login=agent_login, queue_id=queue_id,
        duration=billsec, call_uuid=call_uuid, recording_url=recording_url,
        created_at=end_at, raw_payload=payload,
    ))

    for event in events:
        db.session.add(event)
    db.session.commit()

    for event in events:
        try:
            socketio.emit(
                "telephony_event", event.to_dict(),
                room=str(event.tenant_id), namespace="/telephony",
            )
        except Exception:
            current_app.logger.exception("Échec de diffusion WebSocket d'un événement CDR")

    return jsonify({"message": "CDR enregistré.", "events": len(events)}), 201


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


# Statuts bruts mod_callcenter (CC-Agent-Status) connus, normalisés en
# présence disponible/pause/hors-ligne. Tout statut absent ou non reconnu
# retombe sur "offline" — on ne fabrique jamais un état "disponible" par
# défaut à partir de données incertaines.
_AGENT_PRESENCE_ONLINE = {"available", "available (on demand)"}
_AGENT_PRESENCE_AWAY = {"on break"}


def _normalize_agent_presence(raw_status):
    if not raw_status:
        return "offline"
    key = raw_status.strip().lower()
    if key in _AGENT_PRESENCE_ONLINE:
        return "online"
    if key in _AGENT_PRESENCE_AWAY:
        return "away"
    return "offline"


@telephony_bp.get("/agents/status")
@tenant_required
def agents_status():
    """
    Présence agent (disponible/pause/hors-ligne), dérivée du dernier
    événement `CALLCENTER_AGENT_STATE_CHANGE` connu par `agent_login` —
    seuls les agents ayant émis au moins un tel événement apparaissent (pas
    de roster fabriqué). Croisé avec le volume d'appels traités sur la
    période (même règle que /kpis/agents) : `calls_handled` est un compte
    d'appels, pas un taux d'occupation — aucune durée continue disponible/
    occupée n'est suivie aujourd'hui.
    """
    dt_from, dt_to = _parse_period()

    latest_ts = (
        db.session.query(
            TelephonyEvent.agent_login,
            db.func.max(TelephonyEvent.created_at).label("max_created_at"),
        )
        .filter(
            TelephonyEvent.tenant_id == g.tenant_id,
            TelephonyEvent.event_type == "CALLCENTER_AGENT_STATE_CHANGE",
            TelephonyEvent.agent_login.isnot(None),
        )
        .group_by(TelephonyEvent.agent_login)
        .subquery()
    )
    latest_events = (
        TelephonyEvent.query
        .join(
            latest_ts,
            db.and_(
                TelephonyEvent.agent_login == latest_ts.c.agent_login,
                TelephonyEvent.created_at == latest_ts.c.max_created_at,
            ),
        )
        .filter(TelephonyEvent.tenant_id == g.tenant_id)
        .all()
    )

    calls_events = (
        TelephonyEvent.query.filter(
            TelephonyEvent.tenant_id == g.tenant_id,
            TelephonyEvent.created_at >= dt_from,
            TelephonyEvent.created_at <= dt_to,
            TelephonyEvent.agent_login.isnot(None),
            TelephonyEvent.call_uuid.isnot(None),
        ).all()
    )
    by_call = {}
    for e in calls_events:
        by_call.setdefault(e.call_uuid, []).append(e)
    calls_handled = {}
    for call_uuid, call_events in by_call.items():
        call_events.sort(key=lambda e: e.created_at)
        terminal = next((e for e in call_events if e.call_status in TERMINAL_STATUSES), None)
        if terminal is None:
            continue
        agent_login = next((e.agent_login for e in call_events if e.agent_login), None)
        if not agent_login:
            continue
        answered = next((e for e in call_events if e.call_status == "answered"), None)
        if answered:
            calls_handled[agent_login] = calls_handled.get(agent_login, 0) + 1

    agents = sorted(
        (
            {
                "agent_login": e.agent_login,
                "presence": _normalize_agent_presence(e.agent_status),
                "raw_status": e.agent_status,
                "last_seen_at": e.created_at.isoformat() if e.created_at else None,
                "calls_handled": calls_handled.get(e.agent_login, 0),
            }
            for e in latest_events
        ),
        key=lambda a: a["agent_login"],
    )

    return jsonify({
        "period": {"from": dt_from.isoformat(), "to": dt_to.isoformat()},
        "agents": agents,
    }), 200


# ═════════════════════════════════════════════════════════════════════════
#  Historique des appels (Rapports > Téléphonie) — pagination/filtres/export
# ═════════════════════════════════════════════════════════════════════════

MAX_HISTORY_RANGE_DAYS = 92  # ~3 mois — borne le volume chargé en mémoire
MAX_EXPORT_ROWS = 10_000
MAX_RECORDINGS_BULK_EXPORT = 200


def _parse_history_filters():
    """Filtres communs à /calls, /calls/export et /recordings. `from`/`to`
    par défaut sur les 30 derniers jours, bornés à MAX_HISTORY_RANGE_DAYS
    pour éviter de charger un historique complet en mémoire (même approche
    Python-side-grouping que /kpis/*, pas de fenêtre glissante DB)."""
    now = datetime.utcnow()

    def _parse_dt(raw, default):
        if not raw:
            return default
        try:
            return datetime.fromisoformat(raw.replace("Z", ""))
        except ValueError:
            return default

    dt_from = _parse_dt(request.args.get("from"), now - timedelta(days=30))
    dt_to = _parse_dt(request.args.get("to"), now)
    if dt_to < dt_from:
        dt_from, dt_to = dt_to, dt_from
    if (dt_to - dt_from).days > MAX_HISTORY_RANGE_DAYS:
        dt_from = dt_to - timedelta(days=MAX_HISTORY_RANGE_DAYS)

    return {
        "dt_from": dt_from,
        "dt_to": dt_to,
        "call_status": request.args.get("call_status") or None,
        "direction": request.args.get("direction") or None,
        "queue_id": request.args.get("queue_id") or None,
        "agent_login": request.args.get("agent_login") or None,
        "search": (request.args.get("search") or "").strip() or None,
    }


def _query_calls_history(filters, *, recordings_only=False):
    """Un call = un dict, groupé par call_uuid à partir des événements bruts
    (même approche que /kpis/summary). Retourne la liste triée par date de
    début décroissante — la pagination/l'export se font ensuite en mémoire
    sur ce résultat."""
    query = TelephonyEvent.query.filter(
        TelephonyEvent.tenant_id == g.tenant_id,
        TelephonyEvent.created_at >= filters["dt_from"],
        TelephonyEvent.created_at <= filters["dt_to"],
        TelephonyEvent.call_uuid.isnot(None),
    )
    if filters.get("agent_login"):
        query = query.filter(TelephonyEvent.agent_login == filters["agent_login"])
    if filters.get("queue_id"):
        query = query.filter(TelephonyEvent.queue_id == filters["queue_id"])

    by_call = {}
    for e in query.all():
        by_call.setdefault(e.call_uuid, []).append(e)

    rows = []
    for call_uuid, call_events in by_call.items():
        call_events.sort(key=lambda e: e.created_at)
        terminal = next((e for e in call_events if e.call_status in TERMINAL_STATUSES), None)
        if terminal is None:
            continue  # appel encore en cours sur la période — hors historique

        first = call_events[0]
        caller = next((e.caller_number for e in call_events if e.caller_number), None)
        callee = next((e.callee_number for e in call_events if e.callee_number), None)
        direction = next((e.call_direction for e in call_events if e.call_direction), None)
        agent_login = next((e.agent_login for e in call_events if e.agent_login), None)
        queue_id = next((e.queue_id for e in call_events if e.queue_id), None)
        recording_url = next((e.recording_url for e in call_events if e.recording_url), None)

        if recordings_only and not recording_url:
            continue
        if filters.get("call_status") and terminal.call_status != filters["call_status"]:
            continue
        if filters.get("direction") and direction != filters["direction"]:
            continue
        if filters.get("search"):
            needle = filters["search"].lower()
            haystack = f"{caller or ''} {callee or ''}".lower()
            if needle not in haystack:
                continue

        rows.append({
            "call_uuid": call_uuid,
            "caller": caller,
            "callee": callee,
            "direction": direction,
            "agent_login": agent_login,
            "queue_id": queue_id,
            "call_status": terminal.call_status,
            "duration": terminal.duration,
            "started_at": first.created_at.isoformat() if first.created_at else None,
            "ended_at": terminal.created_at.isoformat() if terminal.created_at else None,
            "recording_url": recording_url,
            "recording_available": bool(recording_url) and urlparse(recording_url).scheme in ("http", "https"),
        })

    rows.sort(key=lambda r: r["started_at"] or "", reverse=True)
    return rows


@telephony_bp.get("/calls")
@tenant_required
def list_calls():
    filters = _parse_history_filters()
    rows = _query_calls_history(filters)

    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 25))))
    except (TypeError, ValueError):
        page, per_page = 1, 25

    start = (page - 1) * per_page
    return jsonify({
        "calls": rows[start:start + per_page],
        "total": len(rows),
        "page": page,
        "per_page": per_page,
    }), 200


@telephony_bp.get("/calls/export")
@tenant_required
def export_calls_csv():
    filters = _parse_history_filters()
    rows = _query_calls_history(filters)[:MAX_EXPORT_ROWS]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "call_uuid", "started_at", "ended_at", "caller", "callee", "direction",
        "agent_login", "queue_id", "call_status", "duration_seconds",
    ])
    for r in rows:
        writer.writerow([
            r["call_uuid"], r["started_at"], r["ended_at"], r["caller"], r["callee"],
            r["direction"], r["agent_login"], r["queue_id"], r["call_status"], r["duration"],
        ])

    filename = f"appels_{filters['dt_from'].date()}_{filters['dt_to'].date()}.csv"
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@telephony_bp.get("/recordings")
@tenant_required
def list_recordings():
    filters = _parse_history_filters()
    rows = _query_calls_history(filters, recordings_only=True)

    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 25))))
    except (TypeError, ValueError):
        page, per_page = 1, 25

    start = (page - 1) * per_page
    return jsonify({
        "recordings": rows[start:start + per_page],
        "total": len(rows),
        "page": page,
        "per_page": per_page,
    }), 200


@telephony_bp.get("/recordings/<call_uuid>/download")
@tenant_required
def download_recording(call_uuid):
    """
    Proxy le fichier d'enregistrement si `recording_url` est une URL
    http(s) exploitable. FreeSWITCH renseigne souvent un chemin de fichier
    local (pas une URL) : dans ce cas, 422 explicite plutôt qu'un
    téléchargement silencieusement cassé — cf. limitation documentée dans
    TELEPHONIE_INTEGRATION_PLAN.md (exposition des fichiers côté FusionPBX
    non confirmée à ce jour).
    """
    event = (
        TelephonyEvent.query
        .filter(
            TelephonyEvent.tenant_id == g.tenant_id,
            TelephonyEvent.call_uuid == call_uuid,
            TelephonyEvent.recording_url.isnot(None),
        )
        .order_by(TelephonyEvent.created_at.desc())
        .first()
    )
    if event is None:
        return jsonify({"error": "Enregistrement introuvable."}), 404

    if urlparse(event.recording_url).scheme not in ("http", "https"):
        return jsonify({
            "error": "Ce fichier n'est pas exposé via une URL accessible depuis PERMATEL "
                     "(configuration FusionPBX requise).",
        }), 422

    try:
        upstream = requests.get(event.recording_url, stream=True, timeout=15)
        upstream.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Échec du téléchargement de l'enregistrement %s : %s", call_uuid, exc)
        return jsonify({"error": "Le fichier n'a pas pu être récupéré depuis le PBX."}), 502

    filename = f"enregistrement_{call_uuid}.{(event.recording_url.rsplit('.', 1)[-1] or 'audio')[:5]}"
    return Response(
        upstream.iter_content(chunk_size=8192),
        mimetype=upstream.headers.get("Content-Type", "audio/mpeg"),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@telephony_bp.post("/recordings/export")
@tenant_required
def bulk_export_recordings():
    """
    Export groupé en ZIP. Body optionnel `{"call_uuids": [...]}` pour une
    sélection explicite (UI : cases à cocher) ; sans body, exporte tout ce
    qui correspond aux filtres de la requête (même query params que
    /recordings), plafonné à MAX_RECORDINGS_BULK_EXPORT. Les fichiers non
    exposés via une URL http(s) sont exclus du zip et listés dans
    `_indisponibles.txt` plutôt que silencieusement absents.
    """
    filters = _parse_history_filters()
    rows = _query_calls_history(filters, recordings_only=True)

    data = request.get_json(silent=True) or {}
    requested_uuids = data.get("call_uuids")
    if requested_uuids:
        wanted = set(requested_uuids)
        rows = [r for r in rows if r["call_uuid"] in wanted]

    rows = rows[:MAX_RECORDINGS_BULK_EXPORT]

    buffer = io.BytesIO()
    unavailable = []
    included = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in rows:
            if not r["recording_available"]:
                unavailable.append(f"{r['call_uuid']} — fichier non exposé via une URL accessible (chemin local PBX)")
                continue
            try:
                upstream = requests.get(r["recording_url"], timeout=15)
                upstream.raise_for_status()
            except requests.RequestException as exc:
                unavailable.append(f"{r['call_uuid']} — échec de récupération : {exc}")
                continue
            ext = (r["recording_url"].rsplit(".", 1)[-1] or "audio")[:5]
            zf.writestr(f"{r['call_uuid']}.{ext}", upstream.content)
            included += 1
        if unavailable:
            zf.writestr(
                "_indisponibles.txt",
                "Enregistrements non inclus dans cet export :\n\n" + "\n".join(unavailable),
            )

    if included == 0 and not unavailable:
        return jsonify({"error": "Aucun enregistrement ne correspond à la sélection."}), 404

    buffer.seek(0)
    filename = f"enregistrements_{filters['dt_from'].date()}_{filters['dt_to'].date()}.zip"
    return Response(
        buffer.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
        authorized_ip=(data.get("authorized_ip") or "").strip() or None,
    )
    if data.get("password"):
        # Colonne EncryptedText : chiffrement transparent à l'écriture (pas
        # d'appel manuel à encrypt_secret ici — même convention que Email.subject).
        connector.password = data["password"]

    # Jeton webhook CDR généré dès la création : l'URL est copiable
    # immédiatement, pas besoin d'une étape "générer" séparée avant le
    # premier usage (régénération disponible ensuite si besoin).
    raw_token = secrets.token_urlsafe(32)
    connector.cdr_webhook_token_hash = _hash_webhook_token(raw_token)
    connector.cdr_webhook_token = raw_token

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
    if "authorized_ip" in data:
        connector.authorized_ip = (data["authorized_ip"] or "").strip() or None

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


@telephony_bp.post("/connectors/<int:connector_id>/cdr-token/regenerate")
@tenant_admin_required
def regenerate_cdr_token(connector_id):
    """
    (Re)génère le jeton webhook CDR du connecteur. Invalide immédiatement
    l'ancienne URL (FusionPBX doit être reconfiguré) — confirmation gérée
    côté frontend, pas ici.
    """
    connector = _connector_or_404(connector_id)
    raw_token = secrets.token_urlsafe(32)
    connector.cdr_webhook_token_hash = _hash_webhook_token(raw_token)
    connector.cdr_webhook_token = raw_token  # chiffré à l'écriture (EncryptedText)
    db.session.commit()
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
