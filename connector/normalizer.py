# -*- coding: utf-8 -*-
"""
Normalisation événements FreeSWITCH (ESL) -> format d'ingestion PERMATEL.

Vocabulaire cible (voir backend/app/models/telephony_event.py) :
  event_type    : CHANNEL_CREATE | CHANNEL_PROGRESS_MEDIA | CHANNEL_ANSWER
                  | CHANNEL_HANGUP_COMPLETE | CALLCENTER_QUEUE_ENTER
                  | CALLCENTER_AGENT_STATE_CHANGE
  call_direction: inbound | outbound
  call_status   : ringing | early_media | answered | missed | abandoned
                  | technical_failure | on_hold | ended

Événements FreeSWITCH bruts pris en charge (souscrits par ESLAdapter) :
  CHANNEL_CREATE, CHANNEL_PROGRESS_MEDIA, CHANNEL_ANSWER,
  CHANNEL_HANGUP_COMPLETE, et l'événement CUSTOM `callcenter::info`
  (mod_callcenter — files d'attente).

⚠️ Les noms d'en-têtes `CC-*` de mod_callcenter (CC-Action, CC-Queue,
CC-Member-Uuid, CC-Agent) sont ceux documentés par FreeSWITCH/FusionPBX au
moment de l'écriture — à valider/ajuster contre un flux d'événements réel
(accès FusionPBX de test disponible) avant mise en production du connecteur.
"""
import re
from datetime import datetime, timezone

# Causes de raccrochage FreeSWITCH indiquant un échec technique (config PBX,
# réseau, codec…) plutôt qu'un comportement d'appel normal.
_TECHNICAL_FAILURE_CAUSES = {
    "NORMAL_TEMPORARY_FAILURE",
    "RECOVERY_ON_TIMER_EXPIRE",
    "DESTINATION_OUT_OF_ORDER",
    "NETWORK_OUT_OF_ORDER",
    "SWITCH_CONGESTION",
    "INCOMPATIBLE_DESTINATION",
}

# Causes indiquant un appel non abouti côté appelé (pas de réponse / rejet).
_MISSED_CAUSES = {"NO_ANSWER", "USER_BUSY", "USER_NOT_REGISTERED", "CALL_REJECTED", "NO_USER_RESPONSE"}

# Confirmé sur trafic réel (30/07) : 'variable_record_file_path' ne se peuple
# JAMAIS (ni sur un appel direct sans enregistrement, ni sur un appel de file
# avec enregistrement confirmé présent sur disque) — variable non fiable.
# Le seul chemin exploitable est celui, déjà résolu par FreeSWITCH, de
# 'variable_execute_on_pre_bridge' porté par l'événement 'bridge-agent-start'
# (ex. "record_session /var/.../<uuid>.wav") — capturé via cette regex.
_RECORD_SESSION_PATH_RE = re.compile(r"record_session\s+(\S+)")


def _extract_recording_path(execute_on_pre_bridge: str | None) -> str | None:
    if not execute_on_pre_bridge:
        return None
    match = _RECORD_SESSION_PATH_RE.search(execute_on_pre_bridge)
    return match.group(1) if match else None


