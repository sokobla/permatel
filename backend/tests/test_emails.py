import csv
import io
from datetime import datetime, timedelta

import pytest
from app.models.email import Email


@pytest.fixture
def auth_headers_tenant(client, user_permanencier, default_tenant):
    resp_login = client.post("/api/auth/login", json={
        "username": user_permanencier.username,
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
def emails_echelonnees(db, default_tenant):
    """Crée 3 emails sortants avec des created_at distincts."""
    now = datetime.utcnow()
    rows = []
    for days_ago in [60, 15, 1]:
        e = Email(
            tenant_id=default_tenant.id,
            direction="outbound",
            status="sent",
            from_address="permatel@example.com",
            to_addresses="client@example.com",
            subject=f"Sujet J-{days_ago}",
            body_text="Corps confidentiel du message.",
            created_at=now - timedelta(days=days_ago),
        )
        db.session.add(e)
        rows.append(e)
    db.session.commit()
    return rows


class TestEmailsDateFilterAndExport:

    def test_list_filtree_par_from(self, client, auth_headers_tenant, emails_echelonnees):
        cutoff = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%d")
        resp = client.get(f"/api/emails?from={cutoff}", headers=auth_headers_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 2

    def test_export_csv_metadata_only_par_defaut(self, client, auth_headers_tenant, emails_echelonnees):
        """Sans include_body=true, le corps chiffré n'apparaît jamais dans l'export."""
        resp = client.get("/api/emails/export", headers=auth_headers_tenant)
        assert resp.status_code == 200
        assert resp.mimetype == "text/csv"
        text = resp.get_data(as_text=True)
        rows = list(csv.reader(io.StringIO(text)))
        assert "body_text" not in rows[0]
        assert "Corps confidentiel du message." not in text
        assert len(rows) - 1 == 3

    def test_export_csv_include_body(self, client, auth_headers_tenant, emails_echelonnees):
        """include_body=true ajoute body_text déchiffré, jamais par défaut."""
        resp = client.get("/api/emails/export?include_body=true", headers=auth_headers_tenant)
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        rows = list(csv.reader(io.StringIO(text)))
        assert "body_text" in rows[0]
        assert "Corps confidentiel du message." in text

    def test_export_csv_filtre_par_date(self, client, auth_headers_tenant, emails_echelonnees):
        cutoff = (datetime.utcnow() - timedelta(days=20)).strftime("%Y-%m-%d")
        resp = client.get(f"/api/emails/export?from={cutoff}", headers=auth_headers_tenant)
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        assert len(rows) - 1 == 2


class TestEmailStatsSmoke:
    """Couverture minimale sur /emails/stats — logique interne (agrégation
    Python) non testée en détail ici, seulement la forme de la réponse.
    Cf. le plan Rapports : la réécriture SQL de cette agrégation est
    explicitement reportée (risque cross-dialecte)."""

    def test_email_stats_200_et_forme_de_la_reponse(self, client, auth_headers_tenant, emails_echelonnees):
        resp = client.get("/api/emails/stats", headers=auth_headers_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "kpi" in data
        assert "sent_total" in data["kpi"]
        assert "received_total" in data["kpi"]
