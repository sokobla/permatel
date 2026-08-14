# PERMATEL × Odoo — Plan d'intégration et d'Architecture Globale

**Statut** : Planification et Architecture Validées — prêt pour l'implémentation.
**Date** : 13 Août 2026
**Suivi des tâches** : `docs/suivi_taches_permatel.xlsx` 

*(Note contextuelle : Les Phases 1 à 5 du projet global concernaient le développement du cœur de PERMATEL. L'intégration ERP constitue le deuxième grand bloc du projet, s'étalant historiquement des Phases 6 à 10 dans le document de suivi).*

---

## 1. Analyse du besoin et Philosophie

L'intégration d'Odoo 18 Community agit comme un service ERP additionnel (CRM/Vente, Comptabilité/Facturation, Planning RH) activable par tenant. 

**Philosophie de synchronisation :**
- PERMATEL est l'unique interface de saisie opérationnelle (Master).
- ERP assure le traitement financier et RH (Moteur backend).
- Les suppressions PERMATEL se traduisent TOUJOURS par un **Archivage (Soft Delete)** dans ERP (`active=False`) pour préserver l'intégrité comptable.

---

## 2. Décisions d'architecture technique

### 2.1 Orchestration : Cron + `erp_sync_queue`
Après le commit d'une action, tentative **synchrone à timeout court (2-3s)** vers ERP via XML-RPC. Succès → terminé. Échec/timeout → insertion dans `erp_sync_queue`, reprise par `flask erp-sync-dispatch` sur cron. Aucun broker Celery n'est requis.

### 2.2 Client ERP
Utilisation de `xmlrpc.client` (stdlib Python), encapsulé dans `app/services/erp_client.py`, exposant une méthode bas niveau unique (`execute_kw`). Le client est **injecté par paramètre** dans les services de synchro plutôt qu'importé en singleton — nécessaire pour le mock en test (cf. §2.5).

### 2.3 Topologie ERP : instance partagée, scoping par société
Une **seule instance ERP**, partagée entre tenants, scopée via `res.company` (une société ERP par tenant PERMATEL). `ErpConfig` (par tenant) ne stocke donc pas des credentials de connexion différents, mais l'URL/DB commune + le `company_id` ERP cible.

Conséquence directe sur le client : chaque appel `execute_kw` doit être émis avec `with_context(allowed_company_ids=[company_id], company_id=company_id)` pour que le filtrage multi-société d'ERP fasse l'isolation — ce n'est pas automatique, à coder explicitement dans `erp_client.py` (un paramètre `company_id` obligatoire sur chaque méthode du service, jamais un défaut implicite).

### 2.4 Idempotence de la synchronisation : champ miroir côté ERP
Chaque modèle ERP synchronisé (`res.partner`, `project.project`, `sale.order`, `hr.employee`, …) reçoit un champ custom **`x_permatel_ref`** (string, indexé), rempli avec `"{tenant_id}:{modele_permatel}:{id}"`.

