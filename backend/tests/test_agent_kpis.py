import pytest
from app.models.agent_securite import AgentSecurite
from app.routes import agents_securite as agents_securite_route


@pytest.fixture
def auth_headers_manager_tenant(client, user_manager, default_tenant):
    resp_login = client.post("/api/auth/login", json={
        "username": user_manager.username,
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
def deux_agents(db, default_tenant, agent_securite):
    """agent_securite (fixture conftest) + un second agent, tous deux actifs."""
    agent2 = AgentSecurite(
        matricule="AGENT002", nom="Deuxième", prenom="Agent",
        tenant_id=default_tenant.id, is_active=True,
    )
    db.session.add(agent2)
    db.session.commit()
    return [agent_securite, agent2]


class TestAgentsKpisListNPlusOne:

    def test_agents_kpis_list_appelle_discriminant_codes_une_seule_fois(
        self, client, auth_headers_manager_tenant, deux_agents, monkeypatch,
    ):
        """Avant le correctif, `discriminant_codes` était rechargée pour chaque
        agent (N+1). Elle doit maintenant être calculée une seule fois pour tout
        le classement, quel que soit le nombre d'agents."""
        call_count = {"n": 0}
        original = agents_securite_route.discriminant_codes

        def counting_wrapper(tenant_id):
            call_count["n"] += 1
            return original(tenant_id)

        monkeypatch.setattr(agents_securite_route, "discriminant_codes", counting_wrapper)

        resp = client.get("/api/agents/kpis", headers=auth_headers_manager_tenant)
        assert resp.status_code == 200
        assert call_count["n"] == 1

    def test_agents_kpis_list_retourne_un_agent_par_ligne(
        self, client, auth_headers_manager_tenant, deux_agents,
    ):
        resp = client.get("/api/agents/kpis", headers=auth_headers_manager_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["agents"]) == 2

    def test_agents_kpis_list_isolation_tenant(
        self, client, auth_headers_manager_tenant, deux_agents, db,
    ):
        """Smoke test tenant-scoping : un agent d'un autre tenant n'apparaît pas."""
        from app.models.tenant import Tenant
        other_tenant = Tenant(nom="Autre Tenant Agents", code="OTHAG", slug="othag")
        db.session.add(other_tenant)
        db.session.commit()
        other_agent = AgentSecurite(
            matricule="LEAK", nom="Fuite", prenom="Agent",
            tenant_id=other_tenant.id, is_active=True,
        )
        db.session.add(other_agent)
        db.session.commit()

        resp = client.get("/api/agents/kpis", headers=auth_headers_manager_tenant)
        assert resp.status_code == 200
        matricules = {a["matricule"] for a in resp.get_json()["agents"]}
        assert "LEAK" not in matricules
