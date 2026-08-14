import csv
import io
from datetime import datetime, timedelta

import pytest
from app.models.telephony_event import TelephonyEvent
from app.models.user_session import UserSession, SessionStatus
from app.routes.auth import _session_status_durations


@pytest.fixture
def auth_headers_manager_tenant(client, user_manager, default_tenant):
    """Token JWT MANAGER + tenant_id (tid) — requis par les routes de monitoring
    (@role_required(ADMIN, MANAGER))."""
    resp_login = client.post("/api/auth/login", json={
        "username": user_manager.username,
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
def sessions_echelonnees(db, default_tenant, user_permanencier):
    """Crée 2 sessions ACTIVE avec des session_start distincts pour le tenant actif."""
    now = datetime.utcnow()
    rows = []
    for days_ago in [40, 2]:
        s = UserSession(
            user_id=user_permanencier.id,
            active_tenant_id=default_tenant.id,
            status=SessionStatus.ACTIVE,
            session_start=now - timedelta(days=days_ago),
            ip_address="10.0.0.1",
        )
        db.session.add(s)
        rows.append(s)
    db.session.commit()
    return rows


class TestSessionsMonitoringDateFilterAndExport:

    # NB : auth_headers_manager_tenant effectue un vrai login, qui crée sa propre
    # UserSession (session_start = now) — elle est donc toujours incluse en plus
    # des `sessions_echelonnees` créées directement en base ci-dessous.

    def test_monitoring_filtree_par_from(self, client, auth_headers_manager_tenant, sessions_echelonnees):
        cutoff = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d")
        resp = client.get(f"/api/auth/sessions/monitoring?status=all&from={cutoff}", headers=auth_headers_manager_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 2  # session J-2 + la session de login du manager

    def test_export_csv(self, client, auth_headers_manager_tenant, sessions_echelonnees):
        resp = client.get("/api/auth/sessions/monitoring/export?status=all", headers=auth_headers_manager_tenant)
        assert resp.status_code == 200
        assert resp.mimetype == "text/csv"
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        assert rows[0] == [
            "username", "full_name", "role", "status", "ip_address", "user_agent",
            "agent_login", "station_extension", "session_start", "last_activity_at", "session_end",
            "active_minutes", "pause_minutes",
        ]
        assert len(rows) - 1 == 3  # 2 sessions échelonnées + la session de login du manager

    def test_export_csv_filtre_par_date(self, client, auth_headers_manager_tenant, sessions_echelonnees):
        cutoff = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d")
        resp = client.get(f"/api/auth/sessions/monitoring/export?status=all&from={cutoff}", headers=auth_headers_manager_tenant)
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        assert len(rows) - 1 == 2  # session J-2 + la session de login du manager

    def test_export_csv_refuse_role_non_staff(self, client, auth_headers, sessions_echelonnees):
        """PERMANENCIER (auth_headers) n'a pas accès à l'export de supervision."""
        resp = client.get("/api/auth/sessions/monitoring/export", headers=auth_headers)
        assert resp.status_code == 403


class TestSessionsStatsSmoke:
    """Couverture minimale sur /sessions/stats — logique interne (agrégation
    Python) non testée en détail ici, seulement la forme de la réponse et le
    tenant-scoping. Cf. le plan Rapports : la réécriture SQL de cette
    agrégation est explicitement reportée (risque cross-dialecte)."""

    def test_sessions_stats_200_et_forme_de_la_reponse(self, client, auth_headers_manager_tenant, sessions_echelonnees):
        resp = client.get("/api/auth/sessions/stats", headers=auth_headers_manager_tenant)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "realtime" in data
        assert "activity" in data
        assert "security" in data

    def test_sessions_stats_refuse_role_non_staff(self, client, auth_headers, sessions_echelonnees):
        resp = client.get("/api/auth/sessions/stats", headers=auth_headers)
        assert resp.status_code == 403

    def test_sessions_stats_total_online_min_somme_les_sessions_terminees(
        self, client, db, default_tenant, user_permanencier, auth_headers_manager_tenant,
    ):
        """total_online_min doit être la SOMME des durées des sessions
        terminées dans la période — pas la moyenne (déjà couverte par
        avg_duration_min) ni la médiane."""
        base = datetime.utcnow() - timedelta(days=1)
        db.session.add(UserSession(
            user_id=user_permanencier.id, active_tenant_id=default_tenant.id,
            status=SessionStatus.ENDED, session_start=base, session_end=base + timedelta(minutes=30),
        ))
        db.session.add(UserSession(
            user_id=user_permanencier.id, active_tenant_id=default_tenant.id,
            status=SessionStatus.ENDED, session_start=base, session_end=base + timedelta(minutes=45),
        ))
        db.session.commit()

        resp = client.get("/api/auth/sessions/stats", headers=auth_headers_manager_tenant)
        assert resp.status_code == 200
        activity = resp.get_json()["activity"]
        assert activity["total_online_min"] == 75.0
        assert activity["avg_duration_min"] == 37.5

    def test_sessions_stats_total_pause_et_active_min_decomposent_le_temps(
        self, client, db, default_tenant, user_permanencier, auth_headers_manager_tenant,
    ):
        """Suivi des temps de login/pause (14/08) : total_active_min +
        total_pause_min doit reconstituer total_online_min pour une session
        dont l'historique de statut est connu."""
        base = datetime.utcnow() - timedelta(days=1)
        session = UserSession(
            user_id=user_permanencier.id, active_tenant_id=default_tenant.id,
            status=SessionStatus.ENDED, session_start=base, session_end=base + timedelta(minutes=60),
        )
        db.session.add(session)
        db.session.commit()
        # 0-20min : actif (implicite, avant le premier événement) ;
        # 20-45min : pause ; 45-60min : actif.
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, user_session_id=session.id,
            event_type="CALLCENTER_AGENT_STATE_CHANGE", agent_status="On Break",
            agent_uuid="agent-uuid-1", created_at=base + timedelta(minutes=20),
        ))
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, user_session_id=session.id,
            event_type="CALLCENTER_AGENT_STATE_CHANGE", agent_status="Available",
            agent_uuid="agent-uuid-1", created_at=base + timedelta(minutes=45),
        ))
        db.session.commit()

        resp = client.get("/api/auth/sessions/stats", headers=auth_headers_manager_tenant)
        activity = resp.get_json()["activity"]
        assert activity["total_active_min"] == 35.0
        assert activity["total_pause_min"] == 25.0


