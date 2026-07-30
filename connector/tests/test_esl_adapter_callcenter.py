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
    non mappée par normalize_callcenter_info() (ex. 'agent-contact-change',
    un dump de reconfiguration en masse des agents, sans intérêt pour la
    corrélation d'appels) doit être journalisée, pas silencieusement perdue."""
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(), ingest_client=ingest_client)
    headers = {
        "variable_domain_name": "tenant.pbx.local",
        "CC-Action": "agent-contact-change",
        "CC-Queue": "queue-support",
    }

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_not_called()
    assert any("agent-contact-change" in record.message for record in caplog.records)


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
    # login = l'uuid CC-Agent lui-même (== User.agent_login désormais), pas
    # l'extension/poste physique.
    assert payload["agent"]["login"] == "e8a58298-87e7-4960-a222-d05763866b15"
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


# ── _on_callcenter_info : chemin agent-offering (enrichissement) ──────────
# Confirmé en prod (29/07) : ne porte pas 'variable_domain_name' non plus,
# mais porte CC-Member-Session-UUID (== Unique-ID du leg entrant déjà en
# base), CC-Member-DNIS (vrai numéro composé) et CC-Agent.

def _offering_headers(**overrides):
    base = {
        "CC-Action": "agent-offering",
        "CC-Queue": "8004@africallpbx.fusion.cloud228.com",
        "CC-Agent": "fd18b0f6-47f3-4fe2-8e85-fe36ca077b79",
        "CC-Member-Session-UUID": "0200801b-3e1f-422c-9335-7fac4f4cc867",
        "CC-Member-DNIS": "33186569392",
    }
    base.update(overrides)
    return base


def test_agent_offering_resout_domaine_et_agent_via_annuaire():
    domains = [{"pbx_domain": "africallpbx.fusion.cloud228.com", "queue_ids": ["8004"]}]
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=ingest_client)
    adapter._agent_directory = {
        "fd18b0f6-47f3-4fe2-8e85-fe36ca077b79": {
            "domain": "africallpbx.fusion.cloud228.com", "extension": "22101010",
        },
    }

    adapter._on_callcenter_info(_FakeEvent(_offering_headers()))

    ingest_client.send.assert_called_once()
    payload = ingest_client.send.call_args[0][0]
    assert payload["pbx_domain"] == "africallpbx.fusion.cloud228.com"
    assert payload["call"]["id"] == "0200801b-3e1f-422c-9335-7fac4f4cc867"
    assert payload["call"]["callee"] == "33186569392"
    # login = l'uuid CC-Agent lui-même (== User.agent_login désormais), pas
    # l'extension/poste physique.
    assert payload["agent"]["login"] == "fd18b0f6-47f3-4fe2-8e85-fe36ca077b79"
    assert payload["queue"]["id"] == "8004@africallpbx.fusion.cloud228.com"


def test_agent_offering_repli_sur_unique_domaine_configure_si_agent_inconnu():
    """Agent pas encore dans l'annuaire (pas encore rafraîchi) : repli sur
    l'unique domaine configuré plutôt que d'abandonner — même logique que
    pour l'annuaire agents lui-même."""
    domains = [{"pbx_domain": "africallpbx.fusion.cloud228.com", "queue_ids": ["8004"]}]
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=ingest_client)

    adapter._on_callcenter_info(_FakeEvent(_offering_headers()))

    ingest_client.send.assert_called_once()
    payload = ingest_client.send.call_args[0][0]
    assert payload["pbx_domain"] == "africallpbx.fusion.cloud228.com"
    assert payload["agent"] == {}  # agent non résolu, mais l'appel est quand même enrichi


def test_agent_offering_abandonne_si_plusieurs_domaines_et_agent_inconnu(caplog):
    domains = [
        {"pbx_domain": "d1", "queue_ids": ["8004"]},
        {"pbx_domain": "d2", "queue_ids": ["8005"]},
    ]
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=ingest_client)

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_callcenter_info(_FakeEvent(_offering_headers(**{"CC-Queue": "8004@d1"})))

    ingest_client.send.assert_not_called()
    assert any("domaine non résolvable" in r.message for r in caplog.records)


def test_agent_offering_sans_member_session_uuid_est_abandonne(caplog):
    domains = [{"pbx_domain": "d1", "queue_ids": ["8004"]}]
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=ingest_client)
    headers = _offering_headers(**{"CC-Queue": "8004@d1"})
    del headers["CC-Member-Session-UUID"]

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_not_called()
    assert any("CC-Member-Session-UUID" in r.message for r in caplog.records)


def test_agent_offering_queue_non_supervisee_est_ignoree():
    domains = [{"pbx_domain": "d1", "queue_ids": ["8005"]}]  # 8004 pas supervisée
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=ingest_client)

    adapter._on_callcenter_info(_FakeEvent(_offering_headers(**{"CC-Queue": "8004@d1"})))

    ingest_client.send.assert_not_called()


