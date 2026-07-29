# -*- coding: utf-8 -*-
"""
_on_callcenter_info() ne doit jamais perdre silencieusement un événement
CUSTOM callcenter::info dont le CC-Action n'est pas encore reconnu par
normalize_callcenter_info() (aujourd'hui : seuls 'queue-enter' et
'agent-state-change' le sont) — un tel événement doit être journalisé avec
ses en-têtes complets, pour repérer une action manquante (ex. un éventuel
'agent-status-change' distinct pour les changements de statut manuels
Available/On Break/Logged Out) plutôt que de le perdre sans trace.
"""
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.esl_adapter import ESLAdapter  # noqa: E402


def _fake_connector_config(domains=None):
    return {
        "name": "Test PBX", "host": "pbx.local", "port": 8021, "password": "x",
        "domains": domains or [],
    }


class _FakeEvent:
    def __init__(self, headers):
        self.headers = headers


def test_callcenter_info_action_reconnue_est_transmise():
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    headers = {
        "variable_domain_name": "tenant.pbx.local",
        "CC-Action": "agent-state-change",
        "CC-Queue": "queue-support",
        "CC-Agent": "agent01",
    }

    adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_called_once()

def test_callcenter_info_action_non_reconnue_est_journalisee_pas_perdue(caplog):
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    headers = {
        "variable_domain_name": "tenant.pbx.local",
        "CC-Action": "agent-status-change",  # non reconnue par normalize_callcenter_info()
        "CC-Queue": "queue-support",
        "CC-Agent": "agent01",
        "CC-Agent-Status": "Available",
    }

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_not_called()
    assert any("agent-status-change" in record.message for record in caplog.records)


def test_callcenter_info_sans_domaine_est_journalise_pas_perdu(caplog):
    """Pas de variable_domain_name : l'événement est abandonné (comme avant),
    mais désormais journalisé avant abandon — test réel du 29/07 où AUCUNE
    trace 'callcenter'/'agent'/'CC-Action' n'apparaissait dans les logs,
    suggérant un abandon avant même d'atteindre le diagnostic précédent
    (qui ne loguait qu'après le filtre de domaine)."""
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    headers = {"CC-Action": "agent-status-change"}

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_not_called()
    assert any("callcenter::info reçu" in r.message for r in caplog.records)
    assert any("variable_domain_name" in r.message for r in caplog.records)
