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
import os
import re
import secrets
import zipfile
from datetime import datetime, timedelta
from app.utils.time import utcnow, utcfromtimestamp
from urllib.parse import unquote, unquote_plus, urlparse

import requests
from flask import Blueprint, Response, current_app, g, jsonify, request
from flask_cors import CORS

from app import db, socketio
from app.models import PbxConnector, PbxConnectorDomain, TelephonyEvent, TenantUser, User
from app.utils.decorators import tenant_admin_required, tenant_required

telephony_bp = Blueprint("telephony", __name__, url_prefix="/api/telephony")
CORS(telephony_bp, supports_credentials=True)

TERMINAL_STATUSES = {"ended", "missed", "abandoned", "technical_failure"}
SYNC_CHANNEL = "telephony:sync"
# Un appel dont le dernier événement connu n'est pas terminal reste "en
# cours" indéfiniment si l'événement de raccroché a été perdu (redémarrage
# du connecteur en plein appel, coupure ESL, etc. — vu en prod le 29/07).
# Passé ce délai sans nouvel événement, on cesse de le considérer actif
# plutôt que d'afficher un appel fantôme.
ACTIVE_CALL_STALE_AFTER = timedelta(minutes=30)

logger = logging.getLogger(__name__)


def _iso_utc(dt) -> str | None:
    """Toutes les colonnes datetime de ce module sont naïves-UTC
    (`utcnow()`) — `.isoformat()` seul ne porte donc AUCUN
    désignateur de fuseau. Confirmé en prod (30/07) : un navigateur (ou tout
    parseur JS/ISO strict) interprète alors une chaîne date-heure SANS
    désignateur comme heure LOCALE, pas UTC — un décalage de +1h (fuseau
    UTC+1) apparaissait systématiquement sur toutes les durées calculées côté
    Supervision temps réel. Le 'Z' explicite lève l'ambiguïté."""
    return f"{dt.isoformat()}Z" if dt else None


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

def _known_agent_logins_for_tenant(tenant_id) -> list:
    """
    Roster d'agents faisant autorité côté PERMATEL — un `agent_login`
    résolu depuis FusionPBX (annuaire ESL, cf. `ESLAdapter._fetch_agent_list`)
    n'est retenu par le connecteur que s'il correspond à un `User` réel de ce
    tenant. Évite d'attribuer de la présence/des KPI à une extension PBX qui
    ne correspond à aucun agent PERMATEL configuré (poste de test, ancien
    agent jamais nettoyé côté PBX, etc.).
    """
    rows = (
        db.session.query(User.agent_login)
        .join(TenantUser, TenantUser.user_id == User.id)
        .filter(
            TenantUser.tenant_id == tenant_id,
            TenantUser.is_active.is_(True),
            User.is_active.is_(True),
            User.agent_login.isnot(None),
        )
        .distinct()
        .all()
    )
    return [login for (login,) in rows if login]


@telephony_bp.get("/connectors/config")
def connectors_bootstrap_config():
    """
    Config dynamique consommée par le Core Connector au démarrage (et
    périodiquement) : tous les `pbx_connectors` actifs (tous tenants
    confondus — vue globale côté connecteur, même si la ressource est
    tenant-scopée côté administration), identifiants déchiffrés inclus,
    avec leurs domaines rattachés. `sync_requested_at` sert de filet de
    secours au signal Redis temps réel (§ ci-dessus). `known_agent_logins`
    (Phase 13, présence agent) : roster des `User.agent_login` connus pour
    le tenant, utilisé par le connecteur pour valider les extensions
    résolues depuis FusionPBX avant de les retenir dans son annuaire.
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
        data["known_agent_logins"] = _known_agent_logins_for_tenant(c.tenant_id)
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
    now = utcnow()

    updated = 0
    for connector_id_str, status in statuses.items():
        try:
            connector_id = int(connector_id_str)
        except (TypeError, ValueError):
            continue
        connector = db.session.get(PbxConnector, connector_id)
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
        linked_call_uuid=call.get("linked_call_uuid"),
        agent_login=agent.get("login"),
        # Sur ce canal, 'login' EST l'uuid FusionPBX CC-Agent (cf.
        # normalizer.py::normalize_agent_status_change) — accepte aussi une
        # clé 'uuid' explicite si le connecteur en envoie une un jour,
        # 'station' si l'annuaire ESL a pu résoudre l'extension en direct
        # (absent aujourd'hui, connecteur non encore mis à jour pour l'envoyer).
        agent_uuid=agent.get("uuid") or agent.get("login"),
        agent_station_extension=agent.get("station"),
        agent_status=agent.get("status"),
        queue_id=queue.get("id"),
        duration=data.get("duration_seconds"),
        recording_url=data.get("recording_url"),
        raw_payload=data,
        created_at=created_at or utcnow(),
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
    return utcfromtimestamp(value) if value else None


# Fragments de nom de clé (insensible à la casse) considérés porteurs de
# PII/contenu d'appel — la VALEUR de toute clé qui en contient un est
# masquée dans la trace CDR (log ET fichier), seuls le nom de clé et le
# type sont conservés. Volontairement large (mieux vaut sur-masquer une
# clé anodine que laisser fuiter un numéro ou un chemin d'enregistrement) :
# l'outil sert à découvrir la STRUCTURE des payloads PBX, pas leur contenu.
_CDR_TRACE_SENSITIVE_KEY_FRAGMENTS = (
    "caller", "callee", "destination", "cid", "ani", "dnis", "phone",
    "number", "sip_from", "sip_to", "sip_full", "record", "contact",
    "email", "agent", "member",
)


def _cdr_trace_redact(obj):
    """Masque récursivement les valeurs des clés sensibles (voir
    _CDR_TRACE_SENSITIVE_KEY_FRAGMENTS) dans un payload CDR, pour le log ET
    l'écriture disque de _trace_cdr_payload() — jamais de PII/contenu
    d'appel réel dans la trace, seulement sa structure."""
    if isinstance(obj, dict):
        redacted = {}
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                redacted[k] = _cdr_trace_redact(v)
            elif any(frag in k.lower() for frag in _CDR_TRACE_SENSITIVE_KEY_FRAGMENTS):
                redacted[k] = "<redacted>" if v not in (None, "") else v
            else:
                redacted[k] = v
        return redacted
    if isinstance(obj, list):
        return [_cdr_trace_redact(v) for v in obj]
    return obj


