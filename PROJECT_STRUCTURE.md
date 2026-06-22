# Permatel - Architecture et Structure du Projet

**Version** : 1.4.0 | **Statut** : Backend ✅ / Frontend ✅ | **Tests** : 160 ✅

### Changelog v1.4.0 (22 juin 2026)
> ⚠️ Les sections détaillées plus bas datent de v1.1.0 (mai 2026). Les changelogs font foi pour l'état courant.

**Backend — nouveaux modules**
- `models/` : `tenant_invitation.py` (invitations onboarding) ; `tenant_users.membership_role` (admin/member) ; `tenants.channel_telephonie/email/chat` ; `reference_values.is_discriminant` ; `users.username = email` (120) ; `emails` objet/corps chiffrés (`EncryptedText`).
- `services/` (nouveau package) : `tenant_features.py` (dérivation onglets/sections par canaux), `agent_kpis.py` (Anomalies / Incidents agent / score discriminant).
- `routes/` : `tenant_members.py` (roster + invitations, `/api/tenant/*`), `invitations.py` (acceptation publique), `/api/tenant/features`, `/api/agents/<id>/kpis` & `/api/agents/kpis`, `/api/auth/tenants`. `settings.py` délégué au tenant-admin.
- `utils/decorators.py` : `tenant_required` v2 (bypass super-admin) + `tenant_admin_required`. `utils/invitations.py` (token/email).
- `scripts/` : `seeding.py` réduit à `seed_root` (Root + admin global) ; `superadmin_cli.py` (`flask superadmin …`). Suppression de `seed_data.json` et des commandes `seed-prod`/`seed-refvalues`/`seed-export`.
- Migrations ajoutées : `a8b9c0d1e2f3`, `b9c0d1e2f3a4`, `c0d1e2f3a4b5`, `d1e2f3a4b5c6`.

**Frontend — nouveaux éléments**
- `views/` : `SelectTenantView`, `AcceptInviteView` (publique), `TenantMembersView`. `WorkspaceView`/`SettingsView`/`TenantsView`/`AgentView`/`ReportView` adaptés (canaux, KPI, toggles).
- `components/` : `agents/AgentKpiCards.vue` ; `settings/ReferenceValueList` (toggle discriminante) ; `workspace/ChannelTabs` (onglets dynamiques).
- `services/` : `tenantMemberService`, `invitationService`, `agentKpiService` ; `auth` enrichi (`getTenants`, `getFeatures`). `utils/sanitizeHtml.js` (DOMPurify).
- `store/auth.js` : `isGlobalAdmin`, `isTenantAdmin`, `features`, `selectTenant`/`switchTenant`/`fetchFeatures`.
- `router` : `/select-tenant`, `/accept-invite`, `/members` + gardes (sélection tenant, capacité admin tenant).

### Changelog v1.3.0 (21 juin 2026)
> ⚠️ Les sections détaillées plus bas datent de v1.1.0 (mai 2026). Le projet a fortement évolué ; ce changelog fait foi pour l'état courant.

**Backend — nouveaux modules**
- `models/` : `setting.py` (`SmtpSetting` + IMAP, `ReferenceValue`), `email.py` (`Email`), `email_attachment.py` (`EmailAttachment`). Colonnes ajoutées : `tenants.logo_url`/`support_email`, `interactions.contact_id`.
- `routes/` : `settings.py` (SMTP/IMAP/valeurs de référence), `emails.py` (envoi+réception, PJ, stats, conversion), `support.py` (public). `interactions.py` désormais implémenté.
- `utils/` : `crypto.py` (Fernet), `mailer.py` (send SMTP), `login_throttle.py` (anti‑brute‑force), `auth.py` (`role_required`).
- `scripts/` : `seeding.py` (fixture unique + prod + reference values), `session_maintenance.py`, `mail_fetch.py`.
- `scripts/` (CLI cron) : `sessions_sweep.py`, `mail_fetch.py`.
- Commandes CLI : `init-db`, `seed`, `seed-export`, `seed-prod`, `seed-refvalues`, `sessions-sweep`, `mail-fetch`.

**Frontend — nouveaux éléments**
- `views/` : `TenantsView`, `SupervisionView`, `SettingsView`, `ReportView` (onglets Sessions + Email).
- `components/settings/` : `SettingsGeneral`, `SettingsSmtp`, `SettingsImap`, `SettingsReferenceValues`, `ReferenceValueList`, `SettingsIntegrations`.
- `components/workspace/` : `MailChannel`, `MailConvertDialog`, `EmailAttachments`, `ChannelGate`, `DemandeInteractions`, `ContactSelectWithAdd`, `SessionMonitoring` (supervision).
- `composables/` : `useIdleLogout`. `config/integrations.js`.
- `services/` : `emailService`, `supportService`, `settingsService`, `tenantService`, `sessionService`.
- RBAC menu par rôle, footer global, logo tenant dans l'app‑bar, nom d'app paramétrable.

### Changelog v1.1.0 (23 mai 2026)
- **MISE À JOUR MAJEURE** : Audit révèle état réel du projet (plusieurs features manquaient dans la doc)
- Ajout documentation du blueprint Tenants (8 endpoints)
- Correction statut demandes (6 endpoints implémentés, non 0%)
- Frontend : découverte des 9 composants dashboard et 18 fichiers Vue
- Tests : 160 functions au lieu de 153+
- Correction des statuts d'implémentation globaux

## Vue d'ensemble

**Permatel** est une application web full-stack construite avec :
- **Backend** : Framework Flask (Python 3.11) — **50% implémenté** ✅
- **Base de données** : PostgreSQL 15 (prod) / SQLite :memory: (test)
- **Frontend** : Vue.js 3 avec Vite — **15% implémenté** 🚧
- **Orchestration** : Docker Compose
- **Authentification** : JWT (Flask-JWT-Extended) — **complète** ✅
- **Tests** : pytest — **153+ tests tous PASSANTS** ✅
- **Migrations BD** : Alembic (Flask-Migrate)

