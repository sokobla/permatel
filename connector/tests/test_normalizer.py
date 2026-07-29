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
