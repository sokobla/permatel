# backend/tests/test_contacts.py
import pytest
from app.models.contact import Contact
from app.models.client import Client
from app.models.site import Site


class TestContactsBasic:
    def test_list_contacts_retourne_200(self, client, auth_headers):
        response = client.get("/api/contacts", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.get_json()["contacts"], list)


class TestContactsCreateAndAssociations:
    """POST /api/contacts (rôle MANAGER/ADMIN requis).

    Contrat actuel de la route (routes/contacts.py::create_contact) :
      - `type` détermine le rattachement : 'Client' (tenant_id + client_ids
        requis, site_ids optionnel), 'Tenant' (tenant_id seul), 'Prestataire'
        (partner_id requis) — 'Agent de sécurité' est bloqué (403, géré par le
        module Agents). Règle XOR en base : tenant_id OU partner_id, jamais les
        deux (CheckConstraint ck_contacts_tenant_or_partner_xor).
      - nom/prenom/adresse/ville/telephone/email sont requis (400 si absents).
      - client_ids/site_ids invalides → 422 (pas 404) : la route les résout par
        une requête `.filter(Client.id.in_(...))` et compare la taille du
        résultat à la liste demandée plutôt que de faire un lookup unitaire.
    """

    def test_create_contact_valide_avec_associations(self, client, auth_headers_manager, db, default_tenant):
        # Créer client et site
        client_obj = Client(tenant_id=default_tenant.id, nom="Client A", code_client="CLI-A")
        db.session.add(client_obj)
        db.session.commit()

        site_obj = Site(tenant_id=default_tenant.id, client_id=client_obj.id, nom="Site A", code_site="SIT-A")
        db.session.add(site_obj)
        db.session.commit()

        payload = {
            "type": "Client",
            "nom": "Dupont",
            "prenom": "Jean",
            "adresse": "1 Rue Test",
            "ville": "Paris",
            "telephone": "0123456789",
            "email": "jean.dupont@example.com",
            "client_ids": [client_obj.id],
            "site_ids": [site_obj.id],
        }

        resp = client.post("/api/contacts", json=payload, headers=auth_headers_manager)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["nom"] == "Dupont"
        assert data["prenom"] == "Jean"
        assert any(c["id"] == client_obj.id for c in data["clients"])
        assert any(s["id"] == site_obj.id for s in data["sites"])

        # Vérifier en BD
        c_db = Contact.query.filter_by(nom="Dupont", prenom="Jean").first()
        assert c_db is not None
        assert any(cl.id == client_obj.id for cl in c_db.clients)
        assert any(s.id == site_obj.id for s in c_db.sites)

    def test_create_contact_champs_requis(self, client, auth_headers_manager):
        payload = {"nom": "OnlyName"}
        resp = client.post("/api/contacts", json=payload, headers=auth_headers_manager)
        assert resp.status_code == 400
        assert "prenom" in resp.get_json()["error"]

    def test_create_contact_client_inexistant(self, client, auth_headers_manager):
        payload = {
            "type": "Client",
            "nom": "X", "prenom": "Y", "adresse": "1 Rue Test", "ville": "Paris",
            "telephone": "0100000000", "email": "x@example.com",
            "client_ids": [99999],
        }
        resp = client.post("/api/contacts", json=payload, headers=auth_headers_manager)
        assert resp.status_code == 422
        assert "client" in resp.get_json()["error"]

    def test_create_contact_site_inexistant(self, client, auth_headers_manager, db, default_tenant):
        # Créer client valide
        client_obj = Client(tenant_id=default_tenant.id, nom="Client B", code_client="CLI-B")
        db.session.add(client_obj)
        db.session.commit()

        payload = {
            "type": "Client",
            "nom": "X", "prenom": "Y", "adresse": "1 Rue Test", "ville": "Paris",
            "telephone": "0100000000", "email": "x@example.com",
            "client_ids": [client_obj.id], "site_ids": [99999],
        }
        resp = client.post("/api/contacts", json=payload, headers=auth_headers_manager)
        assert resp.status_code == 422
        assert "site" in resp.get_json()["error"]


