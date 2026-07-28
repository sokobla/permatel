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

    # Autre action mod_callcenter non mappée à ce jour (ex. bridge-agent-start) :
    # ignorée plutôt que forcée dans un type approximatif.
    return None
