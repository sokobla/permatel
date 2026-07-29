# PERMATEL — Module Téléphonie : Plan d'intégration

**Statut** : Phases 11 à 14 implémentées et connectées en production (236/236 tests backend). Phase 12 (Core Connector ESL, connecteur **tenant-scopé** — §8.4) raccordée à un FusionPBX réel (`fusion.cloud228.com`) — deux bugs de production détectés et corrigés (deadlock de reconnexion concurrente, route Nginx manquante pour le WebSocket) — voir §8.5. Phase 13 (config relocalisée sous `Paramètres > Intégrations`, `Supervision > Téléphonie` avec grille d'état des agents via `CC-Agent-Status`) et Phase 14 (webhook CDR `POST /telephony/cdr/ingest/<token>` + onglet `Rapports > Téléphonie`) **faites** — voir §8.6, qui documente aussi les six correctifs successifs du webhook CDR, chacun validé contre du trafic FusionPBX réel. Validation des en-têtes ESL réels contre `normalizer.py` toujours en cours (un écart déjà confirmé, `Hangup-Cause: WRONG_CALL_STATE` non catégorisé, capturé sur du trafic de scan, pas encore sur un appel légitime), voir §8.3 — de même, l'exposition des enregistrements par FusionPBX (URL http(s) exploitable ou chemin local) reste à confirmer, voir §8.6. Phase 15 (connecteur Asterisk/AMI) non démarrée.
**Date** : 29 juillet 2026
**Source** : `docs/cdc/CDC-Module-Telephonie.md` (v1.0, 27 juillet 2026)
**Suivi des tâches** : `docs/suivi_taches_permatel.xlsx` (Phases 11 à 14)

---

## 1. Analyse du besoin face à l'existant

Contrairement au module Odoo, une partie de l'infrastructure existe déjà, mais à
l'état **dormant** :

| Élément du CDC | État réel dans PERMATEL |
|---|---|
| Table `telephony_events` | **Existe déjà** (`backend/app/models/telephony_event.py`), créée dans la migration initiale, avec FK composite tenant-scopée déjà en place (`tenant_id, demande_id → demandes.tenant_id, demandes.id`). Schéma **plus étroit** que le besoin (`event_type` enum figé `CALL_START/END/TRANSFER/HOLD`, pas de `call_direction`/`callee`/`queue_id`/`recording_url`/`raw_payload`/`pbx_connector_id`). **Aucune route, service ou script ne l'alimente ni ne la lit** — schéma posé, zéro logique derrière. |
| Flag `channel_telephonie` | Existe, mais purement cosmétique : gate uniquement la visibilité d'une tuile "Téléphonie" dans Réglages > Intégrations (`tenant_features.py`, `frontend/config/integrations.js`). Aucune config ni connecteur derrière. |
| `agent_login` / `station_extension` | Existent sur `User` et `UserSession` (commentaire `# ESL Téléphonie` déjà présent dans le code), mais usage purement administratif aujourd'hui — aucun rapprochement avec un événement PBX nulle part. |
| Chiffrement des identifiants PBX | Pattern déjà établi et **actif** en prod (pas dormant) : `EncryptedText` (TypeDecorator) est utilisé par `Email.subject/body_text/body_html` et supporté par le service de rotation de clé `reencrypt.py`. |
| File interne "mémoire ou Redis" | Redis déjà dans la stack (anti-brute-force), pattern de fallback gracieux déjà écrit dans `login_throttle.py`. |
| `SupervisionTelephonieView.vue` | N'existe pas telle quelle, mais `SupervisionView.vue` + `SessionMonitoring.vue` existent déjà comme coquille réutilisable pour la vue elle-même (KPIs, layout) — leur mécanisme de rafraîchissement (polling HTTP) n'est en revanche pas repris ici (voir décision §2.1). |
| `/ws/telephony` (WebSocket) | **N'existe pas, écart d'infrastructure réel** : pas de `flask-socketio`/`eventlet`/`gevent` dans `requirements.txt`, Gunicorn tourne en workers **sync** par défaut. Un WebSocket persistant par superviseur bloque un worker sync entier par connexion — nécessite de faire évoluer le worker class Gunicorn (`eventlet`/`gevent`) et d'ajouter Flask-SocketIO. Redis (déjà dans la stack) sert de *message queue* Socket.IO pour rester compatible multi-worker (`GUNICORN_WORKERS>1`) malgré ce changement — voir décision §2.1 révisée. |
| Connecteur ESL en process séparé | Cohérent avec l'existant : aucun process long-running ne tourne aujourd'hui dans PERMATEL (tout est requête/réponse Flask ou CLI ponctuel via cron) — ce sera la première brique de ce type. |

---

## 2. Décisions d'architecture

### 2.1 Temps réel : WebSocket (décision révisée — remplace le polling initialement retenu)

Le CDC initial (§6.3) suppose un WebSocket `/ws/telephony`. Une première
itération de ce plan avait écarté cette option au profit du polling HTTP
(infra Gunicorn sync actuelle non compatible nativement, précédent
`SessionMonitoring.vue` en polling). **Décision révisée à la demande du
porteur de projet : WebSocket retenu**, malgré le coût d'infrastructure —
acté en connaissance de cause :

- **Dépendance ajoutée** : `flask-socketio` (+ `python-socketio` côté client
  frontend, déjà couvert par les libs standards de l'écosystème Vite/Vue).
- **Worker class Gunicorn** : passage de sync à `eventlet` (ou `gevent`) pour
  que les workers puissent tenir des connexions WebSocket ouvertes sans se
  bloquer — configuré dans `docker-compose.yml`/`entrypoint.sh`
  (`GUNICORN_WORKER_CLASS`), impact sur *tous* les endpoints de l'app, pas
  seulement `/ws/telephony` (à valider en test de charge avant prod).
- **Multi-worker** : Redis (déjà dans la stack) comme *message queue*
  Flask-SocketIO (`message_queue=REDIS_URL`), pour que les événements diffusés
  par un worker atteignent les clients connectés sur un autre worker —
  indispensable dès que `GUNICORN_WORKERS>1`.
- **Authentification** : le token JWT est vérifié à la connexion socket (query
  param ou header selon le client Socket.IO), résolution `tenant_id` identique
  au flux REST (`tid` claim), le client rejoint une *room* Socket.IO par
  tenant (`join_room(str(tenant_id))`).
- **Snapshot initial conservé** : `GET /api/telephony/active-calls` reste en
  place pour l'état initial au chargement de la page (un client qui se
  connecte au socket n'a pas l'historique des événements déjà émis) ; le
  WebSocket ne pousse que les *deltas* ensuite.

### 2.2 `event_type` / `call_status` : `String` plutôt qu'enum Postgres

Le modèle `TelephonyEvent` existant utilise un enum Postgres natif à 4
valeurs. Le besoin en couvre 6+ (et une phase 2 Asterisk en ajoutera
d'autres). Le projet a déjà tranché ce type d'extensibilité ailleurs via la
migration `c5e10bf50c26_use_varchar_for_enums` (enums Postgres rigides →
`String` validé côté application). **Même traitement retenu ici.**

### 2.3 Extension de table plutôt que recréation

`telephony_events` existe déjà avec des données de production potentielles
(même si l'usage réel est nul aujourd'hui) et des relations actives
(`UserSession`, `Demande`, `Tenant`). **Retenu : migration d'ALTER**
(ajout de colonnes + élargissement `event_type`), pas de nouvelle table
parallèle — `user_session_id` reste nullable (rattachement optionnel à une
session active), complété par un `agent_login` dénormalisé direct, plus
simple à faire correspondre à un événement PBX qu'une session active.

---

## 3. Modèle de données (extension `telephony_events` + nouvelles tables)

| Table | Rôle |
|---|---|
| `telephony_events` (existante, étendue) | + `pbx_connector_id` (FK), `call_direction`, `callee`, `agent_login`, `queue_id`, `recording_url`, `raw_payload` (JSONB) ; `event_type` élargi en `String`. |
| `pbx_connectors` (nouvelle) | `id`, `tenant_id` (FK — **tenant-scopée**, revu post-Phase 12, voir §8.4), `name`, `type` (`String` : ESL/AMI/TSAPI), `host`, `port`, identifiants via `EncryptedText`, `is_active`, `is_connected`/`last_seen_at`/`last_error` (heartbeat), `sync_requested_at` (bouton Sync). |
| `pbx_connector_domains` (nouvelle — ex-`pbx_domains_tenants`) | `id`, `pbx_connector_id` (FK), `pbx_domain`, `queue_ids`. Plus de `tenant_id` propre : hérité du connecteur parent. |

Migrations suivant la convention déjà en place (docstring français, garde-fou
données explicite, jamais de suppression silencieuse).

---

## 4. Phasage détaillé

Le détail tâche-par-tâche est dans `docs/suivi_taches_permatel.xlsx`, onglet
« Tâches » (IDs `11.x` à `14.x`). Résumé :

| Phase | Contenu | Détail |
|---|---|---|
| **Phase 11** | Fondations backend | Migration d'extension `telephony_events`, tables `pbx_connectors`/`pbx_domains_tenants`, route `POST /api/telephony/events/ingest` (auth `X-Connector-Token`), routes `/api/telephony/kpis/*` et `/api/telephony/active-calls` (snapshot initial), route settings CRUD `pbx_connectors`, `config_state.telephony_configured` dans `tenant_features()` |
| **Phase 11bis** | Infra WebSocket | Ajout `flask-socketio`, worker Gunicorn `eventlet`/`gevent`, Redis en *message queue* Socket.IO, namespace `/telephony` avec auth JWT + *room* par tenant, diffusion des événements depuis la route d'ingestion |
| **Phase 12** | Connecteur FusionPBX (ESL) | **Fait** (voir §8) — **Un seul** process Docker autonome (`Core Connector`), `ESLAdapter` (port 8021, `CHANNEL_*` + `mod_callcenter`), `Normalizer`, résilience (reconnexion, backoff), healthcheck. Connecteur **tenant-scopé** (§8.4), géré par l'admin de tenant dans `Paramètres > Intégrations > Téléphonie` (statut live + bouton Sync temps réel via Redis). |
| **Phase 13** | Config relocalisée + Supervision frontend (WebSocket) | **Fait** (voir §8.6) — config déplacée de l'onglet Paramètres autonome vers un panneau "Configurer" inline sous `Paramètres > Intégrations` ; nouvel onglet `Supervision > Téléphonie` (KPIs, appels en cours temps réel, files, grille d'état des agents via `CC-Agent-Status`/`GET /agents/status`) |
| **Phase 14** | Webhook CDR + Rapports | **Fait** (voir §8.6) — `POST /telephony/cdr/ingest/<token>` (jeton par connecteur, canal complémentaire à l'ESL live, alimenté par FusionPBX `mod_json_cdr`), onglet `Rapports > Téléphonie` (historique paginé/filtrable + export CSV, enregistrements + export ZIP) |
| **Phase 15** | Connecteur Asterisk (AMI) | Non démarré — `AMIAdapter` ajouté au **même** process connecteur (pas un second déploiement), orchestré en parallèle de `ESLAdapter` par le `Core Connector` — même contrat `PBXAdapter`, aucun changement API/frontend attendu, validation de l'architecture Adapter |

> ⚠️ **Architecture du connecteur (précision importante)** : il n'y a qu'**un seul process/service connecteur** dans PERMATEL (`Core Connector`, Phase 12.1), quel que soit le nombre de PBX physiques (`pbx_connectors`) ou de types de PBX (ESL, AMI, TSAPI...) à couvrir. Ce process unique orchestre **plusieurs `PBXAdapter` concurrents en son sein** (un par ligne `pbx_connectors`), pas un process par PBX/adapter. C'est pour cette raison que `TELEPHONY_CONNECTOR_TOKEN` (§ ingestion, Phase 11) est un jeton **global unique** et non un jeton par connecteur : toutes les requêtes d'ingestion proviennent du même process quel que soit le PBX/tenant d'origine.

---

## 5. Hors périmètre (inchangé du CDC)

- Stockage physique des enregistrements (lien seulement).
- TSAPI (Avaya/Genesys) — prévu en interface, non développé.

---

## 6. Prochaines étapes

1. Validation de ce plan (fait — décisions §2 actées).
2. Détail des exigences fonctionnelles module par module (format EF-XXX-NN),
   en particulier le contrat `PBXAdapter` et le format de normalisation
   commun ESL/AMI.
3. Détail des exigences non fonctionnelles (dimensionnement du process
   connecteur, stratégie de reprise après incident PBX prolongé).
4. ~~Valider en test de charge l'impact du passage Gunicorn sync → eventlet~~
   — **fait, voir §7.**
5. Démarrage effectif : **Phase 11** (fondations backend) — **fait**, voir §7.
   Phase 11bis (infra WebSocket : `flask-socketio`, worker `eventlet`,
   namespace `/telephony`) — **fait**, voir §7. Suite : Phase 12 (connecteur
   FusionPBX/ESL réel, accès de test disponible).

---

## 7. Test de charge — passage Gunicorn sync → eventlet (Phase 11bis)

**Méthode** : stack Docker réelle (`docker compose up db redis backend`,
Python 3.11, Gunicorn 3 workers `eventlet`), pas de simulation — seul moyen
valable vu que Gunicorn ne tourne pas nativement sous Windows. Client de
charge asyncio (`aiohttp` + `python-socketio[asyncio_client]`) séparé, hors
conteneur.

### 7.1 Bugs réels détectés et corrigés

| # | Constat | Cause | Correction |
|---|---|---|---|
| 1 | `AttributeError: property 'session' of 'RequestContext' object has no setter` — **toute** connexion au namespace `/telephony` échouait (`ConnectionError: One or more namespaces failed to connect`) | Incompatibilité `flask-socketio==5.4.1` / `Flask==3.1.3` (Flask 3.1 a rendu `RequestContext.session` en propriété non-settable ; flask-socketio 5.4.1 essaie de l'assigner directement) | Montée de version : `flask-socketio==5.6.1` (corrige l'incompatibilité) |
| 2 | Risque latent (non confirmé comme cause du bug observé, mais réel et corrigé par prudence) : psycopg2 (extension C, appels réseau via libpq) n'est **pas** rendu coopératif par le monkey-patch automatique du worker Gunicorn `eventlet` (qui ne patche que le module `socket` Python) | Limitation connue d'eventlet + psycopg2 | `eventlet.support.psycopg2_patcher.make_psycopg_green()` appelé explicitement en tête de `app/__init__.py`, conditionné à `eventlet.patcher.is_monkey_patched("socket")` (no-op en dev/tests, mode `threading`) |
| 3 | Engine.IO tente d'importer son driver `eventlet` **dès la construction de l'objet `SocketIO()`**, même sans forcer `async_mode='eventlet'` — cet import déclenche `eventlet.patcher.inject()` sur le module `threading`, qui plante sous Python 3.14 (`AttributeError: module 'eventlet.green.thread' has no attribute 'start_joinable_thread'`) et bloquait la collecte des tests pytest en local (venv Windows Python 3.14) | Eventlet 0.36.1 n'est pas compatible avec les changements internes de `threading` en Python 3.14 ; non bloquant en prod (image Docker figée sur Python 3.11) | Nouveau réglage `SOCKETIO_ASYNC_MODE` (config), défaut `"threading"` (dev/tests), forcé à `"eventlet"` en prod via l'environnement (`docker-compose.yml`) — évite qu'Engine.IO sonde/importe le driver eventlet quand rien n'a pré-patché le process |

### 7.2 Résultats de charge

- **WebSocket seul** (20 connexions concurrentes au namespace `/telephony`,
  sans charge REST) : **20/20 connectées, 0 échec, ~0.3s au total**. La
  gestion des connexions WebSocket sous eventlet est saine.
- **REST seul** (`/health`, 20 requêtes concurrentes) : latences 60-90ms,
  aucune dégradation — confirme que la boucle eventlet gère bien la
  concurrence I/O pure.
- **REST CPU-bound** (`POST /api/auth/login`, hachage PBKDF2-SHA256 à
  600 000 itérations — volontairement coûteux, cf. `models/user.py`) : **un
  seul appel prend déjà ~1.2s** sur les ressources Docker allouées
  (`cpus: 1.5` en compose). En charge concurrente (15-20 requêtes), le temps
  total grimpe à **10-12s**, car ce calcul CPU-bound **bloque tout le thread
  du worker eventlet pendant sa durée** (aucune coopération possible pour du
  code CPU pur, contrairement à de l'I/O) — avec seulement 3 workers, les
  requêtes concurrentes sur la même route se sérialisent par paquets de 3.
  **Ce n'est pas une régression introduite par eventlet** (un worker `sync`
  aurait la même limite physique — 3 workers = 3 hachages en parallèle max) ;
  c'est un comportement inhérent au coût du hachage, à garder en tête pour
  le dimensionnement (`GUNICORN_WORKERS`) si `/auth/login` devait un jour
  subir une charge concurrente significative.
- **Scénario critique validé — survie des WebSocket sous charge REST CPU-bound** :
  20 connexions WebSocket `/telephony` ouvertes et maintenues, puis rafale de
  15 logins concurrents (PBKDF2) lancée en parallèle → rafale REST terminée
  en 12.3s (dégradée comme prévu, 0 échec HTTP), et **les 20 connexions
  WebSocket sont toutes restées connectées (20/20, 0 déconnexion)** pendant
  toute la durée. Le `pingTimeout` par défaut de Socket.IO (20s) laisse
  suffisamment de marge face à la pire latence observée (~12s) : pas de
  déconnexion silencieuse de superviseurs Téléphonie même si une rafale de
  connexions se produit ailleurs dans l'app au même moment.

### 7.3 Conclusion

Le passage `sync` → `eventlet` est **validé pour la production**, sous
réserve des deux fixes ci-dessus (`flask-socketio>=5.6.1`,
`SOCKETIO_ASYNC_MODE`/patch psycopg2 déjà en place dans le code). Point de
vigilance conservé (pas bloquant) : si `/api/auth/login` devait être exposé à
une charge concurrente nettement supérieure (>30-40 requêtes simultanées),
revalider la marge face au `pingTimeout` Socket.IO ou envisager d'augmenter
`GUNICORN_WORKERS`.

---

## 8. Phase 12 — Connecteur FusionPBX (ESL)

### 8.1 Bootstrap config + administration (préalable à l'implémentation du connecteur)

> ⚠️ **Superseded par §8.4** : cette section décrit l'implémentation
> initiale (connecteur global partagé entre tenants, UI admin séparée
> `/pbx-connectors`). Revue le jour même suite à un pivot d'architecture —
> conservée ici pour l'historique, voir §8.4 pour l'état actuel.

Avant d'écrire le connecteur lui-même, deux lacunes ont été comblées (elles
n'étaient pas explicitement dans le phasage initial, mais bloquaient toute
implémentation réelle) :

- **`GET /api/telephony/connectors/config`** (backend, `routes/telephony.py`) :
  auth par jeton technique partagé (même trust boundary que l'ingestion), 
  retourne les `pbx_connectors` actifs avec identifiants déchiffrés + leurs
  rattachements `pbx_domains_tenants`. C'est la source de config du Core
  Connector — pas de fichier de config statique dupliqué, la source de
  vérité reste l'UI admin PERMATEL.
- **UI d'administration globale `/pbx-connectors`** (`PbxConnectorsView.vue`,
  ADMIN uniquement, sur le modèle de `TenantsView.vue`) : CRUD des
  `pbx_connectors` (nom, type, hôte, port, identifiants) + gestion des
  rattachements domaine PBX ↔ tenant ↔ files supervisées.
- **Réglages tenant `Paramètres > Téléphonie`** (`SettingsTelephony.vue`,
  nouvel onglet piloté par `settings_sections.telephony`, déjà exposé par
  `tenant_features()` depuis la Phase 11 mais jamais consommé côté
  frontend) : lecture des rattachements du tenant + édition des files
  d'attente supervisées (`PUT /api/telephony/settings/<id>/queues`). Le
  bouton « Configurer » de la tuile Téléphonie (Réglages > Intégrations),
  jusque-là désactivé sans action, y renvoie désormais.

### 8.2 Core Connector — `connector/` (nouveau répertoire, process Docker séparé)

Bibliothèque ESL retenue : **greenswitch** (implémentation gevent, pas
asyncio — décision actée lors du "attaquons le point 12", en alternative à
`python-ESL` officiel qui nécessite de compiler les bindings C depuis les
sources FreeSWITCH). Le process entier est donc gevent, monkey-patché dès la
première ligne de `core_connector.py` (avant tout import réseau) — modèle
similaire au worker Gunicorn `eventlet` du backend (§7), mais processus
indépendant.

| Fichier | Rôle |
|---|---|
| `connector/core_connector.py` | Entrypoint. Boucle de réconciliation : `GET /connectors/config` au démarrage puis toutes les `CONFIG_REFRESH_SECONDS` (défaut 60s), démarre/arrête une greenlet `PBXAdapter` par connecteur actif vu/disparu, envoie le heartbeat de statut (`POST /connectors/status`) à chaque cycle. Un seul process (jamais un process par PBX). Abonné en tâche de fond au canal Redis `telephony:sync` (§8.4) pour appliquer un Sync quasi instantanément. |
| `connector/adapters/base.py` | Contrat `PBXAdapter` (`run()`/`stop()`/`force_reconnect()`/`is_connected`) — future implémentation AMI (Phase 14) s'y conforme. |
| `connector/adapters/esl_adapter.py` | `ESLAdapter` : connexion ESL inbound (greenswitch), souscription `CHANNEL_CREATE/CHANNEL_PROGRESS_MEDIA/CHANNEL_ANSWER/CHANNEL_HANGUP_COMPLETE` + `CUSTOM callcenter::info` (mod_callcenter), reconnexion avec backoff exponentiel borné sur déconnexion, filtrage des événements de file par `queue_ids` supervisées (tenant), `force_reconnect()` (Sync). |
| `connector/normalizer.py` | Fonctions pures FreeSWITCH → format d'ingestion PERMATEL (`event_type`/`call_status` — vocabulaire documenté dans `models/telephony_event.py`). Testé isolément (`connector/tests/test_normalizer.py`, 10 tests). |
| `connector/ingest_client.py` | POST vers `/api/telephony/events/ingest` + GET config bootstrap, via `requests` (rendu coopératif par le monkey-patch gevent, aucun adaptateur dédié requis contrairement à psycopg2 côté backend). |
| `connector/Dockerfile` | Multi-stage, non-root, `tini` PID 1. Pas de serveur HTTP dans ce process : healthcheck via fichier heartbeat rafraîchi à chaque cycle de réconciliation. |

Intégré à `docker-compose.yml` en service **opt-in** (`profiles: [telephony]`)
— démarré uniquement via `docker compose --profile telephony up -d`, pour ne
pas forcer son exécution sur les déploiements sans téléphonie configurée.

### 8.3 Ce qui reste à valider (accès FusionPBX réel disponible)

Le mapping des causes de raccrochage et surtout des en-têtes `CC-*` de
mod_callcenter (`CC-Action`, `CC-Queue`, `CC-Member-Uuid`, `CC-Agent`) a été
écrit à partir de la documentation FreeSWITCH/FusionPBX, **pas encore
confronté à un flux d'événements réel**. Avant mise en production :

1. Démarrer le connecteur (`docker compose --profile telephony up -d
   --build`) contre le FusionPBX de test, avec au moins un connecteur PBX
   + un domaine rattaché configurés via `Paramètres > Téléphonie`.
2. Passer un appel de test et comparer les événements réellement reçus
   (logs `connector.esl`) aux en-têtes supposés dans `normalizer.py` —
   ajuster `CC-*` et les causes de raccrochage si l'écart le justifie.
3. Vérifier la valeur réelle de `variable_domain_name` sur un environnement
   FusionPBX multi-domaine (résolution du tenant à l'ingestion en dépend).
4. Confirmer le comportement de reconnexion (redémarrage du service
   `mod_event_socket` côté FusionPBX) sans perte prolongée d'événements.
5. Vérifier le bouton Sync (`Paramètres > Téléphonie`) : reconnexion
   effective en quelques secondes avec Redis actif, puis re-tester sans
   Redis pour valider le filet de secours (`sync_requested_at`, appliqué au
   plus tard au prochain sondage périodique).

---

### 8.4 Pivot — connecteur tenant-scopé + Sync temps réel

Décision revue le jour de l'implémentation de la Phase 12 : `PbxConnector`
n'est **plus une ressource globale** partagée entre tenants (§8.1, §2.3
initial). Chaque tenant possède et configure désormais **son propre**
connecteur PBX, exactement comme `SmtpSetting`/`ImapSetting` :

- **Modèle** : `pbx_connectors.tenant_id` (NOT NULL). `pbx_domains_tenants`
  renommée `pbx_connector_domains`, perd sa colonne `tenant_id` propre
  (héritée du connecteur parent). Migration `e7f8a9b0c1d2` — DROP/CREATE
  plutôt qu'ALTER (garde-fou : abandonne si des lignes existent déjà,
  aucune perte de données possible puisque la Phase 12 venait d'être
  mergée sans usage réel).
- **CRUD** : déplacé de `@role_required(ADMIN)` (global) vers
  `@tenant_admin_required` (propre tenant), même niveau de confiance que
  les autres réglages d'intégration.
- **UI** : `/pbx-connectors` (page globale admin) supprimée, fusionnée dans
  `Paramètres > Téléphonie` (`SettingsTelephony.vue`) — gérée par l'admin
  de tenant, visible ssi `channel_telephonie` actif pour ce tenant.
  Sous-ligne dépliable par connecteur (statut live de l'adapter : connecté/
  déconnecté, dernière activité, dernière erreur) + gestion des domaines/
  files supervisées + bouton **Sync**.
- **Sync (reconnexion forcée) quasi temps réel** : `POST
  /connectors/<id>/sync` bump `sync_requested_at` (filet de secours durable,
  repris au prochain sondage périodique du connecteur) **et** publie sur
  Redis (canal `telephony:sync`, Redis déjà présent dans la stack). Le Core
  Connector maintient une greenlet abonnée en tâche de fond
  (`_SyncListener`) qui appelle `adapter.force_reconnect()` dès réception —
  effectif en quelques secondes, sans attendre `CONFIG_REFRESH_SECONDS`
  (60s par défaut). Fonctionne en dégradé (filet de secours seul) si Redis
  est absent/injoignable — décision explicite de ne pas rendre Redis
  obligatoire pour ce cas d'usage non-critique.
