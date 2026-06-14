# backend/tests/test_sites.py
import pytest
from app.models.site import Site
from app.models.client import Client


class TestSitesList:
    """Tests pour GET /api/sites"""

    def test_list_sites_retourne_200(self, client, auth_headers):
        """Test que la liste des sites retourne 200"""
        response = client.get("/api/sites", headers=auth_headers)
        assert response.status_code == 200

    def test_list_sites_retourne_list(self, client, auth_headers):
        """Test que la réponse contient une liste"""
        response = client.get("/api/sites", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_list_sites_ne_retourne_que_actifs(self, client, auth_headers, db):
        """Test que seuls les sites actifs sont retournés"""
        # Créer un client
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        # Créer un site actif
        active_site = Site(
            client_id=test_client.id,
            nom="Site Actif",
            code_site="SIT001",
            is_active=True
        )
        # Créer un site inactif
        inactive_site = Site(
            client_id=test_client.id,
            nom="Site Inactif",
            code_site="SIT002",
            is_active=False
        )

        db.session.add_all([active_site, inactive_site])
        db.session.commit()

        response = client.get("/api/sites", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()

        # Vérifier qu'on a qu'un seul site (l'actif)
        assert len(data) == 1
        assert data[0]["nom"] == "Site Actif"
        assert data[0]["code_site"] == "SIT001"


class TestSitesGet:
    """Tests pour GET /api/sites/<id>"""

    def test_get_site_retourne_200(self, client, auth_headers, db):
        """Test récupération d'un site existant"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        test_site = Site(
            client_id=test_client.id,
            nom="Test Site",
            code_site="SIT001",
            adresse="123 Rue Test",
            ville="Paris",
            telephone="0123456789",
            responsable_site="Jean Dupont",
            effectif_requis=50
        )
        db.session.add(test_site)
        db.session.commit()

        response = client.get(f"/api/sites/{test_site.id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["id"] == test_site.id
        assert data["client_id"] == test_client.id
        assert data["nom"] == "Test Site"
        assert data["code_site"] == "SIT001"
        assert data["adresse"] == "123 Rue Test"
        assert data["ville"] == "Paris"
        assert data["telephone"] == "0123456789"
        assert data["responsable_site"] == "Jean Dupont"
        assert data["effectif_requis"] == 50
        assert data["is_active"] is True

    def test_get_site_404_si_non_existent(self, client, auth_headers):
        """Test que 404 est retourné pour un site inexistant"""
        response = client.get("/api/sites/99999", headers=auth_headers)
        assert response.status_code == 404


class TestSitesCreate:
    """Tests pour POST /api/sites"""

    def test_create_site_valide_retourne_201(self, client, auth_headers, db):
        """Test création d'un site valide"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        payload = {
            "client_id": test_client.id,
            "nom": "Nouveau Site",
            "code_site": "SIT001",
            "adresse": "456 Rue Nouvelle",
            "ville": "Marseille",
            "telephone": "0987654321",
            "responsable_site": "Marie Martin",
            "effectif_requis": 75
        }

        response = client.post("/api/sites", json=payload, headers=auth_headers)
        assert response.status_code == 201

        data = response.get_json()
        assert data["nom"] == "Nouveau Site"
        assert data["code_site"] == "SIT001"
        assert data["client_id"] == test_client.id
        assert data["is_active"] is True

        # Vérifier en BD
        site_db = Site.query.filter_by(code_site="SIT001").first()
        assert site_db is not None
        assert site_db.nom == "Nouveau Site"

    def test_create_site_client_id_requis(self, client, auth_headers):
        """Test que client_id est requis"""
        payload = {"nom": "Test Site", "code_site": "SIT001"}
        response = client.post("/api/sites", json=payload, headers=auth_headers)
        assert response.status_code == 400
        assert "client_id" in response.get_json()["error"]

    def test_create_site_nom_requis(self, client, auth_headers, db):
        """Test que nom est requis"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        payload = {"client_id": test_client.id, "code_site": "SIT001"}
        response = client.post("/api/sites", json=payload, headers=auth_headers)
        assert response.status_code == 400
        assert "nom" in response.get_json()["error"]

    def test_create_site_code_site_requis(self, client, auth_headers, db):
        """Test que code_site est requis"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        payload = {"client_id": test_client.id, "nom": "Test Site"}
        response = client.post("/api/sites", json=payload, headers=auth_headers)
        assert response.status_code == 400
        assert "code_site" in response.get_json()["error"]

    def test_create_site_client_inexistent(self, client, auth_headers):
        """Test 404 pour client inexistant"""
        payload = {
            "client_id": 99999,
            "nom": "Test Site",
            "code_site": "SIT001"
        }
        response = client.post("/api/sites", json=payload, headers=auth_headers)
        assert response.status_code == 404
        assert "client" in response.get_json()["error"]

    def test_create_site_code_site_unique(self, client, auth_headers, db):
        """Test unicité du code_site"""
        # Créer un client
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        # Créer un premier site
        existing_site = Site(
            client_id=test_client.id,
            nom="Site Existant",
            code_site="SIT001"
        )
        db.session.add(existing_site)
        db.session.commit()

        # Tenter de créer un second avec même code
        payload = {
            "client_id": test_client.id,
            "nom": "Nouveau Site",
            "code_site": "SIT001"
        }
        response = client.post("/api/sites", json=payload, headers=auth_headers)
        assert response.status_code == 409
        assert "existe déjà" in response.get_json()["error"]

    def test_create_site_champs_optionnels(self, client, auth_headers, db):
        """Test création avec seulement les champs requis"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        payload = {
            "client_id": test_client.id,
            "nom": "Site Minimal",
            "code_site": "SIT002"
        }
        response = client.post("/api/sites", json=payload, headers=auth_headers)
        assert response.status_code == 201

        data = response.get_json()
        assert data["nom"] == "Site Minimal"
        assert data["code_site"] == "SIT002"
        assert data["adresse"] is None
        assert data["ville"] is None
        assert data["telephone"] is None
        assert data["responsable_site"] is None
        assert data["effectif_requis"] is None


class TestSitesUpdate:
    """Tests pour PUT /api/sites/<id>"""

    def test_update_site_retourne_200(self, client, auth_headers, db):
        """Test mise à jour réussie"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        test_site = Site(
            client_id=test_client.id,
            nom="Site Original",
            code_site="SIT001",
            adresse="Adresse Originale"
        )
        db.session.add(test_site)
        db.session.commit()

        payload = {
            "nom": "Site Modifié",
            "adresse": "Nouvelle Adresse",
            "ville": "Lyon"
        }

        response = client.put(f"/api/sites/{test_site.id}", json=payload, headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["nom"] == "Site Modifié"
        assert data["adresse"] == "Nouvelle Adresse"
        assert data["ville"] == "Lyon"
        assert data["code_site"] == "SIT001"  # Non modifié

    def test_update_site_code_site_unique(self, client, auth_headers, db):
        """Test unicité du code_site lors de la mise à jour"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        site1 = Site(client_id=test_client.id, nom="Site 1", code_site="SIT001")
        site2 = Site(client_id=test_client.id, nom="Site 2", code_site="SIT002")
        db.session.add_all([site1, site2])
        db.session.commit()

        # Tenter de changer SIT002 en SIT001 (déjà pris)
        payload = {"code_site": "SIT001"}
        response = client.put(f"/api/sites/{site2.id}", json=payload, headers=auth_headers)
        assert response.status_code == 409
        assert "existe déjà" in response.get_json()["error"]

    def test_update_site_client_inexistent(self, client, auth_headers, db):
        """Test 404 pour client inexistant lors de la mise à jour"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        test_site = Site(
            client_id=test_client.id,
            nom="Test Site",
            code_site="SIT001"
        )
        db.session.add(test_site)
        db.session.commit()

        payload = {"client_id": 99999}
        response = client.put(f"/api/sites/{test_site.id}", json=payload, headers=auth_headers)
        assert response.status_code == 404
        assert "client" in response.get_json()["error"]

    def test_update_site_404_si_non_existent(self, client, auth_headers):
        """Test 404 pour site inexistant"""
        payload = {"nom": "Nouveau Nom"}
        response = client.put("/api/sites/99999", json=payload, headers=auth_headers)
        assert response.status_code == 404

    def test_update_site_champs_partiels(self, client, auth_headers, db):
        """Test mise à jour partielle (seuls certains champs)"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        test_site = Site(
            client_id=test_client.id,
            nom="Site Original",
            code_site="SIT001",
            adresse="Adresse Originale",
            ville="Paris",
            effectif_requis=50
        )
        db.session.add(test_site)
        db.session.commit()

        payload = {"telephone": "0123456789"}
        response = client.put(f"/api/sites/{test_site.id}", json=payload, headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["telephone"] == "0123456789"
        assert data["nom"] == "Site Original"  # Non modifié
        assert data["adresse"] == "Adresse Originale"  # Non modifié


class TestSitesDelete:
    """Tests pour DELETE /api/sites/<id>"""

    def test_delete_site_retourne_200(self, client, auth_headers, db):
        """Test suppression (soft delete) réussie"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        test_site = Site(
            client_id=test_client.id,
            nom="Test Site",
            code_site="SIT001",
            is_active=True
        )
        db.session.add(test_site)
        db.session.commit()

        response = client.delete(f"/api/sites/{test_site.id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["is_active"] is False
        assert "désactivé" in data["message"]

        # Vérifier en BD que le site est désactivé
        site_db = Site.query.get(test_site.id)
        assert site_db.is_active is False

    def test_delete_site_404_si_non_existent(self, client, auth_headers):
        """Test 404 pour site inexistant"""
        response = client.delete("/api/sites/99999", headers=auth_headers)
        assert response.status_code == 404


class TestSitesToggle:
    """Tests pour PATCH /api/sites/<id>/toggle"""

    def test_toggle_site_activate_retourne_200(self, client, auth_headers, db):
        """Test activation d'un site désactivé"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        test_site = Site(
            client_id=test_client.id,
            nom="Test Site",
            code_site="SIT001",
            is_active=False
        )
        db.session.add(test_site)
        db.session.commit()

        response = client.patch(f"/api/sites/{test_site.id}/toggle", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["is_active"] is True
        assert "activé" in data["message"]

    def test_toggle_site_deactivate_retourne_200(self, client, auth_headers, db):
        """Test désactivation d'un site activé"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        test_site = Site(
            client_id=test_client.id,
            nom="Test Site",
            code_site="SIT001",
            is_active=True
        )
        db.session.add(test_site)
        db.session.commit()

        response = client.patch(f"/api/sites/{test_site.id}/toggle", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["is_active"] is False
        assert "désactivé" in data["message"]

    def test_toggle_site_404_si_non_existent(self, client, auth_headers):
        """Test 404 pour site inexistant"""
        response = client.patch("/api/sites/99999/toggle", headers=auth_headers)
        assert response.status_code == 404


class TestSitesListByClient:
    """Tests pour GET /api/sites/client/<client_id>"""

    def test_list_sites_by_client_retourne_200(self, client, auth_headers, db):
        """Test liste des sites d'un client"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        site1 = Site(
            client_id=test_client.id,
            nom="Site 1",
            code_site="SIT001",
            is_active=True
        )
        site2 = Site(
            client_id=test_client.id,
            nom="Site 2",
            code_site="SIT002",
            is_active=True
        )
        db.session.add_all([site1, site2])
        db.session.commit()

        response = client.get(f"/api/sites/client/{test_client.id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert len(data) == 2
        assert any(s["code_site"] == "SIT001" for s in data)
        assert any(s["code_site"] == "SIT002" for s in data)

    def test_list_sites_by_client_ne_retourne_que_actifs(self, client, auth_headers, db):
        """Test que seuls les sites actifs d'un client sont retournés"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        active_site = Site(
            client_id=test_client.id,
            nom="Site Actif",
            code_site="SIT001",
            is_active=True
        )
        inactive_site = Site(
            client_id=test_client.id,
            nom="Site Inactif",
            code_site="SIT002",
            is_active=False
        )
        db.session.add_all([active_site, inactive_site])
        db.session.commit()

        response = client.get(f"/api/sites/client/{test_client.id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert len(data) == 1
        assert data[0]["code_site"] == "SIT001"

    def test_list_sites_by_client_404_si_client_inexistent(self, client, auth_headers):
        """Test 404 pour client inexistant"""
        response = client.get("/api/sites/client/99999", headers=auth_headers)
        assert response.status_code == 404
