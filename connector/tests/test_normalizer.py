# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import normalizer  # noqa: E402


def _headers(**overrides):
    base = {
        "Unique-ID": "chan-uuid-1",
        "Call-Direction": "inbound",
        "Caller-Caller-ID-Number": "0612345678",
        "Caller-Destination-Number": "0522456789",
        "Event-Date-Timestamp": "1732000000000000",
    }
    base.update(overrides)
    return base


def test_channel_create_maps_to_ringing():
    payload = normalizer.normalize_channel_create(_headers(), "tenant-a.pbx.local")
    assert payload["event_type"] == "CHANNEL_CREATE"
    assert payload["call"]["status"] == "ringing"
    assert payload["call"]["id"] == "chan-uuid-1"
    assert payload["pbx_domain"] == "tenant-a.pbx.local"


def test_channel_progress_media_maps_to_early_media():
    payload = normalizer.normalize_channel_progress_media(_headers(), "d")
    assert payload["call"]["status"] == "early_media"


def test_channel_answer_maps_to_answered():
    payload = normalizer.normalize_channel_answer(_headers(), "d")
    assert payload["event_type"] == "CHANNEL_ANSWER"
    assert payload["call"]["status"] == "answered"


def test_hangup_after_answer_maps_to_ended():
    headers = _headers(
        **{
            "Hangup-Cause": "NORMAL_CLEARING",
            "Caller-Channel-Answered-Time": "1732000005000000",
            "variable_billsec": "42",
        }
    )
    payload = normalizer.normalize_channel_hangup(headers, "d")
    assert payload["call"]["status"] == "ended"
    assert payload["duration_seconds"] == 42


def test_hangup_no_answer_maps_to_missed():
    headers = _headers(**{"Hangup-Cause": "NO_ANSWER", "Caller-Channel-Answered-Time": "0"})
    payload = normalizer.normalize_channel_hangup(headers, "d")
    assert payload["call"]["status"] == "missed"


def test_hangup_technical_failure_cause():
    headers = _headers(**{"Hangup-Cause": "SWITCH_CONGESTION", "Caller-Channel-Answered-Time": "0"})
    payload = normalizer.normalize_channel_hangup(headers, "d")
    assert payload["call"]["status"] == "technical_failure"


def test_hangup_cancelled_before_answer_maps_to_abandoned():
    headers = _headers(**{"Hangup-Cause": "ORIGINATOR_CANCEL", "Caller-Channel-Answered-Time": "0"})
    payload = normalizer.normalize_channel_hangup(headers, "d")
    assert payload["call"]["status"] == "abandoned"


def test_callcenter_queue_enter():
    headers = _headers(**{"CC-Action": "queue-enter", "CC-Queue": "queue-support", "CC-Member-Uuid": "mem-1"})
    payload = normalizer.normalize_callcenter_info(headers, "d")
    assert payload["event_type"] == "CALLCENTER_QUEUE_ENTER"
    assert payload["queue"]["id"] == "queue-support"
    assert payload["call"]["id"] == "mem-1"


def test_callcenter_agent_state_change():
    headers = _headers(**{"CC-Action": "agent-state-change", "CC-Queue": "queue-support", "CC-Agent": "agent01"})
    payload = normalizer.normalize_callcenter_info(headers, "d")
    assert payload["event_type"] == "CALLCENTER_AGENT_STATE_CHANGE"
    assert payload["agent"]["login"] == "agent01"


def test_callcenter_unmapped_action_returns_none():
    headers = _headers(**{"CC-Action": "bridge-agent-start", "CC-Queue": "queue-support"})
    assert normalizer.normalize_callcenter_info(headers, "d") is None


def test_channel_answer_capte_le_leg_lie_une_fois_le_pont_etabli():
    """Confirmé en prod (29/07) : Other-Leg-Unique-ID est vide tant que le
    pont n'est pas établi (jamais peuplé sur un appel jamais décroché), mais
    fiable sur CHANNEL_ANSWER d'un pont direct agent<->externe."""
    headers = _headers(**{"Other-Leg-Unique-ID": "chan-uuid-2"})
    payload = normalizer.normalize_channel_answer(headers, "d")
    assert payload["call"]["linked_call_uuid"] == "chan-uuid-2"


def test_channel_answer_sans_pont_etabli_linked_call_uuid_absent():
    payload = normalizer.normalize_channel_answer(_headers(), "d")
    assert payload["call"]["linked_call_uuid"] is None


def test_normalize_member_enrichment_utilise_champs_reels_confirmes():
    """Confirmé en prod (29/07) sur l'événement callcenter::info
    'agent-offering' : CC-Member-Session-UUID == Unique-ID du leg entrant
    déjà en base (pas un nouvel appel), CC-Member-DNIS porte le vrai numéro
    composé (jamais réécrit, contrairement à Caller-Destination-Number)."""
    headers = _headers(**{
        "CC-Action": "agent-offering", "CC-Queue": "8004@africallpbx.fusion.cloud228.com",
        "CC-Agent": "fd18b0f6-47f3-4fe2-8e85-fe36ca077b79",
        "CC-Member-Session-UUID": "0200801b-3e1f-422c-9335-7fac4f4cc867",
        "CC-Member-DNIS": "33186569392",
    })
    payload = normalizer.normalize_member_enrichment(headers, "africallpbx.fusion.cloud228.com", "22101010")
    assert payload["event_type"] == "CALLCENTER_MEMBER_ENRICHMENT"
    assert payload["call"]["id"] == "0200801b-3e1f-422c-9335-7fac4f4cc867"
    assert payload["call"]["callee"] == "33186569392"
    assert payload["agent"]["login"] == "22101010"
    assert payload["queue"]["id"] == "8004@africallpbx.fusion.cloud228.com"
    assert "status" not in payload["call"]  # ne doit jamais écraser un statut déjà connu


