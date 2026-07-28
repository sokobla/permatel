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

        resp2 = client.put(
            f"/api/telephony/connectors/{pbx_connector.id}/domains/{domain_id}",
            json={"queue_ids": ["a", "b"]},
            headers=auth_headers_admin,
        )
        assert resp2.status_code == 200
        assert resp2.get_json()["queue_ids"] == ["a", "b"]

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
