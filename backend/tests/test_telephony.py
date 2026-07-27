import pytest
from datetime import datetime, timedelta

from app.models import PbxConnector, PbxDomainTenant, TelephonyEvent
from app.models.tenant import Tenant


@pytest.fixture
def pbx_connector(db):
    c = PbxConnector(name="FusionPBX Prod", type="ESL", host="pbx.local", port=8021, is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture
def pbx_binding(db, pbx_connector, default_tenant):
    b = PbxDomainTenant(
        pbx_connector_id=pbx_connector.id,
        pbx_domain="tenant-core.permatel.local",
        tenant_id=default_tenant.id,
        queue_ids=["queue-support"],
    )
    db.session.add(b)
    db.session.commit()
    return b


CONNECTOR_TOKEN_HEADERS = {"X-Connector-Token": "test-connector-token"}


class TestIngestEvent:
    """POST /api/telephony/events/ingest — auth par jeton technique, pas de JWT."""

    def test_ingest_sans_token_retourne_401(self, client, pbx_binding):
        resp = client.post("/api/telephony/events/ingest", json={
            "pbx_domain": pbx_binding.pbx_domain, "event_type": "CHANNEL_CREATE",
        })
        assert resp.status_code == 401

    def test_ingest_mauvais_token_retourne_401(self, client, pbx_binding):
        resp = client.post(
            "/api/telephony/events/ingest",
            json={"pbx_domain": pbx_binding.pbx_domain, "event_type": "CHANNEL_CREATE"},
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

    def test_ingest_evenement_valide_persiste_et_resout_tenant(self, client, db, pbx_binding, default_tenant):
        payload = {
            "event_type": "CHANNEL_CREATE",
            "pbx_domain": pbx_binding.pbx_domain,
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
        assert event.pbx_connector_id == pbx_binding.pbx_connector_id
        assert event.event_type == "CHANNEL_CREATE"
        assert event.call_status == "ringing"
        assert event.agent_login == "agent01"
        assert event.queue_id == "queue-support"
        assert event.raw_payload == payload


class TestBootstrapConfig:
    """GET /api/telephony/connectors/config — bootstrap consommé par le Core Connector."""

    def test_sans_token_retourne_401(self, client, pbx_binding):
        resp = client.get("/api/telephony/connectors/config")
        assert resp.status_code == 401

    def test_mauvais_token_retourne_401(self, client, pbx_binding):
        resp = client.get(
            "/api/telephony/connectors/config",
            headers={"X-Connector-Token": "wrong-token"},
        )
        assert resp.status_code == 401

    def test_retourne_connecteurs_actifs_avec_secrets_et_domaines(
        self, client, db, pbx_connector, pbx_binding, default_tenant
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
        assert c["password"] == "esl_secret"
        assert len(c["domains"]) == 1
        assert c["domains"][0]["pbx_domain"] == pbx_binding.pbx_domain
        assert c["domains"][0]["tenant_id"] == str(default_tenant.id)
        assert c["domains"][0]["queue_ids"] == ["queue-support"]

    def test_exclut_les_connecteurs_inactifs(self, client, db, pbx_connector):
        pbx_connector.is_active = False
        db.session.commit()

        resp = client.get("/api/telephony/connectors/config", headers=CONNECTOR_TOKEN_HEADERS)
        assert resp.status_code == 200
        assert resp.get_json()["connectors"] == []


class TestActiveCalls:
    def test_active_calls_exclut_les_appels_termines(self, client, db, auth_headers, pbx_binding, default_tenant):
        # Appel en cours (dernier évènement = ringing)
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_binding.pbx_connector_id,
            event_type="CHANNEL_CREATE", call_status="ringing", call_uuid="call-active",
            created_at=datetime.utcnow(),
        ))
        # Appel terminé (dernier évènement = ended)
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_binding.pbx_connector_id,
            event_type="CHANNEL_CREATE", call_status="ringing", call_uuid="call-done",
            created_at=datetime.utcnow() - timedelta(seconds=30),
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, pbx_connector_id=pbx_binding.pbx_connector_id,
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
    def test_kpis_summary_calcule_taux_decroche(self, client, db, auth_headers, pbx_binding, default_tenant):
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


class TestConnectorsAdmin:
    """CRUD /api/telephony/connectors — ressource globale, ADMIN uniquement."""

    def test_liste_refusee_sans_role_admin(self, client, auth_headers):
        resp = client.get("/api/telephony/connectors", headers=auth_headers)
        assert resp.status_code == 403

    def test_create_update_delete_connector(self, client, auth_headers_admin, db):
        payload = {"name": "Asterisk Test", "type": "AMI", "host": "ast.local", "port": 5038, "password": "secret"}
        resp = client.post("/api/telephony/connectors", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Asterisk Test"
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

    def test_create_domain_binding(self, client, auth_headers_admin, pbx_connector, default_tenant):
        payload = {"pbx_domain": "new.permatel.local", "tenant_id": str(default_tenant.id), "queue_ids": ["q1"]}
        resp = client.post(f"/api/telephony/connectors/{pbx_connector.id}/domains", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 201
        assert resp.get_json()["pbx_domain"] == "new.permatel.local"

    def test_create_domain_binding_duplique_retourne_409(self, client, auth_headers_admin, pbx_binding):
        payload = {"pbx_domain": pbx_binding.pbx_domain, "tenant_id": str(pbx_binding.tenant_id)}
        resp = client.post(
            f"/api/telephony/connectors/{pbx_binding.pbx_connector_id}/domains",
            json=payload, headers=auth_headers_admin,
        )
        assert resp.status_code == 409


class TestTenantSettings:
    """GET /api/telephony/settings + PUT .../queues — tenant_admin_required."""

    def test_get_settings_retourne_les_rattachements_du_tenant(self, client, auth_headers, pbx_binding):
        resp = client.get("/api/telephony/settings", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["pbx_domain"] == pbx_binding.pbx_domain
        assert data[0]["connector_type"] == "ESL"

    def test_update_queues_refuse_sans_droit_admin_tenant(self, client, auth_headers, pbx_binding):
        resp = client.put(
            f"/api/telephony/settings/{pbx_binding.id}/queues",
            json={"queue_ids": ["a", "b"]},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_update_queues_par_admin_global(self, client, auth_headers_admin, pbx_binding, db):
        resp = client.put(
            f"/api/telephony/settings/{pbx_binding.id}/queues",
            json={"queue_ids": ["a", "b"]},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        assert resp.get_json()["queue_ids"] == ["a", "b"]

    def test_isolation_cross_tenant_sur_queues(self, client, db, auth_headers_admin, pbx_connector, default_tenant):
        """Un rattachement d'un AUTRE tenant n'est pas modifiable via l'admin
        global connecté sur default_tenant (tenant actif != tenant du binding)."""
        other_tenant = Tenant(code="OTHER", nom="Autre Tenant", slug="other")
        db.session.add(other_tenant)
        db.session.commit()

        other_binding = PbxDomainTenant(
            pbx_connector_id=pbx_connector.id,
            pbx_domain="other.permatel.local",
            tenant_id=other_tenant.id,
        )
        db.session.add(other_binding)
        db.session.commit()

        resp = client.put(
            f"/api/telephony/settings/{other_binding.id}/queues",
            json={"queue_ids": ["x"]},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404