class TestContactsUpdateAndReassign:
    """PUT /api/contacts/<id> (rôle MANAGER/ADMIN requis) — mêmes clés que la
    création (`type`, `client_ids`, `site_ids`) ; invalide → 422."""

    def test_update_contact_champs_et_reaffectation_sites_clients(self, client, auth_headers_manager, db, default_tenant):
        # Créer clients/sites initiaux
        c1 = Client(tenant_id=default_tenant.id, nom="Client 1", code_client="C1")
        c2 = Client(tenant_id=default_tenant.id, nom="Client 2", code_client="C2")
        db.session.add_all([c1, c2])
        db.session.commit()

        s1 = Site(tenant_id=default_tenant.id, client_id=c1.id, nom="Site 1", code_site="S1")
        s2 = Site(tenant_id=default_tenant.id, client_id=c2.id, nom="Site 2", code_site="S2")
        db.session.add_all([s1, s2])
        db.session.commit()

        # Créer contact associé à c1/s1
        contact = Contact(
            tenant_id=default_tenant.id, nom="Martin", prenom="Paul",
            adresse="1 Rue Test", ville="Paris", type="Client",
            telephone="0600000000", email="martin.paul@example.com",
        )
        contact.clients = [c1]
        contact.sites = [s1]
        db.session.add(contact)
        db.session.commit()

        # Réaffecter au client c2 et site s2
        payload = {"client_ids": [c2.id], "site_ids": [s2.id], "telephone": "0777777777"}
        resp = client.put(f"/api/contacts/{contact.id}", json=payload, headers=auth_headers_manager)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["telephone"] == "0777777777"
        assert any(c["id"] == c2.id for c in data["clients"])
        assert any(s["id"] == s2.id for s in data["sites"])

        # Recharger depuis la BD et vérifier que les anciennes assoc sont supprimées
        c_db = Contact.query.get(contact.id)
        assert len(c_db.clients) == 1
        assert c_db.clients[0].id == c2.id
        assert len(c_db.sites) == 1
        assert c_db.sites[0].id == s2.id

    def test_update_contact_client_inexistant(self, client, auth_headers_manager, db, default_tenant):
        # Créer contact
        contact = Contact(
            tenant_id=default_tenant.id, nom="Test", prenom="T",
            adresse="1 Rue Test", ville="Paris", type="Tenant",
            telephone="0600000000", email="test@example.com",
        )
        db.session.add(contact)
        db.session.commit()

        payload = {"type": "Client", "client_ids": [99999]}
        resp = client.put(f"/api/contacts/{contact.id}", json=payload, headers=auth_headers_manager)
        assert resp.status_code == 422
        assert "client" in resp.get_json()["error"]

    def test_update_contact_site_inexistant(self, client, auth_headers_manager, db, default_tenant):
        client_obj = Client(tenant_id=default_tenant.id, nom="Client C", code_client="C3")
        db.session.add(client_obj)
        db.session.commit()

        contact = Contact(
            tenant_id=default_tenant.id, nom="Test2", prenom="T2",
            adresse="1 Rue Test", ville="Paris", type="Client",
            telephone="0600000000", email="test2@example.com",
        )
        contact.clients = [client_obj]
        db.session.add(contact)
        db.session.commit()

        payload = {"type": "Client", "client_ids": [client_obj.id], "site_ids": [99999]}
        resp = client.put(f"/api/contacts/{contact.id}", json=payload, headers=auth_headers_manager)
        assert resp.status_code == 422
        assert "site" in resp.get_json()["error"]


class TestContactsDeleteAndListingByRelations:
    def test_delete_contact_physique(self, client, auth_headers_admin, db, default_tenant):
        """DELETE /api/contacts/<id> (rôle ADMIN uniquement)"""
        contact = Contact(
            tenant_id=default_tenant.id,
            nom="ToDelete", prenom="D", adresse="1 Rue Test", ville="Paris",
            type="Tenant", telephone="0100000000", email="todelete@example.com",
        )
        db.session.add(contact)
        db.session.commit()

        resp = client.delete(f"/api/contacts/{contact.id}", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Contact supprimé avec succès."

        assert Contact.query.get(contact.id) is None

    def test_list_contacts_by_client_and_site(self, client, auth_headers, db, default_tenant):
        """Filtrage par client_id/site_id via GET /api/contacts (les routes dédiées
        /contacts/client/<id> et /contacts/site/<id> n'existent plus)."""
        cl = Client(tenant_id=default_tenant.id, nom="CliX", code_client="CX")
        db.session.add(cl)
        db.session.commit()

        s = Site(tenant_id=default_tenant.id, client_id=cl.id, nom="SiteX", code_site="SX")
        db.session.add(s)
        db.session.commit()

        c = Contact(
            tenant_id=default_tenant.id,
            nom="Rel", prenom="R", adresse="1 Rue Test", ville="Paris",
            type="Client", telephone="0100000000", email="rel@example.com",
        )
        c.clients = [cl]
        c.sites = [s]
        db.session.add(c)
        db.session.commit()

        resp1 = client.get(f"/api/contacts?client_id={cl.id}", headers=auth_headers)
        assert resp1.status_code == 200
        data1 = resp1.get_json()["contacts"]
        assert any(item["id"] == c.id for item in data1)

        resp2 = client.get(f"/api/contacts?site_id={s.id}", headers=auth_headers)
        assert resp2.status_code == 200
        data2 = resp2.get_json()["contacts"]
        assert any(item["id"] == c.id for item in data2)
