import pytest
from app.models import Demande, DemandeAnomalie, Client, Site, Contact, Tenant, TenantUser, TypeDemande, StatutDemande

# ============================================================================
# FIXTURES LOCALES
# ============================================================================

@pytest.fixture
def auth_headers_tenant(client, user_permanencier, default_tenant):
    """Génère un token JWT qui inclut le tenant_id (tid)."""
    # 1. Login pour obtenir un token de base
    resp_login = client.post("/api/auth/login", json={
        "username": user_permanencier.username,
        "password": "Password123!"
    })
    assert resp_login.status_code == 200
    token = resp_login.get_json()["access_token"]

    # 2. Sélectionner le tenant pour obtenir un token "tenant-aware"
    resp_tenant = client.post("/api/auth/select-tenant", headers={"Authorization": f"Bearer {token}"}, json={
        "tenant_id": str(default_tenant.id)
    })
    assert resp_tenant.status_code == 200
    tenant_token = resp_tenant.get_json()["access_token"]
    
    return {"Authorization": f"Bearer {tenant_token}"}


@pytest.fixture
def test_data(db, default_tenant, user_permanencier):
    """Crée des données de test (Client, Site, Contact) dans le tenant par défaut."""
    client_obj = Client(nom="Client pour Demandes", code_client="CLIDEM", tenant_id=default_tenant.id)
    db.session.add(client_obj)
    db.session.flush()

    site_obj = Site(nom="Site pour Demandes", code_site="SITEDEM", client_id=client_obj.id, tenant_id=default_tenant.id)
    db.session.add(site_obj)
    db.session.flush()

    contact_obj = Contact(nom="Contact", prenom="Demande")
    contact_obj.clients.append(client_obj)
    db.session.add(contact_obj)
    db.session.commit()

    return {
        "client": client_obj,
        "site": site_obj,
        "contact": contact_obj,
        "permanencier": user_permanencier,
        "tenant_id": default_tenant.id
    }


# ============================================================================
# TESTS
# ============================================================================