- **Heartbeat de statut** : `POST /connectors/status`, appelé par le Core
  Connector à chaque cycle de réconciliation, alimente
  `is_connected`/`last_seen_at`/`last_error` sur `PbxConnector` — c'est ce
  qui peuple la sous-ligne "adapter" de l'UI.

---

### 8.5 Raccordement au FusionPBX réel — deux bugs de production détectés et corrigés

Connecteur mis en service contre `fusion.cloud228.com` (FusionPBX 1.10.8,
production réelle, ~2,7M sessions depuis 108 jours d'uptime). Deux
dysfonctionnements distincts sont apparus, chacun corrigé et validé avant
d'être considérés résolus (pas seulement en test unitaire) :

**a) Deadlock du connecteur sur reconnexion concurrente**

Symptôme en production : deux lignes `Reconnexion forcée (Sync)` loggées
sans qu'aucune ligne `Connexion à ... (ESL)` n'apparaisse jamais entre les
deux — le connecteur restait bloqué indéfiniment après un clic sur "Sync".

Cause : `ESLAdapter.force_reconnect()`/`stop()` appelaient
`ESLProtocol.stop()` (greenswitch) **directement depuis la greenlet
appelante** (boucle de réconciliation ou listener Redis), alors que la
propre greenlet `run()` de l'adapter, réveillée par le même signal,
tentait **aussi** d'appeler `stop()` dans son `finally`. `ESLProtocol.stop()`
envoie `'exit'` et attend la réponse via `AsyncResult.get()` **sans
timeout** — un double appel concurrent laisse l'un des deux bloqué pour
toujours dès que l'unique réponse `'exit'` reçue ne résout qu'un seul des
deux `AsyncResult` en attente. Le listener Redis traitant les messages
séquentiellement, un seul blocage suffisait à rendre tous les Sync suivants
silencieusement inopérants.

