import pytest
from click.testing import CliRunner

from app.models.erp import ErpConfig, ErpSyncQueue
from app.models.audit_log import AuditLog
from app.services.erp_client import ErpClient, ErpClientError
from app.services.erp_sync import dispatch_erp_sync
from tests.fakes.fake_erp_client import FakeErpClient


# ══════════════════════════════════════════════════════════════
#  Modèles
# ══════════════════════════════════════════════════════════════
class TestErpModels:
    def test_erp_config_to_dict_masque_les_secrets_par_defaut(self, db, default_tenant):
        cfg = ErpConfig(
            tenant_id=default_tenant.id, company_id=3,
            url_erp="https://erp.example.com", admin_username="admin",
            admin_password="s3cret",
        )
        db.session.add(cfg)
        db.session.commit()

        data = cfg.to_dict()
        assert data["company_id"] == 3
        assert data["has_admin_password"] is True
        assert "admin_password" not in data
        assert "url_erp" not in data

        full = cfg.to_dict(include_secrets=True)
        assert full["admin_password"] == "s3cret"
        assert full["url_erp"] == "https://erp.example.com"

    def test_erp_config_password_chiffre_au_repos(self, db, default_tenant):
        """EncryptedText : la valeur en base (colonne brute) ne doit jamais être en clair."""
        cfg = ErpConfig(tenant_id=default_tenant.id, admin_password="s3cret")
        db.session.add(cfg)
        db.session.commit()
        db.session.expire_all()

        raw = db.session.execute(
            db.text("SELECT admin_password FROM erp_config WHERE id = :id"),
            {"id": cfg.id},
        ).scalar()
        assert raw != "s3cret"
        assert raw.startswith("enc::")

        reloaded = db.session.get(ErpConfig, cfg.id)
        assert reloaded.admin_password == "s3cret"  # déchiffré transparent à la lecture

    def test_erp_sync_queue_to_dict(self, db, default_tenant):
        row = ErpSyncQueue(tenant_id=default_tenant.id, flux="partner_create", status="pending")
        db.session.add(row)
        db.session.commit()
        data = row.to_dict()
        assert data["flux"] == "partner_create"
        assert data["status"] == "pending"
        assert data["attempts"] == 0


