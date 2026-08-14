# Plan d'implémentation — ERP + modules RH (documents, planning, facturation, droits)

*(Complète `ODOO_INTEGRATION_PLAN.md`, qui fixe l'architecture — ce document
transforme cette architecture en tâches élémentaires séquencées, pour un
impact disruptif minimal et zéro perte de données existantes. Rédigé le
13/08, statut : à revoir/valider avant tout démarrage d'implémentation.
Mis à jour le 15/08 : ajout de la **Phase G.5 — Moteur de majoration
(TimeSplitter)**, qui détaille et corrige `ODOO_TIMESHEETS_MAJORATIONS.md`
suite à son évaluation critique du même jour — voir ce document pour le
contexte métier d'origine, `ODOO_TIMESHEETS_MAJORATIONS.md` porte
désormais une note renvoyant ici pour le détail d'implémentation
faisant foi.)*

## Contexte

`ODOO_INTEGRATION_PLAN.md` fixe l'architecture (validée sur plusieurs tours
d'échange le 13/08) : intégration ERP (CRM/Vente/Compta/RH/Planning) + deux
modules RH natifs PERMATEL (documents agents, planning multi-postes) +
droits granulaires + accès direct ERP audité. Aucun code `erp_*` n'existe
encore dans le repo (vérifié directement dans `backend/app/models/` et
`backend/app/routes/`). Ce document découpe cette architecture en tâches
élémentaires, **séquencées pour un impact disruptif minimal et zéro perte
de données existantes**.

**Principe directeur n°1 (garantit le "zéro perte")** : toute migration de
ce plan est **strictement additive** — nouvelles tables, nouvelles colonnes
nullables/à défaut, une seule contrainte `UNIQUE` ajoutée (`agents_securite`,
triviale et sans risque : `id` est déjà une PK auto-incrémentée donc
`(tenant_id, id)` est mécaniquement déjà unique, aucune ligne existante ne
peut violer la contrainte). Aucun `DROP`, aucun `RENAME`, aucun `ALTER`
resserrant une contrainte sur une colonne déjà peuplée. Chaque migration
suit le motif déjà établi dans le projet :

- Garde de sécurité à l'`upgrade()` façon `_abort_if_null_tenant()`
  (`backend/migrations/versions/a3178519ad55_tenant_id_not_null_clients_sites.py:30-47`)
  — abort avec les IDs en cause plutôt que deviner/écraser — partout où une
  migration touche une table déjà peuplée. Ici, seule l'ajout de la
  contrainte unique sur `agents_securite` touche une table peuplée ; sans
  risque réel, mais la garde est posée par cohérence et parce qu'elle est
  gratuite.
- `String`/`sa.Enum(..., native_enum=False)`, jamais `postgresql.ENUM`
  natif, pour toute nouvelle colonne de statut/type amenée à grandir
  (motif `c5e10bf50c26_use_varchar_for_enums.py:28-31`) — s'applique à
  `vacation_postes.profil_requis`, `erp_sync_queue.status`,
  `erp_factures.statut`, `tenant_user_permissions.permission_code`.
- FK composite vers une table tenant-scopée : motif exact de
  `0cf7c58db304_missing_composite_fks_sla_prises_emails.py:79-110`
  (`batch_op.create_foreign_key(...)` sur `(tenant_id, x_id) → (tenant_id, id)`),
  précédé si besoin de la contrainte unique préalable façon
  `a1b2c3d4e5f6_add_unique_prestataires.py:19-34`.
- **Avant toute nouvelle migration** : `flask db heads` doit renvoyer un
  seul head (2 migrations de fusion existent déjà dans l'historique du
  projet — la divergence est un risque réel et déjà survenu plusieurs fois
  par le passé sur ce projet).
