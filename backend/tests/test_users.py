import pytest
from app.models.user import User, UserRole


class TestUsersList:

    def test_list_users_retourne_200(self, client, user_permanencier, user_manager, auth_headers):
        """Liste tous les utilisateurs avec succès."""
        resp = client.get("/api/users", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 2  # Au moins les 2 utilisateurs de fixtures

    def test_list_users_contient_champs_attendus(self, client, user_permanencier, auth_headers):
        """Chaque utilisateur contient les champs requis."""
        resp = client.get("/api/users", headers=auth_headers)
        users = resp.get_json()
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

    def test_list_users_exclut_password_hash(self, client, user_permanencier, auth_headers):
        """Le password_hash n'est jamais exposé."""
        resp = client.get("/api/users", headers=auth_headers)
        users = resp.get_json()
        for user in users:
            assert "password_hash" not in user


class TestUsersGet:

    def test_get_user_existant_retourne_200(self, client, user_permanencier, auth_headers):
        """Récupération d'un utilisateur existant."""
        resp = client.get(f"/api/users/{user_permanencier.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == user_permanencier.id
        assert data["username"] == "permanencier1"

    def test_get_user_inexistant_retourne_404(self, client, auth_headers):
        """Utilisateur inexistant → 404."""
        resp = client.get("/api/users/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_user_exclut_password_hash(self, client, user_permanencier, auth_headers):
        """Le password_hash n'est jamais exposé."""
        resp = client.get(f"/api/users/{user_permanencier.id}", headers=auth_headers)
        data = resp.get_json()
        assert "password_hash" not in data


class TestUsersCreate:

    def test_create_user_valide_retourne_201(self, client, db, auth_headers):
        """Création d'utilisateur valide."""
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "nom": "Test",
            "prenom": "User",
            "role": "PERMANENCIER",
            "password": "Password123!"
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data["user"]
        assert data["message"] == "Utilisateur créé"

        # Vérifier en base
        user = User.query.filter_by(username="testuser").first()
        assert user is not None
        assert user.email == "test@example.com"
        assert user.nom == "Test"
        assert user.prenom == "User"
        assert user.role == UserRole.PERMANENCIER

    def test_create_user_username_unique(self, client, user_permanencier, auth_headers):
        """Username doit être unique."""
        payload = {
            "username": "permanencier1",  # Déjà existant
            "email": "new@example.com",
            "nom": "New",
            "prenom": "User",
            "role": "MANAGER",
            "password": "Password123!"
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers)
        assert resp.status_code == 409
        data = resp.get_json()
        assert "message" in data

    def test_create_user_email_unique(self, client, user_permanencier, auth_headers):
        """Email doit être unique."""
        payload = {
            "username": "newuser",
            "email": "perm1@permatel.ma",  # Déjà existant
            "nom": "New",
            "prenom": "User",
            "role": "MANAGER",
            "password": "Password123!"
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers)
        assert resp.status_code == 409
        data = resp.get_json()
        assert "message" in data

    def test_create_user_role_invalide(self, client, auth_headers):
        """Role invalide → erreur."""
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "nom": "Test",
            "prenom": "User",
            "role": "INVALID_ROLE",
            "password": "Password123!"
        }
        resp = client.post("/api/users", json=payload, headers=auth_headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "message" in data

    def test_create_user_champs_obligatoires(self, client, auth_headers):
        """Username et email sont obligatoires."""
        # Manque username
        payload = {"email": "test@example.com", "nom": "Test", "prenom": "User", "role": "PERMANENCIER", "password": "Password123!"}
        resp = client.post("/api/users", json=payload, headers=auth_headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "missing_fields" in data
        assert "username" in data["missing_fields"]

    def test_create_user_sans_body_json(self, client, auth_headers):
        """Sans body JSON → erreur."""
        resp = client.post("/api/users", data="not json", headers=auth_headers)
        assert resp.status_code == 400


class TestUsersUpdate:

    def test_update_user_valide_retourne_200(self, client, user_permanencier, db, auth_headers):
        """Mise à jour valide d'utilisateur."""
        payload = {
            "username": "updateduser",
            "email": "updated@example.com",
            "nom": "Updated",
            "prenom": "User",
            "role": "MANAGER"
        }
        resp = client.put(f"/api/users/{user_permanencier.id}", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Utilisateur mis à jour"

        # Vérifier en base
        db.session.refresh(user_permanencier)
        assert user_permanencier.username == "updateduser"
        assert user_permanencier.email == "updated@example.com"
        assert user_permanencier.nom == "Updated"
        assert user_permanencier.prenom == "User"
        assert user_permanencier.role == UserRole.MANAGER

    def test_update_user_partiel(self, client, user_permanencier, db, auth_headers):
        """Mise à jour partielle (seulement email)."""
        payload = {"email": "partial@example.com"}
        resp = client.put(f"/api/users/{user_permanencier.id}", json=payload, headers=auth_headers)
        assert resp.status_code == 200

        db.session.refresh(user_permanencier)
        assert user_permanencier.email == "partial@example.com"
        assert user_permanencier.username == "permanencier1"  # Inchangé

    def test_update_user_inexistant_retourne_404(self, client, auth_headers):
        """Utilisateur inexistant → 404."""
        payload = {"username": "test"}
        resp = client.put("/api/users/99999", json=payload, headers=auth_headers)
        assert resp.status_code == 404

    def test_update_user_username_unique(self, client, user_permanencier, user_manager, auth_headers):
        """Username doit rester unique."""
        payload = {"username": "permanencier1"}  # Déjà pris par user_permanencier
        resp = client.put(f"/api/users/{user_manager.id}", json=payload, headers=auth_headers)
        assert resp.status_code == 409
        data = resp.get_json()
        assert "message" in data


class TestUsersUpdateStatus:

    def test_update_status_actif_retourne_200(self, client, user_permanencier, db, auth_headers):
        """Activation d'utilisateur."""
        payload = {"is_active": True}
        resp = client.patch(f"/api/users/{user_permanencier.id}/status", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Statut utilisateur mis à jour"

        db.session.refresh(user_permanencier)
        assert user_permanencier.is_active is True

    def test_update_status_inactif_retourne_200(self, client, user_permanencier, db, auth_headers):
        """Désactivation d'utilisateur."""
        payload = {"is_active": False}
        resp = client.patch(f"/api/users/{user_permanencier.id}/status", json=payload, headers=auth_headers)
        assert resp.status_code == 200

        db.session.refresh(user_permanencier)
        assert user_permanencier.is_active is False

    def test_update_status_inexistant_retourne_404(self, client, auth_headers):
        """Utilisateur inexistant → 404."""
        payload = {"is_active": False}
        resp = client.patch("/api/users/99999/status", json=payload, headers=auth_headers)
        assert resp.status_code == 404


class TestUsersDelete:

    def test_delete_user_valide_retourne_200(self, client, db, auth_headers):
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

        resp = client.delete(f"/api/users/{user.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Utilisateur supprimé"

        # Vérifier suppression
        deleted_user = User.query.get(user.id)
        assert deleted_user is None

    def test_delete_user_inexistant_retourne_404(self, client, auth_headers):
        """Utilisateur inexistant → 404."""
        resp = client.delete("/api/users/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestUpdatePassword:

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
        assert "au moins 8 caractères" in data["message"]

    def test_update_password_nouveau_trop_court_retourne_400(self, client, user_permanencier, auth_headers):
        """Nouveau mot de passe trop court → 400."""
        payload = {
            "old_password": "Password123!",
            "new_password": "short"  # Moins de 8 caractères
        }
        resp = client.patch(
            f"/api/users/{user_permanencier.id}/password",
            json=payload,
            headers=auth_headers
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "au moins 8 caractères" in data["message"]

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