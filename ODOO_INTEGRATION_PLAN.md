# PERMATEL × Odoo — Plan d'intégration et d'Architecture Globale

**Statut** : Planification et Architecture Validées — prêt pour l'implémentation.
**Date** : 13 Août 2026
**Suivi des tâches** : `docs/suivi_taches_permatel.xlsx` 

*(Note contextuelle : Les Phases 1 à 5 du projet global concernaient le développement du cœur de PERMATEL. L'intégration Odoo constitue le deuxième grand bloc du projet, s'étalant historiquement des Phases 6 à 10 dans le document de suivi).*

---

## 1. Analyse du besoin et Philosophie

L'intégration d'Odoo 18 Community agit comme un service ERP additionnel (CRM/Vente, Comptabilité/Facturation, Planning RH) activable par tenant. 

**Philosophie de synchronisation :**
- PERMATEL est l'unique interface de saisie opérationnelle (Master).
- Odoo assure le traitement financier et RH (Moteur backend).
- Les suppressions PERMATEL se traduisent TOUJOURS par un **Archivage (Soft Delete)** dans Odoo (`active=False`) pour préserver l'intégrité comptable.

---

## 2. Décisions d'architecture technique

### 2.1 Orchestration : Cron + `odoo_sync_queue`
Après le commit d'une action, tentative **synchrone à timeout court (2-3s)** vers Odoo via XML-RPC. Succès → terminé. Échec/timeout → insertion dans `odoo_sync_queue`, reprise par `flask odoo-sync-dispatch` sur cron. Aucun broker Celery n'est requis.

### 2.2 Client Odoo
Utilisation de `xmlrpc.client` (stdlib Python), encapsulé dans `app/services/odoo_client.py`, exposant une méthode bas niveau unique (`execute_kw`). Le client est **injecté par paramètre** dans les services de synchro plutôt qu'importé en singleton — nécessaire pour le mock en test (cf. §2.5).

### 2.3 Topologie Odoo : instance partagée, scoping par société
Une **seule instance Odoo**, partagée entre tenants, scopée via `res.company` (une société Odoo par tenant PERMATEL). `OdooConfig` (par tenant) ne stocke donc pas des credentials de connexion différents, mais l'URL/DB commune + le `company_id` Odoo cible.

Conséquence directe sur le client : chaque appel `execute_kw` doit être émis avec `with_context(allowed_company_ids=[company_id], company_id=company_id)` pour que le filtrage multi-société d'Odoo fasse l'isolation — ce n'est pas automatique, à coder explicitement dans `odoo_client.py` (un paramètre `company_id` obligatoire sur chaque méthode du service, jamais un défaut implicite).

### 2.4 Idempotence de la synchronisation : champ miroir côté Odoo
Chaque modèle Odoo synchronisé (`res.partner`, `project.project`, `sale.order`, `hr.employee`, …) reçoit un champ custom **`x_permatel_ref`** (string, indexé), rempli avec `"{tenant_id}:{modele_permatel}:{id}"`.