L'architecture suit le pattern **MVC (Model-View-Controller)** avec une séparation claire entre le backend API REST et le frontend SPA responsive.

### Statut d'implémentation par module
- ✅ **Authentification JWT** — 50/50 tests passing
- ✅ **Gestion utilisateurs** — 30/30 tests passing  
- ✅ **Clients, Sites, Contacts CRUD** — Implémentés (46+ tests passing)
- ✅ **Prestataires CRUD** — Implémenté (isolation tenant, soft delete, cascade agents)
- 🚧 **Demandes CRUD** — À implémenter
- 🚧 **Frontend** — Skeleton auth/dashboard démarré
- 🟡 **Infrastructure Docker** — Fonctionnelle

---

## Structure du Répertoire

```
permatel/
├── backend/                              # Backend Flask - API REST ✅40%
│   ├── app/                              # Package principal Flask
│   │   ├── __init__.py                   # Factory Flask (create_app) ✅
│   │   ├── config.py                     # Configuration (Dev/Prod/Test) ✅
│   │   │
│   │   ├── models/                       # 15 Modèles SQLAlchemy ORM (✅ tous)
│   │   │   ├── __init__.py               # Exports centralisés
│   │   │   ├── tenant.py                 # Tenant (✅)
│   │   │   ├── tenant_user.py            # TenantUser association (✅)
│   │   │   ├── prestataire.py            # Prestataire (✅)
│   │   │   ├── user.py                   # User + UserRole (✅ Implémenté)
│   │   │   ├── user_session.py           # UserSession + SessionStatus (✅)
│   │   │   ├── token_blocklist.py        # TokenBlocklist pour JWT (✅)
│   │   │   ├── audit_log.py              # AuditLog + AuditAction (✅)
│   │   │   ├── client.py                 # Client (modèle défini)
│   │   │   ├── site.py                   # Site (modèle défini)
│   │   │   ├── contact.py                # Contact many-to-many (modèle défini)
│   │   │   ├── agent_securite.py         # AgentSecurite (modèle défini)
│   │   │   ├── demande.py                # Demande + 4 polymorphes (modèles définis)
│   │   │   ├── interaction.py            # Interaction (modèle défini)
│   │   │   ├── fichier.py                # Fichier (modèle défini)
│   │   │   └── telephony_event.py        # TelephonyEvent (modèle défini)
│   │   │
│   │   ├── routes/                       # Routes REST (blueprints)
│   │   │   ├── __init__.py               # Enregistrement blueprints
│   │   │   │
│   │   │   ├── auth.py                   # ✅ IMPLÉMENTÉ - 5 endpoints
│   │   │   │   ├── POST   /api/auth/login        ← Login (36 tests)
│   │   │   │   ├── POST   /api/auth/refresh      ← Refresh token
│   │   │   │   ├── POST   /api/auth/logout       ← Logout + revocation
│   │   │   │   ├── GET    /api/auth/me           ← Get profil utilisateur
│   │   │   │   └── GET    /api/auth/sessions     ← Sessions actives
│   │   │   │
│   │   │   ├── users.py                  # ✅ IMPLÉMENTÉ - 7 endpoints
│   │   │   │   ├── GET    /api/users              ← Tous utilisateurs (30 tests)
│   │   │   │   ├── GET    /api/users/<id>        ← Un utilisateur
│   │   │   │   ├── POST   /api/users              ← Créer utilisateur
│   │   │   │   ├── PUT    /api/users/<id>        ← Mettre à jour
│   │   │   │   ├── PATCH  /api/users/<id>/status ← Activer/désactiver
│   │   │   │   ├── PATCH  /api/users/<id>/password ← 🔐 Changer mot de passe
│   │   │   │   └── DELETE /api/users/<id>        ← Supprimer
│   │   │   │
│   │   │   ├── clients.py                # ✅ IMPLÉMENTÉ - 6 endpoints
│   │   │   ├── sites.py                  # ✅ IMPLÉMENTÉ - 6 endpoints
│   │   │   ├── contacts.py               # ✅ IMPLÉMENTÉ - 7 endpoints
│   │   │   │   ├── GET    /api/clients              ← Tous clients actifs (21 tests)
│   │   │   │   ├── GET    /api/clients/<id>        ← Un client
│   │   │   │   ├── POST   /api/clients              ← Créer client
│   │   │   │   ├── PUT    /api/clients/<id>        ← Mettre à jour
│   │   │   │   ├── PATCH  /api/clients/<id>/status ← Activer/désactiver
│   │   │   │   └── DELETE /api/clients/<id>        ← Désactiver (soft delete)
│   │   │   │
│   │   │   ├── prestataires.py           # ✅ IMPLÉMENTÉ - 6 endpoints (CRUD + cascade)
│   │   │   ├── tenants.py                # ✅ IMPLÉMENTÉ - 8 endpoints (multi-tenancy management)
│   │   │   ├── demandes.py               # ✅ PARTIELLEMENT - 6 endpoints CRUD (4 types polymorphes)
│   │   │   ├── interactions.py           # 🚧 À implémenter - Interactions
│   │   │   └── fichiers.py               # 🚧 À implémenter - Upload/download
│   │   │
│   │   ├── utils/                        # Utilitaires et helpers
│   │   │   ├── __init__.py
│   │   │   ├── logger.py                 # Logging configuration
│   │   │   ├── decorators.py             # Auth decorators (à compléter)
│   │   │   └── validators.py             # Validateurs métier
│   │   │
│   │   └── middleware/
│   │       ├── __init__.py
│   │       └── error_handler.py          # Global error handling
│   │
│   ├── tests/                            # Tests pytest (103+ TESTS ✅ TOUS PASSANTS)
│   │   ├── conftest.py                   # Fixtures pytest globales (✅)
│   │   │   ├── app() - Flask instance SQLite
│   │   │   ├── db() - Database session
│   │   │   ├── client() - Test client
│   │   │   ├── user_permanencier/manager/admin - Users fixtures
│   │   │   ├── tokens_permanencier - JWT après login
│   │   │   └── auth_headers - Bearer token header
│   │   │
│   │   ├── test_auth_login.py            # ✅ 6 tests - Login TOUS PASSANTS
│   │   ├── test_auth_logout.py           # ✅ 24 tests - Logout & revocation TOUS PASSANTS
│   │   ├── test_auth_refresh.py          # ✅ Tests - Refresh token TOUS PASSANTS
│   │   └── test_users.py                 # ✅ 30 tests - Users CRUD + password TOUS PASSANTS
│   │       ├── List (3), Get (3), Create (6), Update (4)
│   │       ├── Status (3), Delete (2), Password (9)
│   │       └── Total: 30/30 tests
│   │   ├── test_clients.py               # ✅ 21 tests - Clients CRUD
│   │   ├── test_sites.py                 # ✅ 25 tests - Sites CRUD
│   │   └── test_contacts.py              # ✅ Tests - Contacts CRUD
│   │
│   ├── migrations/                        # Alembic - Migrations versionnées BD
│   │   ├── versions/
│   │   │   └── 1b1167b1417e_initial_migration_create_all_tables.py
│   │   ├── alembic.ini
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── README
│   │
│   ├── uploads/                          # Répertoire fichiers uploadés
│   ├── resources/                        # Ressources statiques/données
│   │
│   ├── .env.example                      # Template variables d'environnement
│   ├── app.py                            # Point d'entrée Flask
│   ├── manage.py                         # CLI commands
│   ├── database.py                       # Compatibilité : from database import db
│   ├── test_db.py                        # Test connexion BD
│   ├── update_req.py                     # Utilitaire requirements
│   ├── Dockerfile                        # Image Docker Python 3.11-slim
│   └── requirements.txt                  # Dépendances Python
│
├── frontend/                             # Frontend Vue.js 3 SPA (5% 🚧)
│   ├── public/
│   │   └── index.html                    # Template HTML d'entrée
│   │
│   ├── src/                              # Code source Vue
│   │   ├── main.js                       # Entry point
│   │   ├── App.vue                       # Composant root
│   │   │
│   │   ├── components/                   # Composants réutilisables (18 fichiers)
│   │   │   ├── Header.vue                # ✅ Implémenté
│   │   │   ├── Navigation.vue            # ✅ Implémenté
│   │   │   ├── HelloWorld.vue
│   │   │   └── dashboard/                # 9 dashboard components
│   │   │       ├── DashboardKpiCard.vue
│   │   │       ├── DashboardKpiGrid.vue
│   │   │       ├── DashboardIncidentsTable.vue
│   │   │       ├── DashboardCriticalIncidents.vue
│   │   │       ├── DashboardAgentsStatus.vue
│   │   │       ├── DashboardSitesOverview.vue
│   │   │       ├── DashboardTeamsPerformance.vue
│   │   │       ├── DashboardRealtimeActivity.vue
│   │   │       ├── DashboardPriorityTasks.vue
│   │   │       ├── DashboardFilterBar.vue
│   │   │       └── ...
│   │   │
│   │   ├── views/                        # Pages du routeur (4 vues implémentées)
│   │   │   ├── HomeView.vue              # Home ✅
│   │   │   ├── AboutView.vue             # About ✅
│   │   │   ├── LoginView.vue             # ✅ Login avec formulaire complet
│   │   │   ├── DashboardView.vue         # ✅ Dashboard avec 9 composants
│   │   │   └── (UsersView, ClientsView, etc. à créer)
│   │   │
│   │   ├── router/
│   │   │   └── index.js                  # Routes de l'application
│   │   │
│   │   ├── store/
│   │   │   └── index.js                  # Pinia auth store + scaffold
│   │   │
│   │   └── assets/
│   │       ├── logo.png
│   │       └── styles/
│   │
│   ├── package.json                      # Dépendances Node.js
│   ├── vue.config.js                     # Configuration webpack
│   ├── babel.config.js                   # Configuration Babel
│   ├── jsconfig.json                     # Config JavaScript
│   ├── Dockerfile                        # Multi-stage: build Node + Nginx
│   └── README.md                         # Documentation frontend
│
├── docker-compose.yml                    # Orchestration 3 services ✅
├── .gitignore
├── README.md                             # Documentation principale (✅ 1500+ lignes)
├── PROJECT_STRUCTURE.md                  # Ce fichier (mise à jour 10/05/26)
└── DATABASE_SCHEMA.md                    # Schéma BD (à mettre à jour)
```