class TestCreateDemande:
    
    def test_create_demande_anomalie_success(self, client, auth_headers_tenant, test_data):
        """Teste la création réussie d'une demande d'anomalie."""
        payload = {
            "type_demande": "anomalie",
            "client_id": test_data["client"].id,
            "site_id": test_data["site"].id,
            "titre": "Serveur en panne",
            "description": "Le serveur principal ne répond plus.",
            "nature_anomalie": "defaut_materiel"
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["type_demande"] == "anomalie"
        assert data["titre"] == "Serveur en panne"
        assert data["numero_ticket"].startswith("ANOM_")
        assert data["nature_anomalie"] == "defaut_materiel"

    def test_create_demande_commande_success(self, client, auth_headers_tenant, test_data):
        """Teste la création réussie d'une demande de commande."""
        payload = {
            "type_demande": "commande",
            "client_id": test_data["client"].id,
            "titre": "Achat de 10 licences",
            "type_commande": "licence",
            "quantite": 10
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["type_demande"] == "commande"
        assert data["type_commande"] == "licence"
        assert data["quantite"] == 10

    def test_create_demande_planning_success(self, client, auth_headers_tenant, test_data, agent_securite):
        """Teste la création réussie d'une demande de planning."""
        payload = {
            "type_demande": "planning",
            "client_id": test_data["client"].id,
            "titre": "Absence pour formation",
            "type_modification": "formation",
            "agent_concerne_id": agent_securite.id
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["type_demande"] == "planning"
        assert data["type_modification"] == "formation"
        assert data["agent_concerne_id"] == agent_securite.id

    def test_create_demande_admin_success(self, client, auth_headers_tenant, test_data):
        """Teste la création réussie d'une demande administrative."""
        payload = {
            "type_demande": "admin",
            "client_id": test_data["client"].id,
            "titre": "Nouveau contrat à valider",
            "categorie": "contrat"
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["type_demande"] == "admin"
        assert data["categorie"] == "contrat"

    def test_create_demande_missing_required_field(self, client, auth_headers_tenant, test_data):
        """La création échoue (400) si un champ requis est manquant."""
        payload = {
            "type_demande": "anomalie",
            # "client_id": test_data["client"].id,  <-- Manquant
            "titre": "Titre sans client"
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 400
        assert "missing_fields" in resp.get_json()
        assert "client_id" in resp.get_json()["missing_fields"]

    def test_create_demande_invalid_type(self, client, auth_headers_tenant, test_data):
        """La création échoue (400) si type_demande est invalide."""
        payload = {
            "type_demande": "type_inexistant",
            "client_id": test_data["client"].id,
            "titre": "Titre invalide"
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 400
        assert "type_demande invalide" in resp.get_json()["message"]

    def test_create_demande_client_not_in_tenant(self, client, auth_headers_tenant, db, default_tenant):
        """La création échoue (404) si le client n'appartient pas au tenant."""
        # Créer un client dans un autre tenant
        other_tenant = Tenant(nom="Autre Tenant", code="OTHER", slug="other")
        db.session.add(other_tenant)
        db.session.commit()
        other_client = Client(nom="Client Hors Tenant", code_client="CLI-OTHER", tenant_id=other_tenant.id)
        db.session.add(other_client)
        db.session.commit()

        payload = {
            "type_demande": "anomalie",
            "client_id": other_client.id,
            "titre": "Tentative cross-tenant"
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 404


class TestReadUpdateDeleteDemande:

    @pytest.fixture
    def sample_demande(self, db, test_data):
        """Crée une demande pour les tests de lecture/màj/suppression."""
        demande = DemandeAnomalie(
            type_demande=TypeDemande.ANOMALIE,
            client_id=test_data["client"].id,
            permanencier_id=test_data["permanencier"].id,
            titre="Demande de test",
            tenant_id=test_data["tenant_id"],
            numero_ticket="TEMP"
        )
        db.session.add(demande)
        db.session.flush()
        demande.numero_ticket = f"ANOM_{demande.id}"
        db.session.commit()
        return demande

    def test_list_demandes(self, client, auth_headers_tenant, sample_demande):
        """Teste la récupération de la liste des demandes."""
        resp = client.get("/api/demandes", headers=auth_headers_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(d["id"] == sample_demande.id for d in data)

    def test_get_demande_by_id(self, client, auth_headers_tenant, sample_demande):
        """Teste la récupération d'une demande par son ID."""
        resp = client.get(f"/api/demandes/{sample_demande.id}", headers=auth_headers_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == sample_demande.id
        assert data["titre"] == "Demande de test"

    def test_update_demande(self, client, auth_headers_tenant, sample_demande):
        """Teste la mise à jour d'une demande."""
        payload = {"titre": "Titre mis à jour", "priorite": "haute"}
        resp = client.put(f"/api/demandes/{sample_demande.id}", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["titre"] == "Titre mis à jour"
        assert data["priorite"] == "haute"

    def test_patch_demande_status(self, client, auth_headers_tenant, sample_demande):
        """Teste la mise à jour du statut via PATCH."""
        payload = {"statut": "en_cours"}
        resp = client.patch(f"/api/demandes/{sample_demande.id}/status", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["statut"] == "en_cours"

    def test_soft_delete_demande(self, client, auth_headers_tenant, sample_demande, db):
        """Teste la suppression logique (soft delete) d'une demande."""
        # Suppression
        resp_delete = client.delete(f"/api/demandes/{sample_demande.id}", headers=auth_headers_tenant)
        assert resp_delete.status_code == 200

        # Vérifier en base
        db.session.expire_all()
        demande = db.session.get(Demande, sample_demande.id)
        assert demande.is_deleted is True
        assert demande.deleted_at is not None

        # Vérifier qu'elle n'est plus dans la liste
        resp_list = client.get("/api/demandes", headers=auth_headers_tenant)
        assert not any(d["id"] == sample_demande.id for d in resp_list.get_json())

        # Vérifier que l'accès direct retourne 404
        resp_get = client.get(f"/api/demandes/{sample_demande.id}", headers=auth_headers_tenant)
        assert resp_get.status_code == 404