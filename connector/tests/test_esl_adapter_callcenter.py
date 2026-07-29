# -*- coding: utf-8 -*-
"""
_on_callcenter_info() et l'annuaire agents (_refresh_agent_directory).

Confirmé sur trafic FusionPBX réel (29/07) :
  - 'queue-enter' reste lié à un canal d'appel actif (porte
    'variable_domain_name') — chemin inchangé.
  - 'agent-status-change' (le vrai événement de transition manuelle
    Available/On Break/Logged Out — PAS 'agent-state-change', jamais
    observé) et 'agent-status-get' (lecture passive) ne portent NI domaine
    NI identifiant exploitable : 'CC-Agent' y est un UUID interne
    FusionPBX, pas une extension. Résolus via un annuaire construit par
    `api callcenter_config agent list` (SANS scope par file — confirmé en
    prod que 'agent list <queue>@<domain>' ne filtre jamais rien).
"""
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.esl_adapter import ESLAdapter  # noqa: E402


def _fake_connector_config(domains=None, known_agent_logins=None):
    return {
        "name": "Test PBX", "host": "pbx.local", "port": 8021, "password": "x",
        "domains": domains or [], "known_agent_logins": known_agent_logins or [],
    }


class _FakeEvent:
    def __init__(self, headers):
        self.headers = headers


class _FakeResponse:
    def __init__(self, data):
        self.data = data


# ── _on_callcenter_info : chemin 'queue-enter' (inchangé, lié à un canal) ──

def test_callcenter_info_queue_enter_est_transmis():
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    headers = {
        "variable_domain_name": "tenant.pbx.local",
        "CC-Action": "queue-enter",
        "CC-Queue": "queue-support",
        "CC-Member-Uuid": "mem-1",
    }

    adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_called_once()


def test_callcenter_info_action_non_reconnue_est_journalisee_pas_perdue(caplog):
    """Une CC-Action liée à un canal (donc avec variable_domain_name) mais
    non mappée par normalize_callcenter_info() (ex. bridge-agent-start) doit
    être journalisée, pas silencieusement perdue."""
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    headers = {
        "variable_domain_name": "tenant.pbx.local",
        "CC-Action": "bridge-agent-start",
        "CC-Queue": "queue-support",
    }

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_not_called()
    assert any("bridge-agent-start" in record.message for record in caplog.records)


def test_callcenter_info_sans_domaine_est_journalise_pas_perdu(caplog):
    """CC-Action liée à un canal mais sans variable_domain_name (config PBX
    incomplète) : abandonné, mais journalisé avant abandon."""
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    headers = {"CC-Action": "queue-enter"}

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_not_called()
    assert any("variable_domain_name" in r.message for r in caplog.records)


# ── _on_callcenter_info : chemin agent-status-change/-get (annuaire) ──────

def test_agent_status_get_est_ignore_silencieusement():
    """'agent-status-get' est une lecture passive, pas une transition —
    jamais transmise, même si l'agent est dans l'annuaire."""
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    adapter._agent_directory = {"agent-uuid-1": {"domain": "d", "extension": "1005"}}
    headers = {"CC-Action": "agent-status-get", "CC-Agent": "agent-uuid-1", "CC-Agent-Status": "Available"}

    adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_not_called()


def test_agent_status_change_resout_via_annuaire_et_transmet():
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    adapter._agent_directory = {
        "e8a58298-87e7-4960-a222-d05763866b15": {
            "domain": "africallpbx.fusion.cloud228.com", "extension": "22101005",
        },
    }
    headers = {
        "CC-Action": "agent-status-change",
        "CC-Agent": "e8a58298-87e7-4960-a222-d05763866b15",
        "CC-Agent-Status": "Logged Out",
        "CC-Queue": "8004@africallpbx.fusion.cloud228.com",
    }

    adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_called_once()
    payload = ingest_client.send.call_args[0][0]
    assert payload["pbx_domain"] == "africallpbx.fusion.cloud228.com"
    assert payload["agent"]["login"] == "22101005"
    assert payload["agent"]["status"] == "Logged Out"


def test_agent_status_change_agent_absent_de_l_annuaire_est_journalise(caplog):
    """Annuaire pas encore rafraîchi ou agent hors des files supervisées :
    abandonné proprement, pas d'exception, mais journalisé (pas perdu sans
    trace)."""
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    headers = {
        "CC-Action": "agent-status-change",
        "CC-Agent": "uuid-inconnu",
        "CC-Agent-Status": "Available",
    }

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_not_called()
    assert any("uuid-inconnu" in r.message for r in caplog.records)


# ── Saisie multi-files en une entrée ("8001, 8002, ...") — pour le filtre
# des événements liés à un canal (_on_callcenter_info), pas pour l'annuaire
# agents qui n'est plus scopé par file (voir plus bas) ─────────────────────

def test_queue_ids_avec_plusieurs_files_dans_une_seule_entree_est_scindee():
    """Reproduit le cas réel du 29/07 : 5 files saisies en une fois dans
    l'ancien combobox produisaient UNE entrée "8001, 8002, ..." plutôt que
    5 entrées distinctes — doit être scindée pour le filtrage queue-enter."""
    domains = [{"pbx_domain": "d1", "queue_ids": ["8001, 8002, 8003, 8004, 8005"]}]
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=MagicMock())

    assert adapter._supervised_queues["d1"] == {"8001", "8002", "8003", "8004", "8005"}


def test_queue_ids_normalement_scindes_restent_inchanges():
    domains = [{"pbx_domain": "d1", "queue_ids": ["8001", "8002"]}]
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=MagicMock())

    assert adapter._supervised_queues["d1"] == {"8001", "8002"}