# ══════════════════════════════════════════════════════════════
#  Routes /api/settings/erp
# ══════════════════════════════════════════════════════════════
class TestSettingsErp:
    def test_get_erp_sans_config_retourne_defauts(self, client, auth_headers):
        resp = client.get("/api/settings/erp", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["company_id"] is None
        assert data["has_admin_password"] is False

    def test_put_erp_permanencier_refuse_403(self, client, auth_headers):
        resp = client.put("/api/settings/erp", json={"company_id": 3}, headers=auth_headers)
        assert resp.status_code == 403

    def test_put_erp_admin_cree_la_config(self, client, auth_headers_admin, db, default_tenant):
        resp = client.put("/api/settings/erp", json={"company_id": 5}, headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.get_json()["company_id"] == 5

        cfg = ErpConfig.query.filter_by(tenant_id=default_tenant.id).first()
        assert cfg is not None
        assert cfg.company_id == 5

    def test_put_erp_company_id_invalide_retourne_422(self, client, auth_headers_admin):
        resp = client.put("/api/settings/erp", json={"company_id": "abc"}, headers=auth_headers_admin)
        assert resp.status_code == 422

    def test_put_erp_ignore_champs_acces_direct(self, client, auth_headers_admin, db, default_tenant):
        """url_erp/admin_username/admin_password (§4.4, ADMIN global via /erp/direct-access
        uniquement) ne sont jamais acceptés par cette route tenant-admin."""
        resp = client.put(
            "/api/settings/erp",
            json={"company_id": 5, "url_erp": "https://hack.example.com", "admin_password": "pwned"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        cfg = ErpConfig.query.filter_by(tenant_id=default_tenant.id).first()
        assert cfg.url_erp is None
        assert cfg.admin_password is None

    def test_test_erp_sans_config_serveur_retourne_ok_false(self, client, auth_headers_admin):
        """ERP_URL/DB/USERNAME/PASSWORD absents côté app -> dégradation propre, jamais 500."""
        resp = client.post("/api/settings/erp/test", json={"company_id": 3}, headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is False

    def test_test_erp_succes_avec_client_factice(self, client, auth_headers_admin, monkeypatch):
        client.application.config["ERP_URL"] = "https://erp.example.com"
        client.application.config["ERP_DB"] = "test_db"
        client.application.config["ERP_USERNAME"] = "user"
        client.application.config["ERP_PASSWORD"] = "pass"

        def fake_execute_kw(self, company_id, model, method, args, kwargs=None):
            assert company_id == 3
            assert model == "res.company"
            return [{"id": 3, "name": "Société Test"}]

        monkeypatch.setattr(ErpClient, "execute_kw", fake_execute_kw)

        resp = client.post("/api/settings/erp/test", json={"company_id": 3}, headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "Société Test" in data["message"]

    def test_test_erp_echec_client_retourne_ok_false_200(self, client, auth_headers_admin, monkeypatch):
        client.application.config["ERP_URL"] = "https://erp.example.com"
        client.application.config["ERP_DB"] = "test_db"
        client.application.config["ERP_USERNAME"] = "user"
        client.application.config["ERP_PASSWORD"] = "pass"

        def fake_execute_kw(self, company_id, model, method, args, kwargs=None):
            raise ErpClientError("connexion refusée")

        monkeypatch.setattr(ErpClient, "execute_kw", fake_execute_kw)

        resp = client.post("/api/settings/erp/test", json={"company_id": 3}, headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is False


# ══════════════════════════════════════════════════════════════
#  Routes /api/settings/general (§4.3)
# ══════════════════════════════════════════════════════════════
class TestSettingsGeneral:
    def test_get_general_defauts(self, client, auth_headers):
        resp = client.get("/api/settings/general", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["document_blocking_expired"] is False
        assert data["vacation_delay_threshold_minutes"] == 15

    def test_put_general_permanencier_refuse_403(self, client, auth_headers):
        resp = client.put(
            "/api/settings/general", json={"document_blocking_expired": True}, headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_put_general_admin_met_a_jour(self, client, auth_headers_admin):
        resp = client.put(
            "/api/settings/general",
            json={"document_blocking_expired": True, "vacation_delay_threshold_minutes": 30},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["document_blocking_expired"] is True
        assert data["vacation_delay_threshold_minutes"] == 30

    def test_put_general_seuil_negatif_retourne_422(self, client, auth_headers_admin):
        resp = client.put(
            "/api/settings/general", json={"vacation_delay_threshold_minutes": -5}, headers=auth_headers_admin,
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════
#  Accès direct ERP audité (§4.4)
# ══════════════════════════════════════════════════════════════
class TestErpDirectAccess:
    def test_direct_access_permanencier_refuse_403(self, client, auth_headers):
        resp = client.get("/api/erp/direct-access", headers=auth_headers)
        assert resp.status_code == 403

    def test_direct_access_sans_config_retourne_404(self, client, auth_headers_admin):
        resp = client.get("/api/erp/direct-access", headers=auth_headers_admin)
        assert resp.status_code == 404

    def test_direct_access_admin_retourne_et_trace_audit(self, client, auth_headers_admin, db, default_tenant):
        cfg = ErpConfig(
            tenant_id=default_tenant.id, url_erp="https://erp.example.com",
            admin_username="support", admin_password="s3cret",
        )
        db.session.add(cfg)
        db.session.commit()

        before = AuditLog.query.filter_by(table_name="erp").count()
        resp = client.get("/api/erp/direct-access", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["url_erp"] == "https://erp.example.com"
        assert data["admin_password"] == "s3cret"

        after = AuditLog.query.filter_by(table_name="erp").count()
        assert after == before + 1
        entry = AuditLog.query.filter_by(table_name="erp").order_by(AuditLog.id.desc()).first()
        assert entry.new_values["event"] == "ERP_DIRECT_ACCESS_VIEWED"


# ══════════════════════════════════════════════════════════════
#  Dispatch (flask erp-sync-dispatch)
# ══════════════════════════════════════════════════════════════
class TestDispatchErpSync:
    def test_dispatch_traite_une_ligne_pending(self, db, default_tenant):
        row = ErpSyncQueue(tenant_id=default_tenant.id, flux="partner_create", status="pending")
        db.session.add(row)
        db.session.commit()

        result = dispatch_erp_sync(db)
        assert result["failed"] == 1  # aucun flux réel implémenté en Phase 6 (cf. docstring)

        db.session.refresh(row)
        assert row.status == "failed"
        assert row.attempts == 1
        assert row.locked_at is None
        assert row.locked_until is None

    def test_dispatch_ignore_une_ligne_verrouillee(self, db, default_tenant):
        from datetime import timedelta
        from app.utils.time import utcnow

        row = ErpSyncQueue(
            tenant_id=default_tenant.id, flux="partner_create", status="in_flight",
            locked_at=utcnow(), locked_until=utcnow() + timedelta(seconds=60),
        )
        db.session.add(row)
        db.session.commit()

        result = dispatch_erp_sync(db)
        assert result["processed"] == 0
        assert result["failed"] == 0

    def test_dispatch_ignore_une_ligne_ayant_epuise_ses_tentatives(self, db, default_tenant):
        row = ErpSyncQueue(
            tenant_id=default_tenant.id, flux="partner_create", status="failed", attempts=5,
        )
        db.session.add(row)
        db.session.commit()

        result = dispatch_erp_sync(db)
        assert result["processed"] == 0
        assert result["failed"] == 0
        db.session.refresh(row)
        assert row.attempts == 5  # inchangé, jamais repris


# ══════════════════════════════════════════════════════════════
#  Client factice (§2.5)
# ══════════════════════════════════════════════════════════════
class TestFakeErpClient:
    def test_create_then_search_read(self):
        fake = FakeErpClient()
        partner_id = fake.execute_kw(3, "res.partner", "create", [{"name": "Client X", "x_permatel_ref": "t1:client:1"}])
        assert partner_id == 1

        found = fake.execute_kw(3, "res.partner", "search_read", [[["x_permatel_ref", "=", "t1:client:1"]], ["name"]])
        assert len(found) == 1
        assert found[0]["name"] == "Client X"

    def test_write(self):
        fake = FakeErpClient()
        pid = fake.execute_kw(3, "res.partner", "create", [{"name": "Old"}])
        fake.execute_kw(3, "res.partner", "write", [[pid], {"name": "New"}])
        result = fake.execute_kw(3, "res.partner", "read", [[pid], ["name"]])
        assert result[0]["name"] == "New"

    def test_company_id_obligatoire(self):
        fake = FakeErpClient()
        with pytest.raises(ValueError):
            fake.execute_kw(0, "res.partner", "create", [{"name": "X"}])


# ══════════════════════════════════════════════════════════════
#  Backfill CLI (squelette)
# ══════════════════════════════════════════════════════════════
class TestErpBackfillCommand:
    def test_backfill_dry_run_compte_sans_ecrire(self, app, db, default_tenant):
        from app.scripts.erp_backfill import erp_backfill_command

        default_tenant.channel_erp = True
        db.session.commit()

        runner = CliRunner()
        with app.app_context():
            result = runner.invoke(erp_backfill_command, ["--tenant-code", default_tenant.code])
        assert result.exit_code == 0
        assert "dry-run" in result.output
        assert "total" in result.output

    def test_backfill_canal_erp_desactive_erreur(self, app, db, default_tenant):
        from app.scripts.erp_backfill import erp_backfill_command

        runner = CliRunner()
        with app.app_context():
            result = runner.invoke(erp_backfill_command, ["--tenant-code", default_tenant.code])
        assert result.exit_code != 0

    def test_backfill_tenant_inconnu_erreur(self, app, db):
        from app.scripts.erp_backfill import erp_backfill_command

        runner = CliRunner()
        with app.app_context():
            result = runner.invoke(erp_backfill_command, ["--tenant-code", "INEXISTANT"])
        assert result.exit_code != 0