def test_normalize_member_enrichment_sans_agent_login_resolu():
    headers = _headers(**{
        "CC-Action": "agent-offering", "CC-Queue": "8004@d",
        "CC-Member-Session-UUID": "member-uuid-1", "CC-Member-DNIS": "0102030405",
    })
    payload = normalizer.normalize_member_enrichment(headers, "d", None)
    assert payload["agent"] == {}


def test_normalize_bridge_recording_extrait_le_chemin_de_execute_on_pre_bridge():
    """Confirmé en prod (30/07) : 'variable_record_file_path' ne se peuple
    JAMAIS (même sur un appel de file dont l'enregistrement existe bien sur
    disque) — seul 'variable_execute_on_pre_bridge' (leg agent) porte le
    chemin, déjà résolu par FreeSWITCH avec l'UUID du leg MEMBRE
    (variable_cc_member_session_uuid) comme nom de fichier."""
    headers = _headers(**{
        "CC-Action": "bridge-agent-start", "CC-Queue": "8004@africallpbx.fusion.cloud228.com",
        "CC-Agent": "e8a58298-87e7-4960-a222-d05763866b15",
        "variable_cc_member_session_uuid": "c0fdb4be-a5dd-453c-b456-b84067242923",
        "variable_execute_on_pre_bridge": (
            "record_session /var/lib/freeswitch/recordings/africallpbx.fusion.cloud228.com/"
            "archive/2026/Jul/30/c0fdb4be-a5dd-453c-b456-b84067242923.wav"
        ),
    })
    payload = normalizer.normalize_bridge_recording(headers, "africallpbx.fusion.cloud228.com", "22101001")
    assert payload["event_type"] == "CALLCENTER_BRIDGE_RECORDING"
    assert payload["call"]["id"] == "c0fdb4be-a5dd-453c-b456-b84067242923"
    assert payload["recording_url"] == (
        "/var/lib/freeswitch/recordings/africallpbx.fusion.cloud228.com/"
        "archive/2026/Jul/30/c0fdb4be-a5dd-453c-b456-b84067242923.wav"
    )
    assert payload["agent"]["login"] == "22101001"
    assert payload["queue"]["id"] == "8004@africallpbx.fusion.cloud228.com"
    assert "status" not in payload["call"]  # ne doit jamais écraser un statut déjà connu


def test_normalize_bridge_recording_sans_member_session_uuid_retourne_none():
    headers = _headers(**{
        "CC-Action": "bridge-agent-start",
        "variable_execute_on_pre_bridge": "record_session /var/x.wav",
    })
    assert normalizer.normalize_bridge_recording(headers, "d", "22101001") is None


def test_normalize_bridge_recording_sans_chemin_retourne_none():
    headers = _headers(**{
        "CC-Action": "bridge-agent-start",
        "variable_cc_member_session_uuid": "member-uuid-1",
    })
    assert normalizer.normalize_bridge_recording(headers, "d", "22101001") is None


def test_normalize_agent_status_change_utilise_domaine_et_login_fournis():
    """Domaine et login ne viennent PAS des en-têtes (confirmé absents sur
    trafic réel) mais des paramètres, résolus en amont par ESLAdapter via
    l'annuaire agents."""
    headers = _headers(**{
        "CC-Action": "agent-status-change", "CC-Agent": "e8a58298-87e7-4960-a222-d05763866b15",
        "CC-Agent-Status": "Available", "CC-Queue": "8004@africallpbx.fusion.cloud228.com",
    })
    payload = normalizer.normalize_agent_status_change(headers, "africallpbx.fusion.cloud228.com", "22101005")
    assert payload["event_type"] == "CALLCENTER_AGENT_STATE_CHANGE"
    assert payload["pbx_domain"] == "africallpbx.fusion.cloud228.com"
    assert payload["agent"]["login"] == "22101005"
    assert payload["agent"]["status"] == "Available"
    assert payload["queue"]["id"] == "8004@africallpbx.fusion.cloud228.com"


def test_normalize_agent_status_change_transmet_uuid_et_station_a_part():
    """Audit du 30/07 : `agent.login` reste l'uuid (identité stable), mais
    `agent.uuid` (même valeur, explicite) et `agent.station` (extension
    observée en direct dans l'annuaire ESL) sont désormais transmis à part —
    PERMATEL en a besoin pour joindre les événements CDR/live entre eux et
    afficher un poste à jour sans dépendre uniquement de la config statique."""
    headers = _headers(**{
        "CC-Action": "agent-status-change", "CC-Agent": "e8a58298-87e7-4960-a222-d05763866b15",
        "CC-Agent-Status": "Available", "CC-Queue": "8004@africallpbx.fusion.cloud228.com",
    })
    payload = normalizer.normalize_agent_status_change(
        headers, "africallpbx.fusion.cloud228.com", "e8a58298-87e7-4960-a222-d05763866b15", "22101005",
    )
    assert payload["agent"]["login"] == "e8a58298-87e7-4960-a222-d05763866b15"
    assert payload["agent"]["uuid"] == "e8a58298-87e7-4960-a222-d05763866b15"
    assert payload["agent"]["station"] == "22101005"


def test_normalize_agent_status_change_sans_station_connue_vaut_none():
    headers = _headers(**{
        "CC-Action": "agent-status-change", "CC-Agent": "uuid-x", "CC-Agent-Status": "Available",
    })
    payload = normalizer.normalize_agent_status_change(headers, "d", "uuid-x")
    assert payload["agent"]["station"] is None
