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
* `odoo_planning_slots` : Mapping des vacations planifiées PERMATEL vers `planning.slot` Odoo (`tenant_id`, `vacation_id`, `odoo_slot_id`) — cf. §4.2.

Chaque modèle Odoo cible porte en complément un champ custom `x_permatel_ref` (cf. §2.4) — c'est la clé d'idempotence de la synchro, indépendante des colonnes `odoo_*_id` ci-dessus qui ne sont que le cache local du mapping une fois établi.

---

## 4. Modules RH natifs PERMATEL (prérequis aux Phases 9 et 10)

Deux briques décidées le 13/08, natives à PERMATEL (indépendantes d'Odoo pour leur fonctionnement, mais alimentant la Phase 9 pour les documents et poussées vers Odoo Planning pour le planning). Motivation : un agent recruté doit fournir des documents dont la validité expire, et sa planification (aujourd'hui inexistante — `DemandePlanning` est un ticket de signalement, pas un calendrier de vacations) doit pouvoir être bloquée si ses documents obligatoires sont expirés.

### 4.0 Prérequis technique commun
`agents_securite` n'a aujourd'hui aucune contrainte unique sur `(tenant_id, id)` (seulement sur `(tenant_id, matricule)`), nécessaire pour poser une `ForeignKeyConstraint` composite depuis une nouvelle table (même contrainte qu'a dû poser `prestataires` pour `AgentSecurite.prestataire_id`). Une migration l'ajoute avant les modèles ci-dessous, partagée par §4.1 et §4.2.

### 4.1 Gestion documentaire des agents

**Modèle** :
* `document_types` (ou `ReferenceValue.family="type_document_agent"`, motif déjà en place pour `qualification_agent`) : catalogue des types de documents (carte pro, CQP, SSIAP, visite médicale, permis…), par tenant.
* `qualification_document_requirements` : mapping — pour chaque code `ReferenceValue.family="qualification_agent"`, quels `document_types` sont obligatoires. Piloté par la config tenant, pas codé en dur.
* `agent_documents` : `tenant_id`, `agent_id` (FK composite → `agents_securite`), `document_type_id`, `chemin_fichier` (**chiffré au repos**, motif `EmailAttachment` + `encrypt_bytes()`/`decrypt_bytes()` — pas le motif `Fichier`, non chiffré), `date_delivrance`, `date_expiration` (nullable), `is_current`, `replaced_at`, `uploaded_by_id`, `expiry_warning_notified`, `expiry_breach_notified`.

**Rétention** : un nouvel upload pour le même `(agent_id, document_type_id)` ne supprime rien — il marque l'ancienne ligne `is_current=False`/`replaced_at=now()` et insère la nouvelle en `is_current=True`. Seule la ligne courante compte pour la validité ; l'historique reste consultable dans la fiche agent.

**Upload** : `POST /api/agents/<id>/documents`, `@tenant_required` sans restriction de rôle au-delà — PERMANENCIER et MANAGER autorisés (pas réservé à ADMIN).

**Suivi de validité** : `document_sweep()` calqué sur `sla_sweep()` (`backend/app/services/sla.py`) — requête les lignes `is_current=True` dont `date_expiration` approche/est dépassée, `notify()` avec flags `expiry_warning_notified`/`expiry_breach_notified` pour ne jamais alerter deux fois. Nouvelle commande CLI `flask documents-sweep`, même cadence cron que `sla-sweep`.

**Blocage configurable** : `Tenant.document_blocking_expired` (bool, défaut `False`) — cf. §4.3. Le point d'application du blocage est l'**affectation d'un agent à une vacation** (§4.2), pas la prise de service : si activé et que l'agent a un document obligatoire manquant/expiré, l'affectation est refusée (409) avec le détail des documents en cause.

### 4.2 Planning agents (calendrier de vacations)

Nouvelle entité, distincte de `PriseDeService` (qui reste l'unique source de vérité des heures réellement travaillées — aucun changement sur ce point).

**Modèle `vacations_planifiees`** :
```
tenant_id, agent_id (FK composite → agents_securite, NULLABLE — créneau non affecté),
client_id, site_id, date_debut_prevue, date_fin_prevue (nullable),
prise_de_service_id (FK nullable, posée au pointage effectif si correspondance),
planifie_par_id (manager), no_show_notified (bool),
created_at, updated_at
```

**Statut affiché — dérivé, jamais stocké**, même motif que `sla_state(demande)` (déjà en place, `backend/app/routes/demandes.py`) :

```python
def vacation_state(v):
    if v.prise_de_service_id:
        retard = v.prise_de_service.date_debut - v.date_debut_prevue
        return "honoree" if retard <= seuil else "honoree_retard"   # vert / orange
    if v.agent_id is None:
        return "non_affectee"                                       # gris
    if utcnow() >= v.date_debut_prevue + seuil:
        return "non_honoree"                                        # rouge
    return "affectee"                                                # bleu
```
`seuil` = `Tenant.vacation_delay_threshold_minutes` (cf. §4.3) — **un seul réglage** pour la distinction honorée/honorée-en-retard *et* pour le déclenchement de l'alerte no-show, pour n'avoir qu'une constante métier. Une alerte no-show déjà envoyée n'est jamais "retirée" si l'agent finit par pointer en retard — seul l'affichage se corrige de rouge à orange.

**Rattachement à la prise de service** : au `POST /api/prises-de-service/start`, recherche d'une `vacation_planifiee` correspondante (même agent, fenêtre horaire proche) → si trouvée, pose `prise_de_service_id`. Comportement des prises de service non planifiées inchangé.

**Alerte no-show** : sweep calqué sur `sla_sweep()`/`notify()` — `vacations_planifiees` où `date_debut_prevue + seuil < now()`, `agent_id` non nul, `prise_de_service_id` nul, `no_show_notified=False` → notifie via `tenant_members(tenant_id, roles={MANAGER}, membership_admin=True)` (helper déjà utilisé par les alertes SLA, `backend/app/services/sla.py`), email automatique via le pipeline `notify()` → `EmailOutbox` → `dispatch_emails()` déjà opérationnel. Nouvelle commande CLI `flask vacations-no-show-sweep`.

**Frontend** : 3 vues (Jour / Semaine / Mois). Recommandé : grille custom légère, pas de dépendance calendrier tierce — les vacations sont des évènements ponctuels (une heure de début, pas des plages multi-jours à glisser/redimensionner), donc une lib pensée pour ces cas apporte plus de poids que de valeur ; cohérent avec le choix `xmlrpc.client` plutôt qu'une lib tierce pour Odoo (§2.2). Vue Jour/Semaine = tableau (lignes agents, colonnes heures/jours) ; vue Mois = grille de jours avec puces colorées par agent.

**Push Odoo** : à la création/affectation/annulation d'une vacation, push vers `planning.slot` (app Odoo Planning, dans le périmètre du §1), même mécanique d'idempotence que le reste du plan (§2.4) — champ miroir `x_permatel_ref` sur `planning.slot`, mapping dans `odoo_planning_slots` (§3.B). Les références `agent_id` → `hr.employee` (Phase 9) et `client_id`/`site_id` → `project.project`/`project.task` (Phase 7) sont réutilisées telles quelles, aucun nouveau mapping requis à part la table de correspondance des créneaux.

### 4.3 Nouveaux réglages tenant

Toggles tenant-wide en colonnes directes sur `Tenant` (motif `channel_telephonie`/`email`/`chat`), mais éditables par l'**admin du tenant** (`@tenant_admin_required`) et non l'admin global — nuance par rapport aux toggles `channel_*` existants (`PUT /api/tenants/<id>`, réservé ADMIN global) : ce sont des politiques métier propres au tenant, exposées dans `SettingsGeneral.vue` via une nouvelle route tenant-scopée.

* `document_blocking_expired` (bool, défaut `False`) — §4.1.
* `vacation_delay_threshold_minutes` (int, défaut `15`) — §4.2.

---

## 5. Phasage de l'implémentation (Alignement des Études)

Le détail des tâches est géré dans le fichier de suivi Excel (Phases 6 à 10). Voici l'alignement entre ces phases et les études architecturales (Parties 1, 2 et 3) :

### Phase 6 : Fondations transverses
* Flag `integrations.erp` activable par tenant.
* Création de `OdooConfig` (référence au `company_id` Odoo du tenant, instance partagée — §2.3) et `odoo_sync_queue` (avec `status`/`locked_at` — §2.4).
* Ajout du champ custom `x_permatel_ref` sur les modèles Odoo ciblés (`res.partner`, `project.project`, `sale.order`, `hr.employee`, …).
* Service XML-RPC `odoo_client.py` (client injecté, `execute_kw` avec `company_id` systématique — §2.2/2.3) et script CLI `flask odoo-sync-dispatch`.
* `tests/fakes/fake_odoo_client.py` pour la suite pytest (§2.5).
* Commande CLI de backfill initial, sur le modèle de `seed-prestataires`/`seed-agents` (§2.6).
* Réglages tenant `document_blocking_expired` et `vacation_delay_threshold_minutes` (§4.3) — indépendants d'Odoo mais posés dès cette phase, prérequis des Phases 9/10.

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
* **Prérequis** : contrainte unique `(tenant_id, id)` sur `agents_securite` (§4.0), gestion documentaire des agents (§4.1) — le blocage d'affectation (Phase 10) en dépend.
* **Agent** → Mapping vers `hr.employee`. (Les agents sous-traitants reçoivent une étiquette/tag Odoo spécifique pour les différencier).
* **Vacations (feuilles de temps)** : À la **clôture** exacte d'une `PriseDeService` dans PERMATEL, le script calcule la durée en heures et l'injecte comme feuille de temps (`account.analytic.line`) sur le Projet (Client) et la Tâche (Site) Odoo.
* *Note : Les vacations chevauchant minuit sont scindées en deux feuilles de temps.*

### Phase 10 : Planning agents (§4.2 — remplace l'hypothèse initiale "lecture depuis Odoo")
* **PERMATEL est la source du planning** (cohérent avec la philosophie du §1 — pas une lecture depuis Odoo comme envisagé initialement) : les managers créent/affectent les vacations planifiées dans PERMATEL (calendrier Jour/Semaine/Mois, §4.2), Odoo Planning (`planning.slot`) reçoit le **push**.
* Blocage d'affectation configurable par tenant (§4.1/§4.3) si l'agent a un document obligatoire expiré/manquant.
* Statuts dérivés (vert/bleu/gris/rouge/orange) + alerte no-show aux managers (§4.2) — fonctionnent indépendamment de l'activation d'Odoo pour ce tenant ; le push vers `planning.slot` est un enrichissement, pas une dépendance dure.