---

## Routes implémentées et testées

### ✅ AUTHENTIFICATION (36 tests — TOUS PASSANTS)

**Blueprint** : `auth.py`

```
POST   /api/auth/login
  ├─ Body: {"username": "...", "password": "..."}
  ├─ Response: {access_token, refresh_token, user_data, expires_in}
  ├─ Tests (6): validité, profil retourné, session créée, last_login_at, audit_log
  └─ Status: 200 ✅

POST   /api/auth/refresh
  ├─ Header: Authorization: Bearer <refresh_token>
  ├─ Response: {access_token, refresh_token, expires_in}
  ├─ Features: Renew access token via refresh_token
  └─ Status: 200 ✅

POST   /api/auth/logout
  ├─ Header: Authorization: Bearer <access_token>
  ├─ Features: Revoque tokens via TokenBlocklist, ferme session
  ├─ Tests (24): revocation, blocklist, session close, multi-session isolation
  ├─ Security: Ne ferme que la session visée (JTI matching)
  └─ Status: 200 ✅

GET    /api/auth/me
  ├─ Header: Authorization: Bearer <access_token>
  ├─ Response: {id, username, email, nom, prenom, role, is_active, created_at, last_login_at}
  └─ Status: 200 ✅

GET    /api/auth/sessions
  ├─ Header: Authorization: Bearer <access_token>
  ├─ Response: [{session_id, ip_address, user_agent, jti, status, created_at}]
  └─ Status: 200 ✅
```

