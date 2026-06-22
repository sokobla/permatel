"""
Tests d'isolation multi-tenant & RBAC (A7).

Couvre :
  - cross-tenant : un utilisateur du tenant A n'accède pas aux ressources du
    tenant B (→ 404, jamais 200/403 révélateur) ;
  - RBAC : rôle insuffisant → 403 ;
  - contexte tenant manquant (pas de `tid`) → 401 ;
  - super-admin global : bypass d'appartenance (accède à tout tenant actif) ;
  - capacité d'admin de tenant requise pour la gestion du roster.
"""
import pytest

from app.models.client import Client
from app.models.tenant import Tenant

PWD = "Password123!"


def _login(client, username, password=PWD):
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).get_json()


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures locales : 2e tenant + une ressource dans chaque tenant ──────────
@pytest.fixture
def tenant_b(db):
    t = Tenant(code="TENB", nom="Tenant B", slug="tenant-b")
    db.session.add(t)
    db.session.commit()
    return t


@pytest.fixture
def client_core(db, default_tenant):
    c = Client(nom="Client CORE", code_client="C-CORE", tenant_id=default_tenant.id)
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture
def client_b(db, tenant_b):
    c = Client(nom="Client B", code_client="C-B", tenant_id=tenant_b.id)
    db.session.add(c)
    db.session.commit()
    return c


# ── Isolation cross-tenant ───────────────────────────────────────────────────
def test_acces_ressource_propre_tenant_ok(client, db, user_manager, client_core):
    h = _bearer(_login(client, "manager1")["access_token"])
    assert client.get(f"/api/clients/{client_core.id}", headers=h).status_code == 200


def test_cross_tenant_get_renvoie_404(client, db, user_manager, client_core, client_b):
    """Une ressource d'un autre tenant doit être indistinguable d'une inexistante."""
    h = _bearer(_login(client, "manager1")["access_token"])
    assert client.get(f"/api/clients/{client_b.id}", headers=h).status_code == 404


def test_cross_tenant_update_renvoie_404(client, db, user_manager, client_b):
    h = _bearer(_login(client, "manager1")["access_token"])
    resp = client.put(
        f"/api/clients/{client_b.id}", json={"nom": "Pirate"}, headers=h
    )
    assert resp.status_code == 404


# ── RBAC (rôle insuffisant) ──────────────────────────────────────────────────
def test_permanencier_ne_peut_pas_creer_client(client, db, user_permanencier):
    h = _bearer(_login(client, "permanencier1")["access_token"])
    resp = client.post(
        "/api/clients", json={"nom": "X", "code_client": "X1"}, headers=h
    )
    assert resp.status_code == 403


def test_permanencier_refuse_sur_tenants(client, db, user_permanencier):
    h = _bearer(_login(client, "permanencier1")["access_token"])
    assert client.get("/api/tenants", headers=h).status_code == 403


def test_manager_refuse_sur_users(client, db, user_manager):
    h = _bearer(_login(client, "manager1")["access_token"])
    assert client.get("/api/users", headers=h).status_code == 403


def test_membre_simple_refuse_sur_roster(client, db, user_permanencier):
    """Un membre non-admin n'accède pas à la gestion du roster du tenant."""
    h = _bearer(_login(client, "permanencier1")["access_token"])
    assert client.get("/api/tenant/members", headers=h).status_code == 403


# ── Contexte tenant manquant ─────────────────────────────────────────────────
def test_sans_tenant_actif_renvoie_401(client, db, user_admin):
    """Le super-admin n'a pas de tid auto → route tenant-scopée = 401."""
    data = _login(client, "admin1")
    assert data["active_tenant_id"] is None
    h = _bearer(data["access_token"])
    assert client.get("/api/clients", headers=h).status_code == 401


# ── Super-admin global : bypass d'appartenance ───────────────────────────────
def test_super_admin_bypass_appartenance(client, db, user_admin, tenant_b, client_b, client_core):
    """L'admin global accède au tenant B sans y être membre, scope respecté."""
    data = _login(client, "admin1")
    sel = client.post(
        "/api/auth/select-tenant",
        json={"tenant_id": str(tenant_b.id)},
        headers=_bearer(data["access_token"]),
    ).get_json()
    h = _bearer(sel["access_token"])
    # accède à une ressource de B (dont il n'est pas membre)
    assert client.get(f"/api/clients/{client_b.id}", headers=h).status_code == 200
    # mais reste scopé à B : la ressource de CORE n'est pas visible
    assert client.get(f"/api/clients/{client_core.id}", headers=h).status_code == 404
    # et il administre le roster (super-admin = tenant_admin partout)
    assert client.get("/api/tenant/members", headers=h).status_code == 200