Toute écriture passe par **search-then-write**, jamais un `create` en aveugle :
1. `search_read` sur `x_permatel_ref` — si trouvé, `write` sur l'id retourné ; sinon `create`, puis persistance immédiate de l'`erp_id` obtenu dans la table de mapping correspondante (`erp_partners`, `erp_employees`, …).
2. Une fois le mapping connu, les synchros suivantes écrivent directement par `erp_id` (le `search_read` par `x_permatel_ref` ne sert qu'à la toute première création, ou en secours si la table de mapping locale a été perdue/désynchronisée).

Ce mécanisme rend un retry sans effet de bord : si un appel précédent a réussi côté ERP mais que la ligne de `erp_sync_queue` n'a pas pu être marquée `done` (crash, timeout réseau après écriture), le retry suivant retrouve l'enregistrement existant via `x_permatel_ref` au lieu d'en créer un doublon.

**État de la ligne de queue** (`erp_sync_queue.status`) : `pending → in_flight → done | failed`, avec un `locked_at`/`locked_until` court pour qu'un run de `flask erp-sync-dispatch` qui prend du retard ne se fasse pas doubler par le suivant (même logique de verrouillage que `sessions-sweep`).

### 2.5 Tests : mock du client ERP (pas de vraie instance en CI)
La suite pytest tourne sur SQLite en mémoire, sans ERP réel disponible. Le découplage du §2.2 (client injecté, pas de singleton) permet de fournir en test un **faux client en mémoire** — `tests/fakes/fake_erp_client.py`, un dict Python implémentant juste `create`/`write`/`search_read` pour les modèles concernés — suffisant pour vérifier la logique de mapping/idempotence côté PERMATEL sans dépendre d'un vrai serveur ERP ni mocker XML-RPC au niveau transport.

### 2.6 Backfill initial
Les clients/sites/contacts/agents déjà existants en base au moment de l'activation du flag `integrations.erp` pour un tenant ne sont pas synchronisés rétroactivement par le flux événementiel (qui ne couvre que les créations/modifications futures). Une commande CLI dédiée gère l'amorçage initial, sur le modèle de `flask seed-prestataires`/`seed-agents` déjà existants : dry-run par défaut, `--tenant-code <CODE> --no-dry-run --yes` pour appliquer, un tenant à la fois.

### 2.7 Droits granulaires par action (Planning / Commerce / Facturation)
Le rôle global (PERMANENCIER/MANAGER/ADMIN) et l'admin de tenant seul sont trop grossiers pour ces actions : un tenant peut vouloir qu'un MANAGER précis ait le droit de facturer sans lui donner le droit sur le planning, ou l'inverse. Nouveau modèle **`tenant_user_permissions`** (`tenant_user_id` FK, `permission_code` String, `granted_by_id`, `granted_at`) — un code libre, pas un enum figé, cohérent avec la préférence déjà actée du projet pour `String` plutôt que Postgres `ENUM` sur une colonne amenée à grandir (`c5e10bf50c26_use_varchar_for_enums.py`). Codes prévus au démarrage : `planning`, `commerce`, `facturation` — liste appelée à grandir avec chaque nouveau module, jamais figée en code.

**Bypass** : l'ADMIN global et l'admin du tenant (`membership_role='admin'`) ont toutes les permissions implicitement, sans ligne à créer — seuls les membres non-admin ont besoin d'une permission explicite.

**Décorateur** `permission_required(code)` (`backend/app/utils/decorators.py`, motif `tenant_admin_required`) : contexte tenant chargé, puis `g.is_tenant_admin` OU existence d'une ligne `tenant_user_permissions` pour `(g.user.id, g.tenant_id, code)`.

**Frontend** : extension de `TenantMembersView.vue` (gestion des membres du tenant, déjà existante) — éditeur de permissions par membre (cases à cocher Planning/Commerce/Facturation), `PUT /api/tenants/<tid>/users/<uid>/permissions`.

**Application** : Facturer (§Phase 8) → `permission_required("facturation")` ; créer/valider un Devis (§Phase 8) → `permission_required("commerce")` ; créer/affecter une vacation planifiée (§4.2) → `permission_required("planning")`.

---

## 3. Évolution du Modèle de données (PERMATEL)

L'intégration ERP requiert l'ajout de nouveaux modèles dans PERMATEL pour s'aligner sur les standards ERP.

### A. Modèles Opérationnels (Nouveaux et Modifiés)
* **`Produit`** : Nouveau catalogue de prestations. Remplacera l'enum statique `type_commande`.
* **`TarifClient`** : Nouvelle grille tarifaire négociée par client.
* **`DemandeCommande`** : Modifié. Conserve son rôle de "demande brute" (avec choix multiple de prestations via tableau/JSON).
* **`Devis` / `DevisLigne`** : Nouveaux modèles. Créés par un Manager à partir d'une commande. Miroir exact du `sale.order` et `sale.order.line` d'ERP.

### B. Tables de Mapping ERP (`backend/app/models/erp.py`)
* `erp_config` : Par tenant — pas des credentials de connexion distincts (instance partagée, cf. §2.3), mais le `company_id` ERP cible pour ce tenant.
* `erp_partners` : Mapping CRM (`tenant_id`, type, `permatel_id`, `erp_partner_id`, `erp_project_id`, `erp_task_id`).
* `erp_employees` : Mapping RH (`tenant_id`, `agent_id`, `erp_employee_id`).
* `erp_sync_queue` : File de retry (`flux`, `payload` JSONB, `status: pending|in_flight|done|failed`, `locked_at`/`locked_until` — cf. §2.4).
* `erp_factures` : Copie locale des factures ERP — **1—N par `Devis`** (facturation partielle possible : acompte/solde), colonnes `tenant_id`, `devis_id`, `erp_invoice_id`, `numero_facture`, `montant_ht`, `montant_ttc`, `statut` (`brouillon|validee|payee|annulee`, Pull), `date_facture`, `date_echeance`, `updated_at` — cf. Phase 8.
* `erp_planning_slots` : Mapping des postes de vacation PERMATEL vers `planning.slot` ERP (`tenant_id`, `vacation_poste_id`, `erp_slot_id` — un `planning.slot` par poste, pas par vacation, cf. §4.2).

Chaque modèle ERP cible porte en complément un champ custom `x_permatel_ref` (cf. §2.4) — c'est la clé d'idempotence de la synchro, indépendante des colonnes `erp_*_id` ci-dessus qui ne sont que le cache local du mapping une fois établi.

---

## 4. Modules RH natifs PERMATEL (prérequis aux Phases 9 et 10)

Deux briques décidées le 13/08, natives à PERMATEL (indépendantes d'ERP pour leur fonctionnement, mais alimentant la Phase 9 pour les documents et poussées vers Planning (ERP) pour le planning). Motivation : un agent recruté doit fournir des documents dont la validité expire, et sa planification (aujourd'hui inexistante — `DemandePlanning` est un ticket de signalement, pas un calendrier de vacations) doit pouvoir être bloquée si ses documents obligatoires sont expirés.

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

**Blocage configurable** : `Tenant.document_blocking_expired` (bool, défaut `False`) — cf. §4.3. Le point d'application du blocage est l'**affectation d'un agent à un poste de vacation** (§4.2), pas la prise de service : si activé et que l'agent a un document obligatoire manquant/expiré (au regard du `profil_requis` du poste), l'affectation est refusée (409) avec le détail des documents en cause.

### 4.2 Planning agents (calendrier de vacations, multi-postes)

Nouvelle entité, distincte de `PriseDeService` (qui reste l'unique source de vérité des heures réellement travaillées — aucun changement sur ce point). Une vacation est un créneau de site pouvant nécessiter **plusieurs postes**, chacun avec son propre profil requis et son propre agent (ou vide) — ex. un même créneau peut demander 1×`agent_securite` + 1×`cynophile` simultanément.

**Modèle `vacations_planifiees`** (le créneau — site + horaire) :
```
tenant_id, site_id, client_id, date_debut_prevue, date_fin_prevue (nullable),
planifie_par_id (manager), created_at, updated_at
```

**Modèle `vacation_postes`** (1..N postes par vacation, `profil_requis` fixé **à la création de la vacation**, avant toute affectation) :
```
tenant_id, vacation_id (FK),
profil_requis (code ReferenceValue.qualification_agent — "agent_securite", "ssiap", "cynophile"…),
agent_id (FK composite → agents_securite, NULLABLE — poste non pourvu),
prise_de_service_id (FK nullable, posée au pointage effectif si correspondance),
no_show_notified (bool)
```

**Statut par poste — dérivé, jamais stocké**, même motif que `sla_state(demande)` (déjà en place, `backend/app/routes/demandes.py`) :

```python
def vacation_poste_state(p):
    if p.prise_de_service_id:
        retard = p.prise_de_service.date_debut - p.vacation.date_debut_prevue
        return "honoree" if retard <= seuil else "honoree_retard"   # vert / orange
    if p.agent_id is None:
        return "non_affectee"                                       # gris
    if utcnow() >= p.vacation.date_debut_prevue + seuil:
        return "non_honoree"                                        # rouge
    return "affectee"                                                # bleu
```
`seuil` = `Tenant.vacation_delay_threshold_minutes` (cf. §4.3) — **un seul réglage** pour la distinction honorée/honorée-en-retard *et* pour le déclenchement de l'alerte no-show. Une alerte no-show déjà envoyée n'est jamais "retirée" si l'agent finit par pointer en retard — seul l'affichage se corrige de rouge à orange.

**Statut agrégé par vacation — couverture globale**, calculé seulement une fois `date_debut_prevue` passée (« pourvu » = agent affecté **et** prise de service effective, pas juste affecté sur le papier) :

```python
def vacation_coverage_state(v):
    if utcnow() < v.date_debut_prevue:
        return None                                    # trop tôt, pas de statut agrégé
    postes_honores = [p for p in v.postes if p.prise_de_service_id]
    if not postes_honores:
        return "non_couverte"                          # rouge — personne ne s'est présenté
    if len(postes_honores) < len(v.postes):
        return "couverture_partielle"                  # orange — au moins un poste honoré, pas tous
    return "couverte"                                   # vert — tous les postes honorés
```
Ce statut agrégé est un indicateur de couverture au niveau du créneau (utile pour un coup d'œil manager), distinct des puces individuelles par poste qui gardent leur propre couleur.

**Rattachement à la prise de service** : au `POST /api/prises-de-service/start`, recherche d'un `vacation_poste` correspondant (même agent, fenêtre horaire proche) → si trouvé, pose `prise_de_service_id` sur le poste. Comportement des prises de service non planifiées inchangé.

**Droits** : création d'une vacation (et de ses postes), affectation d'un agent à un poste → `permission_required("planning")` (§2.7), pas un simple rôle MANAGER — un tenant peut réserver ce droit à certains managers seulement.

**Blocage documentaire (§4.1)** : à l'affectation d'un agent à un poste, vérification des documents de l'agent contre les exigences du **`profil_requis` du poste** (via `qualification_document_requirements`), pas seulement la qualification propre de l'agent — détecte au passage un éventuel mismatch de profil (agent SSIAP affecté par erreur à un poste Cynophile).

**Alerte no-show** : sweep calqué sur `sla_sweep()`/`notify()` — `vacation_postes` où `date_debut_prevue + seuil < now()` (via la vacation parente), `agent_id` non nul, `prise_de_service_id` nul, `no_show_notified=False` → notifie via `tenant_members(tenant_id, roles={MANAGER}, membership_admin=True)` (helper déjà utilisé par les alertes SLA, `backend/app/services/sla.py`), email automatique via le pipeline `notify()` → `EmailOutbox` → `dispatch_emails()` déjà opérationnel. Nouvelle commande CLI `flask vacations-no-show-sweep`.

**Frontend** : 3 vues (Jour / Semaine / Mois). Recommandé : grille custom légère, pas de dépendance calendrier tierce — les vacations sont des évènements ponctuels (une heure de début, pas des plages multi-jours à glisser/redimensionner), donc une lib pensée pour ces cas apporte plus de poids que de valeur ; cohérent avec le choix `xmlrpc.client` plutôt qu'une lib tierce pour ERP (§2.2). Vue Jour/Semaine = tableau (lignes agents, colonnes heures/jours) ; vue Mois = grille de jours avec, par vacation, la couleur agrégée de couverture et le détail des postes au clic.

**Push ERP** : à la création/affectation/annulation d'un poste, push vers `planning.slot` (module Planning de l'ERP, dans le périmètre du §1) — **un `planning.slot` par poste**, pas par vacation (le module Planning de l'ERP est structuré par ressource), tous partageant le même site/horaire. Même mécanique d'idempotence que le reste du plan (§2.4) — champ miroir `x_permatel_ref` sur `planning.slot`, mapping dans `erp_planning_slots` (§3.B). Les références `agent_id` → `hr.employee` (Phase 9) et `client_id`/`site_id` → `project.project`/`project.task` (Phase 7) sont réutilisées telles quelles, aucun nouveau mapping requis à part la table de correspondance des postes.

### 4.3 Nouveaux réglages tenant

Toggles tenant-wide en colonnes directes sur `Tenant` (motif `channel_telephonie`/`email`/`chat`), mais éditables par l'**admin du tenant** (`@tenant_admin_required`) et non l'admin global — nuance par rapport aux toggles `channel_*` existants (`PUT /api/tenants/<id>`, réservé ADMIN global) : ce sont des politiques métier propres au tenant, exposées dans `SettingsGeneral.vue` via une nouvelle route tenant-scopée.

* `document_blocking_expired` (bool, défaut `False`) — §4.1.
* `vacation_delay_threshold_minutes` (int, défaut `15`) — §4.2.

### 4.4 Accès direct ERP (support/admin)

Pas une porte dérobée au sens littéral (accès caché, non tracé, contournant l'authentification) — un accès restreint au rôle et **audité**, pour que l'ADMIN global puisse ouvrir ERP directement en cas de besoin de support, sans passer par le flux normal PERMATEL.

**Stockage** : nouveaux champs sur `erp_config` (ou table dédiée `erp_admin_access`) — `url_erp`, `admin_username`, `admin_password` — chiffrés au repos via `EncryptedText` (motif déjà utilisé pour `Email.subject`/`body_text`, `backend/app/utils/crypto.py` ; pas le pattern manuel `SmtpSetting`, pour rester cohérent avec la recommandation déjà actée dans CLAUDE.md : `EncryptedText` pour toute nouvelle colonne chiffrée).

**Endpoint** : `GET /api/erp/direct-access` — `@role_required(UserRole.ADMIN)` (rôle global, pas l'admin de tenant — même distinction qu'au §4.3). Retourne l'URL + les identifiants déchiffrés à la demande.

**Traçabilité** : chaque appel écrit une ligne `AuditLog` (`backend/app/models/audit_log.py`, motif déjà utilisé pour `SESSION_REVOKED` dans `auth.py`) — action `ERP_DIRECT_ACCESS_VIEWED`, avec `actor_id`, `tenant_id`, timestamp, IP. Un identifiant technique partagé reste un point faible (pas de traçabilité *côté ERP* de qui l'a utilisé), mais côté PERMATEL on sait toujours qui a demandé l'accès et quand.

**Frontend** : bouton "Accès direct ERP" visible uniquement pour l'ADMIN global (écran Support/Réglages plateforme, pas `SettingsGeneral.vue` qui est tenant-scopé) — ouvre l'URL ERP dans un nouvel onglet, affiche les identifiants à copier.

**Alternative plus forte (différée)** : flux SSO nominatif (l'admin PERMATEL s'authentifie sur ERP en son nom propre, traçable des deux côtés) — nécessite un module ERP additionnel pour émettre un jeton de connexion, plus d'effort. À envisager seulement si un vrai besoin de traçabilité par personne côté ERP apparaît ; l'identifiant partagé + audit PERMATEL suffit pour démarrer.

---

## 5. Phasage de l'implémentation (Alignement des Études)

Le détail des tâches est géré dans le fichier de suivi Excel (Phases 6 à 10). Voici l'alignement entre ces phases et les études architecturales (Parties 1, 2 et 3) :

### Phase 6 : Fondations transverses

**Statut (14/08) : livré**, code PERMATEL sous préfixe `Erp`/`erp_*` (décision actée avec l'utilisateur — cohérent avec §2.3/§3.B, pas `Odoo`/`odoo_*` malgré le nommage du suivi de tâches d'origine) :
* Flag `integrations.erp` (`Tenant.channel_erp`, motif `channel_telephonie`/`email`/`chat`) activable par tenant — `PUT /api/tenants/<id>`, ADMIN global.
* `ErpConfig` (`backend/app/models/erp.py`) — `company_id` ERP du tenant (instance partagée — §2.3) + 3 champs chiffrés `EncryptedText` pour l'accès direct admin (§4.4). `erp_sync_queue` (`ErpSyncQueue`) avec `status`/`attempts`/`locked_at`/`locked_until` (§2.4). Migration `c1b16fed65e1_erp_foundations.py`.
* Service XML-RPC `backend/app/services/erp_client.py` (`ErpClient`, injecté par paramètre, `execute_kw(company_id, ...)` avec `company_id` obligatoire et `with_context(allowed_company_ids=…)` systématique — §2.2/§2.3, timeout court configurable).
* `flask erp-sync-dispatch` (`backend/app/services/erp_sync.py`) — verrouillage `locked_at`/`locked_until` opérationnel et testé ; **le rejeu réel par flux n'est PAS implémenté** (aucun flux n'écrit encore dans la queue avant la Phase 7) — chaque ligne traitée passe actuellement en `failed` avec un message explicite, en attendant la logique métier de la Phase 7.
* `backend/tests/fakes/fake_erp_client.py` (§2.5) — `create`/`write`/`search_read`/`read` en mémoire, même signature que `ErpClient`.
* `flask erp-backfill --tenant-code <CODE>` (`backend/app/scripts/erp_backfill.py`) — **squelette fonctionnel** : compte les clients/sites/contacts/agents éligibles du tenant (dry-run par défaut, motif `seed-prestataires`), mais n'écrit encore rien vers ERP — dépend structurellement de `erp_partners`/`erp_employees` (§3.B), livrées en Phase 7.
* Réglages tenant `document_blocking_expired`/`vacation_delay_threshold_minutes` (§4.3) — colonnes `Tenant`, `GET/PUT /api/settings/general` (tenant-admin, pas ADMIN global).
* Accès direct ERP audité (§4.4) — `GET /api/erp/direct-access` (`backend/app/routes/erp.py`, `role_required(ADMIN)` global), trace une ligne `AuditLog` (`table_name="erp"`, event `ERP_DIRECT_ACCESS_VIEWED`) à chaque consultation. Écriture des 3 champs `url_erp`/`admin_username`/`admin_password` : **pas de route dédiée** dans cette passe (le plan ne spécifiait qu'un `GET`) — saisie directe en base au déploiement, ou futur écran Support/Réglages plateforme.

**Prérequis restant, hors code PERMATEL — champ custom `x_permatel_ref`** : à créer **côté Odoo lui-même** (Odoo Studio ou module custom) sur chaque modèle ERP ciblé (`res.partner`, `project.project`, `sale.order`, `hr.employee`, …) avant la Phase 7 — ce n'est pas une migration Postgres ni du code Flask, et ne peut pas être vérifié dans cet environnement (aucune instance Odoo réelle disponible). C'est la clé d'idempotence de toute la synchro (§2.4) : sans elle, la Phase 7 ne peut pas démarrer le search-then-write.

### Phase 7 : Gestion des Partenaires (Partie 1 : CRM)
* **Client PERMATEL** → ERP `res.partner(is_company=True)` + `project.project`.
* **Site PERMATEL** → ERP `res.partner(delivery)` + `project.task`.
* **Contact PERMATEL** → ERP `res.partner(contact)` lié au client principal (résolution de la relation N:N).
* *Phase 7.b (Catalogue)* : Synchronisation des `Produits` vers `product.product` et des `TarifsClient` vers `product.pricelist`.

### Phase 8 : Commandes et Facturation (Partie 2 : Ventes/Compta)
1. **Création (Push, `permission_required("commerce")` — §2.7)** : Le Manager transforme une `DemandeCommande` en **Devis** dans PERMATEL. Cela pousse un `sale.order` (Brouillon) dans ERP avec les bonnes lignes de produits.
2. **Validation (Push, `permission_required("commerce")`)** : La validation du devis dans PERMATEL déclenche l'`action_confirm` dans ERP (transformation en Bon de commande).
3. **Facturer (Push, `permission_required("facturation")`)** : Sur un Bon de commande confirmé, action "Facturer" dans PERMATEL → `sale.order.action_invoice_create()` via `erp_client.execute_kw`, crée une facture **brouillon** dans ERP. Mapping stocké dans `erp_factures` (`statut=brouillon`). **Facturation partielle possible** — une même commande peut générer plusieurs factures (acompte/solde), d'où `erp_factures` en 1—N par `Devis` (§3.B).
4. **Traitement (côté ERP, hors PERMATEL)** : la validation/comptabilisation de la facture (passage en `posted`) se fait directement dans ERP par la comptabilité — PERMATEL ne pousse pas cette étape, cohérent avec la délimitation du §1 (PERMATEL = saisie opérationnelle, ERP = moteur financier).
5. **Résultat (Pull)** : synchro régulière (`erp-sync-dispatch`) de `account.move.state`/`payment_state` → `erp_factures.statut` (brouillon/validée/payée/annulée) + montants HT/TTC, visibles dans PERMATEL sans repasser par ERP.
6. **Téléchargement PDF (Devis, Bon de commande, Facture)** : `GET /api/{devis,factures}/<id>/pdf` — appelle `ir.actions.report.render_qweb_pdf(report_name, [erp_id])` via `erp_client.execute_kw` et streame le PDF au navigateur. Motif déjà établi pour ce type de proxy-download : `downloadRecording` (`backend/app/routes/telephony.py`) et le téléchargement de pièces jointes email (`backend/app/routes/emails.py`), `responseType: "blob"` côté frontend — rien de nouveau architecturalement. Le nom exact du rapport QWeb (`sale.report_saleorder_document`, `account.report_invoice_with_payments`, …) dépend des modules ERP installés côté client, à figer en config une fois l'instance connue.

### Phase 9 : Agents & Temps (Partie 3 : RH/Analytique)
* **Prérequis** : contrainte unique `(tenant_id, id)` sur `agents_securite` (§4.0), gestion documentaire des agents (§4.1) — le blocage d'affectation (Phase 10) en dépend.
* **Agent** → Mapping vers `hr.employee`. (Les agents sous-traitants reçoivent une étiquette/tag ERP spécifique pour les différencier).
* **Vacations (feuilles de temps)** : À la **clôture** exacte d'une `PriseDeService` dans PERMATEL, le script calcule la durée en heures et l'injecte comme feuille de temps (`account.analytic.line`) sur le Projet (Client) et la Tâche (Site) ERP.
* *Note : Les vacations chevauchant minuit sont scindées en deux feuilles de temps.*

### Phase 10 : Planning agents (§4.2 — remplace l'hypothèse initiale "lecture depuis ERP")
* **PERMATEL est la source du planning** (cohérent avec la philosophie du §1 — pas une lecture depuis ERP comme envisagé initialement) : les managers créent/affectent les vacations planifiées dans PERMATEL (calendrier Jour/Semaine/Mois, §4.2), le module Planning de l'ERP (`planning.slot`) reçoit le **push**.
* Blocage d'affectation configurable par tenant (§4.1/§4.3) si l'agent a un document obligatoire expiré/manquant.
* Statuts dérivés (vert/bleu/gris/rouge/orange) + alerte no-show aux managers (§4.2) — fonctionnent indépendamment de l'activation d'ERP pour ce tenant ; le push vers `planning.slot` est un enrichissement, pas une dépendance dure.