**Caractéristiques JWT** :
- Access token : 15 minutes (configurable)
- Refresh token : 30 jours (configurable)
- Token blocklist : Revocation instantanée
- Session tracking : JTI, IP, User-Agent stockés en BD
- Audit trail : Toutes actions loggées dans AuditLog
- UserRole enum : PERMANENCIER, MANAGER, ADMIN

### ✅ GESTION CLIENTS (21 tests — TOUS PASSANTS)

**Blueprint** : `clients.py`

```
GET    /api/clients
  ├─ Header: Authorization: Bearer <token> (JWT required)
  ├─ Response: [{id, nom, code_client, adresse, telephone, email, contact_principal, is_active, created_at}]
  ├─ Features: Liste uniquement les clients actifs (is_active=True)
  ├─ Tests (3): 200 response, liste retournée, filtrage actifs uniquement
  └─ Status: 200 ✅

GET    /api/clients/<id>
  ├─ Header: Authorization: Bearer <token> (JWT required)
  ├─ Response: {id, nom, code_client, adresse, telephone, email, contact_principal, is_active, created_at, updated_at}
  ├─ Tests (2): récupération OK, 404 si non existant
  └─ Status: 200 / 404 ✅

POST   /api/clients
  ├─ Header: Authorization: Bearer <token> (JWT required)
  ├─ Body: {nom✓, code_client✓, adresse?, telephone?, email?, contact_principal?}
  ├─ Validations (4 tests):
  │   ├─ nom et code_client requis (400 si manquant)
  │   ├─ code_client unique (409 si existe déjà)
  │   ├─ Champs optionnels acceptés
  │   └─ Création avec is_active=True par défaut
  ├─ Error responses: 400 (champs requis), 409 (unicité)
  └─ Status: 201 Created ✅

PUT    /api/clients/<id>
  ├─ Header: Authorization: Bearer <token> (JWT required)
  ├─ Body: {nom?, code_client?, adresse?, telephone?, email?, contact_principal?}
  ├─ Features: Mise à jour partielle (champs optionnels)
  ├─ Validations (3 tests):
  │   ├─ code_client unique si modifié (409)
  │   ├─ 404 si client non existant
  │   └─ Champs partiels acceptés
  └─ Status: 200 / 404 / 409 ✅

PATCH  /api/clients/<id>/status
  ├─ Header: Authorization: Bearer <token> (JWT required)
  ├─ Body: {is_active: true|false}
  ├─ Validations (3 tests):
  │   ├─ is_active requis (400)
  │   ├─ is_active doit être booléen (400)
  │   └─ 404 si client non existant
  ├─ Features: Activation/désactivation du client
  └─ Status: 200 / 400 / 404 ✅

DELETE /api/clients/<id>
  ├─ Header: Authorization: Bearer <token> (JWT required)
  ├─ Features: Soft delete (désactivation au lieu de suppression)
  ├─ Tests (2): succès, 404 si non existant
  └─ Status: 200 / 404 ✅
```

**Modèle Client** :
- **Champs requis** : nom, code_client
- **Champs optionnels** : adresse, telephone, email, contact_principal
- **Système** : is_active (soft delete), created_at, updated_at
- **Relations** : sites (1:N), contacts (N:N via association table)

**Résumé des validations** :

| Champ | Type | Défaut | Validations |
|-------|------|--------|-------------|
| nom | String(200) | - | ✓ UNIQUE avec code_client, required |
| code_client | String(50) | - | ✓ UNIQUE, required, index |
| adresse | Text | NULL | optional |
| telephone | String(20) | NULL | optional |
| email | String(100) | NULL | optional |
| contact_principal | String(100) | NULL | optional |
| is_active | Boolean | True | - |
| created_at | DateTime | now() | - |
| updated_at | DateTime | now() | - |

### ✅ GESTION UTILISATEURS (30 tests — TOUS PASSANTS)

**Blueprint** : `users.py`

```
GET    /api/users
GET    /api/users/<id>
POST   /api/users
PUT    /api/users/<id>
PATCH  /api/users/<id>/status
PATCH  /api/users/<id>/password
DELETE /api/users/<id>
```

### ✅ GESTION SITES & CONTACTS (25+ tests — TOUS PASSANTS)

**Blueprints** : `sites.py`, `contacts.py`

```
GET    /api/sites
GET    /api/sites/<id>
POST   /api/sites
PUT    /api/sites/<id>
PATCH  /api/sites/<id>/status
DELETE /api/sites/<id>

GET    /api/contacts
GET    /api/contacts/<id>
POST   /api/contacts
PUT    /api/contacts/<id>
DELETE /api/contacts/<id>
```

### 🚧 À IMPLÉMENTER

```
🚧 DEMANDES CRUD (4 types + 15+ endpoints)
   ├─ DemandeAnomalie - Signalement anomalies
   ├─ DemandeCommande - Gestion commandes
   ├─ DemandePlanning - Changements planning
   ├─ DemandeAdmin - Demandes administratives
   ├─ GET    /api/demandes
   ├─ GET    /api/demandes/<id>
   ├─ POST   /api/demandes (multi-type)
   ├─ PUT    /api/demandes/<id>
   ├─ PATCH  /api/demandes/<id>/status
   └─ DELETE /api/demandes/<id>

🚧 INTERACTIONS (5 endpoints)
   ├─ POST   /api/demandes/<id>/interactions
   ├─ GET    /api/demandes/<id>/interactions
   ├─ PUT    /api/interactions/<id>
   └─ DELETE /api/interactions/<id>

🚧 FICHIERS (5 endpoints)
   ├─ POST   /api/fichiers/upload
   ├─ GET    /api/fichiers/<id>
   ├─ DELETE /api/fichiers/<id>
   └─ Plus endpoints de listing/filtrage
```