def _trace_cdr_payload(connector_id: int, payload: dict) -> None:
    """
    Diagnostic activable via TELEPHONY_CDR_TRACE=true — journalise
    l'inventaire complet des variables reçues (clé, type, aperçu de valeur
    MASQUÉ pour les clés sensibles, cf. _cdr_trace_redact) et écrit le
    payload (redacté) dans un fichier, pour confirmer quelles variables un
    PBX réel envoie effectivement. A déjà permis de corriger deux
    hypothèses fausses : caller_id_number/destination_number ne sont pas
    systématiquement sous 'variables' (vivent sous
    callflow[0].caller_profile) et cc_agent est un UUID interne FusionPBX,
    pas un login/une extension (l'agent réel est sous
    callflow[0].caller_profile.originatee). Ne doit jamais faire échouer
    l'ingestion : toute erreur ici est journalisée puis ignorée.

    ⚠️ Audit du 12/08 : ce flag ne doit JAMAIS rester actif durablement en
    production (même redacté, un dump de structure à chaque appel entrant
    est un bruit et un risque évitables) — à activer ponctuellement pour
    diagnostiquer un nouveau PBX, puis désactiver.
    """
    try:
        payload = _cdr_trace_redact(payload)
        variables = payload.get("variables") or {}
        top_level_keys = sorted(k for k in payload.keys() if k != "variables")
        var_lines = []
        for key in sorted(variables.keys()):
            value = variables[key]
            preview = repr(value)
            if len(preview) > 120:
                preview = preview[:120] + "…"
            var_lines.append(f"    {key} ({type(value).__name__}) = {preview}")

        call_uuid = variables.get("uuid") or variables.get("call_uuid") or payload.get("uuid") or "?"
        trace_path = "/tmp/cdr_trace_last.json"
        try:
            with open(trace_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
            # Lecture restreinte au propriétaire du process — le fichier est
            # écrasé à chaque appel (pas d'accumulation), mais /tmp reste
            # potentiellement lisible par d'autres utilisateurs du même hôte
            # entre deux écritures sans cette restriction.
            os.chmod(trace_path, 0o600)
        except OSError as exc:
            logger.warning("CDR TRACE : échec d'écriture du fichier %s : %s", trace_path, exc)
            trace_path = None

        logger.info(
            "CDR TRACE connecteur id=%s call_uuid=%s — %d clé(s) top-level=%s, "
            "%d variable(s) sous 'variables' (valeurs sensibles masquées) :\n%s\n"
            "  (payload complet écrit dans %s)",
            connector_id, call_uuid, len(top_level_keys), top_level_keys,
            len(var_lines), "\n".join(var_lines), trace_path or "(échec)",
        )
    except Exception:  # noqa: BLE001 - diagnostic best-effort, ne doit jamais casser l'ingestion
        logger.exception("CDR TRACE : erreur inattendue pendant la trace (ignorée)")


# Confirmé sur trafic FusionPBX réel (28/07) : certains champs (en-têtes SIP
# bruts type `sip_full_from`/`sip_full_to`, ex. `"33186569392" <sip:...>;tag=...`)
# sont interpolés par FusionPBX dans le JSON SANS échapper les guillemets
# internes (nom d'affichage SIP entre guillemets) — JSON syntaxiquement
# invalide, indépendant de tout problème de décodage/encodage. Répare en
# repérant la VRAIE fin de chaque valeur-chaîne (le prochain '"' suivi de
# ',' '}' ou ']', espaces autorisés) et en échappant tout guillemet interne
# non déjà échappé trouvé avant ce point. Heuristique, pas un vrai parseur —
# mais strictement meilleure que l'échec total actuel, et sans effet sur les
# champs déjà bien formés (aucun guillemet interne à échapper).
_CDR_STRING_VALUE_RE = re.compile(r'"([a-zA-Z0-9_\-]+)"\s*:\s*"(.*?)"(?=\s*[,}\]])', re.DOTALL)


def _repair_unescaped_quotes(text: str) -> str:
    def _escape_inner_quotes(match):
        key, value = match.group(1), match.group(2)
        fixed_value = re.sub(r'(?<!\\)"', r'\"', value)
        return f'"{key}":"{fixed_value}"'

    return _CDR_STRING_VALUE_RE.sub(_escape_inner_quotes, text)


@telephony_bp.post("/cdr/ingest/<token>")
def cdr_ingest(token):
    """
    Webhook CDR — FusionPBX (mod_json_cdr) POSTe un résumé JSON à la fin de
    chaque appel. Contrairement à /events/ingest (jeton global, appelé par
    notre propre Core Connector), le jeton ici est PAR CONNECTEUR et résout
    directement le tenant, sans jamais transiter par le Core Connector.

    Format du corps et variables confirmés contre du trafic FusionPBX réel
    (29/07, appel direct + appel en file d'attente) : `application/x-
    www-form-urlencoded` (`cdr=<json>`), caller/callee sous
    `callflow[0].caller_profile`, `cc_queue` fiable mais `cc_agent` = UUID
    interne FusionPBX (voir extraction `agent_login` ci-dessous). Toujours
    non confirmé : exposition des enregistrements (`recording_url` — aucun
    appel de test avec enregistrement actif à ce jour).
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

    # Confirmé sur trafic FusionPBX réel (28/07, 3 tentatives successives) :
    # Content-Type application/x-www-form-urlencoded (défaut libcurl
    # POSTFIELDS, pas une vraie soumission de formulaire), corps `cdr=<json>`
    # — MAIS le JSON (dump de variables de canal, ~80 Ko) contient des '&'/'='
    # littéraux non échappés (URIs SIP, en-têtes...), que le parseur de
    # formulaire de Werkzeug interprète à tort comme des séparateurs de
    # paires, tronquant `request.form['cdr']` au premier caractère litigieux.
    # On ne fait donc plus confiance au décodage form de Werkzeug : on relit
    # le corps BRUT (non altéré, indépendant du Content-Type déclaré) et on
    # extrait nous-mêmes le premier objet JSON qu'il contient (première '{'
    # à la dernière '}'), avec un essai de décodage URL en repli si le corps
    # s'avère réellement URL-encodé.
    raw_body = request.get_data(as_text=True) or ""
    payload = None
    # Trois hypothèses testées, dans cet ordre :
    #  1. corps déjà en clair (émetteur non conforme, cas réel confirmé en
    #     prod — chercher '{'/'}' littéraux fonctionne même avec des '&'/'='
    #     internes puisqu'aucun parsing clé=valeur n'est tenté) ;
    #  2. corps URL-encodé au sens strict RFC 3986 (%XX uniquement, '+' non
    #     transformé) — le cas d'un encodeur type JS `encodeURIComponent`,
    #     qui laisse '+' tel quel : décoder avec unquote_plus corromprait un
    #     numéro E.164 ("+33...") en le remplaçant par un espace ;
    #  3. corps réellement application/x-www-form-urlencoded au sens strict
    #     (RFC 1866, '+' = espace) — unquote_plus, en dernier recours.
    # 4e hypothèse : double encodage (l'émetteur encode deux fois, ou une
    # couche intermédiaire — proxy, lib HTTP — ré-encode un corps déjà
    # encodé). unquote appliqué deux fois ne casse rien si une seule couche
    # existait (idempotent sur du texte déjà décodé sans '%').
    candidates_text = (
        raw_body, unquote(raw_body), unquote_plus(raw_body), unquote(unquote(raw_body)),
    )
    last_error = None  # (label, JSONDecodeError, sliced_text) — pour diagnostic si tout échoue
    for label, text in zip(("brut", "unquote", "unquote_plus", "unquote x2"), candidates_text):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            continue
        sliced = text[start:end + 1]
        try:
            # strict=False : confirmé sur trafic FusionPBX réel (28/07) — le
            # dump complet des variables de canal (SIP headers multi-lignes,
            # etc.) embarque des caractères de contrôle bruts (\n, \t...) non
            # échappés dans des valeurs de chaîne, invalides au sens strict
            # RFC 8259 mais tolérés ici plutôt que de rejeter tout le CDR
            # pour un champ secondaire mal échappé.
            candidate = json.loads(sliced, strict=False)
        except json.JSONDecodeError as exc:
            last_error = (label, exc, sliced)
            continue
        except (TypeError, ValueError):
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    if payload is None and last_error is not None:
        # Dernier recours : JSON structurellement invalide (guillemets non
        # échappés dans une valeur, cf. _repair_unescaped_quotes) plutôt
        # qu'un problème d'encodage — tenté uniquement sur le texte qui a
        # atteint le stade JSONDecodeError (bornage '{'/'}' déjà correct).
        _, _, sliced = last_error
        try:
            candidate = json.loads(_repair_unescaped_quotes(sliced), strict=False)
        except (TypeError, ValueError):
            candidate = None
        if isinstance(candidate, dict):
            payload = candidate
    if payload is None:
        payload = request.get_json(silent=True, force=True)
    if not isinstance(payload, dict):
        # Diagnostic permanent (requalifié le 12/08 — n'est plus "temporaire",
        # ce chemin ne se déclenche QUE sur un échec réel de parsing, jamais
        # sur du trafic normal) : journalise la position EXACTE où json.loads
        # échoue, avec un extrait centré sur ce point précis, pour diagnostiquer
        # un futur format CDR inattendu sans deviner à l'aveugle. Le WARNING
        # reste justifié malgré l'extrait de payload potentiellement sensible
        # dans le log : il ne fires que sur un échec d'ingestion réel (rare),
        # jamais en fonctionnement normal — contrairement à _trace_cdr_payload
        # ci-dessus qui doit rester désactivée par défaut.
        error_detail = "aucune erreur JSON capturée (aucun '{'/'}' trouvé dans les 4 candidats)"
        if last_error is not None:
            label, exc, sliced = last_error
            window_start = max(0, exc.pos - 120)
            window_end = min(len(sliced), exc.pos + 120)
            error_detail = (
                f"candidat={label!r} erreur={exc.msg!r} ligne={exc.lineno} colonne={exc.colno} "
                f"position={exc.pos} autour_de={sliced[window_start:window_end]!r}"
            )
        logger.warning(
            "CDR webhook : corps illisible pour le connecteur id=%s "
            "(Content-Type=%r, %d octets, clés formulaire=%r) — %s",
            connector.id, request.content_type, request.content_length or 0,
            list(request.form.keys())[:5], error_detail,
        )
        return jsonify({"error": "Corps CDR JSON invalide ou absent."}), 400

    if current_app.config.get("TELEPHONY_CDR_TRACE"):
        _trace_cdr_payload(connector.id, payload)

    variables = payload.get("variables") or {}
    call_uuid = (
        variables.get("uuid") or variables.get("call_uuid") or payload.get("uuid")
        or request.args.get("uuid")
    )
    if not call_uuid:
        return jsonify({"error": "UUID d'appel introuvable dans le CDR."}), 400

    start_at = _cdr_epoch_to_dt(variables.get("start_epoch"))
    answer_at = _cdr_epoch_to_dt(variables.get("answer_epoch"))
    end_at = _cdr_epoch_to_dt(variables.get("end_epoch")) or utcnow()
    try:
        billsec = int(variables["billsec"]) if variables.get("billsec") is not None else None
    except (TypeError, ValueError):
        billsec = None
    was_answered = bool(answer_at) and bool(billsec)

    # Confirmé sur trafic FusionPBX réel (28/07) : 'caller_id_number' et
    # 'destination_number' n'existent PAS sous 'variables' (l'hypothèse
    # initiale était fausse) — ils vivent sous callflow[0].caller_profile.
    # Repli sur les en-têtes SIP (sip_from_user/sip_to_user) si callflow est
    # absent pour une raison quelconque.
    callflow = payload.get("callflow") or []
    caller_profile = (callflow[0].get("caller_profile") or {}) if callflow else {}
    caller = (
        caller_profile.get("caller_id_number")
        or variables.get("caller_id_number") or variables.get("effective_caller_id_number")
        or variables.get("sip_from_user")
    )
    callee = (
        caller_profile.get("destination_number")
        or variables.get("destination_number")
        or variables.get("sip_to_user")
    )
    direction = variables.get("direction")
    # Confirmé sur trafic FusionPBX réel (appel en file d'attente, 29/07) :
    # 'cc_queue' est fiable, format "<extension>@<domaine>" (même convention
    # que le header ESL CC-Queue). 'cc_agent' est un UUID interne FusionPBX
    # (call_center_agents.call_center_agent_uuid) — inexploitable comme
    # login/extension directement, mais c'est la même identité stable que
    # `User.agent_login`/les événements live ESL : conservée sous
    # `agent_uuid` (colonne dédiée, cf. audit du 30/07 — `agent_login` seul
    # mélangeait UUID (live) et extension (CDR), cassant toute jointure
    # entre les deux canaux). L'extension réelle de l'agent qui décroche se
    # trouve dans le profil "originatee" du callflow (le leg vers lequel
    # mod_callcenter a bridgé), pas dans une variable 'cc_*' — absente sur un
    # appel hors file d'attente, d'où le garde conditionné à 'cc_queue'.
    queue_id = variables.get("cc_queue")
    originatee_profiles = (
        (caller_profile.get("originatee") or {}).get("originatee_caller_profiles") or []
    )
    agent_station_extension = (
        (originatee_profiles[0].get("destination_number") if originatee_profiles else None)
        if queue_id else None
    )
    agent_uuid = variables.get("cc_agent") if queue_id else None
    # `agent_login` conservée pour compat descendante (mêmes lecteurs qu'avant
    # ce correctif) — vaut l'extension, comme depuis `d5f9e31`. Les nouveaux
    # consommateurs doivent utiliser `agent_uuid`/`agent_station_extension`.
    agent_login = agent_station_extension
    recording_url = variables.get("record_file_path") or variables.get("recording_follow_transfer")

    events = []
    if start_at:
        events.append(TelephonyEvent(
            tenant_id=connector.tenant_id, pbx_connector_id=connector.id,
            event_type="CDR_RECORD_START", call_direction=direction, call_status="ringing",
            caller_number=caller, callee_number=callee, agent_login=agent_login,
            agent_uuid=agent_uuid, agent_station_extension=agent_station_extension, queue_id=queue_id,
            call_uuid=call_uuid, created_at=start_at, raw_payload=payload,
        ))
    if answer_at and was_answered:
        events.append(TelephonyEvent(
            tenant_id=connector.tenant_id, pbx_connector_id=connector.id,
            event_type="CDR_RECORD_ANSWER", call_direction=direction, call_status="answered",
            caller_number=caller, callee_number=callee, agent_login=agent_login,
            agent_uuid=agent_uuid, agent_station_extension=agent_station_extension, queue_id=queue_id,
            call_uuid=call_uuid, created_at=answer_at, raw_payload=payload,
        ))
    events.append(TelephonyEvent(
        tenant_id=connector.tenant_id, pbx_connector_id=connector.id,
        event_type="CDR_RECORD_END", call_direction=direction,
        call_status=_cdr_terminal_status(variables.get("hangup_cause"), was_answered),
        caller_number=caller, callee_number=callee, agent_login=agent_login,
        agent_uuid=agent_uuid, agent_station_extension=agent_station_extension, queue_id=queue_id,
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

    now = utcnow()
    dt_from = _parse(request.args.get("from"), now - timedelta(days=1))
    dt_to = _parse(request.args.get("to"), now)
    return dt_from, dt_to


def _resolve_active_calls(tenant_id) -> list:
    """
    Appels en cours : un appel physique peut produire plusieurs événements
    ETALÉS DANS LE TEMPS pour le MÊME call_uuid (ex. CHANNEL_CREATE puis,
    bien après, un événement callcenter::info qui n'apporte que l'agent/la
    file/le vrai numéro composé — confirmé en prod 29/07 via
    'agent-offering', CC-Member-Session-UUID == Unique-ID du leg entrant).
    On ne peut donc plus se contenter du DERNIER événement : chaque champ
    (appelant, destination, agent, file, statut) est résolu à sa dernière
    valeur NON NULLE parmi tous les événements du call_uuid, pas seulement
    ceux du tout dernier événement reçu.

    Factorisé hors de la route (31/07) : /agents/status en a aussi besoin,
    pour dériver une présence "en appel" à partir des appels réellement
    ouverts plutôt que du seul statut manuel agent (Available/On Break/
    Logged Out, qui ne change jamais pendant un appel — voir
    _AGENT_PRESENCE_ONLINE/_AWAY et la discussion du 31/07).
    """
    latest_ts = (
        db.session.query(
            TelephonyEvent.call_uuid,
            db.func.max(TelephonyEvent.created_at).label("max_created_at"),
        )
        # CALLCENTER_AGENT_STATE_CHANGE exclu : un événement de présence pure
        # ne porte jamais de Unique-ID/call_uuid réel en production (confirmé
        # sur trafic réel — 'agent-status-change' ne porte AUCUN contexte de
        # canal, cf. _on_agent_status_event) ; l'exclure ici évite qu'une
        # convention de test qui poserait quand même un call_uuid dessus (ou
        # une future source de données) ne le fasse compter à tort comme un
        # appel ouvert.
        .filter(
            TelephonyEvent.tenant_id == tenant_id,
            TelephonyEvent.call_uuid.isnot(None),
            TelephonyEvent.event_type != "CALLCENTER_AGENT_STATE_CHANGE",
        )
        .group_by(TelephonyEvent.call_uuid)
        .subquery()
    )
    latest_events = (
        db.session.query(TelephonyEvent.call_uuid, TelephonyEvent.call_status, TelephonyEvent.created_at)
        .join(
            latest_ts,
            db.and_(
                TelephonyEvent.call_uuid == latest_ts.c.call_uuid,
                TelephonyEvent.created_at == latest_ts.c.max_created_at,
            ),
        )
        .filter(
            TelephonyEvent.tenant_id == tenant_id,
            TelephonyEvent.event_type != "CALLCENTER_AGENT_STATE_CHANGE",
        )
        .all()
    )
    stale_cutoff = utcnow() - ACTIVE_CALL_STALE_AFTER
    candidate_uuids = [
        row.call_uuid for row in latest_events
        if row.call_status not in TERMINAL_STATUSES and row.created_at >= stale_cutoff
    ]
    if not candidate_uuids:
        return []

    all_events = (
        TelephonyEvent.query
        .filter(
            TelephonyEvent.tenant_id == tenant_id,
            TelephonyEvent.call_uuid.in_(candidate_uuids),
        )
        .order_by(TelephonyEvent.created_at.asc())
        .all()
    )
    by_call = {}
    for e in all_events:
        by_call.setdefault(e.call_uuid, []).append(e)

    merged = {}
    for call_uuid, evs in by_call.items():
        m = {
            "call_uuid": call_uuid,
            "pbx_connector_id": None,
            "call_direction": None,
            "call_status": None,
            "caller": None,
            "callee": None,
            "agent_login": None,
            "agent_uuid": None,
            "agent_station_extension": None,
            "queue_id": None,
            "linked_call_uuid": None,
            "started_at": evs[0].created_at,
            "created_at": evs[-1].created_at,
        }
        for e in evs:
            m["pbx_connector_id"] = e.pbx_connector_id or m["pbx_connector_id"]
            if e.call_direction:
                m["call_direction"] = e.call_direction
            if e.call_status:
                m["call_status"] = e.call_status
            if e.caller_number:
                m["caller"] = e.caller_number
            if e.callee_number:
                m["callee"] = e.callee_number
            if e.agent_login:
                m["agent_login"] = e.agent_login
            if e.agent_uuid:
                m["agent_uuid"] = e.agent_uuid
            if e.agent_station_extension:
                m["agent_station_extension"] = e.agent_station_extension
            if e.queue_id:
                m["queue_id"] = e.queue_id
            if e.linked_call_uuid:
                m["linked_call_uuid"] = e.linked_call_uuid
        merged[call_uuid] = m

    # Fusion des legs d'un appel bridgé : Other-Leg-Unique-ID (confirmé en
    # prod, uniquement peuplé une fois le pont établi) relie les deux
    # call_uuid d'un même appel physique. On ne garde que le leg "inbound" —
    # dans les deux scénarios réels observés (appel entrant en file, appel
    # sortant direct d'un agent), c'est systématiquement celui qui porte le
    # numéro humainement lisible (appelant externe réel, ou poste agent qui
    # compose), l'autre leg ne portant que le format de routage interne vers
    # le trunk.
    for call_uuid, m in list(merged.items()):
        linked = m.get("linked_call_uuid")
        if linked and linked in merged and m.get("call_direction") == "outbound":
            merged.pop(call_uuid, None)

    alias_lookup = _agent_alias_lookup(tenant_id)
    queue_alias_lookup = _queue_alias_lookup(tenant_id)
    station_agent_lookup = _live_station_agent_lookup(tenant_id)
    active = []
    for m in merged.values():
        agent_uuid = m["agent_uuid"]
        agent_inferred = False
        if not agent_uuid:
            # Aucun contexte CC-Agent sur cet appel (ex. appel direct hors
            # file) : on tente de retrouver l'agent via son dernier login
            # connu sur ce poste — caller OU callee, l'un des deux est
            # l'extension interne selon le sens de l'appel.
            agent_uuid = station_agent_lookup.get(m["caller"]) or station_agent_lookup.get(m["callee"])
            agent_inferred = agent_uuid is not None
        alias = alias_lookup.get(agent_uuid) if agent_uuid else None
        active.append({
            **m,
            "agent_uuid": agent_uuid,
            # True si l'agent n'est pas confirmé par un contexte CC-Agent sur
            # CET appel — déduit du dernier login connu sur le poste
            # composant/appelé, jamais présenté comme aussi certain qu'une
            # résolution directe.
            "agent_inferred": agent_inferred,
            "agent_name": alias["name"] if alias else (m["agent_login"] or agent_uuid),
            # Poste observé en direct sur cet appel prioritaire sur le poste
            # statique déclaré côté gestion des utilisateurs.
            "agent_station": m["agent_station_extension"] or (alias["station"] if alias else None),
            "queue_label": _format_queue_label(m["queue_id"], queue_alias_lookup),
            "started_at": _iso_utc(m["started_at"]),
            "created_at": _iso_utc(m["created_at"]),
        })
    return active


@telephony_bp.get("/active-calls")
@tenant_required
def active_calls():
    active = _resolve_active_calls(g.tenant_id)
    return jsonify({"active_calls": active, "total": len(active)}), 200


def _agents_currently_on_call(tenant_id) -> set:
    """Ensemble des `agent_uuid` actuellement associés à un appel ouvert
    (résolu comme /active-calls, y compris via l'inférence par poste pour
    les appels sans contexte CC-Agent) — sert à dériver une présence "en
    appel" pour /agents/status, faute de signal live PBX sur les
    sous-transitions Waiting/Receiving/In a queue call (confirmé absent du
    trafic réel, cf. `_normalize_agent_presence`). Volontairement grossier :
    ne distingue pas "en train de sonner" de "en communication" — cette
    distinction dépendrait de la fusion du statut du leg agent sur la ligne
    survivante, non confirmée sur trafic réel à ce jour (cf. discussion
    31/07) — mieux vaut un état "en appel" honnête que deviner un sous-état
    non vérifié."""
    return {
        call["agent_uuid"] for call in _resolve_active_calls(tenant_id)
        if call.get("agent_uuid")
    }


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
        "period": {"from": _iso_utc(dt_from), "to": _iso_utc(dt_to)},
        "total_calls": total_calls,
        "answered_calls": answered_calls,
        "decroche_rate_pct": decroche_rate,
        "avg_response_seconds": avg_response,
    }), 200


def _queue_alias_lookup(tenant_id) -> dict:
    """`"{queue_id}@{pbx_domain}"` -> alias configuré (Paramètres >
    Intégrations > Téléphonie), pour habiller les identifiants bruts
    PBX (même clé que `CC-Queue`/`cc_queue`, cf. normalizer/routes CDR).
    Compat ancien format `queue_ids` (liste de chaînes nues, alias absent :
    l'id sert alors de son propre alias)."""
    domains = (
        db.session.query(PbxConnectorDomain)
        .join(PbxConnector, PbxConnector.id == PbxConnectorDomain.pbx_connector_id)
        .filter(PbxConnector.tenant_id == tenant_id)
        .all()
    )
    lookup = {}
    for d in domains:
        for item in (d.queue_ids or []):
            if isinstance(item, dict):
                queue_id = str(item.get("id") or "").strip()
                alias = str(item.get("alias") or "").strip()
            else:
                queue_id = str(item or "").strip()
                alias = ""
            if queue_id:
                lookup[f"{queue_id}@{d.pbx_domain}"] = alias or queue_id
    return lookup


def _format_queue_label(queue_id, alias_lookup) -> str | None:
    """"{alias} ({id nu})" pour l'affichage humain (monitoring temps réel) —
    None si l'appel n'est rattaché à aucune file. Retombe sur l'id nu seul
    si aucun alias n'est configuré pour cette file (jamais de doublon du
    type "8004 (8004)")."""
    if not queue_id:
        return None
    bare_id = queue_id.split("@", 1)[0]
    alias = alias_lookup.get(queue_id)
    if alias and alias != queue_id:
        return f"{alias} ({bare_id})"
    return bare_id


def _agent_alias_lookup(tenant_id) -> dict:
    """`User.agent_login` (uuid FusionPBX CC-Agent, cf.
    `_known_agent_logins_for_tenant`) -> {"name": "Prénom Nom", "station":
    station_extension}, pour habiller le monitoring temps réel et le CDR
    d'un identifiant humain plutôt que l'uuid brut. `station_extension` est
    le poste déclaré côté PERMATEL (gestion des utilisateurs), pas une
    valeur dérivée en direct du trafic PBX — reste stable même si l'agent
    n'est pas actuellement enregistré sur son poste."""
    rows = (
        db.session.query(User.agent_login, User.prenom, User.nom, User.station_extension)
        .join(TenantUser, TenantUser.user_id == User.id)
        .filter(
            TenantUser.tenant_id == tenant_id,
            User.agent_login.isnot(None),
        )
        .distinct()
        .all()
    )
    return {
        login: {"name": f"{prenom} {nom}".strip(), "station": station}
        for login, prenom, nom, station in rows
        if login
    }


def _live_station_agent_lookup(tenant_id) -> dict:
    """`agent_station_extension` -> `agent_uuid` du plus récent événement
    `CALLCENTER_AGENT_STATE_CHANGE` connu pour ce poste, tous agents/files
    confondus — sert à retrouver l'identité d'un agent sur un appel qui ne
    porte lui-même AUCUN contexte CC-Agent (ex. appel direct/sortant hors
    file, un poste qui compose un code fonction), à partir de son dernier
    login connu sur ce poste (`m["caller"]`/`m["callee"]` matché contre les
    clés retournées).

    Contrairement à `User.station_extension` (déclaratif, statique côté
    gestion des utilisateurs), cette table suit les changements de poste
    sans intervention admin : si l'agent A se délogue du poste X puis
    l'agent B s'y logue, elle reflète B dès que son événement de login est
    arrivé — jamais A par erreur après coup (c'est précisément la limite du
    reverse-match par poste STATIQUE écartée en faveur de celui-ci, cf.
    discussion du 31/07). Reste un best-effort : dans la brève fenêtre entre
    l'appel de B et l'arrivée de son propre événement de présence, cette
    table peut encore pointer vers A ou rester vide."""
    latest_ts = (
        db.session.query(
            TelephonyEvent.agent_station_extension,
            db.func.max(TelephonyEvent.created_at).label("max_created_at"),
        )
        .filter(
            TelephonyEvent.tenant_id == tenant_id,
            TelephonyEvent.event_type == "CALLCENTER_AGENT_STATE_CHANGE",
            TelephonyEvent.agent_station_extension.isnot(None),
        )
        .group_by(TelephonyEvent.agent_station_extension)
        .subquery()
    )
    latest_events = (
        TelephonyEvent.query
        .join(
            latest_ts,
            db.and_(
                TelephonyEvent.agent_station_extension == latest_ts.c.agent_station_extension,
                TelephonyEvent.created_at == latest_ts.c.max_created_at,
            ),
        )
        .filter(TelephonyEvent.tenant_id == tenant_id)
        .all()
    )
    return {
        e.agent_station_extension: e.agent_uuid
        for e in latest_events
        if e.agent_uuid
    }


@telephony_bp.get("/kpis/queues")
@tenant_required
def kpis_queues():
    """Appels par file d'attente, temps d'attente moyen, taux d'abandon —
    uniquement les files avec activité sur la période (pas de file "sans
    file" : un appel sans `queue_id` n'est pas du trafic de file d'attente),
    triées par volume décroissant (file la plus active en premier)."""
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
        queue_id = next((e.queue_id for e in call_events if e.queue_id), None)
        if not queue_id:
            continue  # pas de file d'attente associée à cet appel
        bucket = per_queue.setdefault(queue_id, {"total": 0, "abandoned": 0, "wait_times": []})
        bucket["total"] += 1
        if terminal.call_status == "abandoned":
            bucket["abandoned"] += 1
        answered = next((e for e in call_events if e.call_status == "answered"), None)
        if answered:
            bucket["wait_times"].append((answered.created_at - call_events[0].created_at).total_seconds())

    alias_lookup = _queue_alias_lookup(g.tenant_id)
    result = []
    for queue_id, bucket in per_queue.items():
        wait_times = bucket["wait_times"]
        result.append({
            "queue_id": queue_id,
            "alias": alias_lookup.get(queue_id, queue_id),
            "total_calls": bucket["total"],
            "abandoned_calls": bucket["abandoned"],
            "abandon_rate_pct": round(bucket["abandoned"] / bucket["total"] * 100, 1) if bucket["total"] else 0,
            "avg_wait_seconds": round(sum(wait_times) / len(wait_times), 1) if wait_times else None,
        })
    result.sort(key=lambda q: q["total_calls"], reverse=True)

    return jsonify({
        "period": {"from": _iso_utc(dt_from), "to": _iso_utc(dt_to)},
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
        "period": {"from": _iso_utc(dt_from), "to": _iso_utc(dt_to)},
        "agents": result,
    }), 200


# Statuts bruts mod_callcenter (CC-Agent-Status) connus, normalisés en
# présence disponible/pause/hors-ligne. Tout statut absent ou non reconnu
# retombe sur "offline" — on ne fabrique jamais un état "disponible" par
# défaut à partir de données incertaines.
#
# Ce statut est un TOGGLE MANUEL (Available/On Break/Logged Out) — confirmé
# sur trafic réel (29/07) qu'il ne change PAS pendant un appel (pas de
# transition live Waiting/Receiving/In a queue call observée, cf.
# connector/tests/test_esl_adapter_callcenter.py). D'où la 4e valeur
# "on_call", calculée à part dans agents_status() à partir des appels
# réellement ouverts (_agents_currently_on_call) et prioritaire sur ce
# statut manuel — volontairement grossier (ne distingue pas sonne/en
# communication, cf. discussion du 31/07).
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
    événement `CALLCENTER_AGENT_STATE_CHANGE` connu par `agent_uuid` —
    seuls les agents ayant émis au moins un tel événement apparaissent (pas
    de roster fabriqué). Croisé avec le volume d'appels traités sur la
    période (même règle que /kpis/agents) : `calls_handled` est un compte
    d'appels, pas un taux d'occupation — aucune durée continue disponible/
    occupée n'est suivie aujourd'hui.

    Jointure sur `agent_uuid` (pas `agent_login`, cf. audit du 30/07) : les
    événements de présence live (`CALLCENTER_AGENT_STATE_CHANGE`) et les
    événements CDR (volume d'appels) n'utilisaient pas le même vocabulaire
    dans `agent_login` (uuid vs extension) — `calls_handled` ne recoupait
    donc jamais rien. `agent_uuid` est peuplé sur les deux canaux.

    `presence` peut valoir "on_call" en plus de online/away/offline (audit
    31/07) : le statut manuel mod_callcenter ne change pas pendant un appel
    (dialing/ringing/in-call), donc "on_call" est dérivé à part, à partir
    des appels réellement ouverts pour cet `agent_uuid` (voir
    `_agents_currently_on_call`), et prioritaire sur le statut manuel.
    """
    dt_from, dt_to = _parse_period()

    latest_ts = (
        db.session.query(
            TelephonyEvent.agent_uuid,
            db.func.max(TelephonyEvent.created_at).label("max_created_at"),
        )
        .filter(
            TelephonyEvent.tenant_id == g.tenant_id,
            TelephonyEvent.event_type == "CALLCENTER_AGENT_STATE_CHANGE",
            TelephonyEvent.agent_uuid.isnot(None),
        )
        .group_by(TelephonyEvent.agent_uuid)
        .subquery()
    )
    latest_events = (
        TelephonyEvent.query
        .join(
            latest_ts,
            db.and_(
                TelephonyEvent.agent_uuid == latest_ts.c.agent_uuid,
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
            TelephonyEvent.agent_uuid.isnot(None),
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
        agent_uuid = next((e.agent_uuid for e in call_events if e.agent_uuid), None)
        if not agent_uuid:
            continue
        answered = next((e for e in call_events if e.call_status == "answered"), None)
        if answered:
            calls_handled[agent_uuid] = calls_handled.get(agent_uuid, 0) + 1

    alias_lookup = _agent_alias_lookup(g.tenant_id)
    on_call_uuids = _agents_currently_on_call(g.tenant_id)
    agents = sorted(
        (
            {
                "agent_login": e.agent_login,
                "agent_uuid": e.agent_uuid,
                "agent_name": alias_lookup.get(e.agent_uuid, {}).get("name", e.agent_uuid),
                # Poste observé en direct sur ce dernier événement de
                # présence, prioritaire sur le poste statique déclaré.
                "agent_station": e.agent_station_extension or alias_lookup.get(e.agent_uuid, {}).get("station"),
                "presence": "on_call" if e.agent_uuid in on_call_uuids else _normalize_agent_presence(e.agent_status),
                "raw_status": e.agent_status,
                "last_seen_at": _iso_utc(e.created_at),
                "calls_handled": calls_handled.get(e.agent_uuid, 0),
            }
            for e in latest_events
        ),
        key=lambda a: a["agent_uuid"],
    )

    return jsonify({
        "period": {"from": _iso_utc(dt_from), "to": _iso_utc(dt_to)},
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
    now = utcnow()

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
        # Filtre reçu du frontend sous 'agent_login' (nom de paramètre
        # historique) — accepte indifféremment une valeur uuid ou extension,
        # les deux vocabulaires ayant coexisté dans agent_login par le passé.
        query = query.filter(db.or_(
            TelephonyEvent.agent_login == filters["agent_login"],
            TelephonyEvent.agent_uuid == filters["agent_login"],
        ))
    if filters.get("queue_id"):
        query = query.filter(TelephonyEvent.queue_id == filters["queue_id"])

    by_call = {}
    for e in query.all():
        by_call.setdefault(e.call_uuid, []).append(e)

    alias_lookup = _agent_alias_lookup(g.tenant_id)
    rows_by_uuid = {}
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
        agent_uuid = next((e.agent_uuid for e in call_events if e.agent_uuid), None)
        agent_station_extension = next(
            (e.agent_station_extension for e in call_events if e.agent_station_extension), None,
        )
        queue_id = next((e.queue_id for e in call_events if e.queue_id), None)
        recording_url = next((e.recording_url for e in call_events if e.recording_url), None)
        linked_call_uuid = next((e.linked_call_uuid for e in call_events if e.linked_call_uuid), None)

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

        agent_alias = alias_lookup.get(agent_uuid) if agent_uuid else None
        rows_by_uuid[call_uuid] = {
            "call_uuid": call_uuid,
            "caller": caller,
            "callee": callee,
            "direction": direction,
            "agent_login": agent_login,
            "agent_uuid": agent_uuid,
            "agent_name": agent_alias["name"] if agent_alias else (agent_login or agent_uuid),
            # Poste observé en direct sur cet appel prioritaire sur le poste
            # statique déclaré côté gestion des utilisateurs.
            "agent_station": agent_station_extension or (agent_alias["station"] if agent_alias else None),
            "queue_id": queue_id,
            "call_status": terminal.call_status,
            "duration": terminal.duration,
            "started_at": _iso_utc(first.created_at),
            "ended_at": _iso_utc(terminal.created_at),
            "recording_url": recording_url,
            "recording_available": bool(recording_url) and urlparse(recording_url).scheme in ("http", "https"),
            "_linked_call_uuid": linked_call_uuid,
            "_direction_raw": direction,
        }

    # Fusion des legs d'un appel bridgé — même règle que /active-calls :
    # Other-Leg-Unique-ID (fiable une fois le pont établi) relie les deux
    # call_uuid d'un même appel physique ; on ne garde que le leg "inbound",
    # qui porte le numéro humainement lisible.
    for call_uuid, row in list(rows_by_uuid.items()):
        linked = row["_linked_call_uuid"]
        if linked and linked in rows_by_uuid and row["_direction_raw"] == "outbound":
            rows_by_uuid.pop(call_uuid, None)

    rows = []
    for row in rows_by_uuid.values():
        row.pop("_linked_call_uuid", None)
        row.pop("_direction_raw", None)
        rows.append(row)

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
    # CDR = uniquement le nom d'agent lisible + son poste PERMATEL déclaré
    # (station_extension) — jamais l'uuid CC-Agent brut, illisible pour un
    # export destiné à être lu/partagé tel quel.
    writer.writerow([
        "call_uuid", "started_at", "ended_at", "caller", "callee", "direction",
        "agent_name", "station", "queue_id", "call_status", "duration_seconds",
    ])
    for r in rows:
        writer.writerow([
            r["call_uuid"], r["started_at"], r["ended_at"], r["caller"], r["callee"],
            r["direction"], r["agent_name"], r["agent_station"], r["queue_id"], r["call_status"], r["duration"],
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


def _normalize_queue_ids(raw):
    """
    `queue_ids` : liste de `{"id": "8001", "alias": "Support"}` — un alias
    est un libellé d'affichage PERMATEL, jamais transmis à FreeSWITCH
    (seul `id` sert dans `api callcenter_config agent list <id>@<domaine>`,
    cf. ESLAdapter). Compatible avec l'ancien format (liste de chaînes) pour
    les domaines déjà enregistrés avant ce champ.

    Retourne `None` si `raw` n'est pas une liste (erreur 400 à lever par
    l'appelant), sinon une liste nettoyée (entrées sans `id` écartées).
    """
    if not isinstance(raw, list):
        return None
    cleaned = []
    for item in raw:
        if isinstance(item, dict):
            queue_id = str(item.get("id") or "").strip()
            alias = str(item.get("alias") or "").strip()
        else:
            queue_id = str(item or "").strip()
            alias = ""
        if queue_id:
            cleaned.append({"id": queue_id, "alias": alias})
    return cleaned


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
    connector.sync_requested_at = utcnow()
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

    queue_ids = _normalize_queue_ids(data.get("queue_ids") or [])
    if queue_ids is None:
        return jsonify({"error": "'queue_ids' doit être une liste."}), 400

    domain = PbxConnectorDomain(
        pbx_connector_id=connector_id,
        pbx_domain=pbx_domain,
        queue_ids=queue_ids,
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
    queue_ids = _normalize_queue_ids(data.get("queue_ids"))
    if queue_ids is None:
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
