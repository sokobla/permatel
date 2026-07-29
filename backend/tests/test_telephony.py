import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from app.models import PbxConnector, PbxConnectorDomain, TelephonyEvent
from app.models.tenant import Tenant


@pytest.fixture
def pbx_connector(db, default_tenant):
    c = PbxConnector(
        tenant_id=default_tenant.id, name="FusionPBX Prod", type="ESL",
        host="pbx.local", port=8021, is_active=True,
    )
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture
def pbx_domain(db, pbx_connector):
    d = PbxConnectorDomain(
        pbx_connector_id=pbx_connector.id,
        pbx_domain="tenant-core.permatel.local",
        queue_ids=["queue-support"],
    )
    db.session.add(d)
    db.session.commit()
    return d


CONNECTOR_TOKEN_HEADERS = {"X-Connector-Token": "test-connector-token"}


class TestIngestEvent:
    """POST /api/telephony/events/ingest — auth par jeton technique, pas de JWT."""

    def test_ingest_sans_token_retourne_401(self, client, pbx_domain):
        resp = client.post("/api/telephony/events/ingest", json={
            "pbx_domain": pbx_domain.pbx_domain, "event_type": "CHANNEL_CREATE",
        })
        assert resp.status_code == 401

    def test_ingest_mauvais_token_retourne_401(self, client, pbx_domain):
        resp = client.post(
            "/api/telephony/events/ingest",
            json={"pbx_domain": pbx_domain.pbx_domain, "event_type": "CHANNEL_CREATE"},
            headers={"X-Connector-Token": "wrong-token"},
        )
        assert resp.status_code == 401

    def test_ingest_domaine_inconnu_retourne_404(self, client, db):
        resp = client.post(
            "/api/telephony/events/ingest",
            json={"pbx_domain": "inconnu.permatel.local", "event_type": "CHANNEL_CREATE"},
            headers=CONNECTOR_TOKEN_HEADERS,
        )
        assert resp.status_code == 404

    def test_ingest_champs_requis_manquants_retourne_400(self, client, db):
        resp = client.post(
            "/api/telephony/events/ingest",
            json={"pbx_domain": "x"},
            headers=CONNECTOR_TOKEN_HEADERS,
        )
        assert resp.status_code == 400

    def test_ingest_evenement_valide_persiste_et_resout_tenant(self, client, db, pbx_domain, default_tenant):
        payload = {
            "event_type": "CHANNEL_CREATE",
            "pbx_domain": pbx_domain.pbx_domain,
            "call": {
                "id": "call-uuid-1",
                "direction": "inbound",
                "caller": "0612345678",
                "callee": "0522456789",
                "status": "ringing",
            },
            "agent": {"login": "agent01", "state": "available"},
            "queue": {"id": "queue-support", "name": "Support"},
        }
        resp = client.post("/api/telephony/events/ingest", json=payload, headers=CONNECTOR_TOKEN_HEADERS)
        assert resp.status_code == 201

        event = TelephonyEvent.query.filter_by(call_uuid="call-uuid-1").first()
        assert event is not None
        assert event.tenant_id == default_tenant.id
        assert event.pbx_connector_id == pbx_domain.pbx_connector_id
        assert event.event_type == "CHANNEL_CREATE"
        assert event.call_status == "ringing"
        assert event.agent_login == "agent01"
        assert event.queue_id == "queue-support"
        assert event.raw_payload == payload

    def test_ingest_persiste_le_statut_agent_brut(self, client, db, pbx_domain):
        payload = {
            "event_type": "CALLCENTER_AGENT_STATE_CHANGE",
            "pbx_domain": pbx_domain.pbx_domain,
            "call": {"id": "call-agent-status", "status": "on_hold"},
            "agent": {"login": "agent01", "status": "Available"},
            "queue": {"id": "queue-support"},
        }
        resp = client.post("/api/telephony/events/ingest", json=payload, headers=CONNECTOR_TOKEN_HEADERS)
        assert resp.status_code == 201

        event = TelephonyEvent.query.filter_by(call_uuid="call-agent-status").first()
        assert event.agent_status == "Available"

    def test_ingest_diffuse_sur_le_websocket_du_tenant(self, client, db, pbx_domain, default_tenant):
        payload = {
            "event_type": "CHANNEL_ANSWER",
            "pbx_domain": pbx_domain.pbx_domain,
            "call": {"id": "call-uuid-ws", "status": "answered"},
        }
        with patch("app.routes.telephony.socketio.emit") as emit_mock:
            resp = client.post("/api/telephony/events/ingest", json=payload, headers=CONNECTOR_TOKEN_HEADERS)
        assert resp.status_code == 201

        emit_mock.assert_called_once()
        args, kwargs = emit_mock.call_args
        assert args[0] == "telephony_event"
        assert args[1]["call_uuid"] == "call-uuid-ws"
        assert kwargs["room"] == str(default_tenant.id)
        assert kwargs["namespace"] == "/telephony"

    def test_ingest_reussit_meme_si_la_diffusion_websocket_echoue(self, client, db, pbx_domain):
        payload = {
            "event_type": "CHANNEL_CREATE",
            "pbx_domain": pbx_domain.pbx_domain,
            "call": {"id": "call-uuid-ws2", "status": "ringing"},
        }
        with patch("app.routes.telephony.socketio.emit", side_effect=RuntimeError("boom")):
            resp = client.post("/api/telephony/events/ingest", json=payload, headers=CONNECTOR_TOKEN_HEADERS)
        assert resp.status_code == 201