---

## Architecture Backend (Flask)

### 1. **Point d'entrée** (`app.py`)
```python
from app import create_app
app = create_app()  # Factory pattern
```
- Crée l'instance Flask via la factory function `create_app()`
- Utilisé comme point d'entrée pour `flask` CLI et le serveur

### 2. **Factory Pattern** (`app/__init__.py`)

La fonction `create_app()` :
- **Initialise Flask** avec la configuration appropriée (Dev/Prod/Test)
- **Configure SQLAlchemy** pour les modèles ORM
- **Initialise les extensions** :
  - `db` (SQLAlchemy) - ORM
  - `jwt` (Flask-JWT-Extended) - Authentification JWT
  - `Migrate` (Flask-Migrate) - Gestion migrations Alembic
  - `CORS` (Flask-CORS) - Autorise les requêtes cross-origin
- **Charge les modèles** pour que Alembic les détecte
- **Crée un endpoint health** (`/health`)
- **Retourne l'instance Flask configurée**

### 3. **Configuration** (`app/config.py`)

Trois classes de configuration héritant d'une `BaseConfig` :

| Classe | Contexte | DEBUG | SQLALCHEMY_ECHO |
|--------|----------|-------|-----------------|
| `BaseConfig` | Configuration commune | False | True |
| `DevelopmentConfig` | Développement local | True | True |
| `ProductionConfig` | Production | False | False |

**Paramètres configurables via `.env`** :
- `FLASK_ENV` - Sélectionne la config (development/production)
- `SECRET_KEY` / `JWT_SECRET_KEY` - Clé secrète JWT
- `PORT`, `BINDADDR` - Adresse et port du serveur
- `DB_*` - Paramètres PostgreSQL
- `CORS_ORIGINS` - Origines autorisées en CORS
- `UPLOAD_FOLDER` - Dossier pour fichiers uploadés

### 4. **Modèles ORM** (`app/models/`)

**11 modèles SQLAlchemy** définissant le schéma de données :

#### Utilisateurs & Authentification
- **`User`** - Utilisateurs avec rôles (Permanencier, Manager, Admin)
- **`UserSession`** - Sessions utilisateur avec statut

#### Clients & Sites
- **`Client`** - Clients de l'entreprise
- **`Site`** - Sites clients
- **`Contact`** - Contacts avec relations many-to-many vers Clients/Sites

#### Opérationnel
- **`AgentSecurite`** - Agents de sécurité
- **`Demande`** - Demandes centrales + 4 sous-types :
  - `DemandeAnomalie` - Signalement d'anomalies
  - `DemandeCommande` - Commandes
  - `DemandePlanning` - Changements de planning
  - `DemandeAdmin` - Demandes administratives

#### Interactions & Audit
- **`Interaction`** - Communications/interactions sur demandes
- **`Fichier`** - Fichiers uploadés
- **`AuditLog`** - Journal audit des actions
- **`TelephonyEvent`** - Événements de la téléphonie ESL

**Relations clés** :
- `User` → `Demande` (assigne/clôture)
- `Client` ↔ `Contact` (many-to-many)
- `Demande` → `Interaction` (discussions)
- `User` → `AuditLog` (traçabilité)

### 5. **Routes** (`app/routes/`)

#### ✅ IMPLÉMENTÉES ET TESTÉES

**`auth.py`** - Authen tification (36 tests ✅) :
```python
@auth_bp.route('/api/auth/login', methods=['POST'])
def login()
    # Valide username/password
    # Crée JWT access + refresh tokens
    # Crée UserSession en BD
    # Enregistre AuditLog LOGIN
    # Met à jour last_login_at
    # Retourne tokens + profil utilisateur
    # → 200 JSON

@auth_bp.route('/api/auth/refresh', methods=['POST'])
def refresh()
    # Renouvelle access_token via refresh_token
    # Nécessite JWT type 'refresh'
    # → 200 JSON avec nouveau access_token

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout()
    # Ajoute tokens en TokenBlocklist (revocation instantanée)
    # Ferme session via refresh_jti from claims
    # Enregistre AuditLog LOGOUT
    # → 200 JSON

@auth_bp.route('/api/auth/me', methods=['GET'])
def me()
    # Retourne le profil de l'utilisateur authentifié
    # Nécessite JWT access token
    # → 200 JSON

@auth_bp.route('/api/auth/sessions', methods=['GET'])
def sessions()
    # Liste les sessions actives de l'user
    # Retour: [{session_id, ip, user_agent, jti, status, created_at}]
    # → 200 JSON
```

**`users.py`** - Gestion utilisateurs (30 tests ✅) :
```python
@users_bp.route('/api/users', methods=['GET'])
def get_users()
    # Retourne tous les utilisateurs
    # Pagination optionnelle
    # → 200 JSON

@users_bp.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id)
    # Retourne un utilisateur par ID
    # → 200 JSON ou 404 Not Found

@users_bp.route('/api/users', methods=['POST'])
def create_user()
    # Crée nouvel utilisateur
    # Valide: username unique, email unique, role enum
    # Hash password avec pbkdf2
    # → 201 Created ou 400/422 errors

@users_bp.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id)
    # Met à jour l'utilisateur (champs partiels OK)
    # Vérifie uniqueness username/email si modifiés
    # → 200 JSON ou 404

@users_bp.route('/api/users/<int:user_id>/status', methods=['PATCH'])
def update_user_status(user_id)
    # Bascule is_active (true/false)
    # → 200 JSON ou 400/404

@users_bp.route('/api/users/<int:user_id>/password', methods=['PATCH'])
def update_user_password(user_id)
    # 🔐 JWT REQUIRED
    # Valide old_password (401 si incorrect)
    # Vérifie new_password ≠ old_password (400)
    # Vérifie longueur min (8 chars)
    # Hash nouveau password pbkdf2
    # → 200 JSON ou 400/401/403/404

@users_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id)
    # Supprime utilisateur
    # → 204 No Content ou 404
```

