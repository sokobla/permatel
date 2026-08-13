# -*- coding: utf-8 -*-
"""
Exécution à distance ESL (13/08) — ESLAdapter.execute_job(),
_emit_pause_code_event() et _on_agent_pause_code_event().

Voir C:\\Users\\Sokobla GAZARO\\.claude\\plans\\glowing-launching-eagle.md
(Phase B) pour le contexte : PERMATEL dispatche des jobs (login/logout/
changement de statut agent) au connecteur via Redis (cf.
core_connector.py::_SyncListener), le connecteur les exécute via des
commandes ESL synchrones (`self._esl.send`, `+OK`/`-ERR` immédiat).
"""
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.esl_adapter import ESLAdapter  # noqa: E402


def _fake_connector_config():
    return {
        "name": "Test PBX", "host": "pbx.local", "port": 8021, "password": "x",
        "domains": [], "known_agent_logins": [],
    }


class _FakeEvent:
    def __init__(self, headers):
        self.headers = headers


class _FakeResponse:
    def __init__(self, data):
        self.data = data


def _connected_adapter():
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    adapter._esl = MagicMock()
    adapter._esl.connected = True
    adapter._esl.send.return_value = _FakeResponse("+OK")
    return adapter, ingest_client


# ── execute_job : les 3 job_type ───────────────────────────────────────────

def test_execute_job_agent_login_met_on_break_et_emet_pause_code_0():
    adapter, _ingest_client = _connected_adapter()

    adapter.execute_job({"job_type": "agent_login", "agent_uuid": "agent-uuid-1"})

    calls = [c.args[0] for c in adapter._esl.send.call_args_list]
    assert calls[0] == "api callcenter_config agent set status agent-uuid-1 'On Break'"
    assert "sendevent CUSTOM" in calls[1]
    assert "Event-Subclass: esl_adapter::agent_pause_code" in calls[1]
    assert "CC-Agent: agent-uuid-1" in calls[1]
    assert "Agent-Pause-Code: 0" in calls[1]


def test_execute_job_agent_logout_met_logged_out():
    adapter, _ingest_client = _connected_adapter()

    adapter.execute_job({"job_type": "agent_logout", "agent_uuid": "agent-uuid-1"})

    adapter._esl.send.assert_called_once_with(
        "api callcenter_config agent set status agent-uuid-1 'Logged Out'"
    )


def test_execute_job_agent_status_change_vers_available_pas_de_pause_code():
    adapter, _ingest_client = _connected_adapter()

    adapter.execute_job({
        "job_type": "agent_status_change", "agent_uuid": "agent-uuid-1",
        "target_status": "Available",
    })

    adapter._esl.send.assert_called_once_with(
        "api callcenter_config agent set status agent-uuid-1 'Available'"
    )


def test_execute_job_agent_status_change_vers_on_break_emet_pause_code_choisi():
    adapter, _ingest_client = _connected_adapter()

    adapter.execute_job({
        "job_type": "agent_status_change", "agent_uuid": "agent-uuid-1",
        "target_status": "On Break", "pause_code": "3",
    })

    calls = [c.args[0] for c in adapter._esl.send.call_args_list]
    assert calls[0] == "api callcenter_config agent set status agent-uuid-1 'On Break'"
    assert "Agent-Pause-Code: 3" in calls[1]


def test_execute_job_status_invalide_abandonne_sans_appel_esl(caplog):
    adapter, _ingest_client = _connected_adapter()

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter.execute_job({
            "job_type": "agent_status_change", "agent_uuid": "agent-uuid-1",
            "target_status": "Bogus",
        })

    adapter._esl.send.assert_not_called()


def test_execute_job_type_inconnu_journalise_sans_exception(caplog):
    adapter, _ingest_client = _connected_adapter()

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter.execute_job({"job_type": "bogus", "agent_uuid": "agent-uuid-1"})

    adapter._esl.send.assert_not_called()


def test_execute_job_sans_agent_uuid_abandonne(caplog):
    adapter, _ingest_client = _connected_adapter()

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter.execute_job({"job_type": "agent_login"})

    adapter._esl.send.assert_not_called()


def test_execute_job_non_connecte_abandonne(caplog):
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    adapter._esl = None  # is_connected -> False

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter.execute_job({"job_type": "agent_login", "agent_uuid": "agent-uuid-1"})

    # Rien à asserter sur _esl.send (jamais créé) — l'absence d'exception suffit.


# ── _on_agent_pause_code_event : réception en retour de l'événement CUSTOM ─

def test_on_agent_pause_code_event_resout_via_annuaire_et_transmet():
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    adapter._agent_directory = {
        "agent-uuid-1": {"domain": "tenant.pbx.local", "extension": "1005"},
    }
    headers = {"CC-Agent": "agent-uuid-1", "Agent-Pause-Code": "2"}

    adapter._on_agent_pause_code_event(_FakeEvent(headers))

    ingest_client.send.assert_called_once()
    payload = ingest_client.send.call_args[0][0]
    assert payload["event_type"] == "CALLCENTER_AGENT_PAUSE_CODE"
    assert payload["pbx_domain"] == "tenant.pbx.local"
    assert payload["agent"]["login"] == "agent-uuid-1"
    assert payload["agent"]["pause_code"] == "2"


def test_on_agent_pause_code_event_agent_absent_de_l_annuaire_est_journalise(caplog):
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    headers = {"CC-Agent": "uuid-inconnu", "Agent-Pause-Code": "0"}

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_agent_pause_code_event(_FakeEvent(headers))

    ingest_client.send.assert_not_called()
    assert any("uuid-inconnu" in r.message for r in caplog.records)