- Chaque migration implémente un `downgrade()` correct (ne supprime que ce
  qu'elle a ajouté) — la réversibilité est le filet de sécurité ultime.

**Principe directeur n°2 (impact disruptif minimal)** : tout ce qui est
livré reste **invisible/inactif pour les tenants existants tant qu'il n'est
pas explicitement activé** — nouveaux flags (`integrations.erp`,
`document_blocking_expired`, permissions `tenant_user_permissions`), aucune
route ni comportement existant modifié en dehors des points d'intégration
explicitement listés (ex. `POST /api/prises-de-service/start` gagne une
recherche de correspondance en plus, mais son comportement pour les prises
de service non planifiées reste identique).

**Réordonnancement volontaire par rapport à la numérotation Phase 6-10 du
doc d'architecture** : les deux modules RH natifs (documents, planning) ne
dépendent pas d'ERP pour fonctionner (`ODOO_INTEGRATION_PLAN.md` §4,
intro : "indépendantes d'ERP pour leur fonctionnement"). Les livrer
**avant** toute la mécanique ERP (client XML-RPC, sync queue, cron) réduit
le risque : de la valeur utilisable et testée arrive tôt, sans dépendance à
une instance ERP externe encore non connectée. L'intégration ERP
elle-même vient ensuite, phase par phase, chacune indépendamment activable
par tenant.

---

## Phase A — Droits granulaires (prérequis du reste)

Nécessaire avant B/C car leurs routes d'écriture sont gardées par
`permission_required(...)`.

1. Migration additive : table `tenant_user_permissions`
   (`tenant_user_id` FK, `permission_code` String, `granted_by_id`,
   `granted_at`) — nouvelle table, zéro risque.
2. Modèle `backend/app/models/permission.py`.
3. `permission_required(code)` dans `backend/app/utils/decorators.py`,
   motif `tenant_admin_required` — bypass si `g.is_tenant_admin` ou
   `g.is_super_admin`, sinon vérifie l'existence de la ligne.
4. Routes : `GET/PUT /api/tenants/<tid>/users/<uid>/permissions`
   (`@tenant_admin_required`).