Correction : `force_reconnect()`/`stop()` ne touchent plus jamais `_esl`
directement — ils se contentent de réveiller l'event. Seule la greenlet
`run()` (jamais concurrente avec elle-même) ferme la connexion, via
`_hard_disconnect()` qui clôt directement la socket (non bloquant) plutôt
que de négocier un arrêt propre avec `'exit'`. 5 tests de régression
(`connector/tests/test_esl_adapter_reconnect.py`), dont un reproduisant
l'appel concurrent avec un `gevent.Timeout` explicite.

**b) Panneau live bloqué en "Déconnecté" — route Nginx manquante**

Symptôme : le panneau "Événements ESL en temps réel" restait en
"Déconnecté" en permanence, aucun événement ne remontait, malgré un
connecteur ESL fonctionnel et des événements bien ingérés côté backend.

Cause : le chemin Engine.IO par défaut (`/socket.io/`) n'était proxifié par
**aucune** `location` Nginx du frontend (seuls `/api` et `/uploads` le
sont) — le handshake WebSocket tombait dans le fallback SPA et recevait
`index.html` au lieu de jamais joindre le backend. Même en le routant,
`proxy_set_header Upgrade`/`Connection` (requis pour que Nginx propage le
handshake d'upgrade WebSocket) était absent de la location `/api/`.

Correction : `socketio.init_app(..., path="/api/socket.io")` côté backend
et `useTelephonySocket.js` aligné sur le même chemin (reste same-origin
sous `/api`, cohérent avec le reste de l'app — pas de nouvelle `location`
Nginx dédiée). Ajout d'un `map $http_upgrade $connection_upgrade` (upgrade
uniquement si le client le demande réellement, pour ne pas casser le
keep-alive des requêtes REST classiques sur la même location) +
`proxy_set_header Upgrade`/`Connection` sur `/api/`.