class TestSessionStatusDurations:
    """`_session_status_durations()` — reconstruction des minutes actif/pause
    à partir de l'historique TelephonyEvent d'une session (14/08)."""

    def test_sans_evenement_toute_la_session_est_active(self, db, default_tenant, user_permanencier):
        base = datetime.utcnow()
        session = UserSession(
            user_id=user_permanencier.id, active_tenant_id=default_tenant.id,
            status=SessionStatus.ENDED, session_start=base, session_end=base + timedelta(minutes=30),
        )
        db.session.add(session)
        db.session.commit()

        durations = _session_status_durations(session)
        assert durations == {"active_min": 30.0, "pause_min": 0.0, "offline_min": 0.0}

    def test_segments_pause_actif_et_deconnecte(self, db, default_tenant, user_permanencier):
        base = datetime.utcnow() - timedelta(hours=1)
        session = UserSession(
            user_id=user_permanencier.id, active_tenant_id=default_tenant.id,
            status=SessionStatus.ENDED, session_start=base, session_end=base + timedelta(minutes=40),
        )
        db.session.add(session)
        db.session.commit()
        # 0-10 actif (implicite) ; 10-25 pause ; 25-30 déconnecté (Logged
        # Out, agent raccroché sans quitter PERMATEL) ; 30-40 actif.
        for offset, status in [(10, "On Break"), (25, "Logged Out"), (30, "Available")]:
            db.session.add(TelephonyEvent(
                tenant_id=default_tenant.id, user_session_id=session.id,
                event_type="CALLCENTER_AGENT_STATE_CHANGE", agent_status=status,
                agent_uuid="agent-uuid-1", created_at=base + timedelta(minutes=offset),
            ))
        db.session.commit()

        durations = _session_status_durations(session)
        assert durations["active_min"] == 20.0
        assert durations["pause_min"] == 15.0
        assert durations["offline_min"] == 5.0

    def test_session_encore_ouverte_bornee_a_now(self, db, default_tenant, user_permanencier):
        base = datetime.utcnow() - timedelta(minutes=30)
        session = UserSession(
            user_id=user_permanencier.id, active_tenant_id=default_tenant.id,
            status=SessionStatus.ACTIVE, session_start=base, session_end=None,
        )
        db.session.add(session)
        db.session.commit()
        db.session.add(TelephonyEvent(
            tenant_id=default_tenant.id, user_session_id=session.id,
            event_type="CALLCENTER_AGENT_STATE_CHANGE", agent_status="On Break",
            agent_uuid="agent-uuid-1", created_at=base + timedelta(minutes=10),
        ))
        db.session.commit()

        now = base + timedelta(minutes=30)
        durations = _session_status_durations(session, now=now)
        assert durations["active_min"] == 10.0
        assert durations["pause_min"] == 20.0