#### 🚧 À IMPLÉMENTER

**`clients.py`, `sites.py`, `contacts.py`** - CRUD CRM (✅) :
- GET /api/clients (sites, contacts)
- GET /api/clients/<id>
- POST /api/clients
- PUT /api/clients/<id>
- DELETE /api/clients/<id>
- PATCH /api/clients/<id>/status

**`demandes.py`** - CRUD Demandes (À créer, multitype) :
- GET /api/demandes (tous types)
- GET /api/demandes/<id>
- POST /api/demandes (détecte type via body)
- PUT /api/demandes/<id>
- PATCH /api/demandes/<id>/status
- DELETE /api/demandes/<id>

**`interactions.py`** - Interactions (À créer) :
- POST /api/demandes/<id>/interactions (créer)
- GET /api/demandes/<id>/interactions (lister)
- PUT /api/interactions/<id> (modifier)
- DELETE /api/interactions/<id> (supprimer)

**`fichiers.py`** - Fichiers (À créer) :
- POST /api/fichiers/upload (multipart/form-data)
- GET /api/fichiers/<id> (download)
- DELETE /api/fichiers/<id>
- GET /api/fichiers (listing)

### 6. **Tests** (`tests/`) — 103+ TESTS IMPLÉMENTÉS ✅

**Framework** : pytest 8.1+ avec pytest-flask  
**Coverage** : ~97% du code backend

**Fixtures globales** (`conftest.py`) — réutilisables dans tous les tests :
- `app()` — Instance Flask avec config TestingConfig + SQLite :memory:
- `db(app)` — Session BD nettoyée avant/après chaque test
- `client(app)` — Test client Flask pour requêtes HTTP
- `user_permanencier/manager/admin/inactive(db)` — Fixtures utilisateurs prédéfinis
- `tokens_permanencier(client)` — JWT tokens après login automatique
- `auth_headers/refresh_headers(tokens)` — Authorization headers

**Tests implémentés** (103+ tests, tous PASSANTS) :

✅ **test_auth_login.py** — 6 tests
- Login valide retourne 200 + profil + tokens
- Création UserSession + AuditLog
- Mise à jour last_login_at

✅ **test_auth_logout.py** — 24 tests
- Logout ferme session + revoque tokens
- Tokens dans blocklist immédiatement
- Autres sessions ne sont pas affectées
- Multi-logout detection

✅ **test_auth_refresh.py** — Tests
- Refresh token retourne nouveau access_token
- Validation JWT type

✅ **test_users.py** — 30 tests
- List (3) — Récupération tous users
- Get (3) — Get user + 404 handling
- Create (6) — Validation unique/enum/required fields
- Update (4) — Mise à jour partielle + uniqueness
- Status (3) — Activer/désactiver
- Password (9) — 🔐 Bien testé (old pwd, longueur, distinctness)
- Delete (2) — Suppression + 404

✅ **test_clients.py, test_sites.py, test_contacts.py** — 46+ tests
- List/Get/Create/Update/Delete avec multi-tenant
- Validations d'unicité composite

**Commandes de test** :
```bash
pytest -v                      # Tous les tests
pytest tests/test_auth_login.py::test_login_valide_retourne_200  # Spécifique
pytest --cov=app --cov-report=html                              # Couverture
```

### 7. **Base de données** (`database.py`)

Fichier de compatibilité réexportant `db` depuis `app/__init__.py`.
Permet : `from database import db`

### 8. **Migrations** (`migrations/`)

Géré par **Alembic** (via Flask-Migrate) :
- `versions/` — Fichiers de migration SQL
- `1b1167b1417e_initial_migration_create_all_tables.py` — ✅ Migration initiale (toutes tables créées)
- `env.py` — Configuration Alembic
- `alembic.ini` — Paramètres de connexion

**Workflow** :
```bash
flask db init           # Initialiser la gestion de migration
flask db migrate -m "message"  # Créer une migration
flask db upgrade        # Appliquer les migrations
```

---

## Architecture Frontend (Vue.js)

### Structure source (`frontend/src/`)

```
src/
├── main.js           # Entry point (montage Vue)
├── App.vue           # Composant racine
├── api/              # Configuration Axios et intercepteurs
│   ├── axios.js
│   └── interceptor.js
├── services/         # Services API (e.g., authService)
│   └── authService.js
├── assets/           # Images, styles globaux (avec Vite)
├── components/       # Composants réutilisables (avec Vite)
│   └── HelloWorld.vue
├── router/           # Vue Router configuration
│   └── index.js      # Routes de l'application
├── store/            # State management (Pinia)
│   └── index.js
└── views/            # Pages du routeur
    ├── HomeView.vue
    └── AboutView.vue
```

### Configuration

- **`package.json`** - Dépendances Node.js (Vue 3, Vue Router, Pinia, Axios)
- **`vue.config.js`** - Configuration webpack Custom
- **`babel.config.js`** - Configuration Babel (transpilation)
- **`jsconfig.json`** - Alias et configuration TypeScript (optionnel)
- **`Dockerfile`** - Build multi-stage :
  1. Build Node.js
  2. Serve avec Nginx lightweight
- **Serveur dev** : Vite (http://localhost:8080)

---

## Configuration Docker

### 3 Services orchestrés (`docker-compose.yml`)

```yaml
Services:
├── db               # PostgreSQL 15-Alpine
│   ├── Port : 5432
│   ├── Image : postgres:15-alpine
│   ├── Volume : postgres_data (persistance)
│   └── Creds : permatel_user / permatel_pass
│
├── backend          # Flask API
│   ├── Port : 5000
│   ├── Build : ./backend/Dockerfile
│   ├── Dépend de : db
│   ├── Volume : ./backend (hot-reload en dev)
│   └── Env : DATABASE_URL, JWT_SECRET_KEY, FLASK_APP, FLASK_ENV
│
└── frontend         # Vue.js SPA
    ├── Port : 8080
    ├── Build : ./frontend/Dockerfile
    ├── Volume : ./frontend (live reload)
    └── Env : Variables de build si nécessaire

Network: permatel_network (bridge custom)
```

### Dockerfiles

#### Backend (`backend/Dockerfile`)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0"]
```

#### Frontend (`frontend/Dockerfile`)
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 8080
CMD ["npm", "run", "serve"]
```

---

## Variables d'Environnement (`.env`)

**Fichier backend** (`backend/.env`) :
```env
BINDADDR=0.0.0.0
PORT=5000
SECRET_KEY=your-secret-key
DEBUG=True
```

**Fichier docker-compose** - Injecté via `environment:` :
```yaml
DATABASE_URL: postgresql://permatel_user:permatel_pass@db:5432/permatel
JWT_SECRET_KEY: your-secret-key-change-in-production
FLASK_APP: app
FLASK_ENV: development
```

---

## Flux de Déploiement

### Développement
```bash
docker-compose up    # Démarre les 3 services
```
- Backend Flask en mode debug
- HMR (Hot Module Reload) activé pour Vue.js
- PostgreSQL persiste les données

### Migration BD
```bash
cd backend
flask db init         # Premier démarrage
flask db migrate -m "Initial schema"
flask db upgrade      # Appliquer les migrations
```

### Points d'accès
- **Backend API** : http://localhost:5000
- **Health check** : http://localhost:5000/health
- **Frontend SPA** : http://localhost:8080
- **PostgreSQL** : localhost:5432

---

## Dépendances clés

### Backend
| Dépendance | Version | Rôle |
|------------|---------|------|
| Flask | 3.1.3 | Framework web |
| Flask-SQLAlchemy | 3.1.1 | ORM |
| Flask-Migrate | 4.1.0 | Gestion migrations |
| Flask-JWT-Extended | 4.7.1 | Authentification JWT |
| Flask-CORS | 6.0.2 | CORS |
| psycopg2-binary | 2.9.11 | Driver PostgreSQL |
| python-dotenv | 1.2.2 | Variables d'env |
| Marshmallow | 4.3.0 | Sérialisation (optionnel) |

### Frontend
| Dépendance | Rôle |
|------------|------|
| Vue | 3.x - Framework UI |
| Vue Router | 4.x - Routage SPA |
| Pinia | State management |
| Axios | Client HTTP |

---

## Patterns et Bonnes Pratiques

### Backend
✅ **Factory Pattern** - `create_app()` pour créer instances Flask  
✅ **Configuration Externalisée** - Classe config + env vars  
✅ **ORM SQLAlchemy** - Modèles déclaratifs  
✅ **Relations Many-to-Many** - Association tables (contacts_clients, contacts_sites)  
✅ **Migrations Alembic** - Versioning schéma  
✅ **Blueprints** - À implémenter pour organiser routes  
✅ **JWT** - Authentification stateless

### Frontend
✅ **SPA (Single Page Application)** - Vue Router pour navigation  
✅ **Components** - Réutilisabilité  
✅ **State Management** - Pinia (auth store configuré)  
✅ **Build Process** - Vite avec optimisations  

### Infrastructure
✅ **Docker Compose** - Orchestration multi-service  
✅ **Network isolation** - Bridge network custom  
✅ **Volume Management** - Persistance PostgreSQL + hot-reload  
✅ **Service Dependencies** - Backend attend la DB  

---

## Statut d'implémentation (Mis à jour 23 mai 2026)

### Backend : 70% ✅

```
✅ Infrastructure Core (100%)
   ├─ Factory pattern create_app()
   ├─ Configuration (Dev/Prod/Test)
   ├─ Extensions (SQLAlchemy, JWT, Migrate, CORS)
   └─ Error handling globales

✅ Modèles ORM (100% — 15 modèles)
   ├─ Tenant, TenantUser, Prestataire (isolation multi-tenant)
   ├─ User + UserRole + auth methods
   ├─ UserSession + SessionStatus
   ├─ TokenBlocklist
   ├─ AuditLog + AuditAction
   ├─ Client, Site, Contact, AgentSecurite, Demande(+4 types)
   └─ Interaction, Fichier, TelephonyEvent (avec contraintes composites tenant_id)

✅ Authentification JWT (100% — 36 tests)
   ├─ Login/Logout/Refresh
   ├─ Token blocklist revocation
   ├─ Session tracking (JTI, IP, User-Agent)
   ├─ Audit trails
   ├─ Multi-session support
   └─ Password hashing (pbkdf2:sha256:600000)

✅ Gestion Utilisateurs CRUD (100% — 30 tests)
   ├─ List/Get/Create/Update/Delete
   ├─ Status toggle (is_active)
   ├─ Password change endpoint (🔐)
   ├─ Validation (unicité, enum, required)
   └─ Error handling (400/401/403/404/422)

✅ Gestion Clients CRUD (100% — 21 tests)
   ├─ List/Get/Create/Update/Delete
   ├─ Status toggle (is_active)
   ├─ Soft delete (désactivation)
   ├─ Validation (unicité code_client, required fields)
   └─ Error handling (400/404/409)

✅ Gestion Sites CRUD (100% — 25 tests)
   ├─ List/Get/Create/Update/Delete
   ├─ List by client
   ├─ Status toggle (is_active)
   ├─ Soft delete (désactivation)
   ├─ Validation (unicité code_site, required fields, client exists)
   └─ Error handling (400/404/409)

✅ Gestion Contacts CRUD (100%)
   ├─ List/Get/Create/Update/Delete
   ├─ List by Client/Site
   ├─ Liaisons Many-to-Many (clients, sites)
   └─ Error handling (400/404)

✅ Gestion Tenants Multi-tenancy (80%)
   ├─ 8 endpoints pour gestion tenants
   ├─ Isolation logique par tenant_id
   ├─ Gestion de l'active tenant
   └─ Routes ENTIÈREMENT DOCUMENTÉES (manquait dans v1.0.0)

✅ Demandes CRUD (60%)
   ├─ 6 endpoints implémentés (List/Get/Create/Update/Delete/Status)
   ├─ Support 4 types polymorphes (Anomalie, Commande, Planning, Admin)
   ├─ Validation et constraints OK
   └─ Tests complets couvrant les principaux cas

🚧 Interactions (0% — À implémenter)
   └─ Modèle OK, routes à créer

🚧 Fichiers Upload (0% — À implémenter)
   └─ Modèle OK, routes à créer

✅ Tests (100% — 160 tests ✅ TOUS PASSANTS)
   ├─ Auth (36+ tests)
   ├─ Users (30 tests)
   ├─ Clients (21 tests)
   ├─ Sites (25 tests)
   ├─ Demandes (12+ tests)
   ├─ Tenants (10+ tests)
   └─ Coverage: ~99%

✅ Database (100%)
   ├─ PostgreSQL 15 (production)
   ├─ SQLite :memory: (tests)
   ├─ Alembic migrations
   └─ Initial migration (all tables created)

✅ Docker Infrastructure (100%)
   ├─ Backend Dockerfile
   ├─ Frontend Dockerfile
   └─ docker-compose.yml (3 services)
```

### Frontend : 40% ✅

```
✅ Setup (100%)
   ├─ Vue 3 + Vite + Vue Router + Pinia
   ├─ Vuetify 3 properly configured
   ├─ Build configuration (Vite)
   └─ Development server HMR active

✅ Authentication & Layout (100%)
   ├─ Login view avec formulaire complet
   ├─ Header component avec menu
   ├─ Navigation component implémenté
   ├─ Route guards configurés
   └─ Auth store (Pinia) complet

✅ Dashboard Components (80% — 9 composants)
   ├─ DashboardKpiGrid (KPIs cards)
   ├─ DashboardIncidentsTable (incidents list)
   ├─ DashboardCriticalIncidents (alertes critiques)
   ├─ DashboardAgentsStatus (status agents)
   ├─ DashboardSitesOverview (vue sites)
   ├─ DashboardTeamsPerformance (perf équipes)
   ├─ DashboardRealtimeActivity (activité temps réel)
   ├─ DashboardPriorityTasks (tasks prioritaires)
   ├─ DashboardFilterBar (filtrage avancé)
   ├─ Mock data service implémenté (useMockDashboardData.js)
   └─ Total: 18 fichiers Vue découverts

🚧 Intégration API (40%)
   ├─ Dashboard utilise mock data (à remplacer par API)
   ├─ Axios client configuré
   ├─ Services API partiellement implémentés
   └─ À faire: intégration des endpoints backend

🚧 Pages CRUD entités (0%)
   ├─ User management pages
   ├─ Clients / Sites / Contacts pages
   ├─ Demandes / Interactions pages
   └─ File uploads pages

✅ Services (60%)
   ├─ HTTP client (Axios)
   ├─ Auth API service
   ├─ Mock data service
   └─ À faire: services pour autres entités

✅ Store (60%)
   ├─ Pinia auth store complet
   ├─ Composables (useMockDashboardData)
   └─ À faire: stores pour autres modules
```

### DevOps : 60%

```
✅ Containerization (100%)
   ├─ Backend Dockerfile ✅
   ├─ Frontend Dockerfile ✅
   └─ docker-compose.yml ✅

✅ Database (100%)
   └─ Alembic setup + initial migration ✅

🚧 Production (50%)
   ├─ Nginx configuration
   ├─ Gunicorn configuration
   ├─ Secrets management
   └─ Monitoring/Logging
```

---

## Prochaines Étapes / À Implémenter

### Court terme (1-2 semaines)
1. **Clients CRUD** (~15 endpoints avec tests)
2. **Demandes CRUD** (~25 endpoints multi-type avec tests)
3. **Interactions** (~8 endpoints avec tests)

### Moyen terme (3-4 semaines)
4. **Fichiers upload/download** (~10 endpoints)
5. **Recherche et filtrage avancé**
6. **Frontend login + dashboard Vue.js**
7. **Frontend Users management**

### Long terme (1-2 mois)
8. **Permissions par rôle (RBAC)**
9. **Notifications temps réel (WebSocket)**
10. **Export rapports (PDF/Excel)**
11. **Analytics et reporting**
12. **CI/CD Pipeline (GitHub Actions)**

---

## Résumé Technique

| Aspect | Technologie |
|--------|------------|
| **Language Backend** | Python 3.11 |
| **Framework Backend** | Flask 3.1.3 |
| **ORM** | SQLAlchemy 2.0 |
| **Base de données** | PostgreSQL 15 |
| **Authentification** | JWT (Flask-JWT-Extended) |
| **Language Frontend** | JavaScript (Vue 3) |
| **Framework Frontend** | Vue.js 3 + Vue Router |
| **State Management** | Pinia |
| **Orchestration** | Docker Compose |
| **Runtime Node** | Node 20-Alpine |
| **Runtime Python** | Python 3.11-Slim |
