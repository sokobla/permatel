"""
Mot de passe oublié (self-service) : POST /api/auth/forgot-password,
GET/POST /api/auth/reset-password/<token> — anti-énumération, expiration 1h,
et invalidation des sessions actives à la complétion.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.models.setting import SmtpSetting
from app.models.token_blocklist import TokenBlocklist
from app.models.user_session import SessionStatus, UserSession
from app.models.user_token import UserToken, PURPOSE_PASSWORD_RESET, STATUS_PENDING, STATUS_COMPLETED, STATUS_EXPIRED
from app.utils.tokens import hash_token


@pytest.fixture
def smtp_settings(db, default_tenant):
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
    sent = []

    def _fake_send(cfg, msg):
        sent.append(msg)

    monkeypatch.setattr("app.utils.email_templates.send_via_smtp", _fake_send)
    return sent


class TestForgotPassword:
    def test_email_existant_retourne_200_et_cree_un_jeton(
        self, client, db, user_permanencier, smtp_settings, mock_smtp_send,
    ):
        resp = client.post("/api/auth/forgot-password", json={"email": user_permanencier.email})
        assert resp.status_code == 200

        token = UserToken.query.filter_by(
            user_id=user_permanencier.id, purpose=PURPOSE_PASSWORD_RESET,
        ).first()
        assert token is not None
        assert token.status == STATUS_PENDING
        assert len(mock_smtp_send) == 1

    def test_email_inexistant_retourne_200_identique_anti_enumeration(self, client, db):
        """Ne doit JAMAIS distinguer 'existe' de 'n'existe pas' — même statut,
        même message, quel que soit le cas."""
        resp_unknown = client.post("/api/auth/forgot-password", json={"email": "personne@nulle-part.example"})
        assert resp_unknown.status_code == 200
        assert "Si un compte existe" in resp_unknown.get_json()["message"]

    def test_compte_inactif_ne_recoit_pas_de_jeton_mais_reponse_identique(
        self, client, db, user_inactive, smtp_settings, mock_smtp_send,
    ):
        resp = client.post("/api/auth/forgot-password", json={"email": user_inactive.email})
        assert resp.status_code == 200
        assert UserToken.query.filter_by(user_id=user_inactive.id).first() is None
        assert len(mock_smtp_send) == 0

    def test_email_absent_du_corps_retourne_200(self, client, db):
        resp = client.post("/api/auth/forgot-password", json={})
        assert resp.status_code == 200


class TestResetPassword:
    def _create_reset_token(self, db, user, raw="reset-token-abc", ttl_hours=1):
        token = UserToken(
            user_id=user.id, purpose=PURPOSE_PASSWORD_RESET, token_hash=hash_token(raw),
            status=STATUS_PENDING, expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
        )
        db.session.add(token)
        db.session.commit()
        return token

    def test_check_token_valide_retourne_200(self, client, db, user_permanencier):
        self._create_reset_token(db, user_permanencier)
        resp = client.get("/api/auth/reset-password/reset-token-abc")
        assert resp.status_code == 200
        assert resp.get_json()["valid"] is True

    def test_check_token_inconnu_retourne_404(self, client, db):
        resp = client.get("/api/auth/reset-password/inconnu")
        assert resp.status_code == 404

    def test_check_token_expire_retourne_410(self, client, db, user_permanencier):
        token = self._create_reset_token(db, user_permanencier, ttl_hours=-1)
        resp = client.get("/api/auth/reset-password/reset-token-abc")
        assert resp.status_code == 410
        db.session.refresh(token)
        assert token.status == STATUS_EXPIRED

    def test_reset_definit_le_nouveau_mot_de_passe(self, client, db, user_permanencier):
        self._create_reset_token(db, user_permanencier)
        resp = client.post("/api/auth/reset-password/reset-token-abc", json={"password": "NouveauMdp123!"})
        assert resp.status_code == 200

        db.session.refresh(user_permanencier)
        assert user_permanencier.check_password("NouveauMdp123!")

        login_resp = client.post("/api/auth/login", json={
            "username": user_permanencier.username, "password": "NouveauMdp123!",
        })
        assert login_resp.status_code == 200

    def test_reset_mot_de_passe_trop_court_retourne_400(self, client, db, user_permanencier):
        self._create_reset_token(db, user_permanencier)
        resp = client.post("/api/auth/reset-password/reset-token-abc", json={"password": "short"})
        assert resp.status_code == 400

    def test_reset_deux_fois_echoue_la_seconde_fois(self, client, db, user_permanencier):
        self._create_reset_token(db, user_permanencier)
        first = client.post("/api/auth/reset-password/reset-token-abc", json={"password": "NouveauMdp123!"})
        assert first.status_code == 200
        second = client.post("/api/auth/reset-password/reset-token-abc", json={"password": "AutreMdp456!"})
        assert second.status_code == 404

    def test_reset_invalide_toutes_les_sessions_actives(
        self, client, db, user_permanencier, tokens_permanencier, auth_headers,
    ):
        """Décision produit actée : une réinitialisation de mot de passe
        révoque immédiatement toute session déjà ouverte, pas seulement les
        futures connexions."""
        # La session créée par tokens_permanencier (fixture de login) doit
        # être ACTIVE et fonctionnelle avant le reset.
        me_before = client.get("/api/auth/me", headers=auth_headers)
        assert me_before.status_code == 200

        active_sessions_before = UserSession.query.filter_by(
            user_id=user_permanencier.id, status=SessionStatus.ACTIVE,
        ).all()
        assert len(active_sessions_before) >= 1

        self._create_reset_token(db, user_permanencier)
        resp = client.post("/api/auth/reset-password/reset-token-abc", json={"password": "NouveauMdp123!"})
        assert resp.status_code == 200

        for s in active_sessions_before:
            db.session.refresh(s)
            assert s.status == SessionStatus.REVOKED
            if s.jti:
                assert TokenBlocklist.query.filter_by(jti=s.jti).first() is not None

        # Le refresh token de la session d'avant reset ne doit plus fonctionner.
        refresh_headers = {"Authorization": f"Bearer {tokens_permanencier['refresh_token']}"}
        refresh_resp = client.post("/api/auth/refresh", headers=refresh_headers)
        assert refresh_resp.status_code == 401

    def test_reset_declenche_un_job_pbx_pour_une_session_avec_agent_login(
        self, client, db, user_permanencier, default_tenant,
    ):
        """Exécution à distance ESL (15/08) : réinitialiser le mot de passe
        révoque les sessions actives — chacune portant un agent PBX doit
        aussi déclencher un agent_logout, pas seulement logout() manuel."""
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()
        client.post("/api/auth/login", json={"username": "permanencier1", "password": "Password123!"})
        # Le login d'un agent démarre la session en PAUSED ("On Break"
        # implicite, cf. test_auth_pbx_dispatch.py) — _revoke_all_active_sessions()
        # ne cible que ACTIVE (comportement préexistant, hors périmètre de
        # cette passe) : on simule ici une session active pour tester le
        # câblage du dispatch, pas le statut initial post-login.
        UserSession.query.filter_by(user_id=user_permanencier.id).update({"status": SessionStatus.ACTIVE})
        db.session.commit()

        self._create_reset_token(db, user_permanencier)
        with patch("app.routes.telephony._dispatch_pbx_job") as dispatch_mock:
            resp = client.post("/api/auth/reset-password/reset-token-abc", json={"password": "NouveauMdp123!"})

        assert resp.status_code == 200
        dispatch_mock.assert_called_once_with(default_tenant.id, "agent_logout", "agent-uuid-1")

    def test_reset_sans_agent_login_ne_declenche_rien(self, client, db, user_permanencier):
        client.post("/api/auth/login", json={"username": "permanencier1", "password": "Password123!"})

        self._create_reset_token(db, user_permanencier)
        with patch("app.routes.telephony._dispatch_pbx_job") as dispatch_mock:
            resp = client.post("/api/auth/reset-password/reset-token-abc", json={"password": "NouveauMdp123!"})

        assert resp.status_code == 200
        dispatch_mock.assert_not_called()

    def test_reset_reussit_meme_si_le_dispatch_pbx_echoue(self, client, db, user_permanencier):
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()
        client.post("/api/auth/login", json={"username": "permanencier1", "password": "Password123!"})

        self._create_reset_token(db, user_permanencier)
        with patch("app.routes.telephony._dispatch_pbx_job", side_effect=RuntimeError("boom")):
            resp = client.post("/api/auth/reset-password/reset-token-abc", json={"password": "NouveauMdp123!"})

        assert resp.status_code == 200

    def test_reset_declenche_un_job_par_session_multi_appareil(
        self, client, db, user_permanencier, default_tenant,
    ):
        """Deux sessions actives (deux appareils) pour le même agent ->
        deux jobs agent_logout distincts, un par session révoquée."""
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()
        client.post("/api/auth/login", json={"username": "permanencier1", "password": "Password123!"})
        client.post("/api/auth/login", json={"username": "permanencier1", "password": "Password123!"})
        # cf. commentaire du test précédent : le login d'un agent démarre en
        # PAUSED, on simule deux sessions actives pour tester le dispatch.
        UserSession.query.filter_by(user_id=user_permanencier.id).update({"status": SessionStatus.ACTIVE})
        db.session.commit()

        active_before = UserSession.query.filter_by(
            user_id=user_permanencier.id, status=SessionStatus.ACTIVE,
        ).count()
        assert active_before == 2

        self._create_reset_token(db, user_permanencier)
        with patch("app.routes.telephony._dispatch_pbx_job") as dispatch_mock:
            resp = client.post("/api/auth/reset-password/reset-token-abc", json={"password": "NouveauMdp123!"})

        assert resp.status_code == 200
        assert dispatch_mock.call_count == 2
        dispatch_mock.assert_called_with(default_tenant.id, "agent_logout", "agent-uuid-1")
