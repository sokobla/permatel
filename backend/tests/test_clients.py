# backend/tests/test_clients.py
import pytest
from app.models.client import Client


class TestClientsList:
    """Tests pour GET /api/clients"""

    def test_list_clients_retourne_200(self, client, auth_headers):
        """Test que la liste des clients retourne 200"""
        response = client.get("/api/clients", headers=auth_headers)
        assert response.status_code == 200

    def test_list_clients_retourne_list(self, client, auth_headers):
        """Test que la réponse contient une liste"""
        response = client.get("/api/clients", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_list_clients_ne_retourne_que_actifs(self, client, auth_headers, db):
        """Test que seuls les clients actifs sont retournés"""
        # Créer un client actif
        active_client = Client(
            nom="Client Actif",
            code_client="CLI001",
            is_active=True
        )
        # Créer un client inactif
        inactive_client = Client(
            nom="Client Inactif",
            code_client="CLI002",
            is_active=False
        )

        db.session.add_all([active_client, inactive_client])
        db.session.commit()

        response = client.get("/api/clients", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()

        # Vérifier qu'on a qu'un seul client (l'actif)
        assert len(data) == 1
        assert data[0]["nom"] == "Client Actif"
        assert data[0]["code_client"] == "CLI001"


class TestClientsGet:
    """Tests pour GET /api/clients/<id>"""

    def test_get_client_retourne_200(self, client, auth_headers, db):
        """Test récupération d'un client existant"""
        test_client = Client(
            nom="Test Client",
            code_client="CLI001",
            adresse="123 Rue Test",
            telephone="0123456789",
            email="test@client.com",
            contact_principal="Jean Dupont"
        )
        db.session.add(test_client)
        db.session.commit()

        response = client.get(f"/api/clients/{test_client.id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["id"] == test_client.id
        assert data["nom"] == "Test Client"
        assert data["code_client"] == "CLI001"
        assert data["adresse"] == "123 Rue Test"
        assert data["telephone"] == "0123456789"
        assert data["email"] == "test@client.com"
        assert data["contact_principal"] == "Jean Dupont"
        assert data["is_active"] is True

    def test_get_client_404_si_non_existent(self, client, auth_headers):
        """Test que 404 est retourné pour un client inexistant"""
        response = client.get("/api/clients/99999", headers=auth_headers)
        assert response.status_code == 404


class TestClientsCreate:
    """Tests pour POST /api/clients"""

    def test_create_client_valide_retourne_201(self, client, auth_headers, db):
        """Test création d'un client valide"""
        payload = {
            "nom": "Nouveau Client",
            "code_client": "CLI001",
            "adresse": "456 Rue Nouvelle",
            "telephone": "0987654321",
            "email": "nouveau@client.com",
            "contact_principal": "Marie Martin"
        }

        response = client.post("/api/clients", json=payload, headers=auth_headers)
        assert response.status_code == 201

        data = response.get_json()
        assert data["nom"] == "Nouveau Client"
        assert data["code_client"] == "CLI001"
        assert data["is_active"] is True

        # Vérifier en BD
        client_db = Client.query.filter_by(code_client="CLI001").first()
        assert client_db is not None
        assert client_db.nom == "Nouveau Client"

    def test_create_client_nom_requis(self, client, auth_headers):
        """Test que nom est requis"""
        payload = {"code_client": "CLI001"}
        response = client.post("/api/clients", json=payload, headers=auth_headers)
        assert response.status_code == 400
        assert "nom" in response.get_json()["error"]

    def test_create_client_code_client_requis(self, client, auth_headers):
        """Test que code_client est requis"""
        payload = {"nom": "Test Client"}
        response = client.post("/api/clients", json=payload, headers=auth_headers)
        assert response.status_code == 400
        assert "code_client" in response.get_json()["error"]

    def test_create_client_code_client_unique(self, client, auth_headers, db):
        """Test unicité du code_client"""
        # Créer un premier client
        existing_client = Client(nom="Client Existant", code_client="CLI001")
        db.session.add(existing_client)
        db.session.commit()

        # Tenter de créer un second avec même code
        payload = {"nom": "Nouveau Client", "code_client": "CLI001"}
        response = client.post("/api/clients", json=payload, headers=auth_headers)
        assert response.status_code == 409
        assert "existe déjà" in response.get_json()["error"]

    def test_create_client_champs_optionnels(self, client, auth_headers):
        """Test création avec seulement les champs requis"""
        payload = {"nom": "Client Minimal", "code_client": "CLI002"}
        response = client.post("/api/clients", json=payload, headers=auth_headers)
        assert response.status_code == 201

        data = response.get_json()
        assert data["nom"] == "Client Minimal"
        assert data["code_client"] == "CLI002"
        assert data["adresse"] is None
        assert data["telephone"] is None
        assert data["email"] is None
        assert data["contact_principal"] is None


class TestClientsUpdate:
    """Tests pour PUT /api/clients/<id>"""

    def test_update_client_retourne_200(self, client, auth_headers, db):
        """Test mise à jour réussie"""
        test_client = Client(
            nom="Client Original",
            code_client="CLI001",
            adresse="Adresse Originale"
        )
        db.session.add(test_client)
        db.session.commit()

        payload = {
            "nom": "Client Modifié",
            "adresse": "Nouvelle Adresse"
        }

        response = client.put(f"/api/clients/{test_client.id}", json=payload, headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["nom"] == "Client Modifié"
        assert data["adresse"] == "Nouvelle Adresse"
        assert data["code_client"] == "CLI001"  # Non modifié

    def test_update_client_code_client_unique(self, client, auth_headers, db):
        """Test unicité du code_client lors de la mise à jour"""
        client1 = Client(nom="Client 1", code_client="CLI001")
        client2 = Client(nom="Client 2", code_client="CLI002")
        db.session.add_all([client1, client2])
        db.session.commit()

        # Tenter de changer CLI002 en CLI001 (déjà pris)
        payload = {"code_client": "CLI001"}
        response = client.put(f"/api/clients/{client2.id}", json=payload, headers=auth_headers)
        assert response.status_code == 409
        assert "existe déjà" in response.get_json()["error"]

    def test_update_client_404_si_non_existent(self, client, auth_headers):
        """Test 404 pour client inexistant"""
        payload = {"nom": "Nouveau Nom"}
        response = client.put("/api/clients/99999", json=payload, headers=auth_headers)
        assert response.status_code == 404

    def test_update_client_champs_partiels(self, client, auth_headers, db):
        """Test mise à jour partielle (seuls certains champs)"""
        test_client = Client(
            nom="Client Original",
            code_client="CLI001",
            adresse="Adresse Originale",
            telephone="0123456789"
        )
        db.session.add(test_client)
        db.session.commit()

        # Modifier seulement le téléphone
        payload = {"telephone": "0987654321"}
        response = client.put(f"/api/clients/{test_client.id}", json=payload, headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data["nom"] == "Client Original"  # Non modifié
        assert data["telephone"] == "0987654321"  # Modifié


class TestClientsDelete:
    """Tests pour DELETE /api/clients/<id>"""

    def test_delete_client_retourne_200(self, client, auth_headers, db):
        """Test suppression réussie (soft delete)"""
        test_client = Client(nom="Client à Supprimer", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        response = client.delete(f"/api/clients/{test_client.id}", headers=auth_headers)
        assert response.status_code == 200
        assert "désactivé" in response.get_json()["message"]

        # Vérifier que le client est désactivé en BD
        client_db = Client.query.get(test_client.id)
        assert client_db.is_active is False

    def test_delete_client_404_si_non_existent(self, client, auth_headers):
        """Test 404 pour client inexistant"""
        response = client.delete("/api/clients/99999", headers=auth_headers)
        assert response.status_code == 404


class TestClientsStatus:
    """Tests pour PATCH /api/clients/<id>/status"""

    def test_status_desactiver_client(self, client, auth_headers, db):
        """Test désactivation d'un client"""
        test_client = Client(nom="Client Actif", code_client="CLI001", is_active=True)
        db.session.add(test_client)
        db.session.commit()

        payload = {"is_active": False}
        response = client.patch(f"/api/clients/{test_client.id}/status", json=payload, headers=auth_headers)
        assert response.status_code == 200
        assert "désactivé" in response.get_json()["message"]
        assert response.get_json()["is_active"] is False

        # Vérifier en BD
        client_db = Client.query.get(test_client.id)
        assert client_db.is_active is False

    def test_status_activer_client(self, client, auth_headers, db):
        """Test activation d'un client"""
        test_client = Client(nom="Client Inactif", code_client="CLI001", is_active=False)
        db.session.add(test_client)
        db.session.commit()

        payload = {"is_active": True}
        response = client.patch(f"/api/clients/{test_client.id}/status", json=payload, headers=auth_headers)
        assert response.status_code == 200
        assert "activé" in response.get_json()["message"]
        assert response.get_json()["is_active"] is True

    def test_status_is_active_requis(self, client, auth_headers, db):
        """Test que is_active est requis"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        response = client.patch(f"/api/clients/{test_client.id}/status", json={}, headers=auth_headers)
        assert response.status_code == 400
        assert "is_active" in response.get_json()["error"]

    def test_status_is_active_doit_etre_booleen(self, client, auth_headers, db):
        """Test que is_active doit être un booléen"""
        test_client = Client(nom="Test Client", code_client="CLI001")
        db.session.add(test_client)
        db.session.commit()

        payload = {"is_active": "true"}  # String au lieu de bool
        response = client.patch(f"/api/clients/{test_client.id}/status", json=payload, headers=auth_headers)
        assert response.status_code == 400
        assert "booléen" in response.get_json()["error"]

    def test_status_404_si_non_existent(self, client, auth_headers):
        """Test 404 pour client inexistant"""
        payload = {"is_active": False}
        response = client.patch("/api/clients/99999/status", json=payload, headers=auth_headers)
        assert response.status_code == 404