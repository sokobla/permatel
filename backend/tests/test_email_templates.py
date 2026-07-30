"""
CRUD des modèles d'email (Paramètres > Emails) — délégué à l'admin de tenant.
Couvre en particulier la validation sandboxée (rejet propre d'une variable
non autorisée, d'une syntaxe invalide, et d'une tentative d'injection SSTI
réelle — pas juste l'absence de crash).
"""
from app.models.email_template import EmailTemplate, TEMPLATE_ONBOARDING_WELCOME, TEMPLATE_PASSWORD_RESET


class TestListTemplates:
    def test_liste_les_deux_cles_connues_non_personnalisees(self, client, auth_headers_admin):
        resp = client.get("/api/tenant/email-templates", headers=auth_headers_admin)
        assert resp.status_code == 200
        templates = {t["template_key"]: t for t in resp.get_json()["templates"]}
        assert set(templates) == {TEMPLATE_ONBOARDING_WELCOME, TEMPLATE_PASSWORD_RESET}
        assert all(not t["is_customized"] for t in templates.values())
        assert "activation_url" in templates[TEMPLATE_ONBOARDING_WELCOME]["available_variables"]


class TestUpdateTemplate:
    def test_put_contenu_valide_cree_un_override(self, client, db, auth_headers_admin, default_tenant):
        resp = client.put(
            f"/api/tenant/email-templates/{TEMPLATE_PASSWORD_RESET}",
            json={"subject": "Réinitialisez, {{ prenom }} !", "body_html": "<p>{{ reset_url }}</p>"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        assert resp.get_json()["template"]["is_customized"] is True

        override = EmailTemplate.query.filter_by(
            tenant_id=default_tenant.id, template_key=TEMPLATE_PASSWORD_RESET,
        ).first()
        assert override is not None
        assert override.is_active is True

    def test_put_variable_non_autorisee_retourne_400(self, client, auth_headers_admin):
        resp = client.put(
            f"/api/tenant/email-templates/{TEMPLATE_PASSWORD_RESET}",
            json={"subject": "Bonjour", "body_html": "<p>{{ mot_de_passe_admin }}</p>"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400

    def test_put_syntaxe_invalide_retourne_400(self, client, auth_headers_admin):
        resp = client.put(
            f"/api/tenant/email-templates/{TEMPLATE_PASSWORD_RESET}",
            json={"subject": "Bonjour", "body_html": "<p>{{ reset_url </p>"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400

    def test_put_tentative_ssti_est_rejetee_proprement(self, client, auth_headers_admin):
        """Une vraie chaîne d'exploitation SSTI (pas juste un attribut isolé
        qui s'évalue silencieusement à vide) doit être rejetée avec un 400
        propre — jamais un 500 (l'exception SecurityError de la sandbox doit
        être interceptée par validate_template_content, pas remonter
        jusqu'à la route)."""
        payload = "{{ ''.__class__.__mro__[1].__subclasses__() }}"
        resp = client.put(
            f"/api/tenant/email-templates/{TEMPLATE_PASSWORD_RESET}",
            json={"subject": "Bonjour", "body_html": payload},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400
        assert "Gabarit invalide" in resp.get_json()["error"]

    def test_put_cle_inconnue_retourne_404(self, client, auth_headers_admin):
        resp = client.put(
            "/api/tenant/email-templates/inconnu",
            json={"subject": "x", "body_html": "y"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404

    def test_put_refuse_sans_droits_admin(self, client, auth_headers):
        """auth_headers = PERMANENCIER, @tenant_admin_required doit refuser."""
        resp = client.put(
            f"/api/tenant/email-templates/{TEMPLATE_PASSWORD_RESET}",
            json={"subject": "x", "body_html": "y"},
            headers=auth_headers,
        )
        assert resp.status_code == 403


class TestResetTemplate:
    def test_reset_desactive_l_override_et_retombe_sur_le_defaut(
        self, client, db, auth_headers_admin, default_tenant,
    ):
        client.put(
            f"/api/tenant/email-templates/{TEMPLATE_PASSWORD_RESET}",
            json={"subject": "Perso", "body_html": "<p>{{ reset_url }}</p>"},
            headers=auth_headers_admin,
        )
        resp = client.post(
            f"/api/tenant/email-templates/{TEMPLATE_PASSWORD_RESET}/reset", headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        assert resp.get_json()["template"]["is_customized"] is False

        override = EmailTemplate.query.filter_by(
            tenant_id=default_tenant.id, template_key=TEMPLATE_PASSWORD_RESET,
        ).first()
        assert override.is_active is False  # conservé, juste désactivé (pas supprimé)


class TestPreviewTemplate:
    def test_preview_rend_avec_des_valeurs_d_exemple(self, client, auth_headers_admin):
        resp = client.post(
            f"/api/tenant/email-templates/{TEMPLATE_PASSWORD_RESET}/preview",
            json={"subject": "Bonjour {{ prenom }}", "body_html": "<p>{{ reset_url }}</p>"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "Bonjour" in data["subject"]
        assert "{{" not in data["subject"]  # effectivement rendu, pas renvoyé tel quel

    def test_preview_brouillon_invalide_retourne_400_pas_de_crash(self, client, auth_headers_admin):
        resp = client.post(
            f"/api/tenant/email-templates/{TEMPLATE_PASSWORD_RESET}/preview",
            json={"subject": "x", "body_html": "{{ ''.__class__.__mro__[1].__subclasses__() }}"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400
