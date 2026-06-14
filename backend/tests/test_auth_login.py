"""
Tests Phase 1 - POST /api/auth/login

Scenarios couverts :
  - Login reussi : 200 + access_token, refresh_token, session_id, user, tenants
  - Mauvais mot de passe : 401
  - Username inexistant : 401
  - Compte inactif : 403
  - Aucun tenant assigne : 403
  - Body JSON manquant : 400
  - Champ username manquant/vide : 400
  - Champ password manquant/vide : 400
"""

URL = "/api/auth/login"


# ─────────────────────────────────────────────────────────────────────────────
# Login reussi
# ─────────────────────────────────────────────────────────────────────────────

class TestLoginSuccess:
    """Verifications sur un login valide (200)."""

    def test_login_returns_200(self, client, user_permanencier):
        resp = client.post(URL, json={"username": "permanencier1", "password": "Password123!"})
        assert resp.status_code == 200

    def test_login_has_access_token(self, client, user_permanencier):
        resp = client.post(URL, json={"username": "permanencier1", "password": "Password123!"})
        data = resp.get_json()
        assert "access_token" in data
        assert data["access_token"]

    def test_login_has_refresh_token(self, client, user_permanencier):
        resp = client.post(URL, json={"username": "permanencier1", "password": "Password123!"})
        data = resp.get_json()
        assert "refresh_token" in data
        assert data["refresh_token"]

    def test_login_tokens_are_different(self, client, user_permanencier):
        """L'access token et le refresh token doivent etre distincts."""
        resp = client.post(URL, json={"username": "permanencier1", "password": "Password123!"})
        data = resp.get_json()
        assert data["access_token"] != data["refresh_token"]

    def test_login_has_session_id(self, client, user_permanencier):
        resp = client.post(URL, json={"username": "permanencier1", "password": "Password123!"})
        data = resp.get_json()
        assert "session_id" in data
        assert data["session_id"] is not None

    def test_login_user_block_correct(self, client, user_permanencier):
        resp = client.post(URL, json={"username": "permanencier1", "password": "Password123!"})
        data = resp.get_json()
        assert "user" in data
        user = data["user"]
        assert user["username"] == "permanencier1"
        assert user["role"] == "PERMANENCIER"
        assert user["is_active"] is True

    def test_login_tenants_list_populated(self, client, user_permanencier):
        resp = client.post(URL, json={"username": "permanencier1", "password": "Password123!"})
        data = resp.get_json()
        assert "tenants" in data
        assert isinstance(data["tenants"], list)
        assert len(data["tenants"]) == 1

    def test_login_active_tenant_set_automatically(self, client, user_permanencier):
        """Avec un seul tenant, active_tenant_id doit etre defini automatiquement."""
        resp = client.post(URL, json={"username": "permanencier1", "password": "Password123!"})
        data = resp.get_json()
        assert "active_tenant_id" in data
        assert data["active_tenant_id"] is not None
        assert data["active_tenant_id"] == data["tenants"][0]["id"]

    def test_login_has_expires_in(self, client, user_permanencier):
        resp = client.post(URL, json={"username": "permanencier1", "password": "Password123!"})
        data = resp.get_json()
        assert "expires_in" in data
        assert isinstance(data["expires_in"], int)
        assert data["expires_in"] > 0

    def test_login_username_case_insensitive(self, client, user_permanencier):
        """Le login doit fonctionner avec le username en majuscules."""
        resp = client.post(URL, json={"username": "PERMANENCIER1", "password": "Password123!"})
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Identifiants incorrects (401)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoginBadCredentials:
    """Echecs d'authentification : mauvais mdp ou username inexistant."""

    def test_bad_password_returns_401(self, client, user_permanencier):
        resp = client.post(URL, json={"username": "permanencier1", "password": "WrongPass!"})
        assert resp.status_code == 401

    def test_bad_password_has_error_key(self, client, user_permanencier):
        resp = client.post(URL, json={"username": "permanencier1", "password": "WrongPass!"})
        data = resp.get_json()
        assert "error" in data

    def test_unknown_username_returns_401(self, client, db):
        resp = client.post(URL, json={"username": "nobody_here", "password": "Password123!"})
        assert resp.status_code == 401

    def test_unknown_username_has_error_key(self, client, db):
        resp = client.post(URL, json={"username": "nobody_here", "password": "Password123!"})
        data = resp.get_json()
        assert "error" in data

    def test_bad_credentials_no_token_in_response(self, client, user_permanencier):
        """En cas d'echec, la reponse ne doit contenir aucun token."""
        resp = client.post(URL, json={"username": "permanencier1", "password": "WrongPass!"})
        data = resp.get_json()
        assert "access_token" not in data
        assert "refresh_token" not in data


# ─────────────────────────────────────────────────────────────────────────────
# Compte inactif (403)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoginInactiveAccount:
    """Un compte desactive doit etre refuse avec 403."""

    def test_inactive_account_returns_403(self, client, user_inactive):
        resp = client.post(URL, json={"username": "inactif1", "password": "Password123!"})
        assert resp.status_code == 403

    def test_inactive_account_has_error_key(self, client, user_inactive):
        resp = client.post(URL, json={"username": "inactif1", "password": "Password123!"})
        data = resp.get_json()
        assert "error" in data

    def test_inactive_account_no_token_in_response(self, client, user_inactive):
        resp = client.post(URL, json={"username": "inactif1", "password": "Password123!"})
        data = resp.get_json()
        assert "access_token" not in data


# ─────────────────────────────────────────────────────────────────────────────
# Aucun tenant assigne (403)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoginNoTenant:
    """Un utilisateur sans tenant assigne doit etre refuse avec 403."""

    def test_no_tenant_returns_403(self, client, db):
        """Creer un user orphelin (sans tenant) et tenter de le connecter."""
        from app.models.user import User, UserRole
        u = User(
            username  = "orphan_user",
            email     = "orphan@permatel.ma",
            nom       = "Nobody",
            prenom    = "Orphan",
            role      = UserRole.PERMANENCIER,
            is_active = True,
        )
        u.set_password("Password123!")
        db.session.add(u)
        db.session.commit()

        resp = client.post(URL, json={"username": "orphan_user", "password": "Password123!"})
        assert resp.status_code == 403

    def test_no_tenant_has_error_key(self, client, db):
        from app.models.user import User, UserRole
        u = User(
            username  = "orphan_user2",
            email     = "orphan2@permatel.ma",
            nom       = "Nobody",
            prenom    = "Orphan",
            role      = UserRole.PERMANENCIER,
            is_active = True,
        )
        u.set_password("Password123!")
        db.session.add(u)
        db.session.commit()

        resp = client.post(URL, json={"username": "orphan_user2", "password": "Password123!"})
        data = resp.get_json()
        assert "error" in data


# ─────────────────────────────────────────────────────────────────────────────
# Validation du body (400)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoginValidation:
    """Champs manquants ou body absent."""

    def test_missing_body_returns_400(self, client, db):
        """Aucun body JSON -> 400."""
        resp = client.post(URL)
        assert resp.status_code == 400

    def test_missing_body_has_error_key(self, client, db):
        resp = client.post(URL)
        data = resp.get_json()
        assert "error" in data

    def test_missing_username_returns_400(self, client, db):
        resp = client.post(URL, json={"password": "Password123!"})
        assert resp.status_code == 400

    def test_missing_password_returns_400(self, client, db):
        resp = client.post(URL, json={"username": "permanencier1"})
        assert resp.status_code == 400

    def test_empty_username_returns_400(self, client, db):
        resp = client.post(URL, json={"username": "", "password": "Password123!"})
        assert resp.status_code == 400

    def test_empty_password_returns_400(self, client, db):
        resp = client.post(URL, json={"username": "permanencier1", "password": ""})
        assert resp.status_code == 400
