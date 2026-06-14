# Backend QA Checklist - Migration Multi-Tenant

Ce document contient les listes de vérification pour garantir la qualité et la robustesse de l'implémentation multi-tenant dans le backend.

## 1. Modèles SQLAlchemy & Relations ORM

- [ ] La colonne `tenant_id` est ajoutée à tous les modèles métier scopés.
- [ ] La colonne `tenant_id` est bien typée en `UUID` et liée par `ForeignKey` à `tenants.id`.
- [ ] Les relations inter-tables scopées (ex: `Site.client`) utilisent une `ForeignKeyConstraint` composite `['tenant_id', 'client_id']`.
- [ ] Le modèle `AgentSecurite` a une `ForeignKeyConstraint` composite pour `prestataire_id` pointant sur `['prestataires.tenant_id', 'prestataires.id']`.
- [ ] Les contraintes d'unicité (ex: `code_client`) sont redéfinies comme `UniqueConstraint('tenant_id', 'code_client')`.
- [ ] Le modèle `User` reste global (pas de `tenant_id`).
- [ ] Les modèles `Tenant` et `TenantUser` sont correctement définis avec leurs relations.

## 2. Authentification (JWT) & Session

- [ ] Le endpoint de login (`/auth/login`) retourne la liste des tenants auxquels l'utilisateur appartient.
- [ ] Un endpoint (`/auth/select-tenant/{tenant_id}`) permet à l'utilisateur de choisir son tenant actif.
- [ ] Le token JWT généré contient le `user_id` (`sub`) ET le `tenant_id` actif (`tid`).
- [ ] Un `before_request` hook est implémenté pour chaque requête authentifiée.
- [ ] Le hook `before_request` valide que l'utilisateur du token appartient bien au tenant du token (`tid`).
- [ ] Le `tenant_id` et l'objet `user` sont stockés dans le contexte de la requête (`flask.g`).
- [ ] La logique de révocation de token (`TokenBlocklist`) reste fonctionnelle.

## 3. Blueprints & Logique Métier (CRUD)

- [ ] **Principe fondamental :** AUCUNE requête ne doit être faite sans un filtre sur `tenant_id`.
- [ ] Toutes les requêtes de lecture (`GET /items`, `GET /items/{id}`) incluent un filtre `.filter(Model.tenant_id == g.tenant_id)`.
- [ ] Pour `GET /items/{id}`, si l'item n'est pas trouvé dans le tenant, une erreur 404 est retournée (et non 403) pour ne pas fuiter d'information.
- [ ] Lors de la création (`POST /items`), le `tenant_id` est automatiquement renseigné avec `g.tenant_id` et n'est pas une valeur fournie par le client.
- [ ] Lors de la mise à jour (`PUT /items/{id}`), la recherche de l'objet à mettre à jour se fait avec `id` ET `g.tenant_id`.
- [ ] Lors de la suppression (`DELETE /items/{id}`), la recherche de l'objet à supprimer se fait avec `id` ET `g.tenant_id`.

## 4. Validations Cross-Tenant

- [ ] Avant d'associer deux objets (ex: lier un `Contact` à un `Site`), le code vérifie que les deux objets appartiennent au même `g.tenant_id`.
- [ ] Si une association cross-tenant est tentée, une erreur 400 (Bad Request) ou 422 (Unprocessable Entity) est retournée avec un message clair.

## 5. Tests Unitaires & Intégration

- [ ] Le setup des tests (`conftest.py`) est mis à jour pour créer par défaut un ou plusieurs tenants et des utilisateurs associés.
- [ ] Une fixture `authenticated_client(user, tenant)` est créée pour faciliter les tests dans un contexte donné.
- [ ] **Tests d'isolation :** Des tests critiques sont ajoutés pour vérifier qu'un utilisateur du Tenant A ne peut JAMAIS voir, créer, modifier ou supprimer des données du Tenant B.
- [ ] Les tests existants sont tous adaptés pour fonctionner dans un contexte de tenant.
- [ ] Des tests sont ajoutés pour les nouvelles routes (sélection de tenant, etc.).

## 6. Seeds & Données de Développement

- [ ] Le script de seeding est mis à jour pour créer des données cohérentes au sein d'un ou plusieurs tenants.
- [ ] Le script de seeding crée des utilisateurs appartenant à un ou plusieurs tenants pour tester la navigation.

## 7. Migration des Données (Backfill)

- [ ] Le script de backfill (`003_...`) a été testé sur une copie de la base de production.
- [ ] Le script est idempotent (le relancer ne cause pas d'erreur ou de duplication).
- [ ] Le script gère correctement les relations parent-enfant pour propager le `tenant_id` (ex: `Client` -> `Site`).

## 8. Vérifications Pré-Production

- [ ] Le plan de migration a été relu et approuvé par l'équipe.
- [ ] Un backup de la base de données de production est prêt et validé.
- [ ] La fenêtre de maintenance est communiquée.
- [ ] Le plan de rollback a été lu et compris par l'opérateur.

## 9. Smoke Tests Post-Déploiement

- [ ] Se connecter avec un utilisateur existant (migré).
- [ ] Vérifier que les données existantes sont visibles et accessibles.
- [ ] Créer un nouvel objet (ex: un Client).
- [ ] Modifier cet objet.
- [ ] Supprimer cet objet.
- [ ] Vérifier les logs pour s'assurer qu'il n'y a pas d'erreurs anormales.

---

## Ordre recommandé d’exécution dans le projet

1.  **Développement Backend** :
    - Mettre à jour les modèles SQLAlchemy.
    - Implémenter la logique d'authentification et de session (JWT + `g.tenant_id`).
    - Adapter 1 ou 2 Blueprints (lecture seule d'abord) pour valider l'approche.
    - Mettre à jour le setup des tests.

2.  **Migrations & Backfill** :
    - Créer les 5 fichiers de migration Alembic.
    - Développer et tester intensivement le script de backfill (`003_...`) sur des données locales.

3.  **Finalisation Backend** :
    - Adapter tous les Blueprints restants.
    - Adapter tous les tests.
    - Adapter le script de seed.

4.  **Tests d'Intégration & Pré-production** :
    - Déployer la branche sur un environnement de staging avec une copie de la base de production.
    - Exécuter la totalité du `MIGRATION_PLAN.md`.
    - Exécuter l'intégralité de cette `BACKEND_QA_CHECKLIST.md`.

5.  **Déploiement en Production** :
    - Suivre le `MIGRATION_PLAN.md` à la lettre.