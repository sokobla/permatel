# Cahier des Charges — Module Téléphonie PERMATEL

**Version** : 1.0
**Date** : 27 juillet 2026
**Statut** : En cours de rédaction — validation progressive
**Plan d'implémentation associé** : [`TELEPHONIE_INTEGRATION_PLAN.md`](../../TELEPHONIE_INTEGRATION_PLAN.md)

---

## 1. Contexte et objectifs

PERMATEL est une plateforme SaaS multi-tenant existante de gestion d'opérations pour agents de sécurité (anomalies, commandes, planning, demandes administratives), construite sur une stack Flask/SQLAlchemy/PostgreSQL côté backend et Vue 3/Vuetify/Pinia côté frontend, avec isolation logique par `tenant_id` sur toutes les tables métier.

Ce document cadre l'extension **Module Téléphonie**, dont l'objectif est de **collecter, standardiser et historiser** les événements de téléphonie des agents PERMATEL, afin d'alimenter une supervision temps réel, une analyse de performance agent et du reporting/BI. Un flag `channel_telephonie` existe déjà par tenant dans le modèle de données, actuellement listé comme intégration inactive (purement cosmétique — gate seulement la visibilité d'une tuile dans les réglages), et sera activé fonctionnellement par ce module.

> ⚠️ Une table `telephony_events` existe déjà dans PERMATEL (schéma initial), mais à l'état **dormant** : posée mais non alimentée, avec un schéma plus étroit que le besoin de ce module. Voir `TELEPHONIE_INTEGRATION_PLAN.md` §1 pour l'écart exact et la stratégie d'extension (migration d'ALTER, pas de recréation).

## 2. Périmètre fonctionnel

### 2.1 Sources et types d'événements

- Sources PBX : **FusionPBX** en phase 1, **Asterisk** en phase 2, avec une architecture standardisée pour couvrir plusieurs types de PBX de façon extensible.
- Événements d'appel : entrant/sortant, durée, statut (répondu, manqué, abandonné, échec technique, mis en attente).
- Statuts agents : basés sur les statuts natifs FusionPBX (disponible, en pause, en communication, post-appel/wrap-up, déconnecté), standardisés pour rester compatibles avec d'autres PBX.
- Enregistrement : seul un **lien** vers le fichier audio est conservé, aucun stockage physique côté PERMATEL.

### 2.2 Mode de collecte

FusionPBX n'expose pas de vrais webhooks HTTP pour les événements d'appel : la communication événementielle temps réel repose sur l'**Event Socket Layer (ESL)** de FreeSWITCH, un socket TCP (port 8021). Le module doit donc agir comme un **client ESL** qui se connecte activement au socket événementiel de chaque PBX, plutôt que d'attendre un push HTTP entrant.

### 2.3 Rattachement aux données PERMATEL existantes