def _fs_timestamp_to_iso(raw_micros) -> str | None:
    """Event-Date-Timestamp FreeSWITCH = microsecondes depuis epoch (string)."""
    if not raw_micros:
        return None
    try:
        return datetime.fromtimestamp(int(raw_micros) / 1_000_000, tz=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def _base_payload(headers: dict, pbx_domain: str, event_type: str) -> dict:
    return {
        "pbx_domain": pbx_domain,
        "event_type": event_type,
        "call": {
            "id": headers.get("Unique-ID"),
            "direction": headers.get("Call-Direction"),
            "caller": headers.get("Caller-Caller-ID-Number"),
            "callee": headers.get("Caller-Destination-Number"),
            "created_at": _fs_timestamp_to_iso(headers.get("Event-Date-Timestamp")),
            # Confirmé en prod (29/07) : vide tant que le pont n'est pas
            # établi (jamais peuplé sur un appel jamais décroché), mais
            # fiable sur CHANNEL_ANSWER/HANGUP d'un pont direct agent<->
            # externe — sert à fusionner les deux legs côté /active-calls.
            "linked_call_uuid": headers.get("Other-Leg-Unique-ID"),
        },
        "agent": {},
        "queue": {},
    }


def normalize_channel_create(headers: dict, pbx_domain: str) -> dict:
    payload = _base_payload(headers, pbx_domain, "CHANNEL_CREATE")
    payload["call"]["status"] = "ringing"
    return payload


def normalize_channel_progress_media(headers: dict, pbx_domain: str) -> dict:
    payload = _base_payload(headers, pbx_domain, "CHANNEL_PROGRESS_MEDIA")
    payload["call"]["status"] = "early_media"
    return payload


def normalize_channel_answer(headers: dict, pbx_domain: str) -> dict:
    payload = _base_payload(headers, pbx_domain, "CHANNEL_ANSWER")
    payload["call"]["status"] = "answered"
    return payload


def normalize_channel_hangup(headers: dict, pbx_domain: str) -> dict:
    payload = _base_payload(headers, pbx_domain, "CHANNEL_HANGUP_COMPLETE")

    cause = (headers.get("Hangup-Cause") or "").upper()
    answered_time = headers.get("Caller-Channel-Answered-Time") or headers.get("variable_answered_time")
    was_answered = bool(answered_time) and answered_time != "0"

    if cause in _TECHNICAL_FAILURE_CAUSES:
        status = "technical_failure"
    elif was_answered:
        status = "ended"
    elif cause in _MISSED_CAUSES:
        status = "missed"
    else:
        # Raccroché avant réponse pour une autre raison (ex. ORIGINATOR_CANCEL
        # côté appelant) : traité comme abandonné plutôt que manqué.
        status = "abandoned"
    payload["call"]["status"] = status

    duration = headers.get("variable_billsec") or headers.get("variable_duration")
    try:
        payload["duration_seconds"] = int(duration) if duration is not None else None
    except (ValueError, TypeError):
        payload["duration_seconds"] = None

    recording_path = headers.get("variable_record_file_path") or headers.get("variable_recording_follow_transfer")
    if recording_path:
        payload["recording_url"] = recording_path

    return payload


def normalize_callcenter_info(headers: dict, pbx_domain: str) -> dict | None:
    """Événement CUSTOM `callcenter::info` (mod_callcenter) — files d'attente."""
    action = headers.get("CC-Action")
    queue_id = headers.get("CC-Queue")
    agent_login = headers.get("CC-Agent")

    if action == "queue-enter":
        payload = _base_payload(headers, pbx_domain, "CALLCENTER_QUEUE_ENTER")
        payload["call"]["id"] = headers.get("CC-Member-Uuid") or payload["call"]["id"]
        payload["call"]["status"] = "ringing"
        payload["queue"]["id"] = queue_id
        return payload

    if action == "agent-state-change":
        payload = _base_payload(headers, pbx_domain, "CALLCENTER_AGENT_STATE_CHANGE")
        payload["call"]["status"] = "on_hold"
        payload["agent"]["login"] = agent_login
        # Statut brut mod_callcenter (ex. "Available", "On Break", "Logged
        # Out") — la route d'ingestion se charge de le normaliser en
        # présence disponible/pause/hors-ligne, on ne fait ici que le
        # relayer tel quel (pas de perte d'information à l'ingestion).
        payload["agent"]["status"] = headers.get("CC-Agent-Status")
        payload["queue"]["id"] = queue_id
        return payload

    # Autre action mod_callcenter non mappée à ce jour : ignorée plutôt que
    # forcée dans un type approximatif ('bridge-agent-start' est routé à part
    # par ESLAdapter, voir normalize_bridge_recording — jamais atteint ici).
    return None


def normalize_member_enrichment(headers: dict, pbx_domain: str, agent_login: str | None) -> dict:
    """Événement callcenter::info de gestion de file ('agent-offering',
    'bridge-agent-start'/'bridge-agent-fail') — sans contexte de canal
    exploitable (pas de 'variable_domain_name'), comme
    'agent-status-change', mais porte des informations différentes :
    `CC-Member-Session-UUID` EST l'Unique-ID du leg entrant déjà en base
    (confirmé en prod 29/07) — pas la peine de le fusionner, il s'agit du
    MÊME appel. On envoie donc un événement qui n'apporte QUE l'agent, la
    file et le vrai numéro composé (`CC-Member-DNIS`, disponible ici alors
    qu'il est réécrit en id de file dès `CHANNEL_PROGRESS_MEDIA`), sans
    statut — pour ne jamais écraser un statut d'appel déjà mieux connu.
    `pbx_domain` et `agent_login` sont résolus EN AMONT par ESLAdapter via
    l'annuaire agents (même mécanisme que `normalize_agent_status_change`).
    """
    return {
        "pbx_domain": pbx_domain,
        "event_type": "CALLCENTER_MEMBER_ENRICHMENT",
        "call": {
            "id": headers.get("CC-Member-Session-UUID"),
            "callee": headers.get("CC-Member-DNIS"),
        },
        "agent": {"login": agent_login} if agent_login else {},
        "queue": {"id": headers.get("CC-Queue")},
    }


def normalize_bridge_recording(headers: dict, pbx_domain: str, agent_login: str | None) -> dict | None:
    """Événement callcenter::info 'bridge-agent-start' — seule source
    confirmée (30/07) du chemin d'enregistrement d'un appel de file :
    `variable_execute_on_pre_bridge`, porté par le LEG AGENT, déjà résolu par
    FreeSWITCH avec l'UUID du leg MEMBRE (`variable_cc_member_session_uuid`,
    == Unique-ID du leg entrant déjà en base) comme nom de fichier. Comme
    `normalize_member_enrichment`, on n'envoie ici QUE l'enregistrement, sans
    statut, pour ne jamais écraser un statut d'appel déjà mieux connu.
    Retourne None si aucun chemin n'a pu être extrait (pas de contenu utile
    à transmettre)."""
    member_session_uuid = headers.get("variable_cc_member_session_uuid") or headers.get("CC-Member-Session-UUID")
    recording_path = _extract_recording_path(headers.get("variable_execute_on_pre_bridge"))
    if not member_session_uuid or not recording_path:
        return None

    return {
        "pbx_domain": pbx_domain,
        "event_type": "CALLCENTER_BRIDGE_RECORDING",
        "call": {"id": member_session_uuid},
        "recording_url": recording_path,
        "agent": {"login": agent_login} if agent_login else {},
        "queue": {"id": headers.get("CC-Queue")},
    }


def normalize_agent_status_change(headers: dict, pbx_domain: str, agent_login: str) -> dict:
    """Changement de statut agent (`CC-Action: agent-status-change`,
    ex. Available/On Break/Logged Out).

    Confirmé sur trafic FusionPBX réel (29/07) : cet événement ne porte
    AUCUN contexte de canal (pas de `Unique-ID`, pas de `variable_domain_name`
    — contrairement aux autres événements callcenter::info comme
    `queue-enter`, qui restent liés à un appel actif). `CC-Agent` s'y est
    aussi révélé être un UUID interne FusionPBX, pas un login exploitable.
    `pbx_domain` et `agent_login` sont donc résolus EN AMONT par
    `ESLAdapter` via l'annuaire construit depuis
    `api callcenter_config agent list <queue>@<domain>` (voir
    `esl_adapter.py::_refresh_agent_directory`), pas extraits des en-têtes
    ici — d'où la signature différente de `normalize_callcenter_info`.
    """
    payload = _base_payload(headers, pbx_domain, "CALLCENTER_AGENT_STATE_CHANGE")
    payload["call"]["status"] = "on_hold"
    payload["agent"]["login"] = agent_login
    payload["agent"]["status"] = headers.get("CC-Agent-Status")
    payload["queue"]["id"] = headers.get("CC-Queue")
    return payload
