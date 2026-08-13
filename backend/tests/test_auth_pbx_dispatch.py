"""
Exécution à distance ESL (13/08) — déclenchement automatique des jobs
`agent_login`/`agent_logout` au login/logout PERMATEL (Phase C du plan).

`_dispatch_pbx_job` est importé paresseusement dans auth.py (à l'intérieur
de login()/logout()) pour éviter tout risque d'import circulaire avec
app.routes.telephony — on patche donc directement
`app.routes.telephony._dispatch_pbx_job`, la cible réellement résolue à
l'exécution.
"""
from unittest.mock import patch

LOGIN_URL = "/api/auth/login"
LOGOUT_URL = "/api/auth/logout"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestLoginDispatchesAgentLoginJob:
    def test_login_avec_agent_login_declenche_le_job(self, client, db, user_permanencier, default_tenant):
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()

        with patch("app.routes.telephony._dispatch_pbx_job") as dispatch_mock:
            resp = client.post(LOGIN_URL, json={"username": "permanencier1", "password": "Password123!"})

        assert resp.status_code == 200
        dispatch_mock.assert_called_once_with(default_tenant.id, "agent_login", "agent-uuid-1")

    def test_login_sans_agent_login_ne_declenche_rien(self, client, db, user_permanencier):
        with patch("app.routes.telephony._dispatch_pbx_job") as dispatch_mock:
            resp = client.post(LOGIN_URL, json={"username": "permanencier1", "password": "Password123!"})

        assert resp.status_code == 200
        dispatch_mock.assert_not_called()

    def test_login_reussit_meme_si_le_dispatch_pbx_echoue(self, client, db, user_permanencier):
        """Best-effort : une exception dans le dispatch ne doit jamais faire
        échouer le login lui-même."""
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()

        with patch("app.routes.telephony._dispatch_pbx_job", side_effect=RuntimeError("boom")):
            resp = client.post(LOGIN_URL, json={"username": "permanencier1", "password": "Password123!"})

        assert resp.status_code == 200


class TestLogoutDispatchesAgentLogoutJob:
    def test_logout_avec_agent_login_declenche_le_job(self, client, db, user_permanencier, default_tenant, tokens_permanencier):
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()
        # Rejoue le login pour que la session porte bien agent_login (déjà
        # chargé sur l'objet UserSession à la création, cf. auth.py:383) —
        # le fixture tokens_permanencier a créé sa session AVANT ce commit.
        login_resp = client.post(LOGIN_URL, json={"username": "permanencier1", "password": "Password123!"})
        access = login_resp.get_json()["access_token"]

        with patch("app.routes.telephony._dispatch_pbx_job") as dispatch_mock:
            resp = client.post(LOGOUT_URL, headers=_auth(access))

        assert resp.status_code == 200
        dispatch_mock.assert_called_once_with(default_tenant.id, "agent_logout", "agent-uuid-1")

    def test_logout_sans_agent_login_ne_declenche_rien(self, client, db, tokens_permanencier):
        access = tokens_permanencier["access_token"]

        with patch("app.routes.telephony._dispatch_pbx_job") as dispatch_mock:
            resp = client.post(LOGOUT_URL, headers=_auth(access))

        assert resp.status_code == 200
        dispatch_mock.assert_not_called()

    def test_logout_reussit_meme_si_le_dispatch_pbx_echoue(self, client, db, user_permanencier):
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()
        login_resp = client.post(LOGIN_URL, json={"username": "permanencier1", "password": "Password123!"})
        access = login_resp.get_json()["access_token"]

        with patch("app.routes.telephony._dispatch_pbx_job", side_effect=RuntimeError("boom")):
            resp = client.post(LOGOUT_URL, headers=_auth(access))

        assert resp.status_code == 200
