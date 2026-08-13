import csv
import io
from datetime import datetime, timedelta

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
def auth_headers_tenant_admin(client, user_admin, default_tenant):
    """Token JWT ADMIN + tenant_id (tid) — requis par DELETE /api/demandes/<id>
    (@role_required(ADMIN)), que auth_headers_tenant (PERMANENCIER) ne peut pas utiliser."""
    resp_login = client.post("/api/auth/login", json={
        "username": user_admin.username,
        "password": "Password123!"
    })
    assert resp_login.status_code == 200
    token = resp_login.get_json()["access_token"]

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

    contact_obj = Contact(
        tenant_id=default_tenant.id, nom="Contact", prenom="Demande",
        adresse="1 Rue Test", ville="Paris", type="Client",
        telephone="0100000000", email="contact.demande@example.com",
    )
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
            "titre": "Interphone du site en panne",
            "description": "Le boîtier interphone du site ne répond plus.",
            "nature_anomalie": "probleme_technique"
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["type_demande"] == "anomalie"
        assert data["titre"] == "Interphone du site en panne"
        assert data["numero_ticket"].startswith("ANOM_")
        assert data["nature_anomalie"] == "probleme_technique"

    def test_create_demande_commande_success(self, client, auth_headers_tenant, test_data):
        """Teste la création réussie d'une demande de commande (rondes supplémentaires)."""
        payload = {
            "type_demande": "commande",
            "client_id": test_data["client"].id,
            "titre": "Rondes supplémentaires demandées",
            "type_commande": "rondes",
            "quantite": 10
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["type_demande"] == "commande"
        assert data["type_commande"] == "rondes"
        assert data["quantite"] == 10
        assert data["nombre_heures"] is None

    def test_create_demande_commande_avec_nombre_heures_seul_succeeds(self, client, auth_headers_tenant, test_data):
        """`nombre_heures` seul (sans `quantite`) doit suffire à la validation —
        les deux champs sont des alternatives, pas une exclusivité mutuelle."""
        payload = {
            "type_demande": "commande",
            "client_id": test_data["client"].id,
            "titre": "Renfort ponctuel de nuit",
            "type_commande": "rondes",
            "nombre_heures": 8,
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["quantite"] is None
        assert data["nombre_heures"] == 8

    def test_create_demande_commande_avec_les_deux_champs_succeeds(self, client, auth_headers_tenant, test_data):
        """Les deux champs peuvent être renseignés simultanément (décision produit
        du 02/08) — les deux valeurs doivent être persistées, pas l'une au
        détriment de l'autre."""
        payload = {
            "type_demande": "commande",
            "client_id": test_data["client"].id,
            "titre": "Renfort agents + heures supplémentaires",
            "type_commande": "rondes",
            "quantite": 3,
            "nombre_heures": 12,
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["quantite"] == 3
        assert data["nombre_heures"] == 12

    def test_create_demande_commande_sans_agents_ni_heures_retourne_400(self, client, auth_headers_tenant, test_data):
        """Ni `quantite` ni `nombre_heures` renseigné -> 400, pas de création
        silencieuse d'une commande sans volumétrie exploitable."""
        payload = {
            "type_demande": "commande",
            "client_id": test_data["client"].id,
            "titre": "Commande sans volumétrie",
            "type_commande": "rondes",
        }
        resp = client.post("/api/demandes", json=payload, headers=auth_headers_tenant)
        assert resp.status_code == 400

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

    def test_soft_delete_demande(self, client, auth_headers_tenant, auth_headers_tenant_admin, sample_demande, db):
        """Teste la suppression logique (soft delete) d'une demande (rôle ADMIN requis)."""
        # Suppression
        resp_delete = client.delete(f"/api/demandes/{sample_demande.id}", headers=auth_headers_tenant_admin)
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


class TestDemandesDateFilterAndPagination:

    @pytest.fixture
    def demandes_echelonnees(self, db, test_data):
        """Crée 3 demandes avec des created_at distincts pour tester le filtrage par date."""
        now = datetime.utcnow()
        demandes = []
        for i, days_ago in enumerate([60, 15, 1]):
            d = DemandeAnomalie(
                type_demande=TypeDemande.ANOMALIE,
                client_id=test_data["client"].id,
                permanencier_id=test_data["permanencier"].id,
                titre=f"Demande J-{days_ago}",
                tenant_id=test_data["tenant_id"],
                numero_ticket="TEMP",
                created_at=now - timedelta(days=days_ago),
            )
            db.session.add(d)
            db.session.flush()
            d.numero_ticket = f"ANOM_{d.id}"
            demandes.append(d)
        db.session.commit()
        return demandes

    def test_list_demandes_filtree_par_date(self, client, auth_headers_tenant, demandes_echelonnees):
        """`from` exclut les demandes antérieures à la borne."""
        cutoff = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%d")
        resp = client.get(f"/api/demandes?from={cutoff}", headers=auth_headers_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        titres = {d["titre"] for d in data}
        assert "Demande J-60" not in titres
        assert "Demande J-15" in titres
        assert "Demande J-1" in titres

    def test_list_demandes_sans_pagination_retourne_tableau_brut(self, client, auth_headers_tenant, demandes_echelonnees):
        """Sans `page`/`per_page`, la réponse reste un tableau brut (compat descendante)."""
        resp = client.get("/api/demandes", headers=auth_headers_tenant)
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_list_demandes_avec_pagination_retourne_enveloppe(self, client, auth_headers_tenant, demandes_echelonnees):
        """Avec `page`/`per_page`, la réponse devient `{items, total}` (opt-in)."""
        resp = client.get("/api/demandes?page=1&per_page=2", headers=auth_headers_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert "items" in data and "total" in data
        assert data["total"] == 3
        assert len(data["items"]) == 2

    def test_export_demandes_csv(self, client, auth_headers_tenant, demandes_echelonnees):
        """L'export CSV retourne un fichier avec en-tête + une ligne par demande, filtré par date."""
        cutoff = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%d")
        resp = client.get(f"/api/demandes/export?from={cutoff}", headers=auth_headers_tenant)
        assert resp.status_code == 200
        assert resp.mimetype == "text/csv"
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        assert rows[0][:3] == ["numero_ticket", "type_demande", "titre"]
        titres = {r[2] for r in rows[1:]}
        assert "Demande J-60" not in titres
        assert "Demande J-15" in titres
        assert "Demande J-1" in titres

    def test_export_demandes_isolation_tenant(self, client, auth_headers_tenant, demandes_echelonnees, db, user_permanencier):
        """L'export ne fuit pas les demandes d'un autre tenant."""
        other_tenant = Tenant(nom="Autre Tenant Export", code="OTHEXP", slug="othexp")
        db.session.add(other_tenant)
        db.session.commit()
        other_client = Client(nom="Client Autre Tenant", code_client="CLIOTH", tenant_id=other_tenant.id)
        db.session.add(other_client)
        db.session.commit()
        leak = DemandeAnomalie(
            type_demande=TypeDemande.ANOMALIE,
            client_id=other_client.id,
            permanencier_id=user_permanencier.id,
            titre="Ne doit pas fuiter",
            tenant_id=other_tenant.id,
            numero_ticket="LEAK",
        )
        db.session.add(leak)
        db.session.commit()

        resp = client.get("/api/demandes/export", headers=auth_headers_tenant)
        assert resp.status_code == 200
        assert "Ne doit pas fuiter" not in resp.get_data(as_text=True)