# PERMATEL - Gestion Intégrée de Demandes et Sessions

**Version** : 1.5.0  
**Dernière mise à jour** : 25 juin 2026  
**Statut** : Backend ✅ / Frontend ✅ | **Tests** : 160 ✅

### Changelog v1.5.0 (25 juin 2026)
- 🚀 **Seeding & Import Avancé (CLI)** :
  - `flask seed-prestataires` : Import robuste de prestataires par tenant, création et association automatique des Clients et Sites correspondants avec gestion d'idempotence.
  - `flask seed-agents` : Import d'agents de sécurité depuis fichiers de données Excel (`lists_agents_secu.xlsx`), scission intelligente des Noms/Prénoms, gestion du `code_postal`, affectation en mode `INTERNE` ou à un prestataire externe (`--prestataire-code`), et synchronisation stricte avec la table `contacts` (gestion de la contrainte `NOT NULL` sur l'adresse).
- 🏢 **Modèle AgentSecurite enrichi** : Ajout natif de la colonne `code_postal` (migration Alembic épurée et sécurisée pour la production), prise en compte de bout en bout (API, sérialisation et formulaires).
- 🎨 **Améliorations Frontend & Pagination** : Implémentation complète de la pagination côté serveur sur `AgentView.vue` (alignée sur le design premium de `ContactsView`), correction des filtres dynamiques (statut, qualification/type) et réinitialisation automatique de la pagination au changement de filtres.

### Changelog v1.4.0 (22 juin 2026)
- 🏢 **Multi-tenant complet** :
  - **Super-admin global** (rôle `ADMIN`) : accès à **tous** les tenants ; **admin de tenant** (`tenant_users.membership_role='admin'`) : périmètre limité à son tenant.
  - **Écran de sélection de tenant** (`/select-tenant`) : standard mono-tenant connecté directement, ≥2 tenants ou admin → choix ; **sélecteur de bascule** dans l'app-bar (reset d'état au switch).
  - `tenant_required` v2 (bypass super-admin), `tenant_admin_required`, `GET /api/auth/tenants`.
- ✉️ **Onboarding par invitation** (admin de tenant) : `tenant_invitations` (token hashé, TTL 48h, usage unique) + acceptation publique `/accept-invite` ; gestion du **roster** via `/api/tenant/members` et `/api/tenant/invitations`.
- 🆔 **Bascule identifiant = email** : `username = email` partout (connexion par email ou username).
- 🔀 **Canaux métier par tenant** (`channel_telephonie/email/chat`, pilotés par l'admin global dans **Tenants**) → visibilité des onglets Workspace (**MAIL**/**CHAT**) et sections de config (IMAP/Intégrations) dérivées par `GET /api/tenant/features`. SMTP **toujours actif**. **Délégation** de la configuration du tenant (SMTP/IMAP/références/intégrations) à l'**admin de tenant**.
- 📊 **KPI agents discriminants** : nature d'anomalie marquable **discriminante** par tenant (`reference_values.is_discriminant`). **« Incidents agent »** (anomalies discriminantes ou impact sécurité → impactent le **score** 0–100) vs **« Anomalies »** (toutes). Fiche agent + **dashboard « Agents »** (Rapports). Endpoints `/api/agents/<id>/kpis`, `/api/agents/kpis`.
- 🔐 **Chiffrement du contenu des emails** (objet/corps/HTML) + **pièces jointes** au repos (Fernet) ; **rendu HTML** sanitisé (DOMPurify) à la lecture.
- 🌱 **Seeding unique** : tenant **Root** + **admin global** (`adm_root@permatel.local`). CLI `seed` simplifiée ; **`flask superadmin`** (list/create/promote/demote/reset-password/disable/enable) — les super-admins ne sont plus gérables via l'UI ni `/api/users`.
- 🔑 Variables d'env : `SETTINGS_ENCRYPTION_KEY`, `SUPPORT_EMAIL`, `LOGIN_*`, `FRONTEND_BASE_URL`. Retrait de `SEED_ON_STARTUP`/`SEEDING_ENABLED`.

### Changelog v1.3.0 (21 juin 2026)
- 📧 **Module Mail complet** : canal Mail du Workspace.
  - **Envoi** vers contacts enregistrés via SMTP tenant, avec **Cc** et **pièces jointes**.
  - **Réception** (IMAP polling, worker `flask mail-fetch` / cron) : collecte par tenant, dédup, matching contact, **boîte de triage** (Reçus / Non lus / Envoyés / Archivés).
  - **Traitement** : lecture, réponse threadée, archivage, **conversion en demande** (nouvelle ou existante) créant une **interaction** de suivi.
  - **KPI Email** (onglet Reports) : envoyés/reçus, taux d'échec, **taux & délai de réponse**, sans réponse, volume par utilisateur.
- ⚙️ **Paramètres système** (`SettingsView`, ADMIN) : onglets **Général** (nom, logo, email support), **SMTP**, **IMAP**, **Valeurs de référence** (CRUD éditable), **Intégrations** (Slack/Téléphonie inactives).
- 🆘 **Contacter le support** branché : endpoint public `/api/support` → email vers le `support_email` du tenant.
- 🔐 Secrets SMTP/IMAP **chiffrés** (Fernet). Anti‑brute‑force login déjà en place.
- 🧰 Nouvelles commandes CLI : `seed-prod`, `seed-refvalues`, `sessions-sweep`, `mail-fetch`, `seed-export`.

### Changelog v1.2.0 (20 juin 2026)
- 🔐 **Gestion des sessions** : tâche de fond d'expiration + purge blocklist (`flask sessions-sweep` / `backend/scripts/sessions_sweep.py` cron), anti-brute-force sur `/auth/login`, révocation à distance, KPI de sessions.
- 🖥️ **Supervision** : nouvelle vue `/supervision` (STAFF) avec monitoring des sessions du tenant et révocation ; auto-logout d'inactivité côté client (modale d'avertissement).
- 🛡️ **RBAC** : menu filtré par rôle, suppression masquée pour le PERMANENCIER, routes protégées par `meta.roles`.
- 🏢 **Tenants** : vue d'administration `/tenants` (ADMIN), `logo_url` (upload + miniature + app-bar).
- 💬 **Interactions** : champ `contact_id`, composant réutilisable `ContactSelectWithAdd` pour tous les sélecteurs de contact.
- 📊 **Rapports** : onglet « Sessions » (KPI avec infobulles, filtre par utilisateur), sélection libre de plage de dates (daterange).
- ♻️ **Seeding** : fichier unique `app/scripts/seed_data.json` rechargé au premier démarrage en dev (piloté par `.env`).
- 🔧 **Config** : refresh token ramené à 24 h ; nom d'app paramétrable (`VITE_APP_NAME`) ; footer général (copyright + nom + version).