class TestBootstrapConfig:
    """GET /api/telephony/connectors/config — bootstrap consommé par le Core Connector."""

    def test_sans_token_retourne_401(self, client, pbx_domain):
        resp = client.get("/api/telephony/connectors/config")
        assert resp.status_code == 401

    def test_mauvais_token_retourne_401(self, client, pbx_domain):
        resp = client.get(
            "/api/telephony/connectors/config",
            headers={"X-Connector-Token": "wrong-token"},
        )
        assert resp.status_code == 401

    def test_retourne_connecteurs_actifs_avec_secrets_et_domaines(
        self, client, db, pbx_connector, pbx_domain, default_tenant
    ):
        pbx_connector.username = "esl_user"
        pbx_connector.password = "esl_secret"
        db.session.commit()

        resp = client.get("/api/telephony/connectors/config", headers=CONNECTOR_TOKEN_HEADERS)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["connectors"]) == 1

        c = body["connectors"][0]
        assert c["id"] == pbx_connector.id
        assert c["tenant_id"] == str(default_tenant.id)
        assert c["password"] == "esl_secret"
        assert len(c["domains"]) == 1
        assert c["domains"][0]["pbx_domain"] == pbx_domain.pbx_domain
        assert c["domains"][0]["queue_ids"] == ["queue-support"]

    def test_known_agent_logins_liste_les_users_avec_agent_login_du_tenant(
        self, client, db, pbx_connector, default_tenant,
    ):
        """Roster faisant autorité pour l'annuaire agents du connecteur
        (ESLAdapter) : uniquement les User du tenant avec agent_login
        renseigné, actifs, avec une adhésion tenant active."""
        from app.models.user import User, UserRole
        from app.models.tenant import Tenant

        u1 = User(
            username="agent1", email="agent1@permatel.ma", nom="A", prenom="Gent",
            role=UserRole.PERMANENCIER, is_active=True, agent_login="22101005",
        )
        u1.set_password("Password123!")
        u1.tenants.append(default_tenant)
        u2 = User(
            username="noagent", email="noagent@permatel.ma", nom="B", prenom="No",
            role=UserRole.PERMANENCIER, is_active=True, agent_login=None,
        )
        u2.set_password("Password123!")
        u2.tenants.append(default_tenant)
        u3_inactive = User(
            username="agentinactive", email="inactive@permatel.ma", nom="C", prenom="Inactive",
            role=UserRole.PERMANENCIER, is_active=False, agent_login="22101099",
        )
        u3_inactive.set_password("Password123!")
        u3_inactive.tenants.append(default_tenant)
        db.session.add_all([u1, u2, u3_inactive])
        db.session.commit()

        other_tenant = Tenant(code="OTHERKAL", nom="Autre Tenant Kal", slug="otherkal")
        db.session.add(other_tenant)
        db.session.commit()
        u_other = User(
            username="agentother", email="agentother@permatel.ma", nom="D", prenom="Other",
            role=UserRole.PERMANENCIER, is_active=True, agent_login="99999999",
        )
        u_other.set_password("Password123!")
        u_other.tenants.append(other_tenant)
        db.session.add(u_other)
        db.session.commit()

        resp = client.get("/api/telephony/connectors/config", headers=CONNECTOR_TOKEN_HEADERS)
        assert resp.status_code == 200
        c = resp.get_json()["connectors"][0]
        assert c["known_agent_logins"] == ["22101005"]

    def test_exclut_les_connecteurs_inactifs(self, client, db, pbx_connector):
        pbx_connector.is_active = False
        db.session.commit()

        resp = client.get("/api/telephony/connectors/config", headers=CONNECTOR_TOKEN_HEADERS)
        assert resp.status_code == 200
        assert resp.get_json()["connectors"] == []