Validé de bout en bout contre une vraie stack Docker (nginx + Gunicorn
eventlet + Redis), pas seulement au niveau unitaire : connexion WebSocket
via le proxy Nginx exactement comme le ferait un navigateur, création d'un
connecteur + domaine via l'API, ingestion d'un événement, réception
confirmée côté client en moins de 2 secondes.

### 8.6 Phase 13/14 — Relocalisation config, Supervision temps réel, webhook CDR + Rapports

**Phase 13 (config + supervision).** La configuration Téléphonie a quitté
l'onglet `Paramètres` autonome pour un panneau "Configurer" inline sous
`Paramètres > Intégrations` — le bouton s'active dès que `channel_telephonie`
est actif sur le tenant, **indépendamment** d'un connecteur déjà configuré
(contrairement à l'onglet `Supervision > Téléphonie`, qui exige en plus
`telephony_configured` : un tableau de bord sans donnée derrière n'a pas
d'utilité). Le nouvel onglet `Supervision > Téléphonie` affiche des KPIs du
jour, les appels en cours (temps réel via le namespace WebSocket existant),
les files d'attente, et une grille d'état des agents. Cette dernière
s'appuie sur une donnée réellement nouvelle : le connecteur capte désormais
le header FreeSWITCH `CC-Agent-Status` (`mod_callcenter`, jusque-là ignoré),
et `GET /telephony/agents/status` normalise ce statut brut en présence
disponible/pause/hors-ligne (défaut hors-ligne si absent/inconnu — jamais
fabriqué). La charge affichée par agent est un compte d'appels traités
relatif au plus sollicité, pas un taux d'occupation (aucune durée continue
disponible/occupée n'est suivie aujourd'hui).