### Changelog v1.1.0 (23 mai 2026)
- **MISE À JOUR MAJEURE** : Audit complet du projet révèle un état plus avancé que documenté
- Backend : 50% → 70% (demandes routes implémentées, tenants blueprint découvert)
- Frontend : 15% → 40% (dashboard components, 18 Vue files découverts)
- Tests : 153+ → 160 test functions
- Ajout documentation des routes Tenants manquantes
- Correction statut demandes (0% → 6 endpoints implémentés)

---

## 📋 Table des matières

- [Vue d'ensemble](#-vue-densemble)
- [Stack Technologique](#-stack-technologique)
- [État d'avancement](#-état-davancement)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Démarrage Rapide](#-démarrage-rapide)
- [API REST](#-api-rest)
- [Tests](#-tests)
- [Déploiement](#-déploiement)
- [Structure du Projet](#-structure-du-projet)
- [Base de Données](#-base-de-données)
- [Contribution](#-contribution)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Vue d'ensemble

**PERMATEL** est une application web full-stack de gestion intégrée de demandes, conçue pour :

- **Centraliser la gestion des demandes** (anomalies, commandes, planning, administratif)
- **Gérer les clients, sites et contacts** avec relations complexes
- **Tracer les interactions** sur chaque demande en temps réel
- **Sécuriser l'accès** via JWT + sessions utilisateur avec audit trail
- **Supporter les uploads de fichiers** liés aux demandes
- **Fournir une API REST** pour l'intégration serveurs

### Cas d'usage principal

1. **Permanencier** : Reçoit une demande d'anomalie d'un client
2. **Permanencier** : Crée la demande, l'assigne à un agent
3. **Responsable** : Consulte l'historique des interactions
4. **Admin** : Gère les utilisateurs, les prestataires et audite les actions

---

## ️ Stack Technologique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| **Backend** | Flask | 3.1.3 |
| **ORM** | SQLAlchemy | 2.0+ |
| **Authentification** | Flask-JWT-Extended | 4.7.1 |
| **Base de données** | PostgreSQL | 15 (prod) |
| **Tests** | pytest + pytest-flask | 9.0.3 |
| **Migrations BD** | Flask-Migrate (Alembic) | 4.0.5 |
| **Frontend** | Vue.js | 3.2.13 |
| **Routage Frontend** | Vue Router | 4.0.3 |
| **State Management** | Pinia | 3.0+ |
| **Orchestration** | Docker Compose | 1.29+ |

---

## 📊 État d'avancement

### Backend : 70% ✅

- ✅ **Infrastructure Core (100%)** : Factory, Configuration, Extensions (SQLAlchemy, JWT, Migrate, CORS).
- ✅ **Modèles ORM (100%)** : 15 modèles SQLAlchemy définis avec contraintes multi-tenant composites, incluant `Tenant`, `Prestataire`, `User`, `Client`, `Demande` (polymorphe), etc.
- ✅ **Authentification JWT (100%)** : Login, Logout, Refresh, révocation de token, gestion de session et logs d'audit. (36+ tests)
- ✅ **Gestion des Utilisateurs (100%)** : CRUD complet, changement de mot de passe sécurisé, gestion des statuts. (30 tests)
- ✅ **Gestion CRM (100%)** :
    -   CRUD complet pour les **Clients**. (21 tests)
    -   CRUD complet pour les **Sites**. (25 tests)
    -   CRUD complet pour les **Contacts** (avec liaisons N:N).
- ✅ **Gestion des Demandes (60%)** : 6 endpoints implémentés (CRUD multi-type), 160+ tests couvrant principaux cas.
- ✅ **Gestion Tenants/Multi-tenancy (80%)** : 8 endpoints implémentés pour gestion des tenants (non documenté précédemment).
- 🚧 **Interactions & Fichiers (0%)** : À implémenter.

### Frontend : 40% ✅

- ✅ **Setup initial (100%)** : Vue 3 avec Vite, Vue Router et Pinia configurés.
- ✅ **Auth/UI scaffold (100%)** : `Login` et `Dashboard` views implémentées avec authentification complète et Axios.
- ✅ **Composants Dashboard (80%)** : 9 composants dashboard implémentés (KPIs, incidents, agents status, sites overview, real-time activity, etc.). Header et Navigation implémentés.
- ✅ **Structure composants (60%)** : 18 fichiers Vue avec architecture modulaire et réutilisable.
- 🚧 **Intégration API (40%)** : Dashboard utilise mock data; intégration API backend en cours.
- 🚧 **Pages CRUD entités (0%)** : Pages de gestion utilisateurs, clients, sites, demandes restent à implémenter.

### Infrastructure & Tests

- ✅ **Tests (153+ tests)** : Excellente couverture de test pour tous les modules backend implémentés (50 tests auth Phase 1 ajoutés en mai 2026).
- ✅ **Docker (100%)** : L'application est entièrement conteneurisable avec Docker Compose pour le développement et la production (backend, frontend, db).
- ✅ **Migrations de base de données (100%)** : Alembic est configuré et la migration initiale créant toutes les tables est prête.

---

## 🏗️ Architecture

### Schéma actuel (Single-Tenant)

```text
┌─────────────────┐            ┌──────────────────────────────┐
│   Vue.js SPA    │            │       Flask API REST         │
│ (skeleton)      │◄──────────►│                              │
│                 │    HTTP    │  • Blueprints:               │
│  • Router       │            │    - auth.py (✅)            │
│  • Pinia Store  │            │    - users.py (✅)           │
│  • Components   │            │    - clients.py (✅)         │
│                 │            │    - sites.py (✅)           │
│                 │            │    - demandes.py (🚧)        │
│                 │            │                              │
│                 │            │  • Models: 12 (✅)           │
│                 │            │  • Tests: 153+ (✅)          │
│                 │            └──────────────────────────────┘
└─────────────────┘                          │
                                         SQLAlchemy
                                             │
                                             ▼
                                 ┌─────────────────────┐
                                 │    PostgreSQL 15    │
                                 │ (Schéma unique)     │
                                 └─────────────────────┘
```

### Principes d'architecture

- L'application adopte une architecture **multi-tenant à schéma partagé**.
- La base de données est **partagée**, avec une isolation logique par colonne `tenant_id`.
- Tous les objets métier sont rattachés à un **tenant**.
- Les utilisateurs peuvent appartenir à **plusieurs tenants** via une table d'association.
- Les **prestataires** sont des entreprises partenaires rattachées à **un seul tenant**.
- Les **agents de sécurité** peuvent être :
  - **internes** au tenant,
  - ou **fournis par un prestataire** du même tenant.

---

## 🏢 Multi-tenancy

### Concepts métier

#### Tenant
Le **tenant** représente l'entité propriétaire ou exploitante de l'application.  
Tous les objets métier manipulés dans PERMATEL sont affectés à un tenant.

#### Utilisateur multi-tenant
Un **utilisateur** peut appartenir à plusieurs tenants.  
Cette relation est modélisée par une table d'association `tenant_users`.

#### Prestataire
Un **prestataire** est une entreprise partenaire du tenant.  
Un prestataire ne peut appartenir qu'à **un seul tenant**.

#### Agent de sécurité
Un **agent de sécurité** appartient toujours à un tenant.  
Il peut être :
- **interne** au tenant (`prestataire_id = NULL`)
- **rattaché à un prestataire** (`prestataire_id != NULL`)

### Choix d'architecture

PERMATEL retient le modèle :

- **Shared Database**
- **Shared Schema**
- **Isolation logique par `tenant_id`**
- **Filtrage applicatif systématique**
- **Compatibilité future avec Row-Level Security PostgreSQL**

Ce choix permet de limiter la complexité d'exploitation tout en préparant le projet à une isolation renforcée plus tard.

### Règles d'isolation

Toutes les requêtes métier doivent être limitées au **tenant actif** de l'utilisateur.  
Le backend doit refuser toute tentative de liaison entre objets appartenant à des tenants différents.

Exemples :
- un `site` doit appartenir au même tenant que son `client`
- un `agent_securite` ne peut référencer qu'un `prestataire` du même tenant
- une `demande` ne peut lier que des objets du tenant actif

### Tenant actif

Comme un utilisateur peut appartenir à plusieurs tenants, l'application introduit la notion de **tenant actif** :

- après authentification, le backend détermine les tenants disponibles ;
- si un seul tenant est disponible, il devient le tenant actif ;
- si plusieurs tenants sont disponibles, une sélection est requise côté frontend ;
- le `tenant_id` actif est propagé dans le contexte d'exécution et dans les jetons JWT.

---

## 📦 Installation

### Prérequis

- **Python** 3.11+
- **Node.js** 20+
- **PostgreSQL** 15+
- **Docker & Docker Compose** (optionnel)

### 1. Cloner le repository

```bash
git clone <repo-url>
cd permatel
```

### 2. Backend - Configuration Python

```bash
cd backend
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
```

### 3. Frontend - Configuration Node.js

```bash
cd frontend
npm install
```

### 4. Base de données

```bash
cd backend

# Appliquer les migrations (gère les têtes multiples)
flask db upgrade heads
```

Si la base est vide au premier démarrage, le schéma est créé puis une **amorce
unique** est appliquée : tenant **Root** + **admin global** `adm_root@permatel.local`
(aucune donnée de démonstration). `AUTO_MIGRATE` applique les migrations en attente
si la base existe déjà.

Commandes utiles :

```bash
flask init-db          # crée le schéma puis amorce Root + admin global (si BD vide)
flask seed             # amorce unique : tenant Root + admin global (idempotent)
flask sessions-sweep   # expire les sessions inactives + purge la blocklist
flask superadmin list  # gestion des super-admins (create/promote/demote…)
```

---

## ⚙️ Configuration

### Variables d'environnement (`.env`)

| Variable | Description | Exemple |
|----------|-------------|---------|
| `FLASK_ENV` | Mode d'exécution | `development` |
| `FLASK_DEBUG` | Active le debug | `1` |
| `SECRET_KEY` | Clé Flask | `<secret>` |
| `JWT_SECRET_KEY` | Clé JWT | `<secret>` |
| `DATABASE_URL` | URL PostgreSQL | `postgresql://...` |
| `UPLOAD_FOLDER` | Dossier des fichiers | `./uploads` |
| `CORS_ORIGINS` | Origines autorisées | `["http://localhost:8080"]` |
| `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` | Expiration access token (min) | `15` |
| `JWT_REFRESH_TOKEN_EXPIRES_DAYS` | Expiration refresh token (jours) | `1` |
| `SESSION_INACTIVITY_TIMEOUT_MINUTES` | Délai d'inactivité avant expiration | `30` |
| `AUTO_MIGRATE` | Applique les migrations au démarrage si BD existante | `true` |
| `SETTINGS_ENCRYPTION_KEY` | Clé Fernet — chiffrement SMTP/IMAP + contenu emails + PJ (⚠ stable & secrète ; défaut = `JWT_SECRET_KEY`) | `<hex 64>` |
| `SUPPORT_EMAIL` | Destinataire support de repli (si tenant sans `support_email`) | `support@…` |
| `FRONTEND_BASE_URL` | URL publique du frontend (liens d'invitation) | `http://localhost:8080` |
| `LOGIN_MAX_ATTEMPTS` | Tentatives avant verrouillage `/auth/login` | `5` |
| `LOGIN_WINDOW_MINUTES` | Fenêtre glissante des tentatives | `15` |
| `LOGIN_LOCKOUT_MINUTES` | Durée du verrouillage | `15` |

**Frontend (`frontend/.env`, préfixe `VITE_`)** :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | URL de l'API | `http://localhost:5000/api` |
| `VITE_APP_NAME` | Nom de l'application (menu, footer) | `PERMATEL` |
| `VITE_APP_VERSION` | Version affichée | `1.0.0` |
| `VITE_INACTIVITY_TIMEOUT_MINUTES` | Auto-logout client (= timeout serveur) | `30` |

### Paramètres multi-tenant

Les éléments suivants doivent être pris en compte dans la configuration applicative :

- résolution du **tenant actif** après login,
- propagation du `tenant_id` actif dans le JWT,
- validation d'accès au tenant à chaque requête protégée,
- filtrage des requêtes métier par `tenant_id`.

---

## 🚀 Démarrage Rapide

### Mode développement

```bash
# Backend
cd backend
source .venv/bin/activate
flask run

# Frontend
cd frontend
npm run serve
```

### Mode Docker (production)

La stack Compose est **orientée production** (Nginx + Gunicorn, durcie). Voir la section
[Déploiement](#-déploiement-production) pour la procédure complète (secrets, cron, admin global).

```bash
cp .env.example .env   # puis renseigner les secrets (voir Déploiement)
docker compose up -d --build
docker compose logs -f backend
docker compose down
```

> Le développement courant se fait **hors Docker** (`flask run` + `npm run serve`) pour le hot-reload.

### Tests

```bash
cd backend
pytest -v
pytest --cov=app tests/
```

---

## 🔌 API REST

Tous les endpoints protégés attendent un header :

```http
Authorization: Bearer <access_token>
```

### Authentification - `/api/auth`

#### Login

```http
POST /api/auth/login
Content-Type: application/json
```

```json
{
  "username": "permanencier1",
  "password": "Password123!"
}
```

#### Réponse attendue

La réponse de login doit évoluer pour exposer :
- l'utilisateur authentifié,
- la liste des tenants disponibles,
- éventuellement le tenant actif si la sélection est automatique.

Exemple cible :

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 900,
  "user": {
    "id": 1,
    "username": "permanencier1",
    "email": "perm1@permatel.ma"
  },
  "tenants": [
    { "id": 1, "name": "Tenant principal", "is_default": true },
    { "id": 2, "name": "Tenant secondaire", "is_default": false }
  ],
  "active_tenant_id": 1
}
```

#### Sélection du tenant actif

Endpoint cible recommandé :

```http
POST /api/auth/select-tenant
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "tenant_id": 2
}
```

#### Sessions

| Méthode | URL | Rôle | Description |
|---------|-----|------|-------------|
| GET | `/api/auth/sessions` | JWT | Sessions de l'utilisateur courant |
| GET | `/api/auth/sessions/monitoring` | STAFF | Sessions du tenant actif (supervision) |
| DELETE | `/api/auth/sessions/:id` | propriétaire / STAFF | Révoque une session (blocklist refresh + statut `revoked`) |
| GET | `/api/auth/sessions/stats` | STAFF | KPI de sessions (`?from=&to=&user_id=`) ; ADMIN = tous tenants, MANAGER = tenant actif |

> Anti-brute-force : `/api/auth/login` renvoie `429 + Retry-After` après `LOGIN_MAX_ATTEMPTS` échecs (verrouillage `LOGIN_LOCKOUT_MINUTES`).

### Utilisateurs - `/api/users`

Les utilisateurs sont **globaux** dans le système, mais leur accès métier dépend de leurs appartenances dans `tenant_users`.

### Prestataires - `/api/prestataires`

CRUD dédié aux entreprises partenaires rattachées au tenant actif.

### Clients / Sites / Contacts

Tous ces endpoints deviennent **tenant-scopés** :
- lecture filtrée par tenant actif,
- création avec `tenant_id` injecté côté backend,
- interdiction des liaisons cross-tenant.

### Agents de sécurité

Les agents de sécurité sont gérés dans le tenant actif avec deux cas :
- agent **interne**
- agent **prestataire**

### Tenants - `/api/tenants`

CRUD des tenants (réservé **ADMIN** en écriture). Création/édition acceptent du `multipart/form-data` (`data` JSON + `logo`) pour téléverser le **logo** (`logo_url`). La suppression est bloquée (`409`) si des utilisateurs y sont encore rattachés.

### Interactions - `/api/interactions`

Création d'interactions de suivi sur une demande. Accepte un `contact_id` optionnel (contact concerné). Le suivi est aussi listé par `GET /api/demandes/:id/interactions`.

### Mail - `/api/emails`

| Méthode | URL | Description |
|---------|-----|-------------|
| POST | `/api/emails` | Envoi (JSON ou multipart) : `to`/`to_contact_id`, `cc`, `subject`, `body`, `reply_to?`, `attachments?`, `demande_id?` |
| GET | `/api/emails?direction=&contact_id=&demande_id=` | Liste (sortants/entrants) |
| GET | `/api/emails/:id` | Détail (+ pièces jointes) |
| PATCH | `/api/emails/:id` | Statut (non_lu/lu/traite/archive/spam), rattachement |
| POST | `/api/emails/:id/link-demande` | Rattache à une demande + crée une interaction EMAIL |
| GET | `/api/emails/:id/attachments/:aid/download` | Téléchargement authentifié |
| GET | `/api/emails/stats?from=&to=&user_id=` | KPI Email (envoi + réception + réactivité) |

### Paramètres - `/api/settings` (ADMIN en écriture)

| Méthode | URL | Description |
|---------|-----|-------------|
| GET/PUT | `/api/settings/smtp` · POST `/smtp/test` | Config envoi SMTP (+ test) |
| GET/PUT | `/api/settings/imap` · POST `/imap/test` | Config réception IMAP (+ test) |
| GET/POST/PUT/DELETE | `/api/settings/reference-values` | CRUD des valeurs métier (`?family=`) |

### Support - `/api/support` (public)

`POST /api/support` — formulaire « Contacter le support » (pré‑auth). Résout le tenant via l'email émetteur → envoie au `support_email` du tenant (repli `SUPPORT_EMAIL`).

---

## 🧰 Commandes CLI (Flask)

```bash
flask init-db          # crée le schéma si BD vide puis amorce Root + admin global
flask seed             # amorce unique : tenant Root + admin global (idempotent)
flask sessions-sweep   # expire les sessions inactives + purge la blocklist
flask mail-fetch       # relève les emails entrants (IMAP) des tenants activés

# Seeding & Import Avancé par Tenant (Idempotent, Dry-run par défaut)
flask seed-prestataires --tenant-code ADM --no-dry-run --yes
flask seed-agents --tenant-code ADM --no-dry-run --yes
flask seed-agents --tenant-code ADM --prestataire-code CODE_PRESTA --no-dry-run --yes

# Gestion des super-admins globaux (rôle ADMIN — hors UI / hors /api/users)
flask superadmin list
flask superadmin create  --email a@b.com --nom Doe --prenom John
flask superadmin promote a@b.com
flask superadmin demote  a@b.com [--to MANAGER|PERMANENCIER]
flask superadmin reset-password a@b.com
flask superadmin disable a@b.com   # / enable
```

> Amorce par défaut : tenant **Root** + admin global **`adm_root@permatel.local`** (mot de passe `admin123!`, à changer). Aucune donnée de démonstration.

Scripts cron correspondants : `backend/scripts/sessions_sweep.py`, `backend/scripts/mail_fetch.py`.

---

## 🧪 Tests

### Objectifs de test mis à jour

Les tests doivent désormais couvrir :

- l'authentification classique,
- la résolution du tenant actif,
- la sélection de tenant,
- l'isolation des données entre tenants,
- les refus d'accès cross-tenant,
- la création d'agents internes,
- la création d'agents liés à un prestataire.

### Fixtures recommandées

Les fixtures de test doivent inclure au minimum :
- **2 tenants**
- **1 utilisateur mono-tenant**
- **1 utilisateur multi-tenant**
- **1 prestataire**
- **1 agent interne**
- **1 agent prestataire**

---

## 🐳 Déploiement (production)

La stack de production est définie dans [`docker-compose.yml`](docker-compose.yml). Elle est **durcie** :

- **Reverse-proxy Traefik en edge** (seul service exposé, ports **80/443**) : **TLS automatique** Let's Encrypt (redirection HTTP→HTTPS, HSTS). TLS 1.2/1.3 par défaut Traefik ; durcissement ciphers/minVersion **optionnel** via [`traefik/dynamic.yml`](traefik/dynamic.yml) (à ré-activer une fois le mount vérifié — cf. § Dépannage).
- **Anti-DoS** : limite de débit globale (100 req/s, burst 50), **login limité à 5/min** au niveau edge (complète l'anti-brute-force applicatif), plafond de **requêtes concurrentes**, **timeouts** (mitige slowloris), taille de corps bornée (20 Mo).
- **Anti-fuite de données** : en-têtes de sécurité (HSTS, `frameDeny`, `nosniff`, Referrer/Permissions-Policy), suppression des en-têtes `Server`/`X-Powered-By`, `exposedByDefault=false` (Traefik n'expose que les services labellisés), **dashboard Traefik désactivé**, `docker.sock` monté **en lecture seule**.
- **Frontend Nginx, backend et base sur réseau interne** (jamais publiés). Nginx proxifie `/api` et `/uploads` (**same-origin**). Backend **Gunicorn**, images **multi-stage**, conteneurs **non-root**, `no-new-privileges`, **limites** mémoire/CPU/PIDs, **logs** rotés, **healthchecks**, frontend **read-only**.
- **Secrets obligatoires** : le démarrage échoue si `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `SETTINGS_ENCRYPTION_KEY` ou `ACME_EMAIL` sont absents.

### 0. Pré-vol (à vérifier AVANT de pousser/déployer)

Ces points ont chacun bloqué un déploiement réel (voir § Dépannage) :

```bash
# a) Aucun dépôt Git imbriqué (gitlink) — sinon le dossier est VIDE sur le serveur
git ls-files -s | awk '$1==160000{print "GITLINK:",$4}'   # doit être vide
# b) Tout est commité (le serveur ne build que ce qui est dans Git)
git status --short                                         # doit être propre
# c) requirements.txt en UTF-8/ASCII (UTF-16 casse pip)
grep -qP '\x00' backend/requirements.txt && echo "⚠ UTF-16 à corriger" || echo "UTF-8 OK"
```

- Sur Docker récent, si Traefik logue `client version 1.24 is too old`, **abaisser
  le minimum d'API du démon** (une fois pour toutes) :
  ```bash
  sudo systemctl edit docker     # ajouter :  [Service]\n Environment="DOCKER_MIN_API_VERSION=1.24"
  sudo systemctl daemon-reload && sudo systemctl restart docker
  ```
- Ne **jamais éditer `docker-compose.yml` sur le serveur** (conflits à chaque `git pull`) :
  toute variation passe par le `.env`.

> Astuce build : `> /dockerdeploy` (skill) automatise ce pré-vol + le dépannage.

### 1. Préparer le `.env`

Copier le template puis générer des secrets forts :

```bash
cp .env.example .env

# Secrets (à coller dans .env)
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(64))"
python -c "import secrets; print('SETTINGS_ENCRYPTION_KEY=' + secrets.token_hex(32))"
```

Renseigner au minimum : `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`,
`SETTINGS_ENCRYPTION_KEY`, **`DOMAIN`** (FQDN public), **`ACME_EMAIL`** (Let's Encrypt),
`CORS_ORIGINS` et `FRONTEND_BASE_URL` (= `https://<DOMAIN>`). ⚠️ `SETTINGS_ENCRYPTION_KEY`
doit rester **stable** : la changer rend illisibles les données chiffrées (SMTP/IMAP,
contenu des emails, pièces jointes).

> **Prérequis TLS** : un enregistrement DNS **A/AAAA** de `DOMAIN` doit pointer vers l'hôte,
> et les ports **80 et 443** doivent être accessibles (challenge ACME + HTTPS).

#### Activer / désactiver le reverse-proxy TLS

Le reverse-proxy Traefik est piloté par un **profil Compose** (`COMPOSE_PROFILES` dans `.env`) :

| Mode | `.env` | Comportement |
|------|--------|--------------|
| **TLS géré par Traefik** (défaut) | `COMPOSE_PROFILES=proxy` | Traefik démarre, expose **80/443**, certificat Let's Encrypt automatique. `DOMAIN` + `ACME_EMAIL` requis. |
| **TLS géré autrement** | `COMPOSE_PROFILES=` (vide) | Traefik **ne démarre pas**. Le frontend est publié sur `FRONTEND_BIND:FRONTEND_PORT` (défaut `127.0.0.1:8080`) — branchez-y votre proxy/LB/terminaison TLS. Mettre `FRONTEND_BIND=0.0.0.0` si le LB est sur un autre hôte. |

```bash
# Mode sans Traefik (TLS externe) :
#   COMPOSE_PROFILES=        dans .env
docker compose up -d --build           # db + backend + frontend, sans Traefik
# → le frontend écoute sur http://127.0.0.1:8080 (à placer derrière votre proxy)
```

### 2. Démarrer

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

Au premier démarrage, l'entrypoint backend **attend la base**, **applique les migrations**
(`flask db upgrade heads`) puis **amorce** le tenant **Root** + l'**admin global**
`adm_root@permatel.local` (mot de passe `admin123!`). L'application est ensuite disponible
sur **`https://<DOMAIN>`** (certificat Let's Encrypt émis au premier accès ; HTTP redirigé vers HTTPS).

### 3. Première connexion & admin global

```bash
# Se connecter avec adm_root@permatel.local / admin123! puis changer le mot de passe :
docker compose exec backend flask superadmin reset-password adm_root@permatel.local

# Gérer les super-admins (non gérables via l'UI ni /api/users)
docker compose exec backend flask superadmin list
docker compose exec backend flask superadmin create --email ops@exemple.com --nom Ops --prenom Admin
docker compose exec backend flask superadmin demote ops@exemple.com --to MANAGER
docker compose exec backend flask superadmin disable ops@exemple.com   # / enable
```

> Les **tenants** et leurs **canaux** (Téléphonie / Email / Chat) se gèrent ensuite dans l'UI
> (menu **Tenants**, admin global). Chaque **admin de tenant** configure son tenant
> (SMTP/IMAP/valeurs de référence/intégrations) et invite ses utilisateurs (menu **Membres**).

### 4. Tâches planifiées (cron)

Deux tâches doivent tourner périodiquement. On utilise **`docker exec`** (plus
robuste en cron que `docker compose exec` : pas de dépendance au `.env`/dossier
projet) avec le **chemin absolu** de `docker` (le PATH de cron est minimal).

```bash
sudo mkdir -p /var/log/permatel
crontab -e
```
```cron
# Collecte IMAP des emails entrants — toutes les 5 min
*/5  * * * * /usr/bin/docker exec permatel_backend flask mail-fetch     >> /var/log/permatel/mail-fetch.log     2>&1
# Expiration des sessions inactives + purge blocklist — toutes les 15 min
*/15 * * * * /usr/bin/docker exec permatel_backend flask sessions-sweep >> /var/log/permatel/sessions-sweep.log 2>&1
```

`permatel_backend` = `container_name` du backend ; adapter `/usr/bin/docker` selon
`which docker`. Synchronisation manuelle possible depuis le canal **Mail** du
Workspace (bouton **Synchroniser**).

### 5. Mise à jour / sauvegarde

```bash
# Mise à jour (les migrations sont rejouées par l'entrypoint, idempotent)
git pull && docker compose up -d --build

# Sauvegarde de la base
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup_$(date +%F).sql

# Volumes persistants : postgres_data (BD) et backend_uploads (avatars, PJ chiffrées)
```

> Si `git pull` refuse à cause d'un `docker-compose.yml` modifié sur le serveur :
> `git checkout -- docker-compose.yml` puis `git pull` (les variations vont dans `.env`).

### 6. Dépannage déploiement (retour d'expérience)

| Symptôme | Cause | Correctif |
|---|---|---|
| `failed to read dockerfile: open Dockerfile: no such file…` (fichier pourtant présent) | bug du **mode bake** de Compose | `COMPOSE_BAKE=false docker compose up -d --build` (ou désactiver « Use Compose bake » dans Docker Desktop) |
| Même erreur mais fichier **absent sur le serveur** | dossier = **dépôt Git imbriqué** (gitlink) non récupéré | dé-imbriquer : `git rm --cached <dir> && rm -rf <dir>/.git && git add <dir>` puis push/pull |
| `Invalid requirement: 'a\x00l\x00e…'` (pip) | `requirements.txt` en **UTF-16** | réécrire en UTF-8 (heredoc bash) ; `.gitattributes` impose `requirements.txt text eol=lf` |
| Traefik `client version 1.24 is too old. Minimum supported API version is 1.40` | provider Docker de Traefik (n'ignore pas `DOCKER_API_VERSION`) | `DOCKER_MIN_API_VERSION=1.24` sur le **démon** (cf. § Pré-vol) |
| Traefik `Could not find network "permatel_internal"` | Compose **préfixe** le réseau | réseau à **nom fixe** (`networks: permatel_internal: { name: permatel_internal }`) — déjà en place |
| Traefik `unknown TLS options: default@file` | `traefik/dynamic.yml` non monté/chargé | vérifier `docker compose exec traefik cat /etc/traefik/dynamic.yml` ; sinon laisser le TLS par défaut (labels `tls.options` retirés) |
| Navigateur `SSL_ERROR_UNRECOGNIZED_NAME_ALERT` | `sniStrict:true` **+** cert ACME non émis | `sniStrict:false` (déjà) + corriger l'émission (provider Docker, port 80, DNS) |
| ACME `timeout` / `too many certificates` | port 80 fermé / DNS / rate-limit LE | ouvrir 80‑443, vérifier `dig +short <DOMAIN>` ; itérer en **staging** puis revenir prod |

> Référence détaillée : skill **`/dockerdeploy`** (matrice complète + pré-vol).

### Bonnes pratiques sécurité (production)
- **TLS** géré par Traefik (Let's Encrypt). Ouvrir uniquement **80/443** sur le pare-feu de l'hôte ; tous les autres services sont internes.
- **DoS** : ajuster les seuils des middlewares (`permatel-ratelimit`, `permatel-authlimit`, `permatel-inflight`) selon la charge réelle ; envisager un WAF/CDN (Cloudflare…) en amont pour le volumétrique (L3/L4).
- **`docker.sock`** : monté en lecture seule ; pour un durcissement supplémentaire, interposer un **docker-socket-proxy** (expose uniquement l'API conteneurs en lecture).
- Restreindre `CORS_ORIGINS` à l'URL HTTPS publique réelle.
- Sauvegarder **`SETTINGS_ENCRYPTION_KEY`** dans un gestionnaire de secrets (perte = données chiffrées irrécupérables).
- Sauvegardes régulières de `postgres_data` et `backend_uploads` (le volume `traefik_letsencrypt` contient les certificats).
- Évolution envisagée : **Row-Level Security PostgreSQL** en complément de l'isolation applicative par `tenant_id`.

---

## 📁 Structure du Projet

```text
permatel/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── tenant.py
│   │   │   ├── tenant_user.py
│   │   │   ├── prestataire.py
│   │   │   ├── agent_securite.py
│   │   │   ├── client.py
│   │   │   ├── site.py
│   │   │   ├── contact.py
│   │   │   ├── demande.py
│   │   │   ├── interaction.py
│   │   │   └── fichier.py
│   │   ├── routes/
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── prestataires.py
│   │   │   ├── clients.py
│   │   │   ├── sites.py
│   │   │   ├── contacts.py
│   │   │   ├── demandes.py
│   │   │   └── interactions.py
│   │   └── utils/
│   │       ├── auth.py
│   │       ├── tenant.py
│   │       └── logger.py
│   ├── migrations/
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   ├── store/
│   │   └── router/
├── docker-compose.yml
├── DATABASE_SCHEMA.md
├── PROJECT_STRUCTURE.md
└── README.md
```

---

## 🗄️ Base de Données

### Tables globales

| Table | Rôle |
|-------|------|
| `users` | Utilisateurs globaux |
| `tenants` | Entités propriétaires (+ `logo_url`) |
| `tenant_users` | Appartenances utilisateurs ↔ tenants |

### Tables tenant-scopées

| Table | Particularité |
|-------|---------------|
| `prestataires` | Appartient à un tenant unique |
| `clients` | Porte `tenant_id` |
| `sites` | Porte `tenant_id` |
| `contacts` | Porte `tenant_id` |
| `agents_securite` | Porte `tenant_id` + `prestataire_id` nullable, relation composite |
| `demandes` | Porte `tenant_id`, relations composites avec clients et sites |
| `interactions` | Porte `tenant_id`, relation composite avec demande, `contact_id` nullable |
| `fichiers` | Porte `tenant_id`, relation composite avec demande |
| `audit_logs` | Porte `tenant_id` |
| `user_sessions` | Porte `tenant_id` ou contexte actif selon implémentation |
| `telephony_events` | Porte `tenant_id`, relation composite avec demande |

### Migration prévue

La migration vers ce modèle suit la logique suivante :

1. création des tables `tenants`, `tenant_users`, `prestataires`
2. ajout de `tenant_id` nullable sur les tables existantes
3. création d'un tenant par défaut
4. backfill des données existantes
5. refactor backend tenant-aware
6. passage des `tenant_id` en `NOT NULL`

---

## 👥 Contribution

### Règles complémentaires

Toute nouvelle entité métier doit répondre aux questions suivantes :

- appartient-elle à un tenant ?
- doit-elle porter un `tenant_id` direct ?
- peut-elle être liée à un objet d'un autre tenant ?
- quelles règles de validation d'isolation faut-il appliquer ?

### Checklist avant commit

- [ ] Tests passent
- [ ] Code formaté
- [ ] Couverture mise à jour
- [ ] Pas de secrets en dur
- [ ] Migrations créées si modèle modifié
- [ ] Vérification explicite des règles multi-tenant

---

## 🔧 Troubleshooting

### Cas fréquents

#### Accès à des données d'un autre tenant
**Cause** : filtre `tenant_id` absent ou tenant actif mal résolu.  
**Solution** : vérifier la récupération du tenant actif et les clauses de filtrage dans le blueprint concerné.

#### Utilisateur connecté mais sans données visibles
**Cause** : utilisateur rattaché au mauvais tenant ou tenant actif incorrect.  
**Solution** : vérifier les enregistrements `tenant_users` et la sélection du tenant actif.

#### Liaison refusée entre objets
**Cause** : tentative de relation cross-tenant.  
**Solution** : vérifier que tous les objets manipulés appartiennent au même tenant.

---

## 📚 Documentation complémentaire

- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)

---

## 📜 License

**Propriétaire** : PERMATEL  
**Statut** : En développement - 2026

---

**Dernière mise à jour** : 10 mai 2026  
**Mainteneur** : Équipe Développement PERMATEL