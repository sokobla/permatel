# -*- coding: utf-8 -*-
"""
Exécution à distance ESL (13/08) — CoreConnector._on_job_requested() et
_SyncListener._run() (distinction payload JSON job vs entier brut signal
Sync, cf. core_connector.py:96-114).
"""
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core_connector  # noqa: E402


# ── CoreConnector._on_job_requested / _on_sync_requested ───────────────────

def test_on_job_requested_dispatche_vers_l_adapter_du_connecteur_cible():
    connector = core_connector.CoreConnector()
    adapter = MagicMock()
    connector._running_adapters[1] = (adapter, MagicMock())

    connector._on_job_requested({"connector_id": 1, "job_type": "agent_login", "agent_uuid": "a-1"})

    adapter.execute_job.assert_called_once_with(
        {"connector_id": 1, "job_type": "agent_login", "agent_uuid": "a-1"}
    )


def test_on_job_requested_connecteur_non_actif_ici_est_abandonne_sans_exception(caplog):
    connector = core_connector.CoreConnector()

    connector._on_job_requested({"connector_id": 999, "job_type": "agent_login", "agent_uuid": "a-1"})
    # Aucune exception levée, aucun adapter à appeler — comportement attendu.


def test_on_sync_requested_appelle_force_reconnect_de_l_adapter_cible():
    connector = core_connector.CoreConnector()
    adapter = MagicMock()
    connector._running_adapters[1] = (adapter, MagicMock())

    connector._on_sync_requested(1)

    adapter.force_reconnect.assert_called_once()


# ── _SyncListener._run() : distinction JSON (job) vs entier brut (sync) ────

class _StopTestLoop(BaseException):
    """Échappe volontairement le `except Exception` de _run() (boucle
    infinie par conception) pour permettre au test de reprendre la main une
    fois les messages de test consommés."""


def _fake_pubsub(messages):
    class FakePubsub:
        def subscribe(self, channel):
            pass

        def listen(self):
            for m in messages:
                yield m
            raise _StopTestLoop()

    return FakePubsub()


def test_sync_listener_distingue_payload_job_json_et_signal_sync_entier(monkeypatch):
    fake_redis_module = types.ModuleType("redis")
    fake_client = MagicMock()
    fake_client.pubsub.return_value = _fake_pubsub([
        {"type": "subscribe", "data": 1},  # non-'message' — ignoré
        {"type": "message", "data": json.dumps(
            {"connector_id": 1, "job_type": "agent_login", "agent_uuid": "a-1"}
        )},
        {"type": "message", "data": "42"},
    ])
    fake_redis_module.from_url = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "redis", fake_redis_module)
    monkeypatch.setattr(core_connector.config, "REDIS_URL", "redis://fake")

    jobs_received = []
    syncs_received = []
    listener = core_connector._SyncListener(
        on_sync_requested=syncs_received.append,
        on_job_requested=jobs_received.append,
    )

    with pytest.raises(_StopTestLoop):
        listener._run()

    assert jobs_received == [{"connector_id": 1, "job_type": "agent_login", "agent_uuid": "a-1"}]
    assert syncs_received == [42]
