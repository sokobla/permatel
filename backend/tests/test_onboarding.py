"""
Onboarding utilisateur : déclenchement (POST /api/users), complétion publique
(/api/onboarding), renvoi/révocation, et expiration 24h (flask onboarding-sweep).
"""
from datetime import datetime, timedelta

import pytest

from app.models.setting import SmtpSetting
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.user_token import (
    UserToken, PURPOSE_ONBOARDING, STATUS_PENDING, STATUS_COMPLETED, STATUS_REVOKED, STATUS_EXPIRED,
)
from app.utils.tokens import hash_token


@pytest.fixture
def tenant_b(db):
    t = Tenant(code="TENB-ONBOARD", nom="Tenant B", slug="tenant-b-onboard")
    db.session.add(t)
    db.session.commit()
    return t


@pytest.fixture
def smtp_settings(db, default_tenant):
    """SMTP tenant valide (au sens 'config complète') — le mot de passe n'a
    pas besoin d'être un secret valide puisque send_via_smtp est monkeypatché
    dans tous les tests qui l'utilisent (pas d'appel réseau réel)."""
    cfg = SmtpSetting(
        tenant_id=default_tenant.id, host="smtp.example.com", port=587,
        username="noreply@example.com", password="unused", from_address="noreply@example.com",
        security="tls", is_active=True,
    )
    db.session.add(cfg)
    db.session.commit()
    return cfg


@pytest.fixture
def mock_smtp_send(monkeypatch):
    """Empêche tout appel SMTP réel — enregistre les messages envoyés pour
    inspection par les tests."""
    sent = []

    def _fake_send(cfg, msg):
        sent.append(msg)

    monkeypatch.setattr("app.utils.email_templates.send_via_smtp", _fake_send)
    return sent