# ── _on_callcenter_info : chemin bridge-agent-start (enregistrement) ──────
# Confirmé en prod (30/07) : seule source du chemin d'enregistrement d'un
# appel de file — 'variable_record_file_path' reste None partout, y compris
# ici ; le chemin résolu se trouve dans 'variable_execute_on_pre_bridge',
# nommé d'après 'variable_cc_member_session_uuid' (== Unique-ID du leg
# membre déjà en base).

def _bridge_start_headers(**overrides):
    base = {
        "CC-Action": "bridge-agent-start",
        "CC-Queue": "8004@africallpbx.fusion.cloud228.com",
        "CC-Agent": "e8a58298-87e7-4960-a222-d05763866b15",
        "variable_cc_member_session_uuid": "c0fdb4be-a5dd-453c-b456-b84067242923",
        "variable_execute_on_pre_bridge": (
            "record_session /var/lib/freeswitch/recordings/africallpbx.fusion.cloud228.com/"
            "archive/2026/Jul/30/c0fdb4be-a5dd-453c-b456-b84067242923.wav"
        ),
    }
    base.update(overrides)
    return base


def test_bridge_agent_start_resout_domaine_et_agent_via_annuaire_et_transmet():
    domains = [{"pbx_domain": "africallpbx.fusion.cloud228.com", "queue_ids": ["8004"]}]
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=ingest_client)
    adapter._agent_directory = {
        "e8a58298-87e7-4960-a222-d05763866b15": {
            "domain": "africallpbx.fusion.cloud228.com", "extension": "22101001",
        },
    }

    adapter._on_callcenter_info(_FakeEvent(_bridge_start_headers()))

    ingest_client.send.assert_called_once()
    payload = ingest_client.send.call_args[0][0]
    assert payload["event_type"] == "CALLCENTER_BRIDGE_RECORDING"
    assert payload["pbx_domain"] == "africallpbx.fusion.cloud228.com"
    assert payload["call"]["id"] == "c0fdb4be-a5dd-453c-b456-b84067242923"
    assert payload["recording_url"].endswith("c0fdb4be-a5dd-453c-b456-b84067242923.wav")
    # login = l'uuid CC-Agent lui-même (== User.agent_login désormais), pas
    # l'extension/poste physique.
    assert payload["agent"]["login"] == "e8a58298-87e7-4960-a222-d05763866b15"
    assert payload["queue"]["id"] == "8004@africallpbx.fusion.cloud228.com"


def test_bridge_agent_start_repli_sur_unique_domaine_configure_si_agent_inconnu():
    domains = [{"pbx_domain": "africallpbx.fusion.cloud228.com", "queue_ids": ["8004"]}]
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=ingest_client)

    adapter._on_callcenter_info(_FakeEvent(_bridge_start_headers()))

    ingest_client.send.assert_called_once()
    payload = ingest_client.send.call_args[0][0]
    assert payload["pbx_domain"] == "africallpbx.fusion.cloud228.com"
    assert payload["agent"] == {}


def test_bridge_agent_start_abandonne_si_plusieurs_domaines_et_agent_inconnu(caplog):
    domains = [
        {"pbx_domain": "d1", "queue_ids": ["8004"]},
        {"pbx_domain": "d2", "queue_ids": ["8005"]},
    ]
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=ingest_client)

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_callcenter_info(_FakeEvent(_bridge_start_headers(**{"CC-Queue": "8004@d1"})))

    ingest_client.send.assert_not_called()
    assert any("domaine non résolvable" in r.message for r in caplog.records)


def test_bridge_agent_start_sans_chemin_exploitable_est_abandonne(caplog):
    domains = [{"pbx_domain": "d1", "queue_ids": ["8004"]}]
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=ingest_client)
    headers = _bridge_start_headers(**{"CC-Queue": "8004@d1"})
    del headers["variable_execute_on_pre_bridge"]

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._on_callcenter_info(_FakeEvent(headers))

    ingest_client.send.assert_not_called()
    assert any("chemin d'enregistrement exploitable" in r.message for r in caplog.records)


def test_bridge_agent_start_queue_non_supervisee_est_ignoree():
    domains = [{"pbx_domain": "d1", "queue_ids": ["8005"]}]  # 8004 pas supervisée
    ingest_client = MagicMock()
    adapter = ESLAdapter(_fake_connector_config(domains), ingest_client=ingest_client)

    adapter._on_callcenter_info(_FakeEvent(_bridge_start_headers(**{"CC-Queue": "8004@d1"})))

    ingest_client.send.assert_not_called()


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
#
# `known_agent_logins` contient désormais des UUID FusionPBX (User.agent_login
# stocke l'uuid CC-Agent, plus l'extension) : le filtre "agent déclaré côté
# PERMATEL" compare l'uuid de la ligne 'agent list' (colonne "name") à ce
# roster, PAS l'extension parsée depuis 'contact' (qui n'est que le poste
# physique, peut changer sans que ce soit un changement d'agent).

