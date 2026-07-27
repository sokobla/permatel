# -*- coding: utf-8 -*-
"""
Régression : force_reconnect()/stop() ne doivent jamais appeler
ESLProtocol.stop() directement (bloquant, sans timeout, sur l'envoi 'exit')
— seule la propre greenlet de run() (via _hard_disconnect) doit toucher la
socket, pour éviter le double-stop concurrent qui a bloqué le connecteur en
production (deux "Reconnexion forcée (Sync)" sans jamais reconnecter).
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import gevent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.esl_adapter import ESLAdapter  # noqa: E402


def _fake_connector_config():
    return {"name": "Test PBX", "host": "pbx.local", "port": 8021, "password": "x", "domains": []}


def test_force_reconnect_never_calls_blocking_esl_stop(monkeypatch):
    """`esl.stop()` (greenswitch, bloquant sans timeout) ne doit jamais être
    appelé par force_reconnect() lui-même — seul _hard_disconnect() (fermeture
    directe de la socket, non bloquante) doit toucher la connexion."""
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=MagicMock())

    fake_esl = MagicMock()
    fake_esl.sock = MagicMock()
    fake_esl.connected = True
    adapter._esl = fake_esl

    adapter.force_reconnect()

    fake_esl.stop.assert_not_called()
    assert adapter._disconnect_event.is_set()


def test_stop_never_calls_blocking_esl_stop():
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=MagicMock())
    fake_esl = MagicMock()
    fake_esl.sock = MagicMock()
    adapter._esl = fake_esl

    adapter.stop()

    fake_esl.stop.assert_not_called()
    assert adapter._stopping is True
    assert adapter._disconnect_event.is_set()


def test_hard_disconnect_closes_socket_directly_and_clears_esl():
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=MagicMock())
    fake_esl = MagicMock()
    fake_esl.sock = MagicMock()
    adapter._esl = fake_esl

    adapter._hard_disconnect()

    fake_esl.sock.close.assert_called_once()
    assert fake_esl._run is False
    assert adapter._esl is None


def test_hard_disconnect_is_noop_when_no_connection():
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=MagicMock())
    adapter._hard_disconnect()  # ne doit pas lever
    assert adapter._esl is None


def test_concurrent_force_reconnect_calls_do_not_hang():
    """Reproduit le scénario production : deux appels concurrents à
    force_reconnect() (ex. réconciliation périodique + listener Redis) sur
    le même adapter ne doivent jamais bloquer indéfiniment."""
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=MagicMock())
    fake_esl = MagicMock()
    fake_esl.sock = MagicMock()
    adapter._esl = fake_esl

    with gevent.Timeout(2, TimeoutError("force_reconnect() concurrent a bloqué")):
        g1 = gevent.spawn(adapter.force_reconnect)
        g2 = gevent.spawn(adapter.force_reconnect)
        gevent.joinall([g1, g2])

    fake_esl.stop.assert_not_called()
