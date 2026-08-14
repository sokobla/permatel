import csv
import io
from datetime import datetime, timedelta

import pytest
from app.models.client import Client
from app.models.prise_de_service import PriseDeService


@pytest.fixture
def auth_headers_tenant(client, user_permanencier, default_tenant):
    resp_login = client.post("/api/auth/login", json={
        "username": user_permanencier.username,
        "password": "Password123!",
    })
    token = resp_login.get_json()["access_token"]
    resp_tenant = client.post(
        "/api/auth/select-tenant",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": str(default_tenant.id)},
    )
    return {"Authorization": f"Bearer {resp_tenant.get_json()['access_token']}"}


@pytest.fixture
def client_pds(db, default_tenant):
    c = Client(nom="Client PDS", code_client="CLIPDS", tenant_id=default_tenant.id)
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture
def prises_echelonnees(db, default_tenant, agent_securite, client_pds):
    """Crée 3 prises de service avec des date_debut distincts."""
    now = datetime.utcnow()
    rows = []
    for days_ago in [60, 15, 1]:
        p = PriseDeService(
            tenant_id=default_tenant.id,
            agent_id=agent_securite.id,
            client_id=client_pds.id,
            date_debut=now - timedelta(days=days_ago),
            date_fin=now - timedelta(days=days_ago) + timedelta(hours=8),
        )
        db.session.add(p)
        rows.append(p)
    db.session.commit()
    return rows


class TestPrisesDeServiceDateFilterAndExport:

    def test_list_filtree_par_from(self, client, auth_headers_tenant, prises_echelonnees):
        cutoff = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%d")
        resp = client.get(f"/api/prises-de-service?from={cutoff}", headers=auth_headers_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2

    def test_list_filtree_par_to(self, client, auth_headers_tenant, prises_echelonnees):
        cutoff = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%d")
        resp = client.get(f"/api/prises-de-service?to={cutoff}", headers=auth_headers_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1

    def test_export_csv(self, client, auth_headers_tenant, prises_echelonnees):
        resp = client.get("/api/prises-de-service/export", headers=auth_headers_tenant)
        assert resp.status_code == 200
        assert resp.mimetype == "text/csv"
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        assert rows[0] == [
            "date", "agent", "type_agent", "client", "site",
            "heure_debut", "declare_debut_par", "heure_fin", "declare_fin_par", "duree_minutes",
        ]
        assert len(rows) - 1 == 3

    def test_export_csv_filtre_par_date(self, client, auth_headers_tenant, prises_echelonnees):
        cutoff = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%d")
        resp = client.get(f"/api/prises-de-service/export?from={cutoff}", headers=auth_headers_tenant)
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        assert len(rows) - 1 == 2


class TestPrisesDeServiceDeclarants:
    """Rapport détaillé (14/08) : `agent_type` + qui a déclaré le début/la
    fin d'une vacation (nom/prénom PERMATEL)."""

    def test_start_enregistre_created_by(
        self, client, db, auth_headers_tenant, user_permanencier, agent_securite, client_pds,
    ):
        agent_securite.type_agent = "Chef d'équipe"
        db.session.commit()
        resp = client.post(
            "/api/prises-de-service/start",
            json={"agent_id": agent_securite.id, "client_id": client_pds.id},
            headers=auth_headers_tenant,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["agent_type"] == "Chef d'équipe"
        assert data["created_by_name"] == f"{user_permanencier.prenom} {user_permanencier.nom}"
        assert data["ended_by_name"] is None

    def test_end_enregistre_ended_by(
        self, client, db, auth_headers_tenant, user_permanencier, agent_securite, client_pds,
    ):
        client.post(
            "/api/prises-de-service/start",
            json={"agent_id": agent_securite.id, "client_id": client_pds.id},
            headers=auth_headers_tenant,
        )
        resp = client.post(
            "/api/prises-de-service/end", json={"agent_id": agent_securite.id}, headers=auth_headers_tenant,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ended_by_name"] == f"{user_permanencier.prenom} {user_permanencier.nom}"

    def test_end_by_id_enregistre_ended_by(
        self, client, db, auth_headers_tenant, user_permanencier, agent_securite, client_pds,
    ):
        start_resp = client.post(
            "/api/prises-de-service/start",
            json={"agent_id": agent_securite.id, "client_id": client_pds.id},
            headers=auth_headers_tenant,
        )
        pds_id = start_resp.get_json()["id"]
        resp = client.post(f"/api/prises-de-service/{pds_id}/end", headers=auth_headers_tenant)
        assert resp.status_code == 200
        assert resp.get_json()["ended_by_name"] == f"{user_permanencier.prenom} {user_permanencier.nom}"

    def test_declare_debut_par_et_fin_par_dans_le_csv(
        self, client, db, auth_headers_tenant, user_permanencier, agent_securite, client_pds,
    ):
        client.post(
            "/api/prises-de-service/start",
            json={"agent_id": agent_securite.id, "client_id": client_pds.id},
            headers=auth_headers_tenant,
        )
        client.post(
            "/api/prises-de-service/end", json={"agent_id": agent_securite.id}, headers=auth_headers_tenant,
        )
        resp = client.get("/api/prises-de-service/export", headers=auth_headers_tenant)
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        full_name = f"{user_permanencier.prenom} {user_permanencier.nom}"
        row = rows[1]
        assert row[6] == full_name  # declare_debut_par
        assert row[8] == full_name  # declare_fin_par