class TestCreateUserOnboarding:
    def test_send_onboarding_sans_password_cree_un_jeton_pending(
        self, client, db, auth_headers_admin, default_tenant, smtp_settings, mock_smtp_send,
    ):
        payload = {
            "email": "onboard1@example.com", "nom": "Onboard", "prenom": "Un",
            "role": "PERMANENCIER", "send_onboarding": True,
            "tenant_ids": [str(default_tenant.id)],
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 201
        data = resp.get_json()["user"]
        assert data["onboarding_status"] == STATUS_PENDING

        user = User.query.filter_by(email="onboard1@example.com").first()
        token = UserToken.query.filter_by(user_id=user.id, purpose=PURPOSE_ONBOARDING).first()
        assert token is not None
        assert token.status == STATUS_PENDING
        assert len(mock_smtp_send) == 1
        assert mock_smtp_send[0]["To"] == "onboard1@example.com"

    def test_send_onboarding_et_password_ensemble_retourne_400(
        self, client, auth_headers_admin, default_tenant,
    ):
        payload = {
            "email": "onboard2@example.com", "nom": "Onboard", "prenom": "Deux",
            "role": "PERMANENCIER", "send_onboarding": True, "password": "Password123!",
            "tenant_ids": [str(default_tenant.id)],
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_sans_onboarding_ni_password_retourne_400(self, client, auth_headers_admin, default_tenant):
        payload = {
            "email": "onboard3@example.com", "nom": "Onboard", "prenom": "Trois",
            "role": "PERMANENCIER", "send_onboarding": False,
            "tenant_ids": [str(default_tenant.id)],
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_echec_envoi_email_annule_toute_la_creation(
        self, client, db, auth_headers_admin, default_tenant,
    ):
        """Pas de SmtpSetting configuré -> l'envoi échoue -> l'utilisateur
        n'est PAS créé (rollback complet, pas de compte orphelin sans email)."""
        payload = {
            "email": "onboard4@example.com", "nom": "Onboard", "prenom": "Quatre",
            "role": "PERMANENCIER", "send_onboarding": True,
            "tenant_ids": [str(default_tenant.id)],
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 502
        assert User.query.filter_by(email="onboard4@example.com").first() is None


class TestOnboardingCompletion:
    def _create_pending_user(self, db, default_tenant, email="pending@example.com"):
        user = User(username=email, email=email, nom="N", prenom="P", role=UserRole.PERMANENCIER,
                    is_active=True, onboarding_status=STATUS_PENDING)
        user.set_password("unusable-random-password-not-known")
        user.tenants.append(default_tenant)
        db.session.add(user)
        db.session.flush()
        token = UserToken(
            user_id=user.id, purpose=PURPOSE_ONBOARDING, token_hash=hash_token("plain-token-abc"),
            status=STATUS_PENDING, expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.session.add(token)
        db.session.commit()
        return user, token

    def test_get_onboarding_valide_retourne_infos(self, client, db, default_tenant):
        user, _token = self._create_pending_user(db, default_tenant)
        resp = client.get("/api/onboarding/plain-token-abc")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["email"] == user.email
        assert data["nom"] == "N"

    def test_get_onboarding_token_inconnu_retourne_404(self, client, db):
        resp = client.get("/api/onboarding/token-inexistant")
        assert resp.status_code == 404

    def test_complete_onboarding_definit_le_mot_de_passe(self, client, db, default_tenant):
        user, token = self._create_pending_user(db, default_tenant, email="complete1@example.com")
        resp = client.post("/api/onboarding/plain-token-abc/complete", json={"password": "NouveauMdp123!"})
        assert resp.status_code == 200

        db.session.refresh(user)
        db.session.refresh(token)
        assert user.onboarding_status == STATUS_COMPLETED
        assert token.status == STATUS_COMPLETED
        assert user.check_password("NouveauMdp123!")

        # Login possible avec le nouveau mot de passe
        login_resp = client.post("/api/auth/login", json={
            "username": "complete1@example.com", "password": "NouveauMdp123!",
        })
        assert login_resp.status_code == 200

    def test_complete_onboarding_mot_de_passe_trop_court_retourne_400(self, client, db, default_tenant):
        self._create_pending_user(db, default_tenant, email="complete2@example.com")
        resp = client.post("/api/onboarding/plain-token-abc/complete", json={"password": "short"})
        assert resp.status_code == 400

    def test_complete_onboarding_deux_fois_echoue_la_seconde_fois(self, client, db, default_tenant):
        self._create_pending_user(db, default_tenant, email="complete3@example.com")
        first = client.post("/api/onboarding/plain-token-abc/complete", json={"password": "NouveauMdp123!"})
        assert first.status_code == 200
        second = client.post("/api/onboarding/plain-token-abc/complete", json={"password": "AutreMdp456!"})
        assert second.status_code == 404

    def test_token_expire_retourne_410_et_marque_expired(self, client, db, default_tenant):
        user, token = self._create_pending_user(db, default_tenant, email="expired1@example.com")
        token.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.session.commit()

        resp = client.get("/api/onboarding/plain-token-abc")
        assert resp.status_code == 410

        db.session.refresh(token)
        db.session.refresh(user)
        assert token.status == STATUS_EXPIRED
        assert user.onboarding_status == STATUS_EXPIRED


class TestResendRevokeOnboarding:
    def _create_pending_user(self, db, default_tenant, email="resend@example.com"):
        from app.models.user import UserRole
        user = User(username=email, email=email, nom="N", prenom="P", role=UserRole.PERMANENCIER,
                    is_active=True, onboarding_status=STATUS_PENDING)
        user.set_password("unusable")
        user.tenants.append(default_tenant)
        db.session.add(user)
        db.session.flush()
        token = UserToken(
            user_id=user.id, purpose=PURPOSE_ONBOARDING, token_hash=hash_token("old-token"),
            status=STATUS_PENDING, expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.session.add(token)
        db.session.commit()
        return user, token

    def test_resend_revoque_l_ancien_jeton_et_en_cree_un_nouveau(
        self, client, db, auth_headers_admin, default_tenant, smtp_settings, mock_smtp_send,
    ):
        user, old_token = self._create_pending_user(db, default_tenant, "resend1@example.com")
        resp = client.post(f"/api/users/{user.id}/onboarding/resend", headers=auth_headers_admin)
        assert resp.status_code == 200

        db.session.refresh(old_token)
        assert old_token.status == STATUS_REVOKED
        new_tokens = UserToken.query.filter_by(
            user_id=user.id, purpose=PURPOSE_ONBOARDING, status=STATUS_PENDING,
        ).all()
        assert len(new_tokens) == 1
        assert len(mock_smtp_send) == 1

    def test_resend_sur_onboarding_non_pending_retourne_400(self, client, db, auth_headers_admin, default_tenant):
        user, token = self._create_pending_user(db, default_tenant, "resend2@example.com")
        token.status = STATUS_COMPLETED
        user.onboarding_status = STATUS_COMPLETED
        db.session.commit()

        resp = client.post(f"/api/users/{user.id}/onboarding/resend", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_revoke_marque_le_jeton_et_l_utilisateur_revoked(self, client, db, auth_headers_admin, default_tenant):
        user, token = self._create_pending_user(db, default_tenant, "revoke1@example.com")
        resp = client.delete(f"/api/users/{user.id}/onboarding", headers=auth_headers_admin)
        assert resp.status_code == 200

        db.session.refresh(token)
        db.session.refresh(user)
        assert token.status == STATUS_REVOKED
        assert user.onboarding_status == STATUS_REVOKED

        # Le jeton révoqué ne fonctionne plus pour compléter l'onboarding
        get_resp = client.get("/api/onboarding/old-token")
        assert get_resp.status_code == 404

    def test_resend_refuse_sans_droits_admin(self, client, db, auth_headers, default_tenant):
        """@role_required(ADMIN) uniquement — un PERMANENCIER ne peut pas
        relancer un onboarding, même pour un utilisateur de son propre
        tenant (RBAC non couvert jusqu'ici pour cette route)."""
        user, _token = self._create_pending_user(db, default_tenant, "resend-rbac@example.com")
        resp = client.post(f"/api/users/{user.id}/onboarding/resend", headers=auth_headers)
        assert resp.status_code == 403

    def test_revoke_refuse_sans_droits_admin(self, client, db, auth_headers, default_tenant):
        user, _token = self._create_pending_user(db, default_tenant, "revoke-rbac@example.com")
        resp = client.delete(f"/api/users/{user.id}/onboarding", headers=auth_headers)
        assert resp.status_code == 403


class TestOnboardingAdminGlobalScope:
    """Audit du 12/08 : `UserToken` n'a pas de colonne `tenant_id` (scopé
    uniquement via `user_id`) et les 3 routes admin d'onboarding
    (resend/send/revoke) sont protégées par `@role_required(ADMIN)` — le
    rôle ADMIN GLOBAL, pas `@tenant_admin_required`. Il n'y a donc pas de
    frontière d'isolation par tenant à faire respecter ici : seul un
    super-admin global peut déclencher ces actions, et un super-admin
    global est documenté (CLAUDE.md, cf. test_isolation.py::
    test_super_admin_bypass_appartenance) comme pouvant agir sur n'importe
    quel tenant sans y être membre — exactement comme le reste de l'API
    `/api/users`, elle-même globale par conception (users/tenant_users ne
    sont pas des ressources tenant-scopées). Ce test fige ce comportement
    intentionnel plutôt que de fabriquer un faux test d'isolation qui
    échouerait à trouver un vrai problème."""

    def test_admin_global_relance_onboarding_utilisateur_autre_tenant(
        self, client, db, user_admin, tenant_b, default_tenant, smtp_settings, mock_smtp_send,
    ):
        from app.models.user import UserRole as _Role

        # Utilisateur pending rattaché à default_tenant (CORE) — pas à tenant_b.
        target = User(username="cross-tenant@example.com", email="cross-tenant@example.com",
                      nom="N", prenom="P", role=_Role.PERMANENCIER, is_active=True,
                      onboarding_status=STATUS_PENDING)
        target.set_password("unusable")
        target.tenants.append(default_tenant)
        db.session.add(target)
        db.session.flush()
        db.session.add(UserToken(
            user_id=target.id, purpose=PURPOSE_ONBOARDING, token_hash=hash_token("cross-tenant-token"),
            status=STATUS_PENDING, expires_at=datetime.utcnow() + timedelta(hours=24),
        ))
        db.session.commit()

        login = client.post("/api/auth/login", json={
            "username": "admin1", "password": "Password123!",
        }).get_json()
        # Le super-admin sélectionne tenant_b comme tenant actif — n'y est
        # pas membre, mais reste un admin global.
        sel = client.post(
            "/api/auth/select-tenant",
            json={"tenant_id": str(tenant_b.id)},
            headers={"Authorization": f"Bearer {login['access_token']}"},
        ).get_json()
        headers_scoped_to_b = {"Authorization": f"Bearer {sel['access_token']}"}

        # Alors qu'il est scopé sur tenant_b, il peut quand même relancer
        # l'onboarding d'un utilisateur de default_tenant — comportement
        # intentionnel, pas une fuite : `/api/users/*` est une API globale.
        resp = client.post(
            f"/api/users/{target.id}/onboarding/resend", headers=headers_scoped_to_b,
        )
        assert resp.status_code == 200
        assert len(mock_smtp_send) == 1


class TestSendOnboardingExisting:
    """POST /users/<id>/onboarding/send — renvoyer un lien d'onboarding à un
    utilisateur EXISTANT (compte déjà actif, mot de passe déjà fonctionnel),
    décision produit du 31/07 : contrairement à l'invitation initiale, le
    jeton créé ne doit jamais désactiver le compte à l'expiration."""

    def _create_active_user(self, db, default_tenant, email="existant@example.com", onboarding_status=None):
        from app.models.user import UserRole
        user = User(username=email, email=email, nom="N", prenom="P", role=UserRole.PERMANENCIER,
                    is_active=True, onboarding_status=onboarding_status)
        user.set_password("MotDePasseReel123!")
        user.tenants.append(default_tenant)
        db.session.add(user)
        db.session.commit()
        return user

    def test_envoie_a_un_utilisateur_jamais_onboarde(
        self, client, db, auth_headers_admin, default_tenant, smtp_settings, mock_smtp_send,
    ):
        user = self._create_active_user(db, default_tenant, "jamais@example.com", onboarding_status=None)
        resp = client.post(f"/api/users/{user.id}/onboarding/send", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert len(mock_smtp_send) == 1

        db.session.refresh(user)
        assert user.onboarding_status == STATUS_PENDING
        assert user.is_active is True  # compte inchangé, toujours actif

        token = UserToken.query.filter_by(
            user_id=user.id, purpose=PURPOSE_ONBOARDING, status=STATUS_PENDING,
        ).first()
        assert token is not None
        assert token.deactivate_on_expiry is False

    def test_fonctionne_aussi_pour_un_onboarding_deja_complete_ou_revoque(
        self, client, db, auth_headers_admin, default_tenant, smtp_settings, mock_smtp_send,
    ):
        for status in (STATUS_COMPLETED, STATUS_REVOKED, STATUS_EXPIRED):
            user = self._create_active_user(
                db, default_tenant, f"deja-{status}@example.com", onboarding_status=status,
            )
            resp = client.post(f"/api/users/{user.id}/onboarding/send", headers=auth_headers_admin)
            assert resp.status_code == 200
            db.session.refresh(user)
            assert user.onboarding_status == STATUS_PENDING

    def test_sans_tenant_rattache_retourne_400(self, client, db, auth_headers_admin):
        from app.models.user import UserRole
        user = User(username="sans-tenant@example.com", email="sans-tenant@example.com",
                    nom="N", prenom="P", role=UserRole.PERMANENCIER, is_active=True)
        user.set_password("MotDePasseReel123!")
        db.session.add(user)
        db.session.commit()

        resp = client.post(f"/api/users/{user.id}/onboarding/send", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_echec_envoi_ne_modifie_rien(self, client, db, auth_headers_admin, default_tenant):
        """Pas de SmtpSetting configuré -> l'envoi échoue -> rollback complet,
        le compte et son onboarding_status restent inchangés (pas de jeton
        orphelin créé sans email envoyé)."""
        user = self._create_active_user(db, default_tenant, "echec@example.com", onboarding_status=None)
        resp = client.post(f"/api/users/{user.id}/onboarding/send", headers=auth_headers_admin)
        assert resp.status_code == 502

        db.session.refresh(user)
        assert user.onboarding_status is None
        assert UserToken.query.filter_by(user_id=user.id).first() is None

    def test_refuse_sans_droits_admin(self, client, db, auth_headers, default_tenant):
        user = self._create_active_user(db, default_tenant, "refuse@example.com")
        resp = client.post(f"/api/users/{user.id}/onboarding/send", headers=auth_headers)
        assert resp.status_code == 403


class TestOnboardingSweep:
    def test_sweep_expire_et_desactive_le_compte(self, db, default_tenant):
        from app.models.user import UserRole
        from app.scripts.onboarding_sweep import sweep_onboarding

        user = User(username="expire@example.com", email="expire@example.com", nom="N", prenom="P",
                    role=UserRole.PERMANENCIER, is_active=True, onboarding_status=STATUS_PENDING)
        user.set_password("unusable")
        user.tenants.append(default_tenant)
        db.session.add(user)
        db.session.flush()
        token = UserToken(
            user_id=user.id, purpose=PURPOSE_ONBOARDING, token_hash=hash_token("sweep-token"),
            status=STATUS_PENDING, expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        db.session.add(token)
        db.session.commit()

        result = sweep_onboarding(db)
        assert result["expired"] == 1

        db.session.refresh(user)
        db.session.refresh(token)
        assert token.status == STATUS_EXPIRED
        assert user.onboarding_status == STATUS_EXPIRED
        assert user.is_active is False

    def test_sweep_ignore_les_jetons_non_expires(self, db, default_tenant):
        from app.models.user import UserRole
        from app.scripts.onboarding_sweep import sweep_onboarding

        user = User(username="notyet@example.com", email="notyet@example.com", nom="N", prenom="P",
                    role=UserRole.PERMANENCIER, is_active=True, onboarding_status=STATUS_PENDING)
        user.set_password("unusable")
        user.tenants.append(default_tenant)
        db.session.add(user)
        db.session.flush()
        db.session.add(UserToken(
            user_id=user.id, purpose=PURPOSE_ONBOARDING, token_hash=hash_token("fresh-token"),
            status=STATUS_PENDING, expires_at=datetime.utcnow() + timedelta(hours=23),
        ))
        db.session.commit()

        result = sweep_onboarding(db)
        assert result["expired"] == 0
        db.session.refresh(user)
        assert user.is_active is True

    def test_sweep_n_expire_pas_le_compte_si_deactivate_on_expiry_est_faux(self, db, default_tenant):
        """Renvoi vers un utilisateur existant (POST .../onboarding/send) :
        le jeton expire normalement, mais le compte déjà actif ne doit
        JAMAIS être désactivé — décision produit du 31/07."""
        from app.models.user import UserRole
        from app.scripts.onboarding_sweep import sweep_onboarding

        user = User(username="existant-expire@example.com", email="existant-expire@example.com",
                    nom="N", prenom="P", role=UserRole.PERMANENCIER, is_active=True,
                    onboarding_status=STATUS_PENDING)
        user.set_password("MotDePasseReel123!")
        user.tenants.append(default_tenant)
        db.session.add(user)
        db.session.flush()
        token = UserToken(
            user_id=user.id, purpose=PURPOSE_ONBOARDING, token_hash=hash_token("sweep-existant"),
            status=STATUS_PENDING, expires_at=datetime.utcnow() - timedelta(hours=1),
            deactivate_on_expiry=False,
        )
        db.session.add(token)
        db.session.commit()

        result = sweep_onboarding(db)
        assert result["expired"] == 1

        db.session.refresh(user)
        db.session.refresh(token)
        assert token.status == STATUS_EXPIRED
        assert user.onboarding_status == STATUS_EXPIRED  # reflète l'état du lien...
        assert user.is_active is True  # ...mais le compte reste utilisable
        assert user.check_password("MotDePasseReel123!")  # mot de passe original intact
