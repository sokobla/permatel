# PERMATEL - Gestion Intégrée de Demandes et Sessions

**Version** : 1.0.0  
**Dernière mise à jour** : 19 avril 2026  
**Statut** : En développement  

---

## 📋 Table des matières

- [Vue d'ensemble](#-vue-densemble)
- [Caractéristiques](#-caractéristiques)
- [Stack Technologique](#-stack-technologique)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Configuration](#-configuration)
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
4. **Admin** : Gère les utilisateurs et audite les actions

---

## ⭐ Caractéristiques

### ✅ Implémentées

- **Authentification JWT** - Login/Logout avec tokens access + refresh
- **Gestion des sessions** - Suivi des connexions utilisateur par JTI, IP, user-agent
- **Token blocklist** - Révocation immédiate des tokens en cas de logout
- **Audit trails** - Journal complet de toutes les actions d'authentification
- **Gestion des utilisateurs** - CRUD avec rôles (Permanencier, Manager, Admin)
- **Change password endpoint** - Mise à jour sécurisée du mot de passe
- **API de santé** - Endpoint `/health` pour monitoring
- **CORS intégré** - Autorise requêtes cross-origin
- **Tests exhaustifs** - 57+ tests unitaires validant tous les endpoints
- **Gestion Clients, Sites, Contacts** - API REST complète pour le CRM de base
- **Docker multi-conteneur** - Backend Flask + PostgreSQL + Frontend Vue.js

### 🚧 En développement

- Endpoints CRUD pour demandes (toutes les variantes)
- Endpoints pour interactions et fichiers
- Recherche/filtrage avancé
- Permissions et autorisations par rôle
- Notification en temps réel (WebSocket)
- Export de rapports (PDF)

---

## 🛠️ Stack Technologique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| **Backend** | Flask | 3.1.3 |
| **ORM** | SQLAlchemy | 2.0+ |
| **Authentification** | Flask-JWT-Extended | 4.5.3 |
| **Base de données** | PostgreSQL | 15 (prod) |
| **Tests** | pytest + pytest-flask | 9.0.3 |
| **Migrations BD** | Flask-Migrate (Alembic) | 4.0.5 |
| **Frontend** | Vue.js | 3.2.13 |
| **Routage Frontend** | Vue Router | 4.0.3 | (avec Vite)
| **State Management** | Pinia | 3.0+ |
| **Orchestration** | Docker Compose | 1.29+ |

---

## 🏗️ Architecture

### Schéma global

```
┌─────────────────────────────────────────────────────────────────┐
│                     PERMATEL Application                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐           ┌──────────────────────┐        │
│  │   Vue.js SPA    │           │    Flask API REST    │        │
│  │  (localhost:80) │◄──────────┤  (localhost:5000)    │        │
│  │                 │  HTTP     │                      │        │
│  │  • Router       │           │  • Blueprints:       │        │
│  │  • Pinia Store  │           │    - auth.py (✅)    │        │
│  │  • Components   │           │    - users.py (✅)   │        │
│  │                 │           │    - clients.py      │        │
│  │                 │           │    - demandes.py     │        │
│  │                 │           │    - interactions.py │        │
│  │                 │           │                      │        │
│  │                 │           │  • Models: 12        │        │
│  │                 │           │  • Tests: 57+        │        │
│  │                 │           │                      │        │
│  └─────────────────┘           └──────────────────────┘        │
│                                         │                       │
│                                    SQLAlchemy                   │
│                                         │                       │
│                                         ▼                       │
│  ┌────────────────────────────────────────────────────────┐   │
│  │       PostgreSQL 15                                    │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │   │
│  │  │ users        │  │ demandes     │  │ clients    │  │   │
│  │  │ audit_logs   │  │ interactions │  │ sites      │  │   │
│  │  │ user_session │  │ fichiers     │  │ contacts   │  │   │
│  │  │ token_bl     │  │ (4 types)    │  │ agents_sec │  │   │
│  │  └──────────────┘  └──────────────┘  └────────────┘  │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Flux d'authentification

```
1. CLIENT                2. BACKEND              3. DATABASE
   │                        │                      │
   ├─POST login────────────>│                      │
   │  (username, pwd)       ├─Recherche User──────>│
   │                        │                      │<─User + hash
   │                        ├─Vérifie password     │
   │                        │                      │
   │                        ├─Crée tokens (JWT)   │
   │                        ├─Crée UserSession───>│
   │                        │                      │<─Session créée
   │                        ├─Crée AuditLog──────>│
   │                        │                      │<─Log créé
   │                        │                      │
   │<──200 + tokens────────┤                      │
   │  (access, refresh)     │                      │
   │  (session_id, user)    │                      │
   │
   ├─GET /api/users/───────>│ @jwt_required()    │
   │  Header: JWT token     ├─Décide JTI         │
   │                        ├─Vérifie TokenBL───>│
   │                        │                      │<─Not revoked
   │                        ├─Retourne data      │
   │<──200 + data──────────┤                      │
   │
   ├─POST logout───────────>│                      │
   │  Header: JWT token     ├─Ajoute à BlockList─>│
   │                        │                      │<─Ajouté
   │                        ├─Clôt Session──────>│
   │                        │                      │<─Session fermée
   │<──200───────────────┤                      │
```

---

## 📦 Installation

### Prérequis

- **Python** 3.11+
- **Node.js** 20+ (pour frontend)
- **PostgreSQL** 15+ (production) / SQLite (développement)
- **Docker & Docker Compose** (optionnel, pour conteneurisation)

### 1. Cloner le repository

```bash
git clone <repo-url>
cd permatel
```

### 2. Backend - Configuration Python

```bash
cd backend

# Créer un environnement virtuel
python -m venv .venv

# Activer l'environnement
# Sur macOS/Linux:
source .venv/bin/activate
# Sur Windows:
.venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Créer le fichier .env
cp .env.example .env
# Éditer .env avec vos paramètres
```

**Contenu `.env` minimal** :

```env
FLASK_ENV=development
FLASK_APP=app:create_app
FLASK_DEBUG=1
SECRET_KEY=votre-cle-secrete-dev
JWT_SECRET_KEY=votre-cle-jwt-dev
DATABASE_URL=sqlite:///permatel.db
UPLOAD_FOLDER=./uploads
CORS_ORIGINS=["http://localhost:8080"]
```

### 3. Frontend - Configuration Node.js

```bash
cd frontend

# Installer les dépendances
npm install

# (Optionnel) Installer globalement Vue CLI
npm install -g @vue/cli
```

### 4. Base de données

```bash
cd backend

# Initialiser les migrations
flask db init

# Créer une migration initiale
flask db migrate -m "initial migration"

# Appliquer les migrations
flask db upgrade

# (Optionnel) Seeder les données de test
flask seed-users
```

---

## ⚙️ Configuration

### Variables d'environnement (`.env`)

| Variable | Valeur | Description |
|----------|--------|-------------|
| `FLASK_ENV` | `development`, `production`, `testing` | Mode d'exécution |
| `FLASK_DEBUG` | `1` ou `0` | Mode debug (hot-reload) |
| `SECRET_KEY` | `<random-string>` | Clé secrète Flask |
| `JWT_SECRET_KEY` | `<random-string>` | Clé secrète JWT |
| `DATABASE_URL` | `postgresql://...` | URL base de données |
| `DB_HOST` | `localhost` | Hôte PostgreSQL |
| `DB_PORT` | `5432` | Port PostgreSQL |
| `DB_USER` | `postgres` | Utilisateur PostgreSQL |
| `DB_PASSWORD` | `password` | Mot de passe PostgreSQL |
| `DB_NAME` | `permatel_db` | Nom de la base |
| `UPLOAD_FOLDER` | `./uploads` | Dossier uploads |
| `CORS_ORIGINS` | `["http://localhost:8080"]` | CORS allowed hosts |
| `JWT_ACCESS_TOKEN_EXPIRES` | `900` | Expiration access (sec) |
| `JWT_REFRESH_TOKEN_EXPIRES` | `2592000` | Expiration refresh (30j) |
| `SESSION_INACTIVITY_TIMEOUT` | `30` | Timeout inactivité (min) |

### Structure des fichiers configuration

```
backend/
├── app/
│   ├── __init__.py          # Factory + setup
│   ├── config.py            # Classes Config (Dev/Prod/Test)
│   ├── models/              # ORM models
│   ├── routes/              # Blueprints API
│   └── utils/               # Helpers
├── .env                      # Variables d'environnement
├── .env.example             # Template .env
└── requirements.txt         # Dépendances Python
```

---

## 🚀 Démarrage Rapide

### Mode développement (sans Docker)

```bash
# Terminal 1 - Backend Flask
cd backend
source .venv/bin/activate
flask run

# Sortie :
# Running on http://127.0.0.1:5000
# Press CTRL+C to quit

# Terminal 2 - Frontend Vue.js
cd frontend
npm run serve

# Sortie :
# App running at:
#  - Local:   http://localhost:8080/
#  - Network: http://192.168.x.x:8080/
```

### Mode Docker

```bash
# Lancer tous les services
docker-compose up -d

# Backend : http://localhost:5000
# Frontend : http://localhost:8080
# PostgreSQL : localhost:5432

# Voir les logs
docker-compose logs -f backend

# Arrêter
docker-compose down
```

### Tests

```bash
cd backend

# Exécuter tous les tests
pytest -v

# Résumé :
# 57 tests passés en ~35 secondes

# Tests par module
pytest tests/test_auth_login.py -v
pytest tests/test_users.py -v

# Avec couverture
pytest --cov=app tests/
```


## 🔌 API REST

Tous les endpoints nécessitant une authentification attendent un `Authorization: Bearer <access_token>` header.

### ✅ Authentification - `/api/auth` (Implémenté)

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "permanencier1",
  "password": "Password123!"
}
```

**Réponse 200** :
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "session_id": 1,
  "expires_in": 900,
  "user": {
    "id": 1,
    "username": "permanencier1",
    "nom": "Martin",
    "prenom": "Alice",
    "role": "PERMANENCIER",
    "email": "perm1@permatel.ma",
    "is_active": true,
    "last_login_at": "2026-04-19T18:30:45"
  }
}
```

#### 2. Refresh Token

```http
POST /api/auth/refresh
Authorization: Bearer <refresh_token>
```

**Réponse 200** :
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 900
}
```

#### 3. Logout

```http
POST /api/auth/logout
Authorization: Bearer <access_token>
```

**Réponse 200** :
```json
{
  "message": "Déconnexion réussie."
}
```

#### 4. Profil utilisateur

```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

**Réponse 200** :
```json
{
  "id": 1,
  "username": "permanencier1",
  "email": "perm1@permatel.ma",
  "nom": "Martin",
  "prenom": "Alice",
  "role": "PERMANENCIER",
  "is_active": true
}
```

#### 5. Sessions actives

```http
GET /api/auth/sessions
Authorization: Bearer <access_token>
```

**Réponse 200** :
```json
{
  "sessions": [
    {
      "id": 1,
      "status": "ACTIVE",
      "ip_address": "127.0.0.1",
      "user_agent": "Mozilla/5.0...",
      "session_start": "2026-04-19T18:30:45",
      "last_activity_at": "2026-04-19T18:35:20"
    }
  ]
}
```

---

### Gestion des utilisateurs - `/api/users`

#### 1. Lister les utilisateurs

```http
GET /api/users
```

**Réponse 200** :
```json
[
  {
    "id": 1,
    "username": "permanencier1",
    "email": "perm1@permatel.ma",
    "nom": "Martin",
    "prenom": "Alice",
    "role": "PERMANENCIER",
    "is_active": true
  }
]
```

#### 2. Récupérer un utilisateur

```http
GET /api/users/{user_id}
```

**Réponse 200** :
```json
{
  "id": 1,
  "username": "permanencier1",
  "email": "perm1@permatel.ma",
  "nom": "Martin",
  "prenom": "Alice",
  "role": "PERMANENCIER",
  "telephone": "0612345678",
  "agent_login": "mat001",
  "station_extension": "101",
  "is_active": true,
  "created_at": "2026-04-19T18:00:00",
  "updated_at": "2026-04-19T18:30:00"
}
```

#### 3. Créer un utilisateur

```http
POST /api/users
Content-Type: application/json

{
  "username": "newuser",
  "email": "new@permatel.ma",
  "nom": "Dupont",
  "prenom": "Jean",
  "role": "PERMANENCIER",
  "password": "SecurePass123!",
  "telephone": "0612345679"
}
```

**Réponse 201** :
```json
{
  "message": "Utilisateur créé",
  "id": 2
}
```

#### 4. Mettre à jour un utilisateur

```http
PUT /api/users/{user_id}
Content-Type: application/json
Authorization: Bearer <access_token>

{
  "email": "newemail@permatel.ma",
  "nom": "Martin Updated",
  "is_active": true
}
```

**Réponse 200** :
```json
{
  "message": "Utilisateur mis à jour"
}
```

#### 5. Changer le statut (actif/inactif)

```http
PATCH /api/users/{user_id}/status
Content-Type: application/json

{
  "is_active": false
}
```

**Réponse 200** :
```json
{
  "message": "Statut utilisateur mis à jour"
}
```

#### 6. Changer le mot de passe

```http
PATCH /api/users/{user_id}/password
Content-Type: application/json
Authorization: Bearer <access_token>

{
  "old_password": "OldPass123!",
  "new_password": "NewPass456!"
}
```

**Réponse 200** :
```json
{
  "message": "Mot de passe mis à jour avec succès"
}
```

**Erreurs possibles** :
- `400` - Nouveau mot de passe trop court (< 8 caractères)
- `401` - Ancien mot de passe incorrect / pas d'authentification
- `403` - Tentative de changer le mot de passe d'un autre utilisateur

#### 7. Supprimer un utilisateur

```http
DELETE /api/users/{user_id}
Authorization: Bearer <access_token>
```

**Réponse 200** :
```json
{
  "message": "Utilisateur supprimé"
}
```

---

## 🧪 Tests

### Structure des tests

```
backend/tests/
├── conftest.py              # Fixtures pytest globales
├── test_auth_login.py       # 6 tests login
├── test_auth_logout.py      # 24 tests logout + refresh
├── test_auth_refresh.py     # Tests refresh token
└── test_users.py            # 30 tests CRUD + password
```

### Résultats des tests

| Module | Tests | Statut |
|--------|-------|--------|
| `test_auth_login.py` | 6 | ✅ PASS |
| `test_auth_logout.py` | 24 | ✅ PASS |
| `test_users.py` | 30 | ✅ PASS |
| **Total** | **60** | **✅ PASS** |

### Exécuter les tests

```bash
# Tous les tests
pytest -v

# Test spécifique
pytest tests/test_users.py::TestUpdatePassword::test_update_password_valide_retourne_200 -v

# Avec couverture de code
pytest --cov=app tests/

# Tests en watch mode (réexécution automatique)
pytest-watch
```

### Fixtures disponibles

Les fixtures prédéfinies dans `conftest.py` :

```python
@pytest.fixture
def app()                   # Instance Flask test
@pytest.fixture
def db()                    # Session DB nettoyée
@pytest.fixture
def client(app)             # Test client Flask
@pytest.fixture
def user_permanencier(db)  # User PERMANENCIER
@pytest.fixture
def user_manager(db)        # User MANAGER
@pytest.fixture
def user_admin(db)          # User ADMIN
@pytest.fixture
def tokens_permanencier()   # Tokens JWT après login
@pytest.fixture
def auth_headers()          # Header Authorization avec token
@pytest.fixture
def refresh_headers()       # Header avec refresh token
```

---

## 🐳 Déploiement

### Docker Compose

**Fichier `docker-compose.yml`** :

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: permatel_user
      POSTGRES_PASSWORD: permatel_pass
      POSTGRES_DB: permatel_db
    ports:
      - "5432:5432"

  backend:
    build: ./backend
    ports:
      - "5000:5000"
    depends_on:
      - db
    environment:
      FLASK_ENV: production
      DATABASE_URL: postgresql://permatel_user:permatel_pass@db:5432/permatel_db
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "80:8080"
    depends_on:
      - backend
    environment:
      - BACKEND_URL=http://localhost:5000

volumes:
  postgres_data:
```

### Lancement en production

```bash
# Build et démarrage
docker-compose -f docker-compose.yml up -d

# Vérifier les services
docker-compose ps

# Logs
docker-compose logs -f backend

# Migration en production
docker-compose exec backend flask db upgrade

# Seeding données initiales
docker-compose exec backend flask seed-users
```

### Considérations de sécurité

✅ **À faire** :
- [ ] Générer `SECRET_KEY` et `JWT_SECRET_KEY` forts (32+ chars)
- [ ] Utiliser HTTPS en production (certificat SSL/TLS)
- [ ] Configurer des headers de sécurité (CORS strict)
- [ ] Implémenter rate limiting sur endpoints sensibles
- [ ] Configurer les backups PostgreSQL
- [ ] Monitorer les logs d'audit
- [ ] Utiliser des secrets managers (Vault, AWS Secrets)

---

## 📁 Structure du Projet

```
permatel/
├── backend/
│   ├── app/
│   │   ├── __init__.py              # Factory Flask
│   │   ├── config.py                # Configurations
│   │   ├── models/
│   │   │   ├── __init__.py          # Exports
│   │   │   ├── user.py              # User + UserRole (✅)
│   │   │   ├── user_session.py      # UserSession (✅)
│   │   │   ├── token_blocklist.py   # TokenBlocklist (✅)
│   │   │   ├── audit_log.py         # AuditLog (✅)
│   │   │   ├── client.py            # Client
│   │   │   ├── site.py              # Site
│   │   │   ├── contact.py           # Contact
│   │   │   ├── demande.py           # Demande + 4 sous-types
│   │   │   ├── interaction.py       # Interaction
│   │   │   ├── fichier.py           # Fichier
│   │   │   ├── agent_securite.py    # AgentSecurite
│   │   │   └── telephony_event.py   # TelephonyEvent
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # Auth endpoints (✅)
│   │   │   ├── users.py             # Users CRUD + password (✅)
│   │   │   ├── clients.py           # Clients CRUD (✅)
│   │   │   ├── sites.py             # Sites CRUD (✅)
│   │   │   ├── contacts.py          # Contacts CRUD (✅)
│   │   │   ├── demandes.py          # À implémenter
│   │   │   └── interactions.py      # À implémenter
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── logger.py            # Logging configuration
│   ├── tests/
│   │   ├── conftest.py              # Fixtures pytest
│   │   ├── test_auth_login.py       # 6 tests
│   │   ├── test_auth_logout.py      # 24 tests
│   │   ├── test_auth_refresh.py     # Tests refresh
│   │   └── test_users.py            # 30 tests
│   ├── migrations/                  # Alembic migrations
│   ├── uploads/                     # Fichiers uploadés
│   ├── app.py                       # Point d'entrée
│   ├── manage.py                    # CLI commands
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example

├── frontend/
│   ├── src/
│   │   ├── main.js                  # Vue entry point
│   │   ├── App.vue                  # Root component
│   │   ├── components/              # Composants réutilisables
│   │   ├── views/                   # Pages principales
│   │   ├── router/
│   │   │   └── index.js             # Vue Router config
│   │   └── store/
│   │       └── index.js             # Pinia store
│   ├── public/
│   │   └── index.html               # HTML template
│   ├── package.json
│   ├── vue.config.js
│   ├── Dockerfile
│   └── README.md

├── docker-compose.yml               # Orchestration services
├── PROJECT_STRUCTURE.md             # Documentation architecture
├── DATABASE_SCHEMA.md               # Schéma BD détaillé
├── README.md                        # Ce fichier
└── requirements.txt                 # Dépendances root
```

---

## 🗄️ Base de Données

### Vue d'ensemble des tables

| Table | Colonnes | Relation | Status |
|-------|----------|----------|--------|
| `users` | 16 | User → Sessions, Demandes, Interactions | ✅ |
| `user_sessions` | 10 | UserSession → User | ✅ |
| `token_blocklist` | 5 | TokenBlocklist → User | ✅ |
| `audit_logs` | 8 | AuditLog → User | ✅ |
| `clients` | 10 | Client ↔ Sites, Contacts, Demandes | ✅ |
| `sites` | 11 | Site → Client, Demandes, Contacts | ✅ |
| `contacts` | 8 | Contact ↔ Clients, Sites | ✅ |
| `demandes` | 15 | Demande → Client, Site, Contact, User | 🚧 |
| `demandes_anomalies` | +5 | Hérite de Demande | 🚧 |
| `demandes_commandes` | +5 | Hérite de Demande | 🚧 |
| `demandes_plannings` | +7 | Hérite de Demande | 🚧 |
| `demandes_admin` | +3 | Hérite de Demande | 🚧 |
| `interactions` | 6 | Interaction → Demande, User | 🚧 |
| `fichiers` | 8 | Fichier → Demande, User | 🚧 |
| `agents_securite` | 10 | AgentSecurite | 🚧 |
| `telephony_events` | 8 | TelephonyEvent → Demande | 🚧 |

### Modèle de données complet

Voir [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) pour le schéma détaillé avec :
- Champs complets de chaque table
- Types de données SQLAlchemy
- Relations et foreign keys
- Enums et contraintes
- Indexes

---

## 👥 Contribution

### Workflow de contribution

1. **Créer une branche** : `git checkout -b feature/ma-feature`
2. **Développer** : Implémenter la fonctionnalité
3. **Tester** : `pytest -v` doit passer à 100%
4. **Commit** : Messages clairs et cohérents
5. **Push & PR** : Créer une pull request avec description

### Standards de code

- **Python** : PEP 8, max 99 caractères
- **Tests** : Couverture min 80%, fixtures réutilisables
- **Noms** : Descriptifs en français/anglais mixte
- **Docstrings** : Format Google/NumPy
- **Endpoints** : RESTful, codes HTTP explicites

### Checklist avant commit

- [ ] Tests passent : `pytest -v`
- [ ] Code formaté : `black app/`
- [ ] Couverture OK : `pytest --cov=app`
- [ ] Pas de secrets en dur (`.env` uniquement)
- [ ] Docstrings à jour
- [ ] Migrations en place si modèle modifié

---

## 🔧 Troubleshooting

### Problèmes communs

#### 1. "ModuleNotFoundError: No module named 'app'"

**Cause** : `.venv` non activé ou `requirements.txt` non installés  
**Solution** :
```bash
source .venv/bin/activate  # ou .venv\Scripts\activate sur Windows
pip install -r requirements.txt
```

#### 2. "Database connection refused"

**Cause** : PostgreSQL non lancé / mauvaise URL  
**Solution** :
```bash
# Vérifier PostgreSQL
docker ps | grep postgres

# Ou démarrer PostgreSQL localement
brew services start postgresql  # macOS
sudo service postgresql start   # Linux
```

#### 3. Tests échouent : "sqlite3.OperationalError: no such table"

**Cause** : BD pas créée en mode test  
**Solution** :
```bash
cd backend
pytest tests/ --create-db  # ou simplement relancer
```

#### 4. JWT token invalide : "Subject must be a string"

**Cause** : `identity` doit être string, pas int  
**Solution** : Utiliser `create_access_token(identity=str(user.id))`

#### 5. CORS errors en développement

**Cause** : Frontend et Backend sur ports différents  
**Solution** : Vérifier `CORS_ORIGINS` dans `.env` :
```env
CORS_ORIGINS=["http://localhost:8080"]  # Frontend Vue
```

#### 6. Docker : "Permission denied" sur uploads

**Cause** : Permissions fichiers dans volume  
**Solution** :
```bash
docker-compose exec backend chmod -R 755 uploads/
```

---

## 📚 Documentation complémentaire

- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Architecture détaillée
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Schéma BD complet
- [API Documentation](#-api-rest) - Endpoints disponibles

---

## 📞 Support

Pour toute question ou bug report :
1. Vérifier la section [Troubleshooting](#-troubleshooting)
2. Consulter la documentation dans le repo
3. Créer une issue GitHub détaillée

---

## 📜 License

**Propriétaire** : PERMATEL  
**Statut** : En développement - 2026

---

**Dernière mise à jour** : 19 avril 2026  
**Maintaineur** : Équipe Développement PERMATEL
