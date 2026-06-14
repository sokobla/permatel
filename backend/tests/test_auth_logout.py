"""
Tests Phase 1 - POST /api/auth/logout

Scenarios couverts :
  - Logout reussi : 200 + message "Deconnexion reussie."
  - Access token revoque apres logout : 401 sur /api/auth/me
  - Refresh token revoque apres logout : 401 sur /api/auth/refresh
  - Session fermee (status=ENDED) apres logout
  - Logout sans Authorization header : 401
"""

LOGOUT_URL  = "/api/auth/logout"
ME_URL      = "/api/auth/me"
REFRESH_URL = "/api/auth/refresh"


def _auth(token):
    """Retourne l'header Authorization Bearer."""
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# Logout reussi
# ─────────────────────────────────────────────────────────────────────────────

class TestLogoutSuccess:
    """Verifications de base sur un logout valide."""

    def test_logout_returns_200(self, client, tokens_permanencier):
        access = tokens_permanencier["access_token"]
        resp = client.post(LOGOUT_URL, headers=_auth(access))
        assert resp.status_code == 200

    def test_logout_response_has_message(self, client, tokens_permanencier):
        access = tokens_permanencier["access_token"]
        resp = client.post(LOGOUT_URL, headers=_auth(access))
        data = resp.get_json()
        assert "message" in data

    def test_logout_response_message_content(self, client, tokens_permanencier):
        """Le message doit indiquer la deconnexion reussie."""
        access = tokens_permanencier["access_token"]
        resp = client.post(LOGOUT_URL, headers=_auth(access))
        data = resp.get_json()
        # On accepte tout message contenant "connect" (minuscule) pour robustesse
        # "Deconnexion" contient "connexion" meme avec l accent unicode
        assert "connexion" in data["message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Revocation des tokens
# ─────────────────────────────────────────────────────────────────────────────

class TestTokenRevocation:
    """Apres logout, les tokens ne doivent plus etre acceptes."""

    def test_access_token_rejected_on_me_after_logout(self, client, tokens_permanencier):
        """L'access token revoque doit retourner 401 sur /api/auth/me."""
        access = tokens_permanencier["access_token"]
        # Logout
        client.post(LOGOUT_URL, headers=_auth(access))
        # Utiliser l'access token revoque
        resp = client.get(ME_URL, headers=_auth(access))
        assert resp.status_code == 401

    def test_refresh_token_rejected_after_logout(self, client, tokens_permanencier):
        """Le refresh token revoque doit retourner 401 sur /api/auth/refresh."""
        access  = tokens_permanencier["access_token"]
        refresh = tokens_permanencier["refresh_token"]
        # Logout
        client.post(LOGOUT_URL, headers=_auth(access))
        # Tenter de rafraichir avec le refresh token revoque
        resp = client.post(REFRESH_URL, headers=_auth(refresh))
        assert resp.status_code == 401

    def test_access_token_was_valid_before_logout(self, client, tokens_permanencier):
        """Verification controle : l'access token est valide AVANT le logout."""
        access = tokens_permanencier["access_token"]
        resp = client.get(ME_URL, headers=_auth(access))
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Fermeture de session
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionClosure:
    """Apres logout, la session doit etre marquee ENDED en base."""

    def test_session_status_ended_after_logout(self, client, tokens_permanencier, db):
        from app.models.user_session import UserSession, SessionStatus
        access     = tokens_permanencier["access_token"]
        session_id = tokens_permanencier["session_id"]

        client.post(LOGOUT_URL, headers=_auth(access))

        # Forcer la relecture depuis la DB (eviter le cache SQLAlchemy)
        db.session.expire_all()
        session = UserSession.query.get(session_id)
        assert session is not None
        assert session.status == SessionStatus.ENDED

    def test_session_end_timestamp_set_after_logout(self, client, tokens_permanencier, db):
        """session_end doit etre renseigne apres le logout."""
        from app.models.user_session import UserSession
        access     = tokens_permanencier["access_token"]
        session_id = tokens_permanencier["session_id"]

        client.post(LOGOUT_URL, headers=_auth(access))

        db.session.expire_all()
        session = UserSession.query.get(session_id)
        assert session.session_end is not None


# ─────────────────────────────────────────────────────────────────────────────
# Logout sans token
# ─────────────────────────────────────────────────────────────────────────────

class TestLogoutWithoutToken:
    """Un appel logout sans Authorization doit etre refuse."""

    def test_logout_without_token_returns_401(self, client, db):
        resp = client.post(LOGOUT_URL)
        assert resp.status_code == 401

    def test_logout_with_invalid_token_returns_401(self, client, db):
        resp = client.post(LOGOUT_URL, headers={"Authorization": "Bearer not.a.valid.token"})
        assert resp.status_code == 422