**Phase 14 (webhook CDR + Rapports).** FusionPBX (`mod_json_cdr`) POSTe un
résumé JSON à la fin de chaque appel vers `POST /telephony/cdr/ingest/<token>`
— canal complémentaire à l'ESL live (jamais d'événement "en cours", un
résumé arrivé après coup), authentifié par un jeton **par connecteur**
(généré à la création, régénérable, stocké chiffré+redisplayable via
"Copier le token" — décision produit délibérée, pas un secret à usage
unique façon jeton d'invitation), avec restriction IP optionnelle
(`authorized_ip`). Un CDR produit jusqu'à 3 `TelephonyEvent` rétrodatés
(ringing/answered/terminal), pour rester compatible sans aucune modification
avec les routes KPI existantes (toutes basées sur "grouper par `call_uuid`,
trouver l'événement terminal + l'événement answered"). Nouvel onglet
`Rapports > Téléphonie` (visible ssi canal actif, gating identique au bouton
"Configurer" — l'historique reste consultable même sans connecteur actif) :
historique des appels paginé/filtrable avec export CSV, et section
Enregistrements avec écoute/téléchargement (proxy backend, uniquement si
`recording_url` est une URL http(s) réellement exploitable — sinon signalé
indisponible plutôt qu'un lien cassé, cf. limitation ci-dessous) et export
groupé en ZIP (`_indisponibles.txt` listant ce qui a été exclu plutôt que
silencieusement absent de l'archive).

> ⚠️ **Limitation connue, non résolue** : `TelephonyEvent.recording_url`
> reflète ce que FreeSWITCH rapporte (`variable_record_file_path`), qui est
> le plus souvent un **chemin de fichier local sur le serveur PBX**, pas une
> URL accessible depuis PERMATEL. Écoute/téléchargement ne fonctionnent que
> si FusionPBX est configuré pour exposer ces fichiers via une URL http(s) —
> non confirmé à ce jour (aucun appel de test avec enregistrement actif),
> à valider avec un enregistrement réel.

**Six correctifs successifs sur le webhook CDR, chacun découvert et validé
contre du vrai trafic FusionPBX en production** (pas en local, pas en
supposant — le format réel a divergé de l'hypothèse initiale à chaque
round) :

1. **`request.get_json()` refusait de parser sans `force=True`** — première
   itération, corps réellement JSON mais Content-Type non reconnu par défaut.
2. **Le corps est en réalité `application/x-www-form-urlencoded`**
   (`cdr=<json>`, comportement par défaut de libcurl `POSTFIELDS`), pas du
   JSON brut malgré ce que suggérait le premier correctif.
3. **`&`/`=` littéraux dans le JSON (~15-80 Ko, dump complet des variables
   de canal) tronquaient la valeur** via le parseur de formulaire de
   Werkzeug (qui les interprète à tort comme des séparateurs clé=valeur).
   Remplacé par une extraction directe sur le corps brut (recherche du
   premier `{` à la dernière `}`), immunisée à ces caractères puisqu'aucun
   découpage clé=valeur n'est tenté.
4. **Préservation du `+` des numéros E.164** : `unquote` (RFC 3986, ne
   touche pas aux `+`) tenté avant `unquote_plus` (RFC 1866, `+` = espace)
   — sinon un `+` non échappé par l'émetteur devient un espace, corruption
   silencieuse (JSON toujours valide, juste une donnée fausse).
5. **Caractères de contrôle bruts non échappés** (probablement issus
   d'en-têtes SIP multi-lignes) rejetés par `json.loads` strict par défaut
   — `strict=False`.
6. **Root cause finale**, identifiée grâce à un diagnostic précis
   (position/ligne/colonne de la `JSONDecodeError`, ajouté après l'échec du
   correctif 5) : FusionPBX interpole certains en-têtes SIP bruts
   (`sip_full_from`/`sip_full_to`, ex. `"Nom Affiché" <sip:...>;tag=...`)
   directement dans le JSON **sans échapper les guillemets internes** du
   nom d'affichage — JSON syntaxiquement invalide à la source, qu'aucun
   décodage/encodage ne peut réparer. `_repair_unescaped_quotes()` (dans
   `app/routes/telephony.py`) répare heuristiquement en dernier recours :
   repère la vraie fin de chaque valeur-chaîne (le prochain `"` suivi de
   `,`/`}`/`]`) et échappe tout guillemet interne rencontré avant ce point —
   sans effet sur les champs déjà bien formés.

Chaque correctif a été écrit avec un test de non-régression reproduisant le
fragment réel exact observé en production (pas un cas synthétique
générique) — 21 tests dédiés au webhook CDR dans `TestCdrIngest` et classes
adjacentes de `backend/tests/test_telephony.py`.

**Trace diagnostique** (`TELEPHONY_CDR_TRACE=true`, désactivée par défaut,
voir `.env.example`) : journalise l'inventaire complet des variables reçues
(nom, type, aperçu de valeur) + écrit le payload intégral dans
`/tmp/cdr_trace_last.json`. Un CDR complet peut peser plusieurs dizaines de
Ko : à activer ponctuellement, pas en fonctionnement normal.

### 8.7 Enseignements de deux traces CDR réelles (appel direct + appel en file d'attente)

Deux traces complètes (`TELEPHONY_CDR_TRACE=true`) — un appel sortant direct
via passerelle SIP, un appel entrant routé en file d'attente `mod_callcenter`
— ont permis de confirmer ou corriger plusieurs hypothèses initiales :

- **`caller_id_number`/`destination_number` n'existent pas systématiquement
  sous `variables`** — absents sur l'appel direct, présents sur l'appel en
  file d'attente (visiblement posés explicitement par le dialplan XML dans
  ce second cas, `app_log` en atteste). La donnée fiable, présente dans les
  deux cas, vit sous `payload.callflow[0].caller_profile.{caller_id_number,
  destination_number}` — c'est désormais la source primaire, avec repli sur
  `variables.sip_from_user`/`sip_to_user` si `callflow` est absent.
- **`cc_queue` confirmé fiable** : format `"<extension>@<domaine>"` (ex.
  `8004@africallpbx.fusion.cloud228.com`), même convention que le header ESL
  `CC-Queue` — aucun changement nécessaire pour `queue_id`.
- **`cc_agent` confirmé être un UUID interne FusionPBX**
  (`call_center_agents.call_center_agent_uuid`), **pas** un login/une
  extension exploitable pour matcher un `User` PERMATEL via `agent_login`.
  L'extension réelle de l'agent qui décroche (`"22101005"` dans la trace)
  vit sous `payload.callflow[0].caller_profile.originatee
  .originatee_caller_profiles[0].destination_number` — le leg vers lequel
  `mod_callcenter` a bridgé l'appel. Extraction corrigée en conséquence,
  gardée derrière la présence de `cc_queue` (jamais fabriquée hors contexte
  de file d'attente réel, même si un profil `originatee` existe pour une
  autre raison — transfert, etc.).
- **`recording_url` toujours non confirmé** : aucune des deux traces ne
  portait d'enregistrement actif (`record_file_path` absent des deux) — la
  limitation ci-dessus reste entièrement ouverte.
- **Chaque leg d'un appel bridgé génère son propre CDR** (observé sur la
  trace directe : `variables.uuid` ≠ `variables.call_uuid`, ce dernier
  pointant vers l'autre leg) — caractéristique déjà partagée avec
  l'ingestion ESL (chaque canal produit ses propres événements), pas une
  régression introduite par le webhook CDR. Non traité pour l'instant
  (chaque leg reste un `call_uuid` PERMATEL distinct).

Deux correctifs supplémentaires appliqués suite à ces traces (extraction
caller/callee, extraction agent_login), chacun avec un test de
non-régression reproduisant la structure réelle exacte.

### 8.8 Présence agent (ESL live) — `agent-status-change` et annuaire uuid → extension

Test réel dédié (29/07, changement de statut manuel Available → Logged Out
→ Available sur une extension) via l'instrumentation ajoutée à
`_on_callcenter_info` (journalisation inconditionnelle des en-têtes bruts).
Deux constats, différents des hypothèses initiales de la Phase 13 :

- **`agent-state-change` (l'action supposée jusqu'ici) ne s'est jamais
  produite.** La vraie action de transition manuelle est
  **`agent-status-change`** (`Event-Calling-Function: cc_agent_update`),
  accompagnée d'une variante passive **`agent-status-get`**
  (`cc_agent_get`, ex. rafraîchissement d'un écran admin) — pas une
  transition, ignorée.
- **Ni l'un ni l'autre ne porte de contexte de canal** : aucun `Unique-ID`,
  aucun `variable_domain_name`. Logique — contrairement à `queue-enter`
  (lié à un appel actif dont le dialplan a positionné ces variables), un
  changement de statut agent est une action administrative sans canal
  associé. `CC-Agent` y est en plus confirmé être un UUID interne
  FusionPBX (cohérent avec le `cc_agent` déjà vu côté CDR, §8.7), pas une
  extension exploitable pour `agent_login`.

**Solution retenue** : un annuaire `uuid FreeSWITCH → {domaine, extension}`
construit via une requête ESL synchrone `api callcenter_config agent list`
(jusque-là le connecteur ne faisait que s'abonner à des événements, jamais
de requête synchrone). **Correction post-premier-test (29/07)** :
initialement scopée par domaine+file (`agent list <queue>@<domaine>`) dans
l'idée de récupérer le domaine "gratuitement" — mais confirmé en
production que ce filtre **n'existe pas** : la commande est acceptée sans
erreur mais ne retourne jamais aucune ligne d'agent (`+OK` brut), quelle
que soit la file passée. mod_callcenter ne documente `agent list` que
filtrable par nom d'agent, jamais par file. Corrigé en un appel **global,
sans scope**, pour l'unique domaine configuré sur le connecteur (limitation
assumée : plusieurs domaines sur un même connecteur ne sont pas supportés
ici, `agent list` global ne permettant pas de savoir à quel domaine chaque
agent appartient — journalisé plutôt que deviné). Rafraîchi à la connexion
puis toutes les `AGENT_DIRECTORY_REFRESH_SECONDS` (300s par défaut).
`_on_callcenter_info` route `agent-status-change`/`agent-status-get` vers
ce chemin avant toute tentative de lecture de `variable_domain_name`.

**Format des colonnes CONFIRMÉ contre une sortie réelle (3e test, 29/07)** :
`name|instance_id|uuid|type|contact|status|state|max_no_answer|
wrap_up_time|reject_delay_time|busy_delay_time|no_answer_delay_time|
last_bridge_start|last_bridge_end|last_offered_call|last_status_change|
no_answer_count|calls_answered|talk_time|ready_time|external_calls_count`
— différent de la convention initialement supposée (`agent_name|agent_type|
contact|status|state|...`). Point notable : la colonne `name` porte en
réalité l'uuid FusionPBX de l'agent (même valeur que `CC-Agent`), pas un
nom lisible ; la colonne `uuid` elle-même est vide sur toutes les lignes
observées. Trois bugs corrigés suite à ce test :

- **La 1ère ligne de la réponse est l'en-tête de colonnes**
  (`name|instance_id|uuid|...`), pas une ligne d'agent — elle était
  auparavant traitée comme une ligne "ininterprétable" (uuid/extension
  absents). Filtrée désormais par son préfixe (`_AGENT_LIST_HEADER_PREFIX`).
- **L'extraction de l'extension matchait le mauvais nombre** : le motif
  générique `\d{2,}` capturait la première séquence numérique du champ
  `contact` (ex. `20` dans `call_timeout=20`), bien avant la vraie
  extension. Corrigé par un ancrage strict sur le motif `user/<extension>@
  <domaine>` (`_EXTENSION_RE`), qui extrait aussi le domaine du contact.
- **`agent list` étant global, il renvoie aussi les agents des AUTRES
  domaines hébergés sur le même FreeSWITCH** (confirmé : des agents du
  domaine `pge.fusion.cloud228.com` apparaissaient aux côtés de ceux du
  domaine configuré `africallpbx.fusion.cloud228.com`). Le domaine extrait
  du `contact` de chaque ligne est désormais comparé au domaine configuré
  du connecteur ; les lignes d'un autre domaine sont ignorées silencieusement.

**Durcissement suite aux deux premiers tests réels (29/07)** : le 1er test
a montré la saisie initiale des 5 files du domaine dans le combobox
"Entrée pour ajouter" produisant UNE entrée `"8001, 8002, 8003, 8004,
8005"` au lieu de 5 entrées distinctes. Le 2e test (une fois cette saisie
scindée) a ensuite révélé le vrai problème ci-dessus (`agent list` non
filtrable par file, jamais lié à la saisie multi-files elle-même). Trois
corrections :

- **Formulaire domaine (`Paramètres > Intégrations > Téléphonie`)** :
  le combobox est remplacé par des champs Identifiant/Alias ajoutables un
  par un ("Ajouter une file") — corrige structurellement la saisie
  multi-files en une entrée (plus de virgules à scinder par l'utilisateur).
  `queue_ids` devient une liste de `{"id", "alias"}` ; l'alias est un
  libellé d'affichage PERMATEL, jamais transmis à FreeSWITCH. Reste utile
  pour le filtrage `queue-enter` (`_on_callcenter_info`), même si l'annuaire
  agents n'est plus scopé par file. Compat ancien format (chaîne nue)
  conservée côté backend (`_normalize_queue_ids`) et connecteur pour les
  domaines pas encore ré-enregistrés.
- **Roster agents faisant autorité côté PERMATEL** : `GET
  /telephony/connectors/config` expose désormais `known_agent_logins`
  (les `User.agent_login` peuplés pour le tenant, actifs, adhésion tenant
  active) ; l'annuaire construit par `ESLAdapter` ne retient une extension
  résolue via FusionPBX que si elle y figure — jamais d'attribution de
  présence à une extension PBX sans agent PERMATEL réel derrière. Rafraîchi
  à chaque sondage périodique sans redémarrer l'adapter.
- **`UsersView.vue`** : le champ "Extension" éditait `station_extension`
  (jamais utilisé côté téléphonie) — remplacé par **"Login Agent CC"**,
  qui édite directement `agent_login`, le vrai champ de corrélation avec
  `TelephonyEvent.agent_login`.
