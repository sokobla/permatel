# backend/tests/test_contacts.py
import pytest
from app.models.contact import Contact
from app.models.client import Client
from app.models.site import Site


class TestContactsBasic:
    def test_list_contacts_retourne_200(self, client, auth_headers):
        response = client.get("/api/contacts", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.get_json(), list)


class TestContactsCreateAndAssociations:
    def test_create_contact_valide_avec_associations(self, client, auth_headers, db):
        # Créer client et site
        client_obj = Client(nom="Client A", code_client="CLI-A")
        db.session.add(client_obj)
        db.session.commit()

        site_obj = Site(client_id=client_obj.id, nom="Site A", code_site="SIT-A")
        db.session.add(site_obj)
        db.session.commit()

        payload = {
            "nom": "Dupont",
            "prenom": "Jean",
            "telephone": "0123456789",
            "email": "jean.dupont@example.com",
            "clients": [client_obj.id],
            "sites": [site_obj.id]
        }

        resp = client.post("/api/contacts", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["nom"] == "Dupont"
        assert data["prenom"] == "Jean"
        assert client_obj.id in data["clients"]
        assert site_obj.id in data["sites"]

        # Vérifier en BD
        c_db = Contact.query.filter_by(nom="Dupont", prenom="Jean").first()
        assert c_db is not None
        assert any(cl.id == client_obj.id for cl in c_db.clients)
        assert any(s.id == site_obj.id for s in c_db.sites)

    def test_create_contact_champs_requis(self, client, auth_headers):
        payload = {"nom": "OnlyName"}
        resp = client.post("/api/contacts", json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert "prenom" in resp.get_json()["error"]

    def test_create_contact_client_inexistant(self, client, auth_headers):
        payload = {"nom": "X", "prenom": "Y", "clients": [99999]}
        resp = client.post("/api/contacts", json=payload, headers=auth_headers)
        assert resp.status_code == 404
        assert "client" in resp.get_json()["error"]

    def test_create_contact_site_inexistant(self, client, auth_headers, db):
        # Créer client valide
        client_obj = Client(nom="Client B", code_client="CLI-B")
        db.session.add(client_obj)
        db.session.commit()

        payload = {"nom": "X", "prenom": "Y", "clients": [client_obj.id], "sites": [99999]}
        resp = client.post("/api/contacts", json=payload, headers=auth_headers)
        assert resp.status_code == 404
        assert "site" in resp.get_json()["error"]


class TestContactsUpdateAndReassign:
    def test_update_contact_champs_et_reaffectation_sites_clients(self, client, auth_headers, db):
        # Créer clients/sites initiaux
        c1 = Client(nom="Client 1", code_client="C1")
        c2 = Client(nom="Client 2", code_client="C2")
        db.session.add_all([c1, c2])
        db.session.commit()

        s1 = Site(client_id=c1.id, nom="Site 1", code_site="S1")
        s2 = Site(client_id=c2.id, nom="Site 2", code_site="S2")
        db.session.add_all([s1, s2])
        db.session.commit()

        # Créer contact associé à c1/s1
        contact = Contact(nom="Martin", prenom="Paul")
        contact.clients = [c1]
        contact.sites = [s1]
        db.session.add(contact)
        db.session.commit()

        # Réaffecter au client c2 et site s2
        payload = {"clients": [c2.id], "sites": [s2.id], "telephone": "0777777777"}
        resp = client.put(f"/api/contacts/{contact.id}", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["telephone"] == "0777777777"
        assert c2.id in data["clients"]
        assert s2.id in data["sites"]

        # Recharger depuis la BD et vérifier que les anciennes assoc sont supprimées
        c_db = Contact.query.get(contact.id)
        assert len(c_db.clients) == 1
        assert c_db.clients[0].id == c2.id
        assert len(c_db.sites) == 1
        assert c_db.sites[0].id == s2.id

    def test_update_contact_client_inexistant(self, client, auth_headers, db):
        # Créer contact
        contact = Contact(nom="Test", prenom="T")
        db.session.add(contact)
        db.session.commit()

        payload = {"clients": [99999]}
        resp = client.put(f"/api/contacts/{contact.id}", json=payload, headers=auth_headers)
        assert resp.status_code == 404
        assert "client" in resp.get_json()["error"]

    def test_update_contact_site_inexistant(self, client, auth_headers, db):
        contact = Contact(nom="Test2", prenom="T2")
        db.session.add(contact)
        db.session.commit()

        payload = {"sites": [99999]}
        resp = client.put(f"/api/contacts/{contact.id}", json=payload, headers=auth_headers)
        assert resp.status_code == 404
        assert "site" in resp.get_json()["error"]


class TestContactsDeleteAndListingByRelations:
    def test_delete_contact_physique(self, client, auth_headers, db):
        contact = Contact(nom="ToDelete", prenom="D")
        db.session.add(contact)
        db.session.commit()

        resp = client.delete(f"/api/contacts/{contact.id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["id"] == contact.id

        assert Contact.query.get(contact.id) is None

    def test_list_contacts_by_client_and_site(self, client, auth_headers, db):
        cl = Client(nom="CliX", code_client="CX")
        db.session.add(cl)
        db.session.commit()

        s = Site(client_id=cl.id, nom="SiteX", code_site="SX")
        db.session.add(s)
        db.session.commit()

        c = Contact(nom="Rel", prenom="R")
        c.clients = [cl]
        c.sites = [s]
        db.session.add(c)
        db.session.commit()

        resp1 = client.get(f"/api/contacts/client/{cl.id}", headers=auth_headers)
        assert resp1.status_code == 200
        data1 = resp1.get_json()
        assert any(item["id"] == c.id for item in data1)

        resp2 = client.get(f"/api/contacts/site/{s.id}", headers=auth_headers)
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert any(item["id"] == c.id for item in data2)
