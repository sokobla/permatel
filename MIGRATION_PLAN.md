# Plan de Migration Multi-Tenant

**Version**: 1.0
**Date**: 26 avril 2026

Ce document détaille la stratégie et les étapes techniques pour la migration de la base de données PERMATEL vers une architecture multi-tenant.

## Stratégie Générale

L'approche est une migration progressive en 5 étapes, conçue pour minimiser les risques et les interruptions de service. Elle suit le cycle :
1.  **Extension du schéma** (sans contraintes bloquantes).
2.  **Remplissage des données** (backfill).
3.  **Déploiement du code applicatif** "tenant-aware".
4.  **Application des contraintes** de base de données finales.

## Pré-requis avant exécution

- **[ ] Backup complet de la base de données de production.**
- **[ ] Validation que tous les tests unitaires et d'intégration passent sur la branche `main`.**
- **[ ] Test complet de la séquence de migration sur une copie récente de la base de production.**
- **[ ] Estimation du temps d'exécution de la migration `003_seed_default_tenant_and_backfill_data`, la plus longue.**
- **[ ] Communication interne sur la fenêtre de maintenance planifiée.**

---

## Séquence des Migrations Alembic

### 1. `001_create_core_multitenant_tables`

- **Objectif** : Créer les nouvelles tables fondamentales (`tenants`, `tenant_users`, `prestataires`).
- **Opérations de schéma** :
  - `op.create_table('tenants', ...)`
  - `op.create_table('tenant_users', ...)`
  - `op.create_table('prestataires', ...)`
- **Opérations de données** : Aucune.
- **Dépendances** : Aucune.
- **Risques** : Faibles. N'affecte pas les tables ou le code existants.
- **Déploiement** : Peut être déployé en production à tout moment avant les étapes suivantes.

### 2. `002_add_nullable_tenant_columns`

- **Objectif** : Ajouter les colonnes `tenant_id` et `prestataire_id` à toutes les tables métier existantes, en les laissant `NULLABLE`.
- **Opérations de schéma** :
  - `op.add_column('agents_securite', sa.Column('tenant_id', UUID, nullable=True))`
  - `op.add_column('agents_securite', sa.Column('prestataire_id', UUID, nullable=True))`
  - `op.add_column('clients', sa.Column('tenant_id', UUID, nullable=True))`
  - `... (pour toutes les tables concernées)`
  - `op.add_column('user_sessions', sa.Column('active_tenant_id', UUID, nullable=True))`
- **Opérations de données** : Aucune.
- **Dépendances** : `001_create_core_multitenant_tables`.
- **Risques** : Faibles. L'ajout de colonnes nullables est une opération non-bloquante sur PostgreSQL.
- **Déploiement** : Peut être déployé en production juste après la migration `001`. L'application existante ignorera ces colonnes.

### 3. `003_seed_default_tenant_and_backfill_data`

- **Objectif** : Créer le tenant par défaut et remplir (backfill) les colonnes `tenant_id` pour toutes les données existantes.
- **Opérations de schéma** : Aucune.
- **Opérations de données** :
  1.  `INSERT INTO tenants` pour créer le tenant "CORE".
  2.  `INSERT INTO tenant_users` pour lier tous les `users` existants au tenant "CORE".
  3.  `UPDATE` sur chaque table métier (`clients`, `sites`, `demandes`, etc.) pour définir `tenant_id` avec l'ID du tenant "CORE". L'ordre doit aller des tables parentes aux tables enfants.
- **Dépendances** : `002_add_nullable_tenant_columns`.
- **Risques** : **Élevé**.
  - **Durée** : Peut être très long sur des tables volumineuses.
  - **Verrouillage** : Les `UPDATE` peuvent poser des verrous sur les tables, impactant les performances de l'application.
- **Déploiement** : **Doit être exécuté pendant une fenêtre de maintenance planifiée.**

### 4. `004_make_tenant_columns_not_nullable`

- **Objectif** : Rendre les colonnes `tenant_id` obligatoires (`NOT NULL`).
- **Opérations de schéma** :
  - `op.alter_column('clients', 'tenant_id', nullable=False)`
  - `... (pour toutes les tables concernées)`
- **Opérations de données** : Aucune.
- **Dépendances** : `003_seed_default_tenant_and_backfill_data`. Le backfill doit être complet.
- **Risques** : Faibles. La migration échouera si une seule valeur `NULL` subsiste, ce qui agit comme une sécurité.
- **Déploiement** : À déployer en même temps que le code applicatif "tenant-aware".

### 5. `005_add_final_foreign_keys_and_constraints`

- **Objectif** : Mettre en place les contraintes d'intégrité finales (clés étrangères composites, unicités par tenant).
- **Opérations de schéma** :
  - `op.create_unique_constraint('uq_clients_tenant_id', 'clients', ['tenant_id', 'id'])`
  - `op.create_foreign_key('fk_sites_client_tenant', 'sites', 'clients', ['tenant_id', 'client_id'], ['tenant_id', 'id'])`
  - `op.create_foreign_key('fk_agents_prestataire_tenant', 'agents_securite', 'prestataires', ['tenant_id', 'prestataire_id'], ['tenant_id', 'id'])`
  - `op.create_unique_constraint('uq_prestataires_code_tenant', 'prestataires', ['tenant_id', 'code'])`
  - `... (pour toutes les contraintes)`
- **Opérations de données** : Aucune.
- **Dépendances** : `004_make_tenant_columns_not_nullable`.
- **Risques** : Modérés. La création des contraintes échouera si des données incohérentes ont été insérées entre le backfill et ce déploiement.
- **Déploiement** : À déployer en même temps que le code applicatif "tenant-aware" et la migration `004`.

---

## Plan de Déploiement Synchronisé

Les étapes `004`, `005` et le déploiement du code applicatif mis à jour doivent se faire **simultanément**.

1.  Mettre l'application en mode maintenance.
2.  Lancer `flask db upgrade` pour appliquer les migrations `004` et `005`.
3.  Déployer la nouvelle version du code backend.
4.  Désactiver le mode maintenance.
5.  Effectuer les smoke tests post-déploiement.

## Stratégie de Rollback

- **Avant `003` (Backfill)** : Le rollback est simple. Il suffit de faire un `flask db downgrade` pour supprimer les colonnes et les tables. Le risque est minime.
- **Après `003` (Backfill)** : Le rollback est complexe et non recommandé. Les données ont été modifiées en masse. La stratégie de repli consiste à restaurer le backup de la base de données pris avant la maintenance.
- **Après le déploiement final** : Le rollback implique deux actions synchronisées :
  1.  Faire un `flask db downgrade` pour annuler les contraintes (`005`) et rendre les colonnes nullables (`004`).
  2.  Redéployer l'ancienne version du code applicatif qui n'est pas "tenant-aware".

Cette opération de rollback est risquée et doit être évitée autant que possible par des tests rigoureux en pré-production.