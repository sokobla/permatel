import pytest
from app.models.user import User, UserRole


class TestUsersList:
    """GET /api/users (rôle ADMIN requis)"""

    def test_list_users_retourne_200(self, client, user_permanencier, user_manager, auth_headers_admin):
        """Liste tous les utilisateurs avec succès."""
        resp = client.get("/api/users", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.get_json()["users"]
        assert isinstance(data, list)
        assert len(data) >= 2  # Au moins les 2 utilisateurs de fixtures

    def test_list_users_contient_champs_attendus(self, client, user_permanencier, auth_headers_admin):
        """Chaque utilisateur contient les champs requis."""
        resp = client.get("/api/users", headers=auth_headers_admin)
        users = resp.get_json()["users"]
        user_data = next(u for u in users if u["id"] == user_permanencier.id)

        assert "id" in user_data
        assert "username" in user_data
        assert "email" in user_data
        assert "nom" in user_data
        assert "prenom" in user_data
        assert "role" in user_data
        assert "is_active" in user_data
        assert user_data["username"] == "permanencier1"
        assert user_data["nom"] == "Martin"
        assert user_data["prenom"] == "Alice"
        assert user_data["role"] == "PERMANENCIER"
        assert user_data["is_active"] is True

    def test_list_users_exclut_password_hash(self, client, user_permanencier, auth_headers_admin):
        """Le password_hash n'est jamais exposé."""
        resp = client.get("/api/users", headers=auth_headers_admin)
        assert resp.status_code == 200
        users = resp.get_json()["users"]
        for user in users:
            assert "password_hash" not in user


class TestUsersGet:
    """GET /api/users/<id> (rôle ADMIN requis)"""

    def test_get_user_existant_retourne_200(self, client, user_permanencier, auth_headers_admin):
        """Récupération d'un utilisateur existant."""
        resp = client.get(f"/api/users/{user_permanencier.id}", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == user_permanencier.id
        assert data["username"] == "permanencier1"

    def test_get_user_inexistant_retourne_404(self, client, auth_headers_admin):
        """Utilisateur inexistant → 404."""
        resp = client.get("/api/users/99999", headers=auth_headers_admin)
        assert resp.status_code == 404

    def test_get_user_exclut_password_hash(self, client, user_permanencier, auth_headers_admin):
        """Le password_hash n'est jamais exposé."""
        resp = client.get(f"/api/users/{user_permanencier.id}", headers=auth_headers_admin)
        data = resp.get_json()
        assert "password_hash" not in data


class TestUsersCreate:
    """POST /api/users (rôle ADMIN requis)"""

    def test_create_user_valide_retourne_201(self, client, db, auth_headers_admin, default_tenant):
        """Création d'utilisateur valide. Un tenant est requis (anti-lockout, rôle
        non-ADMIN) ; username n'est plus un champ soumis — il suit toujours l'email
        (bascule globale username=email)."""
        payload = {
            "email": "test@example.com",
            "nom": "Test",
            "prenom": "User",
            "role": "PERMANENCIER",
            "password": "Password123!",
            "tenant_ids": [str(default_tenant.id)],
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data["user"]
        assert data["message"] == "Utilisateur créé"

        # Vérifier en base
        user = User.query.filter_by(email="test@example.com").first()
        assert user is not None
        assert user.username == "test@example.com"  # username = email
        assert user.nom == "Test"
        assert user.prenom == "User"
        assert user.role == UserRole.PERMANENCIER

    def test_create_user_sans_tenant_retourne_400(self, client, auth_headers_admin):
        """Anti-lockout : un rôle non-ADMIN sans tenant_ids ne peut jamais se connecter → 400."""
        payload = {
            "email": "sanstenant@example.com",
            "nom": "Sans",
            "prenom": "Tenant",
            "role": "PERMANENCIER",
            "password": "Password123!",
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "tenant" in data["message"].lower()

    def test_create_user_email_normalise_en_minuscules(self, client, auth_headers_admin, default_tenant):
        """L'email (et donc username) est normalisé en minuscules à la création."""
        payload = {
            "email": "Mixed.Case@Example.COM",
            "nom": "Mixed",
            "prenom": "Case",
            "role": "PERMANENCIER",
            "password": "Password123!",
            "tenant_ids": [str(default_tenant.id)],
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 201

        user = User.query.filter_by(email="mixed.case@example.com").first()
        assert user is not None
        assert user.username == "mixed.case@example.com"

    def test_create_user_email_unique(self, client, user_permanencier, auth_headers_admin):
        """Email doit être unique."""
        payload = {
            "username": "newuser",
            "email": "perm1@permatel.ma",  # Déjà existant
            "nom": "New",
            "prenom": "User",
            "role": "MANAGER",
            "password": "Password123!"
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 409
        data = resp.get_json()
        assert "message" in data

    def test_create_user_role_invalide(self, client, auth_headers_admin):
        """Role invalide → erreur."""
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "nom": "Test",
            "prenom": "User",
            "role": "INVALID_ROLE",
            "password": "Password123!"
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "message" in data

    def test_create_user_champs_obligatoires(self, client, auth_headers_admin):
        """email/nom/prenom/role/password sont obligatoires (username n'est plus
        soumis — il est dérivé de l'email)."""
        # Manque email
        payload = {"nom": "Test", "prenom": "User", "role": "PERMANENCIER", "password": "Password123!"}
        resp = client.post("/api/users", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "missing_fields" in data
        assert "email" in data["missing_fields"]

    def test_create_user_sans_body_json(self, client, auth_headers_admin):
        """Sans body JSON → erreur."""
        resp = client.post("/api/users", data="not json", headers=auth_headers_admin)
        assert resp.status_code == 400


class TestUsersUpdate:
    """PUT /api/users/<id> (rôle ADMIN requis)"""

    def test_update_user_valide_retourne_200(self, client, user_permanencier, db, auth_headers_admin):
        """Mise à jour valide d'utilisateur (username suit l'email — bascule globale)."""
        payload = {
            "email": "updated@example.com",
            "nom": "Updated",
            "prenom": "User",
            "role": "MANAGER"
        }
        resp = client.put(f"/api/users/{user_permanencier.id}", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Utilisateur mis à jour"

        # Vérifier en base
        db.session.refresh(user_permanencier)
        assert user_permanencier.username == "updated@example.com"
        assert user_permanencier.email == "updated@example.com"
        assert user_permanencier.nom == "Updated"
        assert user_permanencier.prenom == "User"
        assert user_permanencier.role == UserRole.MANAGER

    def test_update_user_partiel(self, client, user_permanencier, db, auth_headers_admin):
        """Mise à jour partielle (seulement email) — username = email (bascule globale)."""
        payload = {"email": "partial@example.com"}
        resp = client.put(f"/api/users/{user_permanencier.id}", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 200

        db.session.refresh(user_permanencier)
        assert user_permanencier.email == "partial@example.com"
        assert user_permanencier.username == "partial@example.com"  # username suit l'email

    def test_update_user_inexistant_retourne_404(self, client, auth_headers_admin):
        """Utilisateur inexistant → 404."""
        payload = {"username": "test"}
        resp = client.put("/api/users/99999", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 404

    def test_update_user_username_unique(self, client, user_permanencier, user_manager, auth_headers_admin):
        """Username doit rester unique."""
        payload = {"username": "permanencier1"}  # Déjà pris par user_permanencier
        resp = client.put(f"/api/users/{user_manager.id}", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 409
        data = resp.get_json()
        assert "message" in data


class TestUsersUpdateStatus:
    """PATCH /api/users/<id>/status (rôle ADMIN requis)"""

    def test_update_status_actif_retourne_200(self, client, user_permanencier, db, auth_headers_admin):
        """Activation d'utilisateur."""
        payload = {"is_active": True}
        resp = client.patch(f"/api/users/{user_permanencier.id}/status", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Statut utilisateur mis à jour"

        db.session.refresh(user_permanencier)
        assert user_permanencier.is_active is True

    def test_update_status_inactif_retourne_200(self, client, user_permanencier, db, auth_headers_admin):
        """Désactivation d'utilisateur."""
        payload = {"is_active": False}
        resp = client.patch(f"/api/users/{user_permanencier.id}/status", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 200

        db.session.refresh(user_permanencier)
        assert user_permanencier.is_active is False

    def test_update_status_inexistant_retourne_404(self, client, auth_headers_admin):
        """Utilisateur inexistant → 404."""
        payload = {"is_active": False}
        resp = client.patch("/api/users/99999/status", json=payload, headers=auth_headers_admin)
        assert resp.status_code == 404


class TestUsersDelete:
    """DELETE /api/users/<id> (rôle ADMIN requis)"""

    def test_delete_user_valide_retourne_200(self, client, db, auth_headers_admin):
        """Suppression d'utilisateur."""
        # Créer un utilisateur de test
        user = User(
            username="todelete",
            email="delete@example.com",
            nom="To",
            prenom="Delete",
            role=UserRole.PERMANENCIER
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        resp = client.delete(f"/api/users/{user.id}", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Utilisateur supprimé"

        # Vérifier suppression
        deleted_user = User.query.get(user.id)
        assert deleted_user is None

    def test_delete_user_inexistant_retourne_404(self, client, auth_headers_admin):
        """Utilisateur inexistant → 404."""
        resp = client.delete("/api/users/99999", headers=auth_headers_admin)
        assert resp.status_code == 404


class TestUpdatePassword:
    """PATCH /api/users/<id>/password (self-service, aucun rôle requis — propriétaire uniquement)"""

    def test_update_password_valide_retourne_200(self, client, user_permanencier, auth_headers, db):
        """Mise à jour valide du mot de passe."""
        payload = {
            "old_password": "Password123!",
            "new_password": "NewPassword456!"
        }
        resp = client.patch(
            f"/api/users/{user_permanencier.id}/password",
            json=payload,
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Mot de passe mis à jour avec succès"

        # Vérifier que l'ancien mot de passe ne fonctionne plus
        db.session.refresh(user_permanencier)
        assert not user_permanencier.check_password("Password123!")

        # Vérifier que le nouveau mot de passe fonctionne
        assert user_permanencier.check_password("NewPassword456!")

    def test_update_password_ancien_incorrect_retourne_401(self, client, user_permanencier, auth_headers):
        """Ancien mot de passe incorrect → 401."""
        payload = {
            "old_password": "WrongPassword",
            "new_password": "NewPassword456!"
        }
        resp = client.patch(
            f"/api/users/{user_permanencier.id}/password",
            json=payload,
            headers=auth_headers
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert "Ancien mot de passe incorrect" in data["message"]

    def test_update_password_champs_manquants_retourne_400(self, client, user_permanencier, auth_headers):
        """Champs obligatoires manquants → 400."""
        # Manque new_password
        payload = {"old_password": "Password123!"}
        resp = client.patch(
            f"/api/users/{user_permanencier.id}/password",
            json=payload,
            headers=auth_headers
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "au moins 12 caractères" in data["message"]

    def test_update_password_nouveau_trop_court_retourne_400(self, client, user_permanencier, auth_headers):
        """Nouveau mot de passe trop court → 400."""
        payload = {
            "old_password": "Password123!",
            "new_password": "short"  # Moins de 12 caractères
        }
        resp = client.patch(
            f"/api/users/{user_permanencier.id}/password",
            json=payload,
            headers=auth_headers
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "au moins 12 caractères" in data["message"]

    def test_update_password_sans_authentification_retourne_401(self, client, user_permanencier):
        """Sans authentification JWT → 401."""
        payload = {
            "old_password": "Password123!",
            "new_password": "NewPassword456!"
        }
        resp = client.patch(
            f"/api/users/{user_permanencier.id}/password",
            json=payload
        )
        assert resp.status_code == 401

    def test_update_password_autre_utilisateur_retourne_403(self, client, user_permanencier, user_manager, auth_headers):
        """Changement du mot de passe d'un autre utilisateur → 403."""
        payload = {
            "old_password": "Password123!",
            "new_password": "NewPassword456!"
        }
        # auth_headers contient le token de user_permanencier
        resp = client.patch(
            f"/api/users/{user_manager.id}/password",
            json=payload,
            headers=auth_headers
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert "Action non autorisée" in data["message"]

    def test_update_password_utilisateur_inexistant_retourne_404(self, client, auth_headers):
        """Utilisateur inexistant → 404."""
        payload = {
            "old_password": "Password123!",
            "new_password": "NewPassword456!"
        }
        resp = client.patch(
            "/api/users/99999/password",
            json=payload,
            headers=auth_headers
        )
        assert resp.status_code == 404

    def test_update_password_nouveau_tres_fort(self, client, user_permanencier, auth_headers, db):
        """Ancien mot de passe avec mot de passe très fort."""
        strong_password = "VeryStrong@Pass#2026WithNumbers123!"
        payload = {
            "old_password": "Password123!",
            "new_password": strong_password
        }
        resp = client.patch(
            f"/api/users/{user_permanencier.id}/password",
            json=payload,
            headers=auth_headers
        )
        assert resp.status_code == 200

        # Vérifier que le nouveau mot de passe fonctionne
        db.session.refresh(user_permanencier)
        assert user_permanencier.check_password(strong_password)


class TestUpdateMyProfile:
    """PATCH /api/users/me (self-service, aucun rôle requis — édite le compte connecté)"""

    def test_update_my_profile_nom_prenom_retourne_200(self, client, user_permanencier, auth_headers, db):
        """Un PERMANENCIER (rôle le plus bas) peut éditer son propre nom/prénom,
        sans avoir besoin d'un rôle ADMIN — contrairement à PUT /users/<id>."""
        payload = {"nom": "Nouveaunom", "prenom": "Nouveauprenom"}
        resp = client.patch("/api/users/me", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["nom"] == "Nouveaunom"
        assert data["user"]["prenom"] == "Nouveauprenom"

        db.session.refresh(user_permanencier)
        assert user_permanencier.nom == "Nouveaunom"
        assert user_permanencier.prenom == "Nouveauprenom"

    def test_update_my_profile_ignore_champs_non_autorises(self, client, user_permanencier, auth_headers, db):
        """role/email/is_active ne sont pas modifiables via cette route self-service
        (contrairement à update_user, réservé aux ADMIN) — ils sont simplement ignorés."""
        payload = {
            "nom": "Test",
            "role": "ADMIN",
            "email": "hacked@example.com",
            "is_active": False,
        }
        resp = client.patch("/api/users/me", json=payload, headers=auth_headers)
        assert resp.status_code == 200

        db.session.refresh(user_permanencier)
        assert user_permanencier.role == UserRole.PERMANENCIER
        assert user_permanencier.email != "hacked@example.com"
        assert user_permanencier.is_active is True

    def test_update_my_profile_sans_auth_retourne_401(self, client):
        """Aucun token → 401."""
        resp = client.patch("/api/users/me", json={"nom": "X"})
        assert resp.status_code == 401

    def test_update_my_profile_suppression_avatar(self, client, user_permanencier, auth_headers, db):
        """avatar_url: null explicite supprime l'avatar existant."""
        user_permanencier.avatar_url = "/uploads/user_1_avatar.png"
        db.session.commit()

        resp = client.patch(
            "/api/users/me", json={"avatar_url": None}, headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.get_json()["user"]["avatar_url"] is None

        db.session.refresh(user_permanencier)
        assert user_permanencier.avatar_url is None