5. Frontend : extension de `TenantMembersView.vue` (éditeur de permissions
   par membre — cases à cocher, vide au départ donc aucun changement
   visible tant que personne n'attribue de droit).
6. Tests : bypass admin, refus sans permission, octroi/retrait.
7. **Vérification** : `flask db heads` (un seul head) → migration →
   `pytest tests/ -q --ignore=test_db.py` → lint+build frontend.

## Phase B — Gestion documentaire des agents

Aucune dépendance ERP. Valeur livrable seule.

1. Migration additive : contrainte `UNIQUE (tenant_id, id)` sur
   `agents_securite` (prérequis FK composite, motif `a1b2c3d4e5f6`) —
   garde de sécurité posée par cohérence même si sans risque réel.
2. Migration additive : tables `qualification_document_requirements`,
   `agent_documents` (chiffré, motif `EmailAttachment` +
   `encrypt_bytes()`/`decrypt_bytes()`, **pas** le motif `Fichier` non
   chiffré). Nouvelle valeur de `ReferenceValue.family="type_document_agent"`
   (pas de migration schéma requise, table déjà générique).
3. Migration additive : colonne `Tenant.document_blocking_expired`
   (Boolean, défaut `False`) — comportement inchangé tant que non activé.
4. Backend : upload chiffré (`POST /api/agents/<id>/documents`, PERMANENCIER
   + MANAGER, pas de restriction de rôle au-delà), rétention
   (`is_current`/`replaced_at`, jamais de suppression physique).
5. Backend : `document_sweep()` (motif `sla_sweep()`,
   `backend/app/services/sla.py`) + CLI `flask documents-sweep`.
6. Frontend :
   - Onglet "Documents" dans la fiche agent (`AgentView.vue`) — additif,
     n'affecte pas les onglets existants ; upload, historique des versions
     remplacées, indicateur de validité (à jour/expire bientôt/expiré).
   - Nouvelle vue de configuration (Settings) : catalogue `document_types`
     (motif `SettingsReferenceValues.vue`, déjà utilisé pour
     `qualification_agent`) et matrice `qualification_document_requirements`
     (quels documents obligatoires par qualification) — sans cette vue, la
     règle de blocage n'est pas paramétrable par le tenant.
   - Toggle `document_blocking_expired` ajouté à `SettingsGeneral.vue`
     (§4.3 — éditable par l'admin du tenant, pas l'admin global).
7. Tests : upload, rétention (remplacement), sweep + notification
   idempotente, isolation tenant.
8. **Vérification** : migration up/down réversible testée sur DB scratch →
   suite complète → lint+build.

## Phase C — Planning agents (multi-postes)

Dépend de A (droits) et B (blocage documentaire, contrainte `agents_securite`).
Aucune dépendance ERP — le push ERP est différé en Phase F.

1. Migration additive : tables `vacations_planifiees` (créneau) et
   `vacation_postes` (1..N postes, `profil_requis` fixé à la création,
   `agent_id` nullable, `prise_de_service_id` nullable, `no_show_notified`).
2. Migration additive : colonne `Tenant.vacation_delay_threshold_minutes`
   (Integer, défaut `15`).
3. Backend : routes création vacation+postes, affectation d'un agent à un
   poste (`permission_required("planning")` + vérification blocage
   documentaire contre `profil_requis`, 409 si documents invalides et
   blocage activé).
4. Backend : fonctions pures dérivées `vacation_poste_state()` (par poste :
   gris/bleu/vert/rouge/orange) et `vacation_coverage_state()` (agrégé par
   vacation : couverte/partielle/non couverte, calculé seulement après
   `date_debut_prevue`) — jamais stockées, motif `sla_state(demande)`.
5. Backend : au `POST /api/prises-de-service/start`, recherche additive
   d'un `vacation_poste` correspondant → pose `prise_de_service_id` si
   trouvé ; **comportement inchangé si aucune correspondance** (prise de
   service non planifiée = comportement actuel, non touché).
6. Backend : sweep no-show (motif `sla_sweep()`/`notify()` +
   `tenant_members(roles={MANAGER}, membership_admin=True)`) + CLI
   `flask vacations-no-show-sweep`.
7. Frontend :
   - Nouvelle route `/planning`, 3 vues (Jour/Semaine/Mois), grille custom
     (pas de dépendance calendrier tierce) — page entièrement nouvelle,
     zéro impact sur le reste de l'app.
   - Formulaire de création de vacation (site, date/heure, ajout de
     postes avec `profil_requis`) et formulaire d'affectation d'un agent
     à un poste (avec message d'erreur explicite si blocage documentaire).
   - Puces colorées par poste (vert/bleu/gris/rouge/orange) + indicateur
     de couverture agrégée par vacation, sur les 3 vues.
   - Toggle `vacation_delay_threshold_minutes` ajouté à
     `SettingsGeneral.vue` (§4.3).
8. Tests : création/affectation, blocage documentaire, statuts dérivés
   (tous les cas de couleur), rattachement prise de service, sweep no-show,
   non-régression sur les prises de service non planifiées existantes.
9. **Vérification** : migration up/down → suite complète → lint+build →
   test manuel des 3 vues calendrier.

## Phase D.0 — Déploiement infrastructure ERP

Prérequis à D : sans instance ERP joignable, tout ce qui suit reste
théorique. `docker-compose.yml` actuel (vérifié) ne contient aucun service
ERP — deux nouveaux services à ajouter, avec les mêmes durcissements que
l'existant (`security_opt: no-new-privileges`, `mem_limit`/`cpus`,
healthcheck, `restart: unless-stopped`, `logging: *default-logging`).

1. **Service `erp_db`** (Postgres **dédié**, séparé de `db` PERMATEL —
   ERP gère son propre schéma, ne jamais partager l'instance existante) :
   image `postgres:15-alpine`, volume `erp_db_data`, sur `permatel_internal`
   uniquement, healthcheck `pg_isready`.
2. **Service `erp`** : image `odoo:18.0` (l'image publiée réellement porte
   le nom du produit — seul le nom de notre service/conteneur est générique),
   `depends_on: erp_db (healthy)`,
   volume `erp_data` (filestore — pièces jointes, PDF générés), variables
   `HOST=erp_db`, `USER`/`PASSWORD` (secrets `.env`, motif
   `POSTGRES_PASSWORD:?requis`). Sur `permatel_internal` (le backend PERMATEL
   doit le joindre en XML-RPC) **et** `traefik_public` (l'UI web doit être
   ouvrable par l'admin global, §4.4).
3. **Installation des modules ERP au premier démarrage** : l'image standard
   démarre sans module métier installé — script d'init (`-i sale,account,hr,
   planning` ou équivalent, `odoo -d <db> -i ... --stop-after-init` en étape
   de build/entrypoint — `odoo` est le binaire réel de l'image, invariant)
   pour que `sale.order`/`account.move`/`hr.employee`/`planning.slot`
   existent avant toute tentative de push PERMATEL.
4. **Exposition Traefik dédiée** (motif labels `frontend` existants) :
   routeur `erp.${DOMAIN}`, TLS `certresolver=le`, **middleware
   supplémentaire de restriction d'accès** (IP allowlist ou basic-auth
   Traefik en plus du login ERP lui-même) — ce n'est pas une UI destinée
   aux utilisateurs finaux, seulement à l'ADMIN global (§4.4) et à la
   comptabilité côté client ERP.
5. **Sauvegardes** : `erp_db_data` a besoin de sa propre stratégie de
   backup (données financières/RH) — distincte de celle de PERMATEL,
   documentée séparément (hors périmètre technique de ce plan applicatif,
   mais bloquant avant mise en production réelle).
6. **Dimensionnement** : Odoo Community (le produit réellement déployé
   derrière le service `erp`) est nettement plus lourd qu'un
   service PERMATEL typique — prévoir `mem_limit: 2g`+/`cpus: 1.5`+ minimum
   à ajuster selon le nombre de tenants actifs sur l'instance partagée.
7. **`.env`** : nouvelles variables `ERP_DB_PASSWORD`, `ERP_ADMIN_PASSWORD`
   (bootstrap initial, à distinguer des identifiants applicatifs stockés
   chiffrés dans `erp_admin_access` côté PERMATEL, §4.4).
8. **Vérification** : `docker compose up -d erp_db erp` → healthcheck vert
   → UI ERP accessible via `https://erp.${DOMAIN}` (derrière la
   restriction d'accès) → modules métier visibles dans ERP → un appel
   `execute_kw` manuel de test (script ponctuel, hors CLI définitif) confirme
   la joignabilité XML-RPC depuis le conteneur `backend`.

## Phase D — Fondations ERP (scaffolding, aucun push réel encore)

Première phase touchant réellement ERP. Tout reste inactif tant que
`integrations.erp` n'est pas activé pour un tenant.

1. Migration additive : tables `erp_config`, `erp_sync_queue`
   (`status` String + `locked_at`/`locked_until`), `erp_admin_access`
   (URL + identifiants chiffrés `EncryptedText`, motif `Email.subject`).
2. Flag `integrations.erp` dans `tenant_features()`
   (`backend/app/services/tenant_features.py`) — dérivé, pas de nouvelle
   colonne `Tenant` (motif déjà en place pour `slack`/`telephony`).
3. `backend/app/services/erp_client.py` : `execute_kw` unique, client
   **injecté par paramètre** (jamais singleton), `company_id` obligatoire
   sur chaque appel (topologie instance partagée/société).
4. `tests/fakes/fake_erp_client.py` (dict en mémoire, `create`/`write`/
   `search_read`) — permet de tester tout le reste sans ERP réel.
5. Mécanique d'idempotence : champ miroir `x_permatel_ref` (recherche avant
   écriture), état de queue `pending → in_flight → done|failed`.
6. CLI `flask erp-sync-dispatch` (cron, no-op tant que la queue est vide).
7. CLI de backfill initial (motif `seed-prestataires`/`seed-agents` :
   dry-run par défaut, `--tenant-code <CODE> --no-dry-run --yes`).
8. Endpoint `GET /api/erp/direct-access` (`@role_required(ADMIN)` global) +
   écriture `AuditLog` (`ERP_DIRECT_ACCESS_VIEWED`) à chaque appel, motif
   `SESSION_REVOKED` dans `auth.py`.
9. Frontend :
   - Nouvelle vue Settings "Intégration ERP" (tenant-scopée, motif
     `SettingsGeneral.vue`/`SettingsSla.vue`) : activation `integrations.erp`,
     `company_id` ERP cible — sans elle, `ErpConfig` n'est configurable
     qu'en base directement.
   - Bouton "Accès direct ERP" (§4.4), visible uniquement ADMIN global —
     écran Support/Réglages plateforme, pas `SettingsGeneral.vue`.
   - Nouvelle vue de supervision (motif `SupervisionView.vue`, onglet
     Téléphonie déjà existant) : file `erp_sync_queue` — syncs en échec
     visibles, action "Relancer" manuelle. Sans cet écran, un échec de
     synchro est invisible pour les utilisateurs (silencieux jusqu'au
     prochain retry cron).
10. Tests : idempotence (retry sans doublon via `fake_erp_client`), queue
    (verrouillage, statuts), audit log sur l'accès direct.
11. **Vérification** : migration → suite complète → CLI exécutables en
    local sans erreur (queue vide = no-op propre) → lint+build frontend.

## Phase E — Push planning vers ERP (branchement sur Phase C)

1. Migration additive : table `erp_planning_slots`
   (`vacation_poste_id`, `erp_slot_id`) — **un mapping par poste**, pas
   par vacation (le module Planning de l'ERP est structuré par ressource).
2. Backend : à la création/affectation/annulation d'un poste, tentative
   synchrone courte (2-3s) → `erp_sync_queue` en secours, push vers
   `planning.slot` (search-then-write sur `x_permatel_ref`).
3. Tests avec `fake_erp_client` : création, retry, idempotence.
4. **Vérification** : suite complète ; test manuel avec un tenant
   `integrations.erp` activé pointant vers une instance ERP de test si
   disponible, sinon validation via les fakes uniquement.

## Phase F — CRM (Client/Site/Contact → ERP)

1. Migration additive : table `erp_partners`.
2. Push : Client → `res.partner(is_company=True)` + `project.project` ;
   Site → `res.partner(delivery)` + `project.task` ; Contact →
   `res.partner(contact)`.
3. Frontend : badge léger "Synchronisé ERP ✓/✗" sur les fiches
   Client/Site/Contact — pas de vue dédiée nécessaire, la synchro reste
   transparente ; le badge suffit pour un diagnostic rapide (le détail des
   échecs reste dans la vue de supervision `erp_sync_queue`, Phase D).
4. Tests avec `fake_erp_client` ; isolation tenant.
5. **Vérification** : suite complète.

## Phase G — Catalogue (coexistence, pas de remplacement destructif)

`ODOO_INTEGRATION_PLAN.md` dit que `Produit` "remplacera" l'enum
`type_commande` — pour le zéro-perte/zéro-disruption, ce plan **ne
supprime pas `type_commande`** : coexistence, pas de bascule forcée.

1. Migration additive : tables `Produit`, `TarifClient`.
2. Migration additive : colonne nullable `DemandeCommande.produit_id`
   (FK), **`type_commande` conservé tel quel** — les demandes existantes
   ne sont ni migrées ni réinterprétées.
3. Frontend :
   - Nouvelle vue de gestion du catalogue (`Produit`/`TarifClient` — CRUD
     complet : ces objets n'ont aujourd'hui aucune UI, à créer de zéro,
     probablement sous Settings ou une nouvelle route `/catalogue`).
   - Le formulaire de commande permet de choisir un `Produit` du catalogue
     **si le tenant en a défini** ; sinon comportement actuel
     (`type_commande`) inchangé — bascule complète vers `Produit` seul
     explicitement **hors périmètre de ce plan**, décision produit séparée
     à prendre plus tard.
4. Push : `Produit` → `product.product`, `TarifClient` → `product.pricelist`.
5. Tests, vérification suite complète.

## Phase G.5 — Moteur de majoration (TimeSplitter)

*(Détaille et corrige `ODOO_TIMESHEETS_MAJORATIONS.md`, dont le statut est
mis à jour en conséquence — voir note en tête de ce document. Insérée
entre G et H car H (facturation multi-lignes) et I (paie RH) en dépendent
tous les deux, mais elle ne dépend elle-même que de l'existant
(`PriseDeService`, `Tenant`) : peut être livrée dès que G est fusionné,
sans attendre l'infra ERP (D.0) ni aucun push réel.)*

**Décisions architecturales actées (corrigent le document d'origine)** :
- **Majorations cumulatives, pas des catégories exclusives** : un segment
  porte un *ensemble* de majorations applicables (ex. `{nuit, ferie}`),
  chacune avec son taux, plutôt qu'une seule catégorie composite figée —
  évite l'explosion combinatoire de lignes de devis (jusqu'à 8+ lignes
  pour couvrir toutes les combinaisons Jour/Nuit×WE×Férié).
- **Moteur unique partagé facturation ET paie** : `time_splitter.py`
  produit une segmentation temporelle neutre (bornes + majorations
  applicables) ; Phase H (facturation, taux client négociés) et Phase I
  (paie, taux légaux/conventionnels) appliquent chacune leurs propres
  règles sur la même segmentation de base — élimine le risque de
  divergence entre deux implémentations séparées identifié dans
  l'évaluation du 15/08.
- **Règles effectives-datées** (`valid_from`/`valid_to`) : éditer une
  règle n'affecte jamais rétroactivement une vacation déjà close (dont le
  découpage est figé en JSON à la clôture, jamais recalculé après coup).
- **Repli explicite si aucune correspondance** : un segment sans ligne de
  devis/majoration correspondante ne doit jamais être facturé sur la
  mauvaise ligne — passe par `erp_sync_queue` (`status=failed`, message
  explicite) et notifie le Manager (motif `notify()` déjà utilisé pour les
  alertes SLA/no-show), jamais un échec silencieux.
- **Hors périmètre explicite de cette phase** : l'exclusion des pauses à
  l'intérieur d'une vacation (`PriseDeService` n'a aujourd'hui aucun
  tracking de pause interne, contrairement à `UserSession.status` côté
  téléphonie — les deux ne sont pas reliés) — à réévaluer seulement si un
  besoin réel émerge, pas anticipé ici pour ne pas complexifier sans
  cas d'usage confirmé.

1. Migration additive : table `tenant_majoration_rules` (`tenant_id`,
   `code` String — pas d'Enum natif, motif `c5e10bf50c26` —, `label`,
   `heure_debut`/`heure_fin` (nullable, règle horaire type "Nuit") ou
   `jour_semaine` (nullable, règle calendaire type "Week-end"),
   `taux_pct` (Numeric), `valid_from`/`valid_to` (DateTime, `valid_to`
   NULL = toujours active), `priority` (Integer, ordre d'affichage/tri
   seulement — les majorations se cumulent, `priority` ne sert pas à
   choisir entre elles). Migration additive : table optionnelle
   `tenant_jours_feries` (`tenant_id`, `date`, `label`) — surcharge/ajout
   pour les tenants DOM-TOM ou Alsace-Moselle (jours fériés
   supplémentaires) ; si vide pour un tenant, repli sur le calendrier
   métropolitain calculé en pur Python (Pâques via l'algorithme de
   Meeus/Jones/Butcher + dates fixes), aucune dépendance externe.
2. Migration additive : colonne nullable `PriseDeService.majoration_segments`
   (JSON) — snapshot immuable du découpage au moment de la clôture, motif
   déjà retenu au §4.3 du document d'origine, jamais recalculé après
   écriture (garantit la valeur probatoire en cas de litige même si les
   règles changent ensuite). Colonne `Tenant.majoration_arrondi_minutes`
   (Integer, défaut `1` = pas d'arrondi) — arrondit la **durée totale**
   avant répartition proportionnelle entre segments, jamais segment par
   segment (évite l'accumulation d'erreurs d'arrondi indépendantes).
3. Modèle `backend/app/models/majoration.py` (`MajorationRule`, `JourFerie`).
4. Service pur `backend/app/services/time_splitter.py` :
   `split_time_range(start, end, rules, holidays) -> list[Segment]`,
   `Segment = {start, end, duration_minutes, majorations: [{code, taux_pct}]}`.
   Datetimes **timezone-aware** (`zoneinfo("Europe/Paris")`) de bout en
   bout — sans quoi les deux nuits de changement d'heure produisent un
   découpage faux. Fonction pure, testable en isolation sans DB.
5. Backend : hook dans la clôture de `PriseDeService`
   (`backend/app/routes/prises_de_service.py::end_current_prise()`/`end_prise()`,
   lignes 168/189) — appelle `split_time_range()`, persiste le résultat
   dans `majoration_segments`. Additif : ne change pas la forme de
   réponse existante au-delà de ce nouveau champ.
6. CLI `flask timesplitter-preview --prise-id <ID>` (lecture seule,
   affiche le découpage calculé sans écrire) — permet de valider une
   nouvelle règle contre des vacations historiques avant mise en
   production, motif déjà établi pour les autres commandes CLI du projet
   (`--dry-run` par défaut ailleurs, ici intrinsèquement non-écrivant).
7. Frontend :
   - Nouvelle vue Settings "Règles de majoration" (motif
     `SettingsReferenceValues.vue`) : CRUD `tenant_majoration_rules`,
     gestion `tenant_jours_feries`, réglage `majoration_arrondi_minutes`.
   - Bouton "Prévisualiser la ventilation" sur une prise de service en
     cours (`PrisesServicesView.vue`) — appelle un endpoint de simulation
     (mêmes règles, aucune écriture) avant clôture réelle, pour détecter
     une règle mal configurée avant qu'elle ne produise une facturation
     fausse.
   - Détail des segments affiché dans le rapport "Prises de service"
     existant (`ReportView.vue`, étendu Phase 16) — nouvelle section
     dépliable par ligne, pas de nouveau tableau.
8. Tests : composition cumulative (nuit+WE+férié simultanés), effet des
   dates `valid_from`/`valid_to` (une règle modifiée n'affecte pas un
   segment déjà figé), arrondi (total avant répartition, pas par
   segment), les deux nuits de changement d'heure DST, CLI preview,
   endpoint de simulation (aucune écriture).
9. **Vérification** : migration up/down → suite complète → CLI exécutable
   en local (`flask timesplitter-preview --prise-id <ID>` sur une donnée
   de test) → lint+build frontend.

## Phase H — Commerce et Facturation

Dépend de F (partenaires), G (catalogue) et **G.5** (segmentation par
majoration — une commande peut désormais générer plusieurs lignes de
feuille de temps par vacation, pas une seule).

1. Migration additive : tables `Devis`, `DevisLigne` (avec colonne
   `majoration_code`, nullable — String, référence libre au `code` d'une
   `MajorationRule`/`null` pour une ligne "Jour" non majorée, pas de FK
   stricte pour rester tolérant à une règle supprimée après coup),
   `erp_factures` (1—N par `Devis`, facturation partielle).
2. Backend : création Devis depuis une `DemandeCommande`
   (`permission_required("commerce")`) → push `sale.order` brouillon.
   Poussée des feuilles de temps (déclenchée à la clôture de
   `PriseDeService`, cf. Phase I) : pour chaque segment de
   `majoration_segments` (Phase G.5), recherche de la `DevisLigne`
   correspondante par `majoration_code`, un appel `execute_kw` par
   segment avec son propre `x_permatel_ref`
   (`"{tenant_id}:vacation_segment:{prise_id}:{index}"`, motif §2.4
   `ODOO_INTEGRATION_PLAN.md` — idempotence par segment, pas par
   vacation entière, pour qu'un échec partiel sur 3 lignes ne duplique
   pas les 2 déjà réussies au retry). **Repli explicite** si un segment
   n'a aucune `DevisLigne` correspondante : entrée `erp_sync_queue`
   `status=failed` avec message explicite (jamais poussé sur une ligne
   au hasard) + notification Manager (motif `notify()`, déjà utilisé
   pour les alertes SLA/no-show).
3. Backend : validation devis (`permission_required("commerce")`) →
   `action_confirm` (Bon de commande).
4. Backend : action "Facturer" (`permission_required("facturation")`) →
   `sale.order.action_invoice_create()`, facture brouillon ERP,
   `erp_factures.statut=brouillon`. Traitement/validation comptable
   **reste dans ERP**, PERMATEL ne pousse pas cette étape.
5. Backend : pull régulier `account.move.state`/`payment_state` →
   `erp_factures.statut` + montants.
6. Backend : `GET /api/{devis,factures}/<id>/pdf` (proxy
   `ir.actions.report.render_qweb_pdf`, motif `downloadRecording`
   `backend/app/routes/telephony.py`).
7. Frontend :
   - Nouvelle vue "Devis" (liste + détail) — `Devis`/`DevisLigne` sont des
     entités nouvelles, elles ont besoin d'un CRUD complet (création depuis
     une `DemandeCommande`, édition des lignes avant validation), pas
     seulement de boutons ajoutés sur la vue `DemandeCommande` existante.
     Chaque `DevisLigne` propose un sélecteur `majoration_code` (liste des
     `MajorationRule` du tenant + "Aucune majoration") — sans lui, le
     mapping segment→ligne de Phase G.5/H reste impossible à configurer.
   - Sur cette vue détail : actions Valider (→ Bon de commande) et
     Facturer, liste des factures liées (1—N, facturation partielle) avec
     leur statut (brouillon/validée/payée/annulée) et montants.
   - Téléchargement PDF (Devis, Bon de commande, chaque Facture).
8. Tests, vérification suite complète.

## Phase I — Agents & Temps (RH/Analytique)

Dépend de D (fondations), F (déjà `hr.employee` similaire au partner push)
et **G.5** (segmentation par majoration — remplace le découpage naïf
"minuit uniquement" initialement envisagé).

1. Migration additive : table `erp_employees`.
2. Push : `AgentSecurite` → `hr.employee` (étiquette ERP spécifique pour
   les sous-traitants).
3. Backend : à la **clôture** d'une `PriseDeService`
   (`majoration_segments` déjà calculé par Phase G.5, hook commun),
   push d'une `account.analytic.line` (feuille de temps) **par segment**,
   pas une ligne unique par vacation — remplace l'approche initialement
   prévue ("vacations chevauchant minuit scindées en deux feuilles"),
   devenue un cas particulier de la segmentation générale (un
   chevauchement de minuit produit mécaniquement ≥2 segments dès que la
   nuit est une catégorie de majoration). Taux de majoration **paie**
   (légal/conventionnel) potentiellement différent du taux de
   **facturation** client (Phase H) pour un même segment temporel — même
   moteur de segmentation (G.5), jeux de règles/taux distincts appliqués
   séparément par chaque phase. Idempotence par segment, même motif que
   Phase H (`x_permatel_ref` dédié, ex.
   `"{tenant_id}:vacation_segment_paie:{prise_id}:{index}"` — préfixe
   distinct de celui de Phase H pour ne jamais confondre une ligne de
   facturation et une ligne de paie partageant le même `prise_id`/index).
4. Frontend : badge "Synchronisé ERP ✓/✗" sur `AgentView.vue` (même motif
   léger que Phase F pour Client/Site/Contact) — pas de nouvelle vue dédiée,
   le push est transparent.
5. Tests (y compris le cas chevauchement minuit comme cas particulier de
   la segmentation générale, taux paie ≠ taux facturation sur un même
   segment), vérification suite complète.

---

## Vérification (à chaque phase, pas seulement à la fin)

- `flask db heads` (un seul head) avant toute nouvelle migration.
- `flask db upgrade heads` puis `flask db downgrade -1` puis
  `flask db upgrade heads` à nouveau sur une base de test — valide la
  réversibilité réelle de chaque migration, pas seulement sa présence.
- `cd backend && python -m pytest tests/ -q --ignore=test_db.py` après
  chaque phase, pas seulement à la fin (pratique déjà suivie sur le module
  Rapports livré le 13/08).
- `cd frontend && npx eslint <fichiers touchés> --rule '{"prettier/prettier":"off"}'`
  puis `npx vite build` après les changements frontend de chaque phase.
- Phase D.0 livre l'instance ERP de test/staging elle-même — avant elle,
  D-I se limitent à une validation via `fake_erp_client` (suffisant pour
  la logique PERMATEL, pas pour valider les noms de rapports QWeb réels ni
  les modules ERP effectivement installés côté client).
- Test manuel de non-régression après Phase C : vérifier que les prises de
  service non planifiées (flux actuel, sans vacation associée) continuent
  de fonctionner à l'identique.