class TestStatusHeartbeat:
    """POST /api/telephony/connectors/status — heartbeat du Core Connector."""

    def test_sans_token_retourne_401(self, client, pbx_connector):
        resp = client.post("/api/telephony/connectors/status", json={})
        assert resp.status_code == 401

    def test_met_a_jour_le_statut_du_connecteur(self, client, db, pbx_connector):
        resp = client.post(
            "/api/telephony/connectors/status",
            json={"connectors": {str(pbx_connector.id): {"connected": True, "error": None}}},
            headers=CONNECTOR_TOKEN_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.get_json()["updated"] == 1

        db.session.refresh(pbx_connector)
        assert pbx_connector.is_connected is True
        assert pbx_connector.last_seen_at is not None
        assert pbx_connector.last_error is None

    def test_ignore_les_connecteurs_inconnus(self, client, db):
        resp = client.post(
            "/api/telephony/connectors/status",
            json={"connectors": {"999999": {"connected": False, "error": "boom"}}},
            headers=CONNECTOR_TOKEN_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.get_json()["updated"] == 0


class TestActiveCalls:
    def test_active_calls_exclut_les_appels_termines(self, client, db, auth_headers, pbx_domain, default_tenant):
        # Appel en cours (dernier évènement = ringing)
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_domain.pbx_connector_id,
            event_type="CHANNEL_CREATE", call_status="ringing", call_uuid="call-active",
            created_at=datetime.utcnow(),
        ))
        # Appel terminé (dernier évènement = ended)
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_domain.pbx_connector_id,
            event_type="CHANNEL_CREATE", call_status="ringing", call_uuid="call-done",
            created_at=datetime.utcnow() - timedelta(seconds=30),
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_domain.pbx_connector_id,
            event_type="CHANNEL_HANGUP_COMPLETE", call_status="ended", call_uuid="call-done",
            created_at=datetime.utcnow(),
        ))
        db.session.commit()

        resp = client.get("/api/telephony/active-calls", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["active_calls"][0]["call_uuid"] == "call-active"

    def test_active_calls_exclut_les_appels_trop_anciens(self, client, db, auth_headers, pbx_domain, default_tenant):
        """Reproduit le cas réel du 29/07 : un appel dont l'événement de
        raccroché a été perdu (redémarrage connecteur en plein appel) reste
        'ringing' indéfiniment — ne doit plus apparaître comme actif passé
        le délai de fraîcheur (ACTIVE_CALL_STALE_AFTER)."""
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_domain.pbx_connector_id,
            event_type="CHANNEL_CREATE", call_status="ringing", call_uuid="call-fantome",
            created_at=datetime.utcnow() - timedelta(hours=10),
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_domain.pbx_connector_id,
            event_type="CHANNEL_CREATE", call_status="ringing", call_uuid="call-recent",
            created_at=datetime.utcnow() - timedelta(minutes=2),
        ))
        db.session.commit()

        resp = client.get("/api/telephony/active-calls", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["active_calls"][0]["call_uuid"] == "call-recent"

    def test_active_calls_fusionne_les_champs_de_plusieurs_evenements(
        self, client, db, auth_headers, pbx_domain, default_tenant,
    ):
        """Reproduit le cas réel du 29/07 : un événement d'enrichissement
        (agent-offering) arrive APRÈS le CHANNEL_CREATE et n'apporte que
        l'agent/la file/le vrai numéro composé, sans statut — ne doit pas
        écraser le statut déjà connu, et doit être visible dans la ligne
        fusionnée finale."""
        base = datetime.utcnow() - timedelta(seconds=10)
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_domain.pbx_connector_id,
            event_type="CHANNEL_CREATE", call_status="ringing", call_uuid="call-enrichi",
            caller_number="212687851794", callee_number="33186569392", created_at=base,
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_domain.pbx_connector_id,
            event_type="CHANNEL_ANSWER", call_status="answered", call_uuid="call-enrichi",
            created_at=base + timedelta(seconds=1),
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_domain.pbx_connector_id,
            event_type="CALLCENTER_MEMBER_ENRICHMENT", call_status=None, call_uuid="call-enrichi",
            agent_login="22101010", queue_id="8004@africallpbx.fusion.cloud228.com",
            callee_number="33186569392", created_at=base + timedelta(seconds=2),
        ))
        db.session.commit()

        resp = client.get("/api/telephony/active-calls", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        call = data["active_calls"][0]
        assert call["call_status"] == "answered"  # pas écrasé par l'enrichissement sans statut
        assert call["caller"] == "212687851794"
        assert call["callee"] == "33186569392"
        assert call["agent_login"] == "22101010"
        assert call["queue_id"] == "8004@africallpbx.fusion.cloud228.com"
        assert call["started_at"] is not None

    def test_active_calls_fusionne_les_legs_d_un_pont_direct(
        self, client, db, auth_headers, pbx_connector, default_tenant,
    ):
        """Reproduit le cas réel du 29/07 : un appel sortant direct (agent
        vers externe) produit deux call_uuid distincts, liés par
        Other-Leg-Unique-ID une fois le pont établi — seul le leg 'inbound'
        (numéro humainement lisible) doit apparaître dans /active-calls."""
        base = datetime.utcnow() - timedelta(seconds=5)
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_connector.id,
            event_type="CHANNEL_ANSWER", call_status="answered", call_uuid="leg-inbound",
            call_direction="inbound", caller_number="22101008", callee_number="010615465411",
            linked_call_uuid="leg-outbound", created_at=base,
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_connector.id,
            event_type="CHANNEL_ANSWER", call_status="answered", call_uuid="leg-outbound",
            call_direction="outbound", caller_number="33186569392", callee_number="50000615465411",
            linked_call_uuid="leg-inbound", created_at=base,
        ))
        db.session.commit()

        resp = client.get("/api/telephony/active-calls", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["active_calls"][0]["call_uuid"] == "leg-inbound"
        assert data["active_calls"][0]["caller"] == "22101008"
        assert data["active_calls"][0]["callee"] == "010615465411"


class TestKpis:
    def test_kpis_summary_calcule_taux_decroche(self, client, db, auth_headers, pbx_domain, default_tenant):
        base = datetime.utcnow() - timedelta(minutes=5)
        # Appel répondu
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CHANNEL_CREATE", call_status="ringing",
            call_uuid="call-1", created_at=base,
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CHANNEL_ANSWER", call_status="answered",
            call_uuid="call-1", created_at=base + timedelta(seconds=5),
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CHANNEL_HANGUP_COMPLETE", call_status="ended",
            call_uuid="call-1", duration=60, created_at=base + timedelta(seconds=65),
        ))
        # Appel abandonné
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CHANNEL_CREATE", call_status="ringing",
            call_uuid="call-2", created_at=base,
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CHANNEL_HANGUP_COMPLETE", call_status="abandoned",
            call_uuid="call-2", created_at=base + timedelta(seconds=10),
        ))
        db.session.commit()

        resp = client.get("/api/telephony/kpis/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_calls"] == 2
        assert data["answered_calls"] == 1
        assert data["decroche_rate_pct"] == 50.0
        assert data["avg_response_seconds"] == 5.0

    def test_kpis_queues_et_agents_repondent_200(self, client, auth_headers, db):
        resp1 = client.get("/api/telephony/kpis/queues", headers=auth_headers)
        assert resp1.status_code == 200
        assert resp1.get_json()["queues"] == []

        resp2 = client.get("/api/telephony/kpis/agents", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.get_json()["agents"] == []

    def test_kpis_queues_habille_l_alias_exclut_sans_file_et_trie_par_volume(
        self, client, db, auth_headers, pbx_connector, default_tenant,
    ):
        """Reproduit le cas réel du 29/07 : le panneau Supervision ne doit
        montrer que les files avec activité (pas de bucket 'sans_file' pour
        les appels hors file d'attente), habillées de leur alias PERMATEL
        configuré, triées par volume décroissant (file la plus active en
        premier)."""
        domain = PbxConnectorDomain(
            pbx_connector_id=pbx_connector.id,
            pbx_domain="africallpbx.fusion.cloud228.com",
            queue_ids=[{"id": "8004", "alias": "Centre d'appels"}],
        )
        db.session.add(domain)
        db.session.commit()
        base = datetime.utcnow() - timedelta(minutes=10)

        def _call(uuid, queue_id, final_status, offset=0):
            db.session.add(TelephonyEvent(
                tenant_id=default_tenant.id, event_type="CHANNEL_CREATE", call_status="ringing",
                call_uuid=uuid, queue_id=queue_id, created_at=base + timedelta(seconds=offset),
            ))
            db.session.add(TelephonyEvent(
                tenant_id=default_tenant.id, event_type="CHANNEL_HANGUP_COMPLETE", call_status=final_status,
                call_uuid=uuid, queue_id=queue_id, created_at=base + timedelta(seconds=offset + 5),
            ))

        # File déclarée avec alias, 2 appels (la plus active)
        _call("call-q1-a", "8004@africallpbx.fusion.cloud228.com", "ended", offset=0)
        _call("call-q1-b", "8004@africallpbx.fusion.cloud228.com", "abandoned", offset=10)
        # File non déclarée (alias absent du config), 1 appel
        _call("call-q2-a", "9001@africallpbx.fusion.cloud228.com", "ended", offset=20)
        # Appel hors file d'attente : ne doit PAS apparaître comme "sans_file"
        _call("call-no-queue", None, "ended", offset=30)
        db.session.commit()

        resp = client.get("/api/telephony/kpis/queues", headers=auth_headers)
        assert resp.status_code == 200
        queues = resp.get_json()["queues"]

        assert [q["queue_id"] for q in queues] == [
            "8004@africallpbx.fusion.cloud228.com",
            "9001@africallpbx.fusion.cloud228.com",
        ]
        assert all(q["queue_id"] != "sans_file" for q in queues)

        declared = queues[0]
        assert declared["alias"] == "Centre d'appels"
        assert declared["total_calls"] == 2
        assert declared["abandoned_calls"] == 1

        undeclared = queues[1]
        assert undeclared["alias"] == "9001@africallpbx.fusion.cloud228.com"
        assert undeclared["total_calls"] == 1


class TestAgentsStatus:
    def test_agents_status_vide_si_aucun_evenement_de_presence(self, client, auth_headers, db):
        resp = client.get("/api/telephony/agents/status", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["agents"] == []

    def test_agents_status_derive_la_presence_du_dernier_evenement(self, client, db, auth_headers, default_tenant):
        base = datetime.utcnow() - timedelta(minutes=10)
        # Deux changements d'état pour agent01 : seul le plus récent doit compter.
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CALLCENTER_AGENT_STATE_CHANGE",
            call_status="on_hold", call_uuid="ev-1", agent_login="agent01",
            agent_status="On Break", created_at=base,
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CALLCENTER_AGENT_STATE_CHANGE",
            call_status="on_hold", call_uuid="ev-2", agent_login="agent01",
            agent_status="Available", created_at=base + timedelta(minutes=5),
        ))
        # Agent en pause, statut inconnu -> offline par défaut (pas de fabrication).
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CALLCENTER_AGENT_STATE_CHANGE",
            call_status="on_hold", call_uuid="ev-3", agent_login="agent02",
            agent_status="Logged Out", created_at=base,
        ))
        db.session.commit()

        resp = client.get("/api/telephony/agents/status", headers=auth_headers)
        assert resp.status_code == 200
        agents = {a["agent_login"]: a for a in resp.get_json()["agents"]}
        assert agents["agent01"]["presence"] == "online"
        assert agents["agent01"]["raw_status"] == "Available"
        assert agents["agent02"]["presence"] == "offline"

    def test_agents_status_compte_les_appels_traites_sur_la_periode(self, client, db, auth_headers, default_tenant):
        base = datetime.utcnow() - timedelta(minutes=5)
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CALLCENTER_AGENT_STATE_CHANGE",
            call_status="on_hold", call_uuid="ev-presence", agent_login="agent01",
            agent_status="Available", created_at=base,
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CHANNEL_ANSWER", call_status="answered",
            call_uuid="call-1", agent_login="agent01", created_at=base,
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CHANNEL_HANGUP_COMPLETE", call_status="ended",
            call_uuid="call-1", agent_login="agent01", duration=30, created_at=base + timedelta(seconds=30),
        ))
        db.session.commit()

        resp = client.get("/api/telephony/agents/status", headers=auth_headers)
        agents = {a["agent_login"]: a for a in resp.get_json()["agents"]}
        assert agents["agent01"]["calls_handled"] == 1

    def test_agents_status_isolation_cross_tenant(self, client, db, auth_headers, default_tenant):
        from app.models.tenant import Tenant
        other_tenant = Tenant(code="AGENTSTATUS", nom="Autre Tenant", slug="agentstatus")
        db.session.add(other_tenant)
        db.session.commit()

        db.session.add(TelephonyEvent(
            tenant_id=other_tenant.id, event_type="CALLCENTER_AGENT_STATE_CHANGE",
            call_status="on_hold", call_uuid="ev-other", agent_login="agent-autre-tenant",
            agent_status="Available", created_at=datetime.utcnow(),
        ))
        db.session.commit()

        resp = client.get("/api/telephony/agents/status", headers=auth_headers)
        assert resp.status_code == 200
        logins = [a["agent_login"] for a in resp.get_json()["agents"]]
        assert "agent-autre-tenant" not in logins