def test_refresh_agent_directory_appelle_agent_list_sans_scope():
    domains = [{"pbx_domain": "d1", "queue_ids": ["queue-support"]}]
    adapter = ESLAdapter(
        _fake_connector_config(domains, known_agent_logins=["e8a58298-87e7-4960-a222-d05763866b15"]),
        ingest_client=MagicMock(),
    )
    fake_esl = MagicMock()
    fake_esl.send.return_value = _FakeResponse(
        "name|instance_id|uuid|type|contact|status|state|max_no_answer|wrap_up_time|"
        "reject_delay_time|busy_delay_time|no_answer_delay_time|last_bridge_start|"
        "last_bridge_end|last_offered_call|last_status_change|no_answer_count|"
        "calls_answered|talk_time|ready_time|external_calls_count\n"
        "e8a58298-87e7-4960-a222-d05763866b15|single_box||callback|user/22101005@d1|"
        "Available|Waiting|5|10|3|3|10|0|0|0|0|0|0|0|0|0\n"
        "+OK"
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
        _fake_connector_config(domains, known_agent_logins=["e8a58298-87e7-4960-a222-d05763866b15"]),
        ingest_client=MagicMock(),
    )
    fake_esl = MagicMock()
    fake_esl.send.return_value = _FakeResponse("+OK")
    adapter._esl = fake_esl

    adapter._refresh_agent_directory()

    assert adapter._agent_directory == {}


def test_refresh_agent_directory_agent_non_declare_est_ignore(caplog):
    """Agent PBX résolu côté FreeSWITCH (uuid + extension) mais dont l'uuid
    ne correspond à AUCUN User.agent_login pour ce tenant : écarté de
    l'annuaire, pas fabriqué — un agent PBX non déclaré côté PERMATEL n'est
    jamais suivi, même si mod_callcenter le connaît."""
    domains = [{"pbx_domain": "d1", "queue_ids": ["queue-support"]}]
    adapter = ESLAdapter(
        _fake_connector_config(domains, known_agent_logins=["uuid-agent-declare-different"]),
        ingest_client=MagicMock(),
    )
    fake_esl = MagicMock()
    fake_esl.send.return_value = _FakeResponse(
        "e8a58298-87e7-4960-a222-d05763866b15|single_box||callback|user/22101005@d1|"
        "Available|Waiting|5|10|3|3|10|0|0|0|0|0|0|0|0|0"
    )
    adapter._esl = fake_esl

    with caplog.at_level(logging.WARNING, logger="connector.esl"):
        adapter._refresh_agent_directory()

    assert adapter._agent_directory == {}
    assert any(
        "e8a58298-87e7-4960-a222-d05763866b15" in r.message and "ignoré" in r.message
        for r in caplog.records
    )


def test_refresh_agent_directory_ignore_la_ligne_d_en_tete():
    """Reproduit le cas réel du 29/07 : la 1ère ligne de la réponse est
    l'en-tête de colonnes ('name|instance_id|uuid|...'), pas un agent — ne
    doit pas être comptée comme une ligne 'ininterprétable'."""
    domains = [{"pbx_domain": "d1", "queue_ids": ["queue-support"]}]
    adapter = ESLAdapter(
        _fake_connector_config(domains, known_agent_logins=["e8a58298-87e7-4960-a222-d05763866b15"]),
        ingest_client=MagicMock(),
    )
    fake_esl = MagicMock()
    fake_esl.send.return_value = _FakeResponse(
        "name|instance_id|uuid|type|contact|status|state|max_no_answer|wrap_up_time|"
        "reject_delay_time|busy_delay_time|no_answer_delay_time|last_bridge_start|"
        "last_bridge_end|last_offered_call|last_status_change|no_answer_count|"
        "calls_answered|talk_time|ready_time|external_calls_count\n"
        "e8a58298-87e7-4960-a222-d05763866b15|single_box||callback|user/22101005@d1|"
        "Available|Waiting|5|10|3|3|10|0|0|0|0|0|0|0|0|0\n"
        "+OK"
    )
    adapter._esl = fake_esl

    adapter._refresh_agent_directory()

    assert adapter._agent_directory == {
        "e8a58298-87e7-4960-a222-d05763866b15": {"domain": "d1", "extension": "22101005"},
    }


def test_refresh_agent_directory_ignore_agent_d_un_autre_domaine():
    """'agent list' est global et renvoie aussi les agents des AUTRES
    domaines hébergés sur le même FreeSWITCH (confirmé en prod 29/07,
    domaine 'pge.fusion.cloud228.com' vu aux côtés du domaine configuré) —
    seuls les agents du domaine réellement configuré sont retenus."""
    domains = [{"pbx_domain": "d1", "queue_ids": ["queue-support"]}]
    adapter = ESLAdapter(
        _fake_connector_config(domains, known_agent_logins=["e8a58298-87e7-4960-a222-d05763866b15"]),
        ingest_client=MagicMock(),
    )
    fake_esl = MagicMock()
    fake_esl.send.return_value = _FakeResponse(
        "e8a58298-87e7-4960-a222-d05763866b15|single_box||callback|user/22101005@autre-domaine|"
        "Available|Waiting|5|10|3|3|10|0|0|0|0|0|0|0|0|0"
    )
    adapter._esl = fake_esl

    adapter._refresh_agent_directory()

    assert adapter._agent_directory == {}


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
