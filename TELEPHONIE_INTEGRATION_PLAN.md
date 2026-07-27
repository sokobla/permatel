# PERMATEL — Module Téléphonie : Plan d'intégration

**Statut** : Phase 11 (fondations backend) implémentée et testée (188/188 tests verts). Phase 11bis (infra WebSocket) implémentée et validée en test de charge Docker réel (§7). Phases 12-14 non démarrées.
**Date** : 27 juillet 2026
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
| `pbx_connectors` (nouvelle) | `id`, `name`, `type` (`String` : ESL/AMI/TSAPI), `host`, `port`, identifiants via `EncryptedText`, `is_active`. |
| `pbx_domains_tenants` (nouvelle) | `id`, `pbx_connector_id` (FK), `pbx_domain`, `tenant_id` (FK), `queue_ids`. |

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
| **Phase 12** | Connecteur FusionPBX (ESL) | **Un seul** process Docker autonome (`Core Connector`), `ESLAdapter` (port 8021, `CHANNEL_*` + `mod_callcenter`), `Normalizer`, résilience (reconnexion, backoff, file Redis), healthcheck |
| **Phase 13** | Supervision frontend (WebSocket) | `SupervisionTelephonieView.vue` (calque de `SupervisionView.vue`), `useTelephonySocket` (connexion Socket.IO + fallback reconnect), `TelephonyKpiCards.vue`, `ActiveCallsTable.vue`, `AgentsGrid.vue`, store `useTelephonyStore` |
| **Phase 14** | Connecteur Asterisk (AMI) | `AMIAdapter` ajouté au **même** process connecteur (pas un second déploiement), orchestré en parallèle de `ESLAdapter` par le `Core Connector` — même contrat `PBXAdapter`, aucun changement API/frontend attendu, validation de l'architecture Adapter |

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
