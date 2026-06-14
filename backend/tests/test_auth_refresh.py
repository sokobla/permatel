"""
Tests Phase 1 - POST /api/auth/refresh

Scenarios couverts :
  - Refresh reussi : 200 + nouveau access_token + expires_in
  - Nouveau token different de l'original
  - Inactivite depassee (> 30 min) : 403
  - Refresh token revoque (blocklist) : 401
  - Session introuvable en base : 401
  - Utilisation d'un access token a la place du refresh : 422
  - Refresh sans Authorization : 401
"""
from datetime import datetime, timedelta

REFRESH_URL = "/api/auth/refresh"
LOGOUT_URL  = "/api/auth/logout"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# Refresh reussi
# ─────────────────────────────────────────────────────────────────────────────

class TestRefreshSuccess:
    """Le refresh token valide doit generer un nouveau access token."""

    def test_refresh_returns_200(self, client, tokens_permanencier):
        refresh = tokens_permanencier["refresh_token"]
        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        assert resp.status_code == 200

    def test_refresh_response_has_access_token(self, client, tokens_permanencier):
        refresh = tokens_permanencier["refresh_token"]
        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        data = resp.get_json()
        assert "access_token" in data
        assert data["access_token"]

    def test_refresh_response_has_expires_in(self, client, tokens_permanencier):
        refresh = tokens_permanencier["refresh_token"]
        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        data = resp.get_json()
        assert "expires_in" in data
        assert isinstance(data["expires_in"], int)
        assert data["expires_in"] > 0

    def test_new_access_token_differs_from_original(self, client, tokens_permanencier):
        """Chaque refresh doit produire un token different (JTI unique)."""
        original = tokens_permanencier["access_token"]
        refresh  = tokens_permanencier["refresh_token"]
        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        data = resp.get_json()
        assert data["access_token"] != original

    def test_new_access_token_is_usable(self, client, tokens_permanencier):
        """Le nouveau access token doit etre accepte sur /api/auth/me."""
        refresh = tokens_permanencier["refresh_token"]
        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        new_access = resp.get_json()["access_token"]

        me_resp = client.get("/api/auth/me", headers=_auth(new_access))
        assert me_resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Inactivite depassee
# ─────────────────────────────────────────────────────────────────────────────

class TestRefreshInactivity:
    """Simuler un timeout d'inactivite en modifiant last_activity_at."""

    def test_inactivity_timeout_returns_403(self, client, tokens_permanencier, db):
        from app.models.user_session import UserSession
        refresh    = tokens_permanencier["refresh_token"]
        session_id = tokens_permanencier["session_id"]

        # Retourner last_activity_at 35 minutes en arriere (seuil = 30 min)
        session = UserSession.query.get(session_id)
        session.last_activity_at = datetime.utcnow() - timedelta(minutes=35)
        db.session.commit()

        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        assert resp.status_code == 403

    def test_inactivity_timeout_has_error_message(self, client, tokens_permanencier, db):
        from app.models.user_session import UserSession
        refresh    = tokens_permanencier["refresh_token"]
        session_id = tokens_permanencier["session_id"]

        session = UserSession.query.get(session_id)
        session.last_activity_at = datetime.utcnow() - timedelta(minutes=35)
        db.session.commit()

        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        data = resp.get_json()
        assert "error" in data

    def test_no_inactivity_within_threshold(self, client, tokens_permanencier, db):
        """Avec seulement 10 min d'inactivite, le refresh doit reussir."""
        from app.models.user_session import UserSession
        refresh    = tokens_permanencier["refresh_token"]
        session_id = tokens_permanencier["session_id"]

        session = UserSession.query.get(session_id)
        session.last_activity_at = datetime.utcnow() - timedelta(minutes=10)
        db.session.commit()

        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Refresh token revoque (blocklist)
# ─────────────────────────────────────────────────────────────────────────────

class TestRefreshRevokedToken:
    """Un refresh token present dans la blocklist doit etre refuse (401)."""

    def test_revoked_token_returns_401(self, client, tokens_permanencier, db):
        from flask_jwt_extended import decode_token
        from app.models.token_blocklist import TokenBlocklist

        refresh = tokens_permanencier["refresh_token"]

        # Decoder le token pour obtenir JTI et expiration
        decoded  = decode_token(refresh)
        jti      = decoded["jti"]
        exp      = datetime.utcfromtimestamp(decoded["exp"])
        user_id  = int(decoded["sub"])

        # Inserer le JTI dans la blocklist
        entry = TokenBlocklist(
            jti        = jti,
            token_type = "refresh",
            user_id    = user_id,
            expires_at = exp,
        )
        db.session.add(entry)
        db.session.commit()

        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        assert resp.status_code == 401

    def test_logout_revokes_refresh_token(self, client, tokens_permanencier):
        """Apres logout, le refresh token doit etre rejete (401)."""
        access  = tokens_permanencier["access_token"]
        refresh = tokens_permanencier["refresh_token"]

        client.post(LOGOUT_URL, headers=_auth(access))

        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Session introuvable
# ─────────────────────────────────────────────────────────────────────────────

class TestRefreshSessionNotFound:
    """Si la session n'existe plus en base, le refresh doit retourner 401."""

    def test_missing_session_returns_401(self, client, tokens_permanencier, db):
        from app.models.user_session import UserSession
        refresh    = tokens_permanencier["refresh_token"]
        session_id = tokens_permanencier["session_id"]

        # Supprimer la session (sans revoquer le token)
        session = UserSession.query.get(session_id)
        if session:
            db.session.delete(session)
            db.session.commit()

        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        assert resp.status_code == 401

    def test_missing_session_has_error_message(self, client, tokens_permanencier, db):
        from app.models.user_session import UserSession
        refresh    = tokens_permanencier["refresh_token"]
        session_id = tokens_permanencier["session_id"]

        session = UserSession.query.get(session_id)
        if session:
            db.session.delete(session)
            db.session.commit()

        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        data = resp.get_json()
        assert "error" in data


# ─────────────────────────────────────────────────────────────────────────────
# Mauvais type de token
# ─────────────────────────────────────────────────────────────────────────────

class TestRefreshWrongTokenType:
    """Utiliser un access token sur l'endpoint refresh doit retourner 422."""

    def test_access_token_on_refresh_returns_422(self, client, tokens_permanencier):
        access = tokens_permanencier["access_token"]
        resp = client.post(REFRESH_URL, headers=_auth(access))
        assert resp.status_code == 422

    def test_no_token_returns_401(self, client, db):
        resp = client.post(REFRESH_URL)
        assert resp.status_code == 401
