import pytest
from app.models.tenant import Tenant
from app.models.tenant_user import TenantUser


# ══════════════════════════════════════════════════════════════
#  FIXTURES LOCALES
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def admin_headers(client, user_admin):
    """Fournit les headers d'authentification pour un administrateur."""
    resp = client.post("/api/auth/login", json={
        "username": "admin1",
        "password": "Password123!"
    })
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def permanencier_headers(client, user_permanencier):
    """Fournit les headers d'authentification pour un permanencier."""
    resp = client.post("/api/auth/login", json={
        "username": "permanencier1",
        "password": "Password123!"
    })
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ══════════════════════════════════════════════════════════════
#  TESTS CRUD TENANT
# ══════════════════════════════════════════════════════════════

def test_list_tenants_success(client, admin_headers, default_tenant):
    """Lister les tenants retourne 200 pour un admin."""
    resp = client.get("/api/tenants", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    
    assert len(data) >= 1
    # default_tenant créé par conftest
    assert any(t["slug"] == default_tenant.slug for t in data)


def test_create_tenant_success(client, admin_headers):
    """Création valide d'un tenant."""
    payload = {"nom": "Nouveau Tenant", "slug": "nouveau-tenant-1", "code": "NT1"}
    resp = client.post("/api/tenants", json=payload, headers=admin_headers)
    
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["nom"] == "Nouveau Tenant"
    assert data["slug"] == "nouveau-tenant-1"
    assert data["is_active"] is True


def test_create_tenant_invalid_slug(client, admin_headers):
    """La création échoue (422) si le slug contient des caractères non autorisés."""
    payload = {"nom": "Tenant Invalide", "slug": "Slug_Invalide@!", "code": "TI1"}
    resp = client.post("/api/tenants", json=payload, headers=admin_headers)
    
    assert resp.status_code == 422
    assert "minuscules" in resp.get_json()["error"]


def test_create_tenant_duplicate_slug(client, admin_headers, default_tenant):
    """La création échoue (409) si le slug est déjà utilisé."""
    payload = {"nom": "Copie", "slug": default_tenant.slug, "code": "CP1"}
    resp = client.post("/api/tenants", json=payload, headers=admin_headers)
    
    assert resp.status_code == 409
    assert "déjà utilisé" in resp.get_json()["error"]


def test_update_tenant_success(client, admin_headers, db):
    """Mise à jour d'un tenant existant."""
    tenant = Tenant(nom="A modifier", slug="a-modifier", code="AMOD")
    db.session.add(tenant)
    db.session.commit()

    payload = {"nom": "Nom Modifié", "slug": "nom-modifie", "is_active": False}
    resp = client.put(f"/api/tenants/{tenant.id}", json=payload, headers=admin_headers)
    
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["nom"] == "Nom Modifié"
    assert data["slug"] == "nom-modifie"
    assert data["is_active"] is False


def test_delete_tenant_with_users_fails(client, admin_headers, default_tenant, user_admin):
    """La suppression échoue (409) si des utilisateurs sont encore rattachés."""
    # default_tenant contient déjà des utilisateurs rattachés (via conftest)
    resp = client.delete(f"/api/tenants/{default_tenant.id}", headers=admin_headers)
    
    assert resp.status_code == 409
    assert "utilisateur" in resp.get_json()["error"]


def test_delete_tenant_success(client, admin_headers, db):
    """La suppression réussit (200) si le tenant est vide."""
    tenant = Tenant(nom="A supprimer", slug="a-supprimer", code="ASUP")
    db.session.add(tenant)
    db.session.commit()

    resp = client.delete(f"/api/tenants/{tenant.id}", headers=admin_headers)
    assert resp.status_code == 200
    
    # Vérifier que le tenant n'existe plus
    assert Tenant.query.get(tenant.id) is None


# ══════════════════════════════════════════════════════════════
#  TESTS GESTION DES UTILISATEURS DANS UN TENANT
# ══════════════════════════════════════════════════════════════

def test_add_user_to_tenant_success(client, admin_headers, db, user_inactive):
    """Rattachement valide d'un utilisateur existant à un tenant."""
    tenant = Tenant(nom="Nouveau Groupe", slug="groupe", code="NG1")
    db.session.add(tenant)
    db.session.commit()

    payload = {"user_id": user_inactive.id, "role": "manager"}
    resp = client.post(f"/api/tenants/{tenant.id}/users", json=payload, headers=admin_headers)
    
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["role"] == "manager"

    # Le rattachement en double doit échouer
    resp_dup = client.post(f"/api/tenants/{tenant.id}/users", json=payload, headers=admin_headers)
    assert resp_dup.status_code == 409


def test_add_user_invalid_role(client, admin_headers, default_tenant, user_inactive):
    """Le rattachement échoue (422) si le rôle fourni est invalide."""
    payload = {"user_id": user_inactive.id, "role": "super-hacker"}
    resp = client.post(f"/api/tenants/{default_tenant.id}/users", json=payload, headers=admin_headers)
    
    assert resp.status_code == 422
    assert "Rôle invalide" in resp.get_json()["error"]


def test_update_tenant_user_success(client, admin_headers, default_tenant, user_admin):
    """Mise à jour du rôle/statut d'un utilisateur au sein d'un tenant."""
    # user_admin est déjà rattaché à default_tenant
    payload = {"role": "manager", "is_active": False}
    resp = client.put(f"/api/tenants/{default_tenant.id}/users/{user_admin.id}", json=payload, headers=admin_headers)
    
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["role"] == "manager"
    assert data["is_active"] is False


def test_remove_tenant_user_success(client, admin_headers, default_tenant, user_inactive):
    """Détachement d'un utilisateur avec succès."""
    # Rattachement préalable
    client.post(f"/api/tenants/{default_tenant.id}/users", 
                json={"user_id": user_inactive.id, "role": "permanencier"}, 
                headers=admin_headers)

    # Détachement
    resp = client.delete(f"/api/tenants/{default_tenant.id}/users/{user_inactive.id}", headers=admin_headers)
    assert resp.status_code == 200

    # Vérifier que le lien n'existe plus (2ème tentative = 404)
    resp2 = client.delete(f"/api/tenants/{default_tenant.id}/users/{user_inactive.id}", headers=admin_headers)
    assert resp2.status_code == 404


# ══════════════════════════════════════════════════════════════
#  TESTS D'AUTORISATIONS DE RÔLE (RBAC)
# ══════════════════════════════════════════════════════════════
def test_non_admin_access_denied(client, permanencier_headers):
    """Un permanencier (non-admin) obtient une erreur 403 sur ces routes."""
    resp = client.get("/api/tenants", headers=permanencier_headers)
    assert resp.status_code == 403