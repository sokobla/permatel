"""
Exécution à distance ESL (13/08) — déclenchement automatique des jobs
`agent_login`/`agent_logout` au login/logout PERMATEL (Phase C du plan).

`_dispatch_pbx_job` est importé paresseusement dans auth.py (à l'intérieur
de login()/logout()) pour éviter tout risque d'import circulaire avec
app.routes.telephony — on patche donc directement
`app.routes.telephony._dispatch_pbx_job`, la cible réellement résolue à
l'exécution.
Correctif 14/08 : login()/logout() persistent aussi immédiatement un
`TelephonyEvent` (CALLCENTER_AGENT_STATE_CHANGE) via
`_record_and_broadcast_agent_status_event` — même motif que
`set_my_agent_status` — pour que le statut implicite déclenché par
l'authentification PERMATEL n'attende pas le round-trip connecteur/PBX
pour apparaître (Supervision temps réel, /agents/status).
"""
from unittest.mock import patch

from app.models import SessionStatus, TelephonyEvent, UserSession

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

    def test_login_persiste_le_statut_on_break_meme_sans_connecteur(
        self, client, db, user_permanencier, default_tenant,
    ):
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()

        resp = client.post(LOGIN_URL, json={"username": "permanencier1", "password": "Password123!"})
        assert resp.status_code == 200

        event = TelephonyEvent.query.filter_by(
            tenant_id=default_tenant.id, agent_uuid="agent-uuid-1",
        ).order_by(TelephonyEvent.id.desc()).first()
        assert event is not None
        assert event.event_type == "CALLCENTER_AGENT_STATE_CHANGE"
        assert event.agent_status == "On Break"
        assert event.pause_code == "0"

    def test_login_met_la_session_en_pause_et_stamp_user_session_id(
        self, client, db, user_permanencier, default_tenant,
    ):
        """Suivi des temps de login/pause (14/08) : au login, la session
        PERMATEL démarre en PAUSED (le statut "On Break" implicite du
        login) — pas ACTIVE — et l'événement porte bien user_session_id."""
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()

        resp = client.post(LOGIN_URL, json={"username": "permanencier1", "password": "Password123!"})
        session_id = resp.get_json()["session_id"]

        db.session.expire_all()
        session = UserSession.query.get(session_id)
        assert session.status == SessionStatus.PAUSED

        event = TelephonyEvent.query.filter_by(
            tenant_id=default_tenant.id, agent_uuid="agent-uuid-1",
        ).order_by(TelephonyEvent.id.desc()).first()
        assert event.user_session_id == session_id


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

    def test_logout_persiste_le_statut_logged_out_meme_sans_connecteur(
        self, client, db, user_permanencier, default_tenant,
    ):
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()
        login_resp = client.post(LOGIN_URL, json={"username": "permanencier1", "password": "Password123!"})
        access = login_resp.get_json()["access_token"]

        resp = client.post(LOGOUT_URL, headers=_auth(access))
        assert resp.status_code == 200

        event = TelephonyEvent.query.filter_by(
            tenant_id=default_tenant.id, agent_uuid="agent-uuid-1", agent_status="Logged Out",
        ).order_by(TelephonyEvent.id.desc()).first()
        assert event is not None
        assert event.event_type == "CALLCENTER_AGENT_STATE_CHANGE"

    def test_logout_ne_reouvre_pas_la_session_deja_terminee(
        self, client, db, user_permanencier, default_tenant,
    ):
        """`_record_and_broadcast_agent_status_event` ne doit jamais
        toucher `session.status` pour "Logged Out" — même en le passant
        explicitement, la session déjà ENDED par logout() ne doit pas
        repasser ACTIVE/PAUSED."""
        user_permanencier.agent_login = "agent-uuid-1"
        db.session.commit()
        login_resp = client.post(LOGIN_URL, json={"username": "permanencier1", "password": "Password123!"})
        access = login_resp.get_json()["access_token"]
        session_id = login_resp.get_json()["session_id"]

        client.post(LOGOUT_URL, headers=_auth(access))

        db.session.expire_all()
        session = UserSession.query.get(session_id)
        assert session.status == SessionStatus.ENDED
        assert session.session_end is not None
