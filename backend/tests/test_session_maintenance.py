"""
Maintenance des sessions (`flask sessions-sweep`) — expiration par
inactivité + purge de la blocklist.

15/08 : une session expirée par inactivité doit aussi déconnecter l'agent
côté PBX (`notify_pbx_agent_logout`, `app/routes/telephony.py`) — jusqu'ici
seul le logout() manuel déclenchait ce job. Aucun test n'existait pour
`expire_inactive_sessions`/`sweep_sessions` avant cette passe.
"""
from datetime import timedelta
from unittest.mock import patch

from app.models.token_blocklist import TokenBlocklist
from app.models.user_session import SessionStatus, UserSession
from app.scripts.session_maintenance import expire_inactive_sessions, sweep_sessions
from app.utils.time import utcnow


def _make_session(db, user, tenant_id=None, status=SessionStatus.ACTIVE,
                   agent_login=None, last_activity_minutes_ago=None, jti=None):
    session = UserSession(
        user_id=user.id,
        jti=jti,
        active_tenant_id=tenant_id,
        status=status,
        agent_login=agent_login,
        last_activity_at=(
            utcnow() - timedelta(minutes=last_activity_minutes_ago)
            if last_activity_minutes_ago is not None else utcnow()
        ),
    )
    db.session.add(session)
    db.session.commit()
    return session


class TestExpireInactiveSessions:
    def test_retourne_la_liste_des_sessions_expirees_pas_un_compte(self, app, db, user_permanencier, default_tenant):
        _make_session(db, user_permanencier, default_tenant.id, last_activity_minutes_ago=60)
        with app.app_context():
            result = expire_inactive_sessions(db, timeout_minutes=30)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], UserSession)

    def test_ne_touche_pas_les_sessions_paused(self, app, db, user_permanencier, default_tenant):
        """Motif déjà en place : les sessions PAUSED (pause téléphonique
        ESL) ne sont jamais expirées par inactivité."""
        paused = _make_session(
            db, user_permanencier, default_tenant.id,
            status=SessionStatus.PAUSED, last_activity_minutes_ago=60,
        )
        with app.app_context():
            result = expire_inactive_sessions(db, timeout_minutes=30)
        assert result == []
        db.session.refresh(paused)
        assert paused.status == SessionStatus.PAUSED

    def test_ne_touche_pas_une_session_active_recente(self, app, db, user_permanencier, default_tenant):
        recent = _make_session(db, user_permanencier, default_tenant.id, last_activity_minutes_ago=5)
        with app.app_context():
            result = expire_inactive_sessions(db, timeout_minutes=30)
        assert result == []
        db.session.refresh(recent)
        assert recent.status == SessionStatus.ACTIVE


class TestSweepSessionsDispatchesAgentLogoutJob:
    def test_sweep_declenche_le_job_pour_une_session_expiree_avec_agent_login(
        self, app, db, user_permanencier, default_tenant,
    ):
        _make_session(
            db, user_permanencier, default_tenant.id,
            agent_login="agent-uuid-1", last_activity_minutes_ago=60,
        )
        with app.app_context():
            with patch("app.routes.telephony._dispatch_pbx_job") as dispatch_mock:
                result = sweep_sessions(db, timeout_minutes=30)

        assert result["expired"] == 1
        dispatch_mock.assert_called_once_with(default_tenant.id, "agent_logout", "agent-uuid-1")

    def test_sweep_ne_declenche_rien_pour_une_session_sans_agent_login(
        self, app, db, user_permanencier, default_tenant,
    ):
        _make_session(db, user_permanencier, default_tenant.id, last_activity_minutes_ago=60)
        with app.app_context():
            with patch("app.routes.telephony._dispatch_pbx_job") as dispatch_mock:
                result = sweep_sessions(db, timeout_minutes=30)

        assert result["expired"] == 1
        dispatch_mock.assert_not_called()

    def test_sweep_reussit_et_committe_meme_si_le_dispatch_pbx_echoue(
        self, app, db, user_permanencier, default_tenant,
    ):
        """Best-effort strict : sweep_sessions() ne doit jamais lever, sinon
        scripts/sessions_sweep.py::main() reporterait à tort un échec du
        sweep alors que le travail DB a réussi."""
        session = _make_session(
            db, user_permanencier, default_tenant.id,
            agent_login="agent-uuid-1", last_activity_minutes_ago=60,
        )
        with app.app_context():
            with patch("app.routes.telephony._dispatch_pbx_job", side_effect=RuntimeError("boom")):
                result = sweep_sessions(db, timeout_minutes=30)  # ne doit pas lever

        assert result["expired"] == 1
        db.session.refresh(session)
        assert session.status == SessionStatus.EXPIRED
        assert session.session_end is not None

    def test_sweep_traite_les_sessions_suivantes_meme_si_une_echoue(
        self, app, db, user_permanencier, default_tenant,
    ):
        """Un échec de dispatch sur une session n'empêche pas le traitement
        des suivantes dans la même boucle."""
        _make_session(
            db, user_permanencier, default_tenant.id,
            agent_login="agent-uuid-1", last_activity_minutes_ago=60, jti="jti-1",
        )
        _make_session(
            db, user_permanencier, default_tenant.id,
            agent_login="agent-uuid-2", last_activity_minutes_ago=60, jti="jti-2",
        )
        with app.app_context():
            with patch(
                "app.routes.telephony._dispatch_pbx_job",
                side_effect=[RuntimeError("boom"), True],
            ) as dispatch_mock:
                result = sweep_sessions(db, timeout_minutes=30)

        assert result["expired"] == 2
        assert dispatch_mock.call_count == 2

    def test_sweep_purge_toujours_la_blocklist_expiree(self, app, db, user_permanencier, default_tenant):
        entry = TokenBlocklist(jti="expired-jti", token_type="access", user_id=user_permanencier.id,
                                expires_at=utcnow() - timedelta(hours=1))
        db.session.add(entry)
        db.session.commit()

        with app.app_context():
            result = sweep_sessions(db)

        assert result["purged"] == 1
        assert TokenBlocklist.query.filter_by(jti="expired-jti").first() is None