# ── _refresh_agent_directory / _fetch_agent_list ──────────────────────────
# Confirmé en prod (29/07) : 'agent list <queue>@<domaine>' est accepté sans
# erreur mais ne retourne jamais aucune ligne ('+OK' brut) — mod_callcenter
# ne filtre 'agent list' que par nom d'agent, jamais par file. L'annuaire
# appelle donc désormais 'agent list' SANS scope, une seule fois, pour
# l'unique domaine du connecteur.

def test_refresh_agent_directory_appelle_agent_list_sans_scope():
    domains = [{"pbx_domain": "d1", "queue_ids": ["queue-support"]}]
    adapter = ESLAdapter(
        _fake_connector_config(domains, known_agent_logins=["22101005"]), ingest_client=MagicMock(),
    )
    fake_esl = MagicMock()
    fake_esl.send.return_value = _FakeResponse(
        "e8a58298-87e7-4960-a222-d05763866b15|callback|user/22101005@d1|Available|Waiting|"
        "5|10|3|3|10|0|0|0|0|0|0|0|0|0"
    )
    adapter._esl = fake_esl

    adapter._refresh_agent_directory()

    assert adapter._agent_directory["e8a58298-87e7-4960-a222-d05763866b15"] == {
        "domain": "d1", "extension": "22101005",
    }
    fake_esl.send.assert_called_once_with("api callcenter_config agent list")


def test_refresh_agent_directory_ignore_la_ligne_ok_brute():
    """Réponse réelle observée pour un filtre sans correspondance ('+OK'
    seul, sans ligne d'agent) — ne doit pas planter, juste ne rien ajouter."""
    domains = [{"pbx_domain": "d1", "queue_ids": ["queue-support"]}]
    adapter = ESLAdapter(
        _fake_connector_config(domains, known_agent_logins=["22101005"]), ingest_client=MagicMock(),
    )
    fake_esl = MagicMock()
    fake_esl.send.return_value = _FakeResponse("+OK")
    adapter._esl = fake_esl

    adapter._refresh_agent_directory()

    assert adapter._agent_directory == {}


def test_refresh_agent_directory_extension_inconnue_de_permatel_est_ignoree(caplog):
    """Extension résolue côté FreeSWITCH mais sans User.agent_login
    correspondant pour ce tenant : écartée de l'annuaire, pas fabriquée."""
    domains = [{"pbx_domain": "d1", "queue_ids": ["queue-support"]}]
    adapter = ESLAdapter(
        _fake_connector_config(domains, known_agent_logins=["99999999"]), ingest_client=MagicMock(),
    )
    fake_esl = MagicMock()
    fake_esl.send.return_value = _FakeResponse(
        "e8a58298-87e7-4960-a222-d05763866b15|callback|user/22101005@d1|Available|Waiting|"
        "5|10|3|3|10|0|0|0|0|0|0|0|0|0"
    )
    adapter._esl = fake_esl

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._refresh_agent_directory()

    assert adapter._agent_directory == {}
    assert any("22101005" in r.message and "ignorée" in r.message for r in caplog.records)


def test_refresh_agent_directory_avertit_si_aucun_agent_login_connu(caplog):
    domains = [{"pbx_domain": "d1", "queue_ids": ["queue-support"]}]
    adapter = ESLAdapter(_fake_connector_config(domains, known_agent_logins=[]), ingest_client=MagicMock())
    fake_esl = MagicMock()
    fake_esl.send.return_value = _FakeResponse("")
    adapter._esl = fake_esl

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._refresh_agent_directory()

    assert any("Aucun agent_login connu" in r.message for r in caplog.records)


def test_update_known_agent_logins_remplace_le_roster():
    adapter = ESLAdapter(_fake_connector_config(known_agent_logins=["1"]), ingest_client=MagicMock())
    adapter.update_known_agent_logins(["2", "3"])
    assert adapter._known_agent_logins == {"2", "3"}


def test_refresh_agent_directory_aucun_domaine_configure():
    adapter = ESLAdapter(_fake_connector_config(domains=[]), ingest_client=MagicMock())
    fake_esl = MagicMock()
    adapter._esl = fake_esl

    adapter._refresh_agent_directory()

    fake_esl.send.assert_not_called()
    assert adapter._agent_directory == {}


def test_refresh_agent_directory_plusieurs_domaines_non_supporte(caplog):
    """'agent list' n'étant pas filtrable par domaine, un connecteur avec
    plus d'un domaine configuré n'est pas rafraîchi (limitation connue,
    journalisée plutôt que devinée)."""
    domains = [
        {"pbx_domain": "d1", "queue_ids": ["q1"]},
        {"pbx_domain": "d2", "queue_ids": ["q2"]},
    ]
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=MagicMock())
    fake_esl = MagicMock()
    adapter._esl = fake_esl

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._refresh_agent_directory()

    fake_esl.send.assert_not_called()
    assert any("Plusieurs domaines" in r.message for r in caplog.records)


def test_refresh_agent_directory_reponse_vide_ne_leve_pas():
    domains = [{"pbx_domain": "d1", "queue_ids": ["queue-support"]}]
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=MagicMock())
    fake_esl = MagicMock()
    fake_esl.send.return_value = _FakeResponse("-ERR no such queue\n")
    adapter._esl = fake_esl

    adapter._refresh_agent_directory()

    assert adapter._agent_directory == {}


def test_refresh_agent_directory_echec_send_ne_leve_pas(caplog):
    domains = [{"pbx_domain": "d1", "queue_ids": ["queue-support"]}]
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=MagicMock())
    fake_esl = MagicMock()
    fake_esl.send.side_effect = RuntimeError("connexion perdue")
    adapter._esl = fake_esl

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._refresh_agent_directory()

    assert adapter._agent_directory == {}
    assert any("Échec de 'agent list'" in r.message for r in caplog.records)