- Chaque événement est rattaché à un agent via le champ `agent_login`, déjà présent dans le modèle `User` (commentaire `# ESL Téléphonie` déjà présent dans le code — champ prévu pour cet usage dès l'origine, jamais exploité).
- Une configuration d'ID de file d'attente FusionPBX est prévue dans les paramètres du module, pour permettre la supervision des files d'attente.
- Un agent peut être rattaché à **plusieurs files d'attente** simultanément.

### 2.4 Usages cibles

- Dashboard temps réel superviseur (vue par file d'attente ET vue par agent individuel).
- Analyse de performance agent.
- Reporting / BI historique.

### 2.5 Rétention

Aucune limite de rétention n'est appliquée aux données de téléphonie historisées.

## 3. Architecture technique du connecteur

### 3.1 Principe général

Le connecteur téléphonie est un **processus séparé et générique**, indépendant du process web Flask, mais colocalisé sur le même serveur pour cette première itération — **premier process long-running du projet** (tout le reste de PERMATEL est requête/réponse Flask ou CLI ponctuel via cron). Il repose sur un pattern **Adapter** afin d'absorber l'hétérogénéité des PBX derrière une interface commune.

| Composant | Rôle |
|---|---|
| Core Connector | Process autonome, orchestre les adapters, gère la résilience et la file de sortie |
| ESLAdapter | Connexion TCP persistante au port 8021 FreeSWITCH/FusionPBX, écoute des événements `CHANNEL_*` et `mod_callcenter` |
| AMIAdapter | Connexion à l'Asterisk Manager Interface (AMI), écoute des événements équivalents (Dial, Hangup, QueueMember...) |
| TSAPIAdapter | Réservé aux futurs PBX propriétaires (Avaya/Genesys via TSAPI), extensibilité prévue dès la conception |
| Interface `PBXAdapter` | Contrat abstrait (`connect()`, `listen()`, `on_event()`, `disconnect()`) implémenté par chaque adapter |
| Normalizer | Transforme l'événement brut spécifique au PBX en événement standardisé PERMATEL |
| Émetteur | Pousse l'événement normalisé vers l'API Flask (`POST /api/telephony/events/ingest`) |

### 3.2 Événements FreeSWITCH pertinents

- `CHANNEL_CREATE` : création d'un nouveau canal, signale le début d'un appel avant sonnerie ou réponse.
- `CHANNEL_PROGRESS_MEDIA` : passage en early media (SDP, 183 Session Progress), typiquement sonnerie ou message de pré-décroché.
- `CHANNEL_ANSWER` : appel décroché.
- `CHANNEL_HANGUP_COMPLETE` : fin d'appel, avec cause de raccroché.
- Événements `mod_callcenter` (`CALLCENTER_QUEUE_ENTER`, `CALLCENTER_AGENT_STATE_CHANGE`) pour la supervision des files d'attente et des statuts agents.

### 3.3 Configuration multi-tenant et multi-PBX

- La configuration du connecteur est lue depuis une **table PostgreSQL exposée par l'API PERMATEL**, permettant un rechargement à chaud sans redéploiement.
- Un même PBX physique peut héberger **plusieurs tenants PERMATEL**. Le routage tenant se fait via le **domaine FusionPBX** (`domain_name`), porté par chaque événement FreeSWITCH.

Modèle de configuration proposé :

**Table `pbx_connectors`** : `id`, `name`, `type` (ESL/AMI/TSAPI — `String`, pas d'enum Postgres figé, cohérent avec la migration `use_varchar_for_enums` déjà appliquée ailleurs sur ce projet pour ce même motif d'extensibilité), `host`, `port`, credentials chiffrés (`EncryptedText`, pattern déjà actif en production sur `Email.subject/body_text/body_html`), `is_active`.

**Table `pbx_domains_tenants`** : `id`, `pbx_connector_id` (FK), `pbx_domain`, `tenant_id` (FK), `queue_ids[]`.

### 3.4 Résilience

- Reconnexion automatique par adapter en cas de perte de socket.
- Backoff exponentiel en cas de panne prolongée du PBX.
- File interne pour absorber les pics sans bloquer le listener — **Redis retenu** (déjà présent dans la stack PERMATEL pour l'anti-brute-force, pattern de fallback gracieux déjà écrit et réutilisable) plutôt qu'une file mémoire perdue au redémarrage.
- Healthcheck exposé par le connecteur pour supervision (Docker/cron) — même traitement que les services `db`/`redis` déjà durcis dans `docker-compose.yml`.
- Logs structurés JSON incluant `pbx_connector_id`, `pbx_domain`, `tenant_id`, `event_type`, `error_code`.

## 4. Modèle de données côté PERMATEL

### 4.1 Table `telephony_events`

Table tenant-scopée, cohérente avec le modèle multi-tenant existant (shared database, shared schema, isolation par `tenant_id`, FK composites) — **table existante à étendre**, pas à recréer (voir `TELEPHONIE_INTEGRATION_PLAN.md` §1).

| Champ | Description |
|---|---|
| `id` | Identifiant PERMATEL |
| `tenant_id` | Tenant propriétaire (FK) |
| `pbx_connector_id` | PBX émetteur (FK) — **nouveau** |
| `pbx_event_id` | Identifiant unique de l'événement côté PBX (ex : `Unique-ID` FreeSWITCH) — recouvre le `call_uuid` déjà présent |
| `event_type` | `CHANNEL_CREATE`, `CHANNEL_PROGRESS_MEDIA`, `CHANNEL_ANSWER`, `CHANNEL_HANGUP_COMPLETE`, etc. — **`String`, pas enum Postgres** (existant à élargir) |
| `call_direction` | `inbound` / `outbound` — **nouveau** |
| `call_status` | `ringing`, `early_media`, `answered`, `missed`, `abandoned`, `technical_failure`, `on_hold`, `ended` — **nouveau** |
| `call_duration` | Durée en secondes (existant : `duration`) |
| `caller` / `callee` | Numéros appelant/appelé (existant : `caller_number` ; `callee` **nouveau**) |
| `agent_login` | Rattachement direct au modèle `User` — **nouveau**, complète le `user_session_id` existant (session active optionnelle) |
| `queue_id` | File d'attente concernée — **nouveau** |
| `recording_url` | Lien vers l'enregistrement (pas de stockage physique) — **nouveau** |
| `raw_payload` | JSONB, événement brut normalisé, conservé sans limite de rétention — **nouveau** |

### 4.2 Endpoints API

- `POST /api/telephony/events/ingest` : ingestion depuis le connecteur, authentification par clé technique dédiée (`X-Connector-Token`), résolution `tenant_id` via `pbx_domain`.
- `GET /api/telephony/kpis/summary?from=&to=` : temps moyen de réponse, taux de décroché, volumes.
- `GET /api/telephony/kpis/queues?from=&to=` : appels par queue, temps d'attente moyen, taux d'abandon.
- `GET /api/telephony/kpis/agents?from=&to=` : temps de conversation, appels traités, distribution des statuts par agent.
- `GET /api/telephony/active-calls` : appels en cours (état initial au chargement de la page — voir §6.3).
- Endpoints filtrés par `tenant_id` via les décorateurs `@tenant_required`/`@tenant_admin_required` déjà en place dans PERMATEL.

## 5. Format standard des données (payload d'ingestion)

Structure commune, quel que soit le PBX source :

```json
{
  "event_type": "CHANNEL_CREATE",
  "pbx_type": "FUSIONPBX",
  "pbx_domain": "client-a.permatel.local",
  "tenant_id": "<uuid-tenant>",
  "call": {
    "id": "uuid-esl-ou-equivalent",
    "direction": "inbound",
    "caller": "0612345678",
    "callee": "0522456789",
    "created_at": "2026-07-27T13:17:00Z",
    "status": "ringing",
    "is_progress_media": false
  },
  "agent": {
    "login": "agent01",
    "state": "available"
  },
  "queue": {
    "id": "queue-support",
    "name": "Support"
  }
}
```

Des variantes existent pour `CHANNEL_PROGRESS_MEDIA` (statut `early_media`), `CHANNEL_ANSWER` (statut `answered`, `agent.state = on_call`) et `CHANNEL_HANGUP_COMPLETE` (statut `ended`, `duration_seconds`, `hangup_cause`, `agent.state = wrap_up`).

## 6. Frontend — Supervision temps réel

### 6.1 Composants Vue

- `SupervisionTelephonieView.vue` : vue principale, charge les KPIs historisés + les appels actifs, injecte les données dans le store. **Réutilise le squelette existant de `SupervisionView.vue`** (pattern de supervision déjà en place pour les sessions utilisateur).
- `TelephonyKpiCards.vue` : cartes KPI (appels en cours, appels en file, agents en ligne, temps moyen de réponse), combinant données courantes et agrégats historisés.
- `ActiveCallsTable.vue` : tableau des appels actifs (queue, agent, caller, statut, durée), filtrable par queue/statut/agent.
- `AgentsGrid.vue` : grille de cartes agents (avatar, login, statut courant, queue principale, charge issue des KPIs historisés).

### 6.2 Store Pinia `useTelephonyStore`

État : `activeCalls` (liste des appels en cours) et `alerts` (file d'événements pour popups/toasts).

Actions principales : `addOrUpdateCall(payload)` (création ou mise à jour d'un appel selon `call.id`), `removeCall(callId)` (retrait à la fin d'appel), `pushAlert(alert)` (notifications UI).

### 6.3 Composable `useTelephonySocket` (WebSocket — conforme au CDC initial)

> ℹ️ Une première itération du plan d'implémentation avait provisoirement
> écarté le WebSocket au profit d'un polling HTTP, l'infrastructure actuelle
> (Gunicorn en workers **sync**, aucune dépendance `flask-socketio`) ne le
> supportant pas nativement. **Décision finale du porteur de projet : WebSocket
> retenu**, conformément à la version initiale de ce CDC. Cela implique un
> changement d'infrastructure explicite (worker Gunicorn `eventlet`/`gevent`,
> Flask-SocketIO, Redis comme *message queue* pour rester compatible
> multi-worker) — voir `TELEPHONIE_INTEGRATION_PLAN.md` §2.1 pour le détail et
> la Phase 11bis dédiée à cette mise à niveau d'infra avant le développement
> fonctionnel du connecteur.

Ouvre la connexion WebSocket (namespace `/telephony`) après authentification
(JWT vérifié à la connexion), rejoint la *room* Socket.IO du tenant actif, et
route chaque message reçu vers le handler correspondant (`CHANNEL_CREATE`,
`CHANNEL_PROGRESS_MEDIA`, `CHANNEL_ANSWER`, `CHANNEL_HANGUP_COMPLETE`), qui
appelle les actions du store Pinia. Un appel `GET /api/telephony/active-calls`
au montage du composant fournit l'état initial (les nouvelles connexions
n'ont pas l'historique des événements déjà émis) ; le WebSocket ne pousse que
les deltas ensuite.

## 7. Articulation temps réel / historisation

Un seul flux d'événements alimente à la fois le suivi courant et l'historisation, garantissant la cohérence entre les deux :

1. Le connecteur normalise l'événement PBX et l'envoie à `POST /api/telephony/events/ingest`.
2. Le backend Flask persiste l'événement dans `telephony_events` (tenant-scopé, `raw_payload` JSONB conservé intégralement).
3. Le backend diffuse le même événement aux clients WebSocket connectés au tenant concerné (namespace `/telephony`, room par `tenant_id`).
4. Le frontend met à jour `activeCalls` en temps réel (store Pinia) tandis que les endpoints `/api/telephony/kpis/*` exposent des agrégats calculés sur `telephony_events` pour les vues Rapports et les cartes KPI.

## 8. Hors périmètre (V1)

- Stockage physique des enregistrements audio (seul le lien est conservé).
- Intégration TSAPI (Avaya/Genesys) — prévue en architecture mais non développée en V1.
- Intégration Asterisk (AMI) — phase 2, après validation FusionPBX.

## 9. Ressources et contraintes

- Développement porté par un développeur unique.
- Le module s'intègre nativement dans la stack existante (Flask/SQLAlchemy/PostgreSQL, Vue 3/Vuetify/Pinia) et respecte le modèle multi-tenant (`tenant_id` obligatoire sur toute nouvelle table métier).

---

## Sources

Cahier des charges initial rédigé à partir d'une revue de la documentation FusionPBX/FreeSWITCH publique (Event Socket Layer, événements `CHANNEL_*` et `mod_callcenter`, restrictions d'accès au socket événementiel) et de projets d'intégration FusionPBX tiers de référence. Les liens de recherche d'origine (signés, à expiration courte) n'ont pas été conservés dans ce document versionné ; se référer à la documentation officielle FusionPBX (`docs.fusionpbx.com`) et FreeSWITCH pour les détails protocolaires.
