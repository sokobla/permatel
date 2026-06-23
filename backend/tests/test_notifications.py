"""Tests notifications : émission à la création de demande + API."""
from app.models.client import Client

PWD = "Password123!"


def _login(client, username):
    return client.post("/api/auth/login", json={"username": username, "password": PWD}).get_json()


def _bearer(tok):
    return {"Authorization": f"Bearer {tok}"}


def _client_core(db, tenant):
    c = Client(nom="Client CORE", code_client="C-CORE", tenant_id=tenant.id)
    db.session.add(c)
    db.session.commit()
    return c


def test_demande_creation_emits_notification(client, db, default_tenant, user_manager):
    cli = _client_core(db, default_tenant)
    h = _bearer(_login(client, "manager1")["access_token"])

    # 0 notif au départ
    assert client.get("/api/notifications/unread-count", headers=h).get_json()["unread_count"] == 0

    # création d'une demande → notif demande.created (+ assigned au créateur)
    r = client.post("/api/demandes", json={
        "type_demande": "anomalie", "client_id": cli.id, "titre": "Porte forcée",
        "priorite": "haute",
    }, headers=h)
    assert r.status_code == 201
    # la demande porte un SLA calculé
    assert r.get_json().get("sla", {}).get("resolution", {}).get("status") in ("on_time", "at_risk")

    data = client.get("/api/notifications", headers=h).get_json()
    assert data["unread_count"] >= 1
    assert any(n["type"] in ("demande.created", "demande.assigned") for n in data["notifications"])


def test_mark_read_and_read_all(client, db, default_tenant, user_manager):
    cli = _client_core(db, default_tenant)
    h = _bearer(_login(client, "manager1")["access_token"])
    client.post("/api/demandes", json={"type_demande": "anomalie", "client_id": cli.id, "titre": "X"}, headers=h)

    listing = client.get("/api/notifications", headers=h).get_json()
    assert listing["unread_count"] >= 1
    nid = listing["notifications"][0]["id"]

    assert client.post(f"/api/notifications/{nid}/read", headers=h).status_code == 200
    client.post("/api/notifications/read-all", headers=h)
    assert client.get("/api/notifications/unread-count", headers=h).get_json()["unread_count"] == 0


def test_preferences_upsert(client, db, default_tenant, user_manager):
    h = _bearer(_login(client, "manager1")["access_token"])
    r = client.put("/api/notifications/preferences",
                   json={"type": "demande.created", "in_app": True, "email": True}, headers=h)
    assert r.status_code == 200 and r.get_json()["email"] is True
    prefs = client.get("/api/notifications/preferences", headers=h).get_json()
    assert any(p["type"] == "demande.created" and p["email"] for p in prefs)