class TestConnectorsCrud:
    """CRUD /api/telephony/connectors — tenant-scopé, tenant_admin_required."""

    def test_liste_refusee_sans_contexte_tenant_admin(self, client, auth_headers):
        resp = client.post(
            "/api/telephony/connectors",
            json={"name": "x", "type": "ESL", "host": "h", "port": 8021},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_liste_scopee_au_tenant_actif(self, client, db, auth_headers, pbx_connector):
        resp = client.get("/api/telephony/connectors", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["id"] == pbx_connector.id
        assert data[0]["tenant_id"] == str(pbx_connector.tenant_id)

    def test_create_update_delete_connector(self, client, auth_headers_admin, db, default_tenant):
        payload = {"name": "Asterisk Test", "type": "AMI", "host": "ast.local", "port": 5038, "password": "secret"}
        resp = client.post("/api/telephony/connectors", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Asterisk Test"
        assert data["tenant_id"] == str(default_tenant.id)
        assert data["has_password"] is True
        assert "password" not in data
        connector_id = data["id"]

        # Le mot de passe est chiffré au repos (EncryptedText déchiffre
        # automatiquement à la lecture via l'ORM : vérifier la valeur brute
        # en base, pas l'attribut ORM qui renvoie déjà le clair).
        from sqlalchemy import text
        raw_value = db.session.execute(
            text("SELECT password FROM pbx_connectors WHERE id = :id"), {"id": connector_id}
        ).scalar()
        assert raw_value != "secret"
        assert raw_value.startswith("enc::")

        stored = PbxConnector.query.get(connector_id)
        assert stored.password == "secret"  # déchiffrement transparent à la lecture

        resp2 = client.put(f"/api/telephony/connectors/{connector_id}", json={"host": "ast2.local"}, headers=auth_headers_admin)
        assert resp2.status_code == 200
        assert resp2.get_json()["host"] == "ast2.local"

        resp3 = client.delete(f"/api/telephony/connectors/{connector_id}", headers=auth_headers_admin)
        assert resp3.status_code == 200
        assert PbxConnector.query.get(connector_id) is None

    def test_isolation_cross_tenant(self, client, db, auth_headers_admin, default_tenant):
        """Un connecteur d'un AUTRE tenant est invisible (404), même pour
        l'admin global — son contexte actif est default_tenant."""
        other_tenant = Tenant(code="OTHER", nom="Autre Tenant", slug="other")
        db.session.add(other_tenant)
        db.session.commit()
        other_connector = PbxConnector(tenant_id=other_tenant.id, name="Autre", type="ESL", host="h", port=8021)
        db.session.add(other_connector)
        db.session.commit()

        resp = client.put(
            f"/api/telephony/connectors/{other_connector.id}", json={"host": "x"}, headers=auth_headers_admin
        )
        assert resp.status_code == 404

    def test_create_domain_and_update_queues(self, client, auth_headers_admin, pbx_connector):
        payload = {"pbx_domain": "new.permatel.local", "queue_ids": ["q1"]}
        resp = client.post(f"/api/telephony/connectors/{pbx_connector.id}/domains", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 201
        domain_id = resp.get_json()["id"]
        assert resp.get_json()["pbx_domain"] == "new.permatel.local"
        # Compat ancien format (liste de chaînes) : normalisé en {"id", "alias"}.
        assert resp.get_json()["queue_ids"] == [{"id": "q1", "alias": ""}]

        resp2 = client.put(
            f"/api/telephony/connectors/{pbx_connector.id}/domains/{domain_id}",
            json={"queue_ids": [{"id": "a", "alias": "Support"}, {"id": "b", "alias": ""}]},
            headers=auth_headers_admin,
        )
        assert resp2.status_code == 200
        assert resp2.get_json()["queue_ids"] == [{"id": "a", "alias": "Support"}, {"id": "b", "alias": ""}]

    def test_create_domain_queue_ids_saisis_avec_alias_vide_ou_manquant(
        self, client, auth_headers_admin, pbx_connector,
    ):
        """Entrées sans alias (chaîne nue, ou dict sans 'alias') acceptées,
        entrées sans 'id' écartées silencieusement."""
        payload = {
            "pbx_domain": "aliases.permatel.local",
            "queue_ids": ["8001", {"id": "8002"}, {"alias": "sans id, écarté"}, {"id": "  ", "alias": "vide"}],
        }
        resp = client.post(
            f"/api/telephony/connectors/{pbx_connector.id}/domains", json=payload, headers=auth_headers_admin,
        )
        assert resp.status_code == 201
        assert resp.get_json()["queue_ids"] == [
            {"id": "8001", "alias": ""},
            {"id": "8002", "alias": ""},
        ]

    def test_create_domain_duplique_retourne_409(self, client, auth_headers_admin, pbx_domain):
        payload = {"pbx_domain": pbx_domain.pbx_domain}
        resp = client.post(
            f"/api/telephony/connectors/{pbx_domain.pbx_connector_id}/domains",
            json=payload, headers=auth_headers_admin,
        )
        assert resp.status_code == 409

    def test_delete_domain(self, client, auth_headers_admin, pbx_connector, pbx_domain):
        resp = client.delete(
            f"/api/telephony/connectors/{pbx_connector.id}/domains/{pbx_domain.id}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        assert PbxConnectorDomain.query.get(pbx_domain.id) is None


class TestSyncConnector:
    """POST /api/telephony/connectors/<id>/sync — force une reconnexion."""

    def test_refuse_sans_droit_admin_tenant(self, client, auth_headers, pbx_connector):
        resp = client.post(f"/api/telephony/connectors/{pbx_connector.id}/sync", headers=auth_headers)
        assert resp.status_code == 403

    def test_bump_sync_requested_at(self, client, db, auth_headers_admin, pbx_connector):
        assert pbx_connector.sync_requested_at is None
        resp = client.post(f"/api/telephony/connectors/{pbx_connector.id}/sync", headers=auth_headers_admin)
        assert resp.status_code == 200
        db.session.refresh(pbx_connector)
        assert pbx_connector.sync_requested_at is not None

    def test_isolation_cross_tenant_sur_sync(self, client, db, auth_headers_admin, default_tenant):
        other_tenant = Tenant(code="OTHER2", nom="Autre Tenant 2", slug="other2")
        db.session.add(other_tenant)
        db.session.commit()
        other_connector = PbxConnector(tenant_id=other_tenant.id, name="Autre", type="ESL", host="h", port=8021)
        db.session.add(other_connector)
        db.session.commit()

        resp = client.post(f"/api/telephony/connectors/{other_connector.id}/sync", headers=auth_headers_admin)
        assert resp.status_code == 404


@pytest.fixture
def pbx_connector_with_cdr_token(db, pbx_connector):
    import hashlib
    raw_token = "test-cdr-webhook-token-raw"
    pbx_connector.cdr_webhook_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    pbx_connector.cdr_webhook_token = raw_token
    db.session.commit()
    return pbx_connector, raw_token


class TestCdrIngest:
    """POST /api/telephony/cdr/ingest/<token> — webhook FusionPBX mod_json_cdr, jeton par connecteur."""

    def test_jeton_invalide_retourne_404(self, client, db, pbx_connector):
        resp = client.post("/api/telephony/cdr/ingest/jeton-inconnu", json={"variables": {"uuid": "x"}})
        assert resp.status_code == 404

    def test_ip_non_autorisee_retourne_403(self, client, db, pbx_connector_with_cdr_token):
        connector, raw_token = pbx_connector_with_cdr_token
        connector.authorized_ip = "10.0.0.5"
        db.session.commit()
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            json={"variables": {"uuid": "call-cdr-1"}},
            headers={"X-Forwarded-For": "203.0.113.9"},
        )
        assert resp.status_code == 403

    def test_ip_autorisee_est_acceptee(self, client, db, pbx_connector_with_cdr_token):
        connector, raw_token = pbx_connector_with_cdr_token
        connector.authorized_ip = "203.0.113.9"
        db.session.commit()
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            json={"variables": {"uuid": "call-cdr-ip-ok", "start_epoch": "1000"}},
            headers={"X-Forwarded-For": "203.0.113.9"},
        )
        assert resp.status_code == 201

    def test_corps_sans_uuid_retourne_400(self, client, db, pbx_connector_with_cdr_token):
        _, raw_token = pbx_connector_with_cdr_token
        resp = client.post(f"/api/telephony/cdr/ingest/{raw_token}", json={"variables": {}})
        assert resp.status_code == 400

    def test_corps_json_tronque_retourne_400_sans_crash(self, client, db, pbx_connector_with_cdr_token):
        """Corps réellement invalide (tronqué, aucune accolade fermante) :
        le diagnostic détaillé ajouté pour instrumenter les échecs réels ne
        doit pas lui-même planter sur un cas simplement invalide."""
        _, raw_token = pbx_connector_with_cdr_token
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            data='cdr={"variables":{"uuid":"call-tronque"',  # accolade jamais fermée
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 400

    def test_corps_json_syntaxiquement_invalide_retourne_400_sans_crash(
        self, client, db, pbx_connector_with_cdr_token,
    ):
        """Accolades présentes (bornage réussi) mais JSON syntaxiquement
        invalide à l'intérieur : exerce le chemin de diagnostic
        JSONDecodeError (position/ligne/colonne) ajouté pour instrumenter
        les échecs réels — ne doit pas planter."""
        _, raw_token = pbx_connector_with_cdr_token
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            data='cdr={"variables":{"uuid":,}}',  # valeur manquante après ':'
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 400

    def test_ingest_cdr_repondu_cree_trois_evenements(self, client, db, pbx_connector_with_cdr_token, default_tenant):
        _, raw_token = pbx_connector_with_cdr_token
        payload = {
            "variables": {
                "uuid": "call-cdr-answered",
                "start_epoch": "1700000000",
                "answer_epoch": "1700000005",
                "end_epoch": "1700000065",
                "billsec": "60",
                "caller_id_number": "0612345678",
                "destination_number": "0522456789",
                "direction": "inbound",
                "hangup_cause": "NORMAL_CLEARING",
                "record_file_path": "/var/lib/freeswitch/recordings/call-cdr-answered.wav",
            }
        }
        resp = client.post(f"/api/telephony/cdr/ingest/{raw_token}", json=payload)
        assert resp.status_code == 201
        assert resp.get_json()["events"] == 3

        events = TelephonyEvent.query.filter_by(call_uuid="call-cdr-answered").order_by(TelephonyEvent.created_at).all()
        assert [e.call_status for e in events] == ["ringing", "answered", "ended"]
        assert events[-1].duration == 60
        assert events[-1].tenant_id == default_tenant.id

    def test_ingest_cdr_extrait_caller_callee_depuis_callflow(
        self, client, db, pbx_connector_with_cdr_token, default_tenant,
    ):
        """Reproduit la structure réelle d'un CDR FusionPBX complet (trace du
        29/07, appel réel via passerelle SIP) : 'caller_id_number' et
        'destination_number' n'existent PAS sous 'variables' (contrairement à
        l'hypothèse initiale) — ils vivent sous callflow[0].caller_profile.
        Sans ce correctif, caller_number/callee_number restent NULL pour
        TOUS les appels ingérés via CDR."""
        _, raw_token = pbx_connector_with_cdr_token
        payload = {
            "variables": {
                "uuid": "call-cdr-callflow",
                "start_epoch": "1785270347",
                "answer_epoch": "1785270363",
                "end_epoch": "1785270386",
                "billsec": "23",
                "direction": "outbound",
                "hangup_cause": "NORMAL_CLEARING",
                "sip_from_user": "33186569392",
                "sip_to_user": "50000620047255",
                # Volontairement absent : caller_id_number / destination_number
            },
            "callflow": [
                {
                    "caller_profile": {
                        "caller_id_number": "33186569392",
                        "destination_number": "50000620047255",
                        "ani": "22101010",
                    },
                },
            ],
        }
        resp = client.post(f"/api/telephony/cdr/ingest/{raw_token}", json=payload)
        assert resp.status_code == 201

        event = TelephonyEvent.query.filter_by(call_uuid="call-cdr-callflow", event_type="CDR_RECORD_END").first()
        assert event.caller_number == "33186569392"
        assert event.callee_number == "50000620047255"
        assert event.tenant_id == default_tenant.id

    def test_ingest_cdr_agent_login_depuis_originatee_pas_cc_agent(
        self, client, db, pbx_connector_with_cdr_token,
    ):
        """Reproduit un appel réel routé en file d'attente (trace du 29/07,
        mod_callcenter) : 'cc_agent' s'est révélé être un UUID interne
        FusionPBX (call_center_agents.call_center_agent_uuid), PAS un login/
        une extension exploitable pour matcher un User PERMATEL. L'extension
        réelle de l'agent qui décroche ("22101005" dans la trace réelle) vit
        sous callflow[0].caller_profile.originatee.originatee_caller_profiles[0]
        .destination_number — c'est CETTE valeur qui doit peupler agent_login,
        pas le contenu de la variable 'cc_agent'."""
        _, raw_token = pbx_connector_with_cdr_token
        payload = {
            "variables": {
                "uuid": "call-cdr-queue",
                "start_epoch": "1785258708",
                "answer_epoch": "1785258708",
                "end_epoch": "1785258746",
                "billsec": "38",
                "direction": "inbound",
                "hangup_cause": "NORMAL_CLEARING",
                "cc_queue": "8004@africallpbx.fusion.cloud228.com",
                "cc_agent": "9fb3f742-b96f-4b5a-9906-32e5e4cf1ccf",  # UUID interne, PAS l'extension
            },
            "callflow": [
                {
                    "caller_profile": {
                        "caller_id_number": "212687851794",
                        "destination_number": "8004",
                        "originatee": {
                            "originatee_caller_profiles": [
                                {"destination_number": "22101005"},
                            ],
                        },
                    },
                },
            ],
        }
        resp = client.post(f"/api/telephony/cdr/ingest/{raw_token}", json=payload)
        assert resp.status_code == 201

        event = TelephonyEvent.query.filter_by(call_uuid="call-cdr-queue", event_type="CDR_RECORD_END").first()
        assert event.queue_id == "8004@africallpbx.fusion.cloud228.com"
        assert event.agent_login == "22101005"

    def test_ingest_cdr_agent_login_absent_hors_file_d_attente(self, client, db, pbx_connector_with_cdr_token):
        """Sans 'cc_queue' (appel hors file d'attente), agent_login doit
        rester None même si un profil 'originatee' existe pour une autre
        raison (ex. transfert) — pas de fabrication de donnée agent sans
        contexte de file d'attente réel."""
        _, raw_token = pbx_connector_with_cdr_token
        payload = {
            "variables": {
                "uuid": "call-cdr-no-queue",
                "start_epoch": "1785258708",
                "end_epoch": "1785258746",
                "hangup_cause": "NORMAL_CLEARING",
            },
            "callflow": [
                {
                    "caller_profile": {
                        "originatee": {
                            "originatee_caller_profiles": [{"destination_number": "22101005"}],
                        },
                    },
                },
            ],
        }
        resp = client.post(f"/api/telephony/cdr/ingest/{raw_token}", json=payload)
        assert resp.status_code == 201
        event = TelephonyEvent.query.filter_by(call_uuid="call-cdr-no-queue", event_type="CDR_RECORD_END").first()
        assert event.agent_login is None

    def test_ingest_cdr_manque_ne_cree_pas_d_evenement_answer(self, client, db, pbx_connector_with_cdr_token):
        _, raw_token = pbx_connector_with_cdr_token
        payload = {
            "variables": {
                "uuid": "call-cdr-missed",
                "start_epoch": "1700000000",
                "end_epoch": "1700000010",
                "hangup_cause": "NO_ANSWER",
            }
        }
        resp = client.post(f"/api/telephony/cdr/ingest/{raw_token}", json=payload)
        assert resp.status_code == 201
        events = TelephonyEvent.query.filter_by(call_uuid="call-cdr-missed").all()
        statuses = {e.call_status for e in events}
        assert "answered" not in statuses
        assert "missed" in statuses

    def test_ingest_cdr_forme_urlencodee(self, client, db, pbx_connector_with_cdr_token):
        """mod_xml_cdr historique poste parfois un champ 'cdr' urlencodé plutôt que du JSON brut."""
        import json as json_mod
        _, raw_token = pbx_connector_with_cdr_token
        payload = {"variables": {"uuid": "call-cdr-form", "start_epoch": "1700000000"}}
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            data={"cdr": json_mod.dumps(payload)},
        )
        assert resp.status_code == 201
        assert TelephonyEvent.query.filter_by(call_uuid="call-cdr-form").count() >= 1

    def test_ingest_cdr_corps_json_brut_sans_content_type(self, client, db, pbx_connector_with_cdr_token):
        """Reproduit le trafic FusionPBX réel observé le 28/07 : mod_json_cdr
        poste du JSON brut avec un Content-Type non reconnu par
        request.get_json() par défaut — le endpoint doit forcer le parsing."""
        import json as json_mod
        _, raw_token = pbx_connector_with_cdr_token
        payload = {"variables": {"uuid": "call-cdr-raw-body", "start_epoch": "1700000000"}}
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            data=json_mod.dumps(payload),
            content_type="text/plain",
        )
        assert resp.status_code == 201
        assert TelephonyEvent.query.filter_by(call_uuid="call-cdr-raw-body").count() >= 1

    def test_ingest_cdr_corps_urlencoded_sans_champ_nomme(self, client, db, pbx_connector_with_cdr_token):
        """Reproduit le trafic réel du 28/07 : Content-Type
        application/x-www-form-urlencoded (défaut libcurl POSTFIELDS) avec le
        JSON brut comme corps entier — sans '=' dans le JSON, Werkzeug le
        décode comme une clé de formulaire à valeur vide, pas comme une paire
        clé=valeur nommée 'cdr'."""
        import json as json_mod
        _, raw_token = pbx_connector_with_cdr_token
        payload = {"variables": {"uuid": "call-cdr-urlencoded-rawbody", "start_epoch": "1700000000"}}
        body = json_mod.dumps(payload, separators=(",", ":"))
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            data=body,
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 201
        assert TelephonyEvent.query.filter_by(call_uuid="call-cdr-urlencoded-rawbody").count() >= 1

    def test_ingest_cdr_corps_cdr_avec_caracteres_speciaux_non_echappes(
        self, client, db, pbx_connector_with_cdr_token,
    ):
        """Reproduit le trafic réel du 28/07 (3e tentative) : corps
        `cdr=<json>` en Content-Type urlencoded, mais le JSON contient des
        '&'/'=' littéraux non échappés (URI SIP, en-têtes...) — le parseur
        de formulaire de Werkzeug tronque la valeur au premier caractère
        litigieux, il faut donc extraire le JSON depuis le corps brut plutôt
        que faire confiance à request.form['cdr']."""
        import json as json_mod
        _, raw_token = pbx_connector_with_cdr_token
        payload = {
            "variables": {
                "uuid": "call-cdr-special-chars",
                "start_epoch": "1700000000",
                "sip_contact_uri": "sip:alice@10.0.0.5;transport=udp&x-fs-orig=abc",
            }
        }
        body = "cdr=" + json_mod.dumps(payload, separators=(",", ":"))
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            data=body,
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 201
        assert TelephonyEvent.query.filter_by(call_uuid="call-cdr-special-chars").count() >= 1

    def test_ingest_cdr_uuid_en_repli_depuis_la_query_string(self, client, db, pbx_connector_with_cdr_token):
        """FusionPBX ajoute `?uuid=<call-uuid>` à l'URL configurée — utilisé
        en repli si le corps ne porte pas l'UUID (observé en prod)."""
        _, raw_token = pbx_connector_with_cdr_token
        payload = {"variables": {"start_epoch": "1700000000"}}
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}?uuid=call-cdr-query-uuid",
            json=payload,
        )
        assert resp.status_code == 201
        assert TelephonyEvent.query.filter_by(call_uuid="call-cdr-query-uuid").count() >= 1

    def test_ingest_cdr_preserve_le_plus_dans_un_numero_e164(self, client, db, pbx_connector_with_cdr_token):
        """Encodeur type RFC 3986 (curl_easy_escape et consorts) qui laisse
        '+' littéral au lieu de l'encoder en %2B : unquote_plus (RFC 1866,
        '+' = espace) corromprait "+33612345678" en " 33612345678". unquote
        (tenté en premier) doit préserver le '+'."""
        import json as json_mod
        from urllib.parse import quote
        _, raw_token = pbx_connector_with_cdr_token
        payload = {
            "variables": {
                "uuid": "call-cdr-plus-e164",
                "start_epoch": "1700000000",
                "caller_id_number": "+33612345678",
            }
        }
        body_json = json_mod.dumps(payload)
        encoded_body = "cdr=" + quote(body_json, safe="+")
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            data=encoded_body,
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 201
        event = TelephonyEvent.query.filter_by(call_uuid="call-cdr-plus-e164").first()
        assert event.caller_number == "+33612345678"

    def test_ingest_cdr_corps_double_encode(self, client, db, pbx_connector_with_cdr_token):
        """Une couche intermédiaire (proxy, lib HTTP) ré-encode un corps déjà
        URL-encodé : un seul passage de unquote ne suffit pas à faire
        réapparaître les '{'/'}' littéraux."""
        import json as json_mod
        from urllib.parse import quote
        _, raw_token = pbx_connector_with_cdr_token
        payload = {"variables": {"uuid": "call-cdr-double-encoded", "start_epoch": "1700000000"}}
        body_json = json_mod.dumps(payload)
        once = "cdr=" + quote(body_json, safe="")
        twice = quote(once, safe="")
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            data=twice,
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 201
        assert TelephonyEvent.query.filter_by(call_uuid="call-cdr-double-encoded").count() >= 1

    def test_ingest_cdr_tolere_les_caracteres_de_controle_bruts(self, client, db, pbx_connector_with_cdr_token):
        """Reproduit le trafic réel du 28/07 (5e round) : le corps décode
        correctement (single-pass unquote, bornes '{'/'}' correctes), mais
        json.loads strict rejette le JSON à cause de caractères de contrôle
        bruts (non échappés) dans une valeur de chaîne — typique d'un dump
        FusionPBX de variables de canal incluant des en-têtes SIP
        multi-lignes. strict=False doit tolérer ça plutôt que de tout rejeter."""
        from urllib.parse import quote
        _, raw_token = pbx_connector_with_cdr_token
        # Construit un JSON syntaxiquement valide SAUF pour une tabulation
        # brute (non échappée en \t) dans une valeur de chaîne — json.dumps()
        # échapperait proprement ce caractère, donc construit à la main pour
        # reproduire fidèlement la non-conformité observée en prod.
        raw_json = (
            '{"variables":{"uuid":"call-cdr-ctrl-char","start_epoch":"1700000000",'
            '"sip_header":"foo\tbar"}}'
        )
        body = "cdr=" + quote(raw_json, safe="")
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            data=body,
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 201
        assert TelephonyEvent.query.filter_by(call_uuid="call-cdr-ctrl-char").count() >= 1

    def test_ingest_cdr_repare_les_guillemets_non_echappes_dans_un_en_tete_sip(
        self, client, db, pbx_connector_with_cdr_token,
    ):
        """Reproduit le trafic réel du 28/07 (6e round, root cause enfin
        identifiée via le diagnostic position/ligne/colonne) : FusionPBX
        interpole l'en-tête SIP `From` brut (`"Display Name" <sip:...>;tag=...`)
        dans le JSON sans échapper les guillemets internes du nom
        d'affichage — JSON syntaxiquement invalide, indépendant de tout
        problème de décodage/encodage. _repair_unescaped_quotes doit
        récupérer un JSON exploitable plutôt que de tout rejeter."""
        from urllib.parse import quote
        _, raw_token = pbx_connector_with_cdr_token
        # Guillemets internes non échappés, exactement comme observé en
        # prod : json.dumps() échapperait proprement, donc construit à la
        # main pour reproduire fidèlement la non-conformité réelle.
        raw_json = (
            '{"variables":{"uuid":"call-cdr-sip-quotes","start_epoch":"1700000000",'
            '"sip_full_from":""33186569392" <sip:33186569392@146.190.232.155>;tag=QmD7B1caeNDBa",'
            '"sip_full_to":"<sip:50000767728320@sbc.maniterm.com:5080>"}}'
        )
        body = "cdr=" + quote(raw_json, safe="")
        resp = client.post(
            f"/api/telephony/cdr/ingest/{raw_token}",
            data=body,
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 201
        assert TelephonyEvent.query.filter_by(call_uuid="call-cdr-sip-quotes").count() >= 1

    def test_ingest_cdr_mode_trace_actif_ne_casse_pas_l_ingestion(self, client, db, pbx_connector_with_cdr_token):
        """TELEPHONY_CDR_TRACE=true (activé le temps d'un appel de test réel,
        cf. TELEPHONIE_INTEGRATION_PLAN.md) journalise l'inventaire complet
        des variables et écrit le payload dans un fichier — ne doit jamais
        faire échouer l'ingestion, même si l'écriture fichier échoue."""
        _, raw_token = pbx_connector_with_cdr_token
        app = client.application
        app.config["TELEPHONY_CDR_TRACE"] = True
        try:
            payload = {
                "variables": {"uuid": "call-cdr-trace-mode", "start_epoch": "1700000000"},
                "app_log": {"applications": []},
            }
            resp = client.post(f"/api/telephony/cdr/ingest/{raw_token}", json=payload)
        finally:
            app.config["TELEPHONY_CDR_TRACE"] = False
        assert resp.status_code == 201
        assert TelephonyEvent.query.filter_by(call_uuid="call-cdr-trace-mode").count() >= 1


class TestCdrTokenRegenerate:
    def test_refuse_sans_droit_admin_tenant(self, client, auth_headers, pbx_connector):
        resp = client.post(f"/api/telephony/connectors/{pbx_connector.id}/cdr-token/regenerate", headers=auth_headers)
        assert resp.status_code == 403

    def test_regenere_le_token(self, client, db, auth_headers_admin, pbx_connector_with_cdr_token):
        connector, old_raw_token = pbx_connector_with_cdr_token
        old_hash = connector.cdr_webhook_token_hash

        resp = client.post(
            f"/api/telephony/connectors/{connector.id}/cdr-token/regenerate", headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["cdr_webhook_token"] is not None
        assert data["cdr_webhook_token"] != old_raw_token

        db.session.refresh(connector)
        assert connector.cdr_webhook_token_hash != old_hash

        # L'ancien jeton n'est plus valide.
        resp2 = client.post(f"/api/telephony/cdr/ingest/{old_raw_token}", json={"variables": {"uuid": "x"}})
        assert resp2.status_code == 404


class TestCallsHistory:
    """GET /api/telephony/calls — historique paginé/filtrable (Rapports > Téléphonie)."""

    def _seed_completed_call(self, db, tenant_id, call_uuid, status="ended", agent_login="agent01",
                              queue_id="queue-support", recording_url=None, base=None):
        base = base or (datetime.utcnow() - timedelta(minutes=10))
        db.session.add(TelephonyEvent(
            tenant_id=tenant_id, event_type="CHANNEL_CREATE", call_status="ringing",
            call_uuid=call_uuid, caller_number="0611111111", callee_number="0622222222",
            call_direction="inbound", created_at=base,
        ))
        db.session.add(TelephonyEvent(
            tenant_id=tenant_id, event_type="CHANNEL_ANSWER", call_status="answered",
            call_uuid=call_uuid, agent_login=agent_login, queue_id=queue_id, created_at=base + timedelta(seconds=5),
        ))
        db.session.add(TelephonyEvent(
            tenant_id=tenant_id, event_type="CHANNEL_HANGUP_COMPLETE", call_status=status,
            call_uuid=call_uuid, agent_login=agent_login, queue_id=queue_id, duration=42,
            recording_url=recording_url, created_at=base + timedelta(seconds=50),
        ))
        db.session.commit()

    def test_liste_les_appels_termines(self, client, db, auth_headers, default_tenant):
        self._seed_completed_call(db, default_tenant.id, "hist-1")
        resp = client.get("/api/telephony/calls", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["calls"][0]["call_uuid"] == "hist-1"
        assert data["calls"][0]["call_status"] == "ended"

    def test_exclut_les_appels_en_cours(self, client, db, auth_headers, default_tenant):
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, event_type="CHANNEL_CREATE", call_status="ringing",
            call_uuid="hist-en-cours", created_at=datetime.utcnow(),
        ))
        db.session.commit()
        resp = client.get("/api/telephony/calls", headers=auth_headers)
        assert resp.get_json()["total"] == 0

    def test_filtre_par_statut(self, client, db, auth_headers, default_tenant):
        self._seed_completed_call(db, default_tenant.id, "hist-answered", status="ended")
        self._seed_completed_call(db, default_tenant.id, "hist-missed", status="missed")
        resp = client.get("/api/telephony/calls?call_status=missed", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] == 1
        assert data["calls"][0]["call_uuid"] == "hist-missed"

    def test_pagination(self, client, db, auth_headers, default_tenant):
        for i in range(5):
            self._seed_completed_call(
                db, default_tenant.id, f"hist-page-{i}", base=datetime.utcnow() - timedelta(minutes=i + 10),
            )
        resp = client.get("/api/telephony/calls?page=1&per_page=2", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] == 5
        assert len(data["calls"]) == 2

    def test_isolation_cross_tenant(self, client, db, auth_headers, default_tenant):
        other_tenant = Tenant(code="OTHER3", nom="Autre Tenant 3", slug="other3")
        db.session.add(other_tenant)
        db.session.commit()
        self._seed_completed_call(db, other_tenant.id, "hist-autre-tenant")

        resp = client.get("/api/telephony/calls", headers=auth_headers)
        uuids = [c["call_uuid"] for c in resp.get_json()["calls"]]
        assert "hist-autre-tenant" not in uuids


class TestCallsExport:
    def test_export_csv_retourne_un_fichier_csv(self, client, db, auth_headers, default_tenant):
        TestCallsHistory()._seed_completed_call(db, default_tenant.id, "export-1")
        resp = client.get("/api/telephony/calls/export", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.mimetype == "text/csv"
        body = resp.get_data(as_text=True)
        assert "call_uuid" in body.splitlines()[0]
        assert "export-1" in body


class TestRecordings:
    def test_liste_uniquement_les_appels_avec_enregistrement(self, client, db, auth_headers, default_tenant):
        TestCallsHistory()._seed_completed_call(db, default_tenant.id, "rec-none")
        TestCallsHistory()._seed_completed_call(
            db, default_tenant.id, "rec-1", recording_url="https://pbx.example.com/rec/rec-1.wav",
        )
        resp = client.get("/api/telephony/recordings", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] == 1
        assert data["recordings"][0]["call_uuid"] == "rec-1"
        assert data["recordings"][0]["recording_available"] is True

    def test_chemin_local_marque_indisponible(self, client, db, auth_headers, default_tenant):
        TestCallsHistory()._seed_completed_call(
            db, default_tenant.id, "rec-local", recording_url="/var/lib/freeswitch/recordings/rec-local.wav",
        )
        resp = client.get("/api/telephony/recordings", headers=auth_headers)
        data = resp.get_json()
        assert data["recordings"][0]["recording_available"] is False

    def test_download_chemin_local_retourne_422(self, client, db, auth_headers, default_tenant):
        TestCallsHistory()._seed_completed_call(
            db, default_tenant.id, "rec-dl-local", recording_url="/var/lib/freeswitch/recordings/x.wav",
        )
        resp = client.get("/api/telephony/recordings/rec-dl-local/download", headers=auth_headers)
        assert resp.status_code == 422

    def test_download_introuvable_retourne_404(self, client, db, auth_headers):
        resp = client.get("/api/telephony/recordings/inconnu/download", headers=auth_headers)
        assert resp.status_code == 404

    def test_bulk_export_sans_enregistrement_disponible_retourne_zip_avec_manifeste(
        self, client, db, auth_headers, default_tenant,
    ):
        import zipfile, io as io_mod
        TestCallsHistory()._seed_completed_call(
            db, default_tenant.id, "rec-bulk-local", recording_url="/local/path/x.wav",
        )
        resp = client.post("/api/telephony/recordings/export", json={}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.mimetype == "application/zip"
        zf = zipfile.ZipFile(io_mod.BytesIO(resp.get_data()))
        assert "_indisponibles.txt" in zf.namelist()

    def test_bulk_export_aucune_correspondance_retourne_404(self, client, db, auth_headers):
        resp = client.post("/api/telephony/recordings/export", json={}, headers=auth_headers)
        assert resp.status_code == 404