Toute écriture passe par **search-then-write**, jamais un `create` en aveugle :
1. `search_read` sur `x_permatel_ref` — si trouvé, `write` sur l'id retourné ; sinon `create`, puis persistance immédiate de l'`odoo_id` obtenu dans la table de mapping correspondante (`odoo_partners`, `odoo_employees`, …).
2. Une fois le mapping connu, les synchros suivantes écrivent directement par `odoo_id` (le `search_read` par `x_permatel_ref` ne sert qu'à la toute première création, ou en secours si la table de mapping locale a été perdue/désynchronisée).

Ce mécanisme rend un retry sans effet de bord : si un appel précédent a réussi côté Odoo mais que la ligne de `odoo_sync_queue` n'a pas pu être marquée `done` (crash, timeout réseau après écriture), le retry suivant retrouve l'enregistrement existant via `x_permatel_ref` au lieu d'en créer un doublon.

**État de la ligne de queue** (`odoo_sync_queue.status`) : `pending → in_flight → done | failed`, avec un `locked_at`/`locked_until` court pour qu'un run de `flask odoo-sync-dispatch` qui prend du retard ne se fasse pas doubler par le suivant (même logique de verrouillage que `sessions-sweep`).

### 2.5 Tests : mock du client Odoo (pas de vraie instance en CI)
La suite pytest tourne sur SQLite en mémoire, sans Odoo réel disponible. Le découplage du §2.2 (client injecté, pas de singleton) permet de fournir en test un **faux client en mémoire** — `tests/fakes/fake_odoo_client.py`, un dict Python implémentant juste `create`/`write`/`search_read` pour les modèles concernés — suffisant pour vérifier la logique de mapping/idempotence côté PERMATEL sans dépendre d'un vrai serveur Odoo ni mocker XML-RPC au niveau transport.

### 2.6 Backfill initial
Les clients/sites/contacts/agents déjà existants en base au moment de l'activation du flag `integrations.erp` pour un tenant ne sont pas synchronisés rétroactivement par le flux événementiel (qui ne couvre que les créations/modifications futures). Une commande CLI dédiée gère l'amorçage initial, sur le modèle de `flask seed-prestataires`/`seed-agents` déjà existants : dry-run par défaut, `--tenant-code <CODE> --no-dry-run --yes` pour appliquer, un tenant à la fois.

---

## 3. Évolution du Modèle de données (PERMATEL)

L'intégration Odoo requiert l'ajout de nouveaux modèles dans PERMATEL pour s'aligner sur les standards ERP.

### A. Modèles Opérationnels (Nouveaux et Modifiés)
* **`Produit`** : Nouveau catalogue de prestations. Remplacera l'enum statique `type_commande`.
* **`TarifClient`** : Nouvelle grille tarifaire négociée par client.
* **`DemandeCommande`** : Modifié. Conserve son rôle de "demande brute" (avec choix multiple de prestations via tableau/JSON).
* **`Devis` / `DevisLigne`** : Nouveaux modèles. Créés par un Manager à partir d'une commande. Miroir exact du `sale.order` et `sale.order.line` d'Odoo.

### B. Tables de Mapping Odoo (`backend/app/models/odoo.py`)
* `odoo_config` : Par tenant — pas des credentials de connexion distincts (instance partagée, cf. §2.3), mais le `company_id` Odoo cible pour ce tenant.
* `odoo_partners` : Mapping CRM (`tenant_id`, type, `permatel_id`, `odoo_partner_id`, `odoo_project_id`, `odoo_task_id`).
* `odoo_employees` : Mapping RH (`tenant_id`, `agent_id`, `odoo_employee_id`).
* `odoo_sync_queue` : File de retry (`flux`, `payload` JSONB, `status: pending|in_flight|done|failed`, `locked_at`/`locked_until` — cf. §2.4).
* `odoo_factures` : Copie locale en lecture seule des factures Odoo (Pull).

Chaque modèle Odoo cible porte en complément un champ custom `x_permatel_ref` (cf. §2.4) — c'est la clé d'idempotence de la synchro, indépendante des colonnes `odoo_*_id` ci-dessus qui ne sont que le cache local du mapping une fois établi.

---

## 4. Phasage de l'implémentation (Alignement des Études)

Le détail des tâches est géré dans le fichier de suivi Excel (Phases 6 à 10). Voici l'alignement entre ces phases et les études architecturales (Parties 1, 2 et 3) :

### Phase 6 : Fondations transverses
* Flag `integrations.erp` activable par tenant.
* Création de `OdooConfig` (référence au `company_id` Odoo du tenant, instance partagée — §2.3) et `odoo_sync_queue` (avec `status`/`locked_at` — §2.4).
* Ajout du champ custom `x_permatel_ref` sur les modèles Odoo ciblés (`res.partner`, `project.project`, `sale.order`, `hr.employee`, …).
* Service XML-RPC `odoo_client.py` (client injecté, `execute_kw` avec `company_id` systématique — §2.2/2.3) et script CLI `flask odoo-sync-dispatch`.
* `tests/fakes/fake_odoo_client.py` pour la suite pytest (§2.5).
* Commande CLI de backfill initial, sur le modèle de `seed-prestataires`/`seed-agents` (§2.6).

### Phase 7 : Gestion des Partenaires (Partie 1 : CRM)
* **Client PERMATEL** → Odoo `res.partner(is_company=True)` + `project.project`.
* **Site PERMATEL** → Odoo `res.partner(delivery)` + `project.task`.
* **Contact PERMATEL** → Odoo `res.partner(contact)` lié au client principal (résolution de la relation N:N).
* *Phase 7.b (Catalogue)* : Synchronisation des `Produits` vers `product.product` et des `TarifsClient` vers `product.pricelist`.

### Phase 8 : Commandes et Facturation (Partie 2 : Ventes/Compta)
1. **Création (Push)** : Le Manager transforme une `DemandeCommande` en **Devis** dans PERMATEL. Cela pousse un `sale.order` (Brouillon) dans Odoo avec les bonnes lignes de produits.
2. **Validation (Push)** : La validation du devis dans PERMATEL déclenche l'`action_confirm` dans Odoo (transformation en Bon de commande).
3. **Facturation (Pull)** : Le cron PERMATEL récupère l'état des factures (`account.move`) depuis Odoo pour les afficher aux managers.

### Phase 9 : Agents & Temps (Partie 3 : RH/Analytique)
* **Agent** → Mapping vers `hr.employee`. (Les agents sous-traitants reçoivent une étiquette/tag Odoo spécifique pour les différencier).
* **Vacations** : À la **clôture** exacte d'une `PriseDeService` dans PERMATEL, le script calcule la durée en heures et l'injecte comme feuille de temps (`account.analytic.line`) sur le Projet (Client) et la Tâche (Site) Odoo. 
* *Note : Les vacations chevauchant minuit sont scindées en deux feuilles de temps.*

### Phase 10 : Planning agents
* Synchronisation en lecture du planning Odoo (si utilisé) et actions d'affectation. (À détailler après stabilisation de la phase 9).
