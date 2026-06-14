# PERMATEL - Gestion Intégrée de Demandes et Sessions

**Version** : 1.1.0  
**Dernière mise à jour** : 23 mai 2026  
**Statut** : Backend 70% ✅ / Frontend 40% ✅ | **Tests** : 160 ✅

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

flask db init
flask db migrate -m "initial migration"
flask db upgrade
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
| `JWT_ACCESS_TOKEN_EXPIRES` | Expiration access token | `900` |
| `JWT_REFRESH_TOKEN_EXPIRES` | Expiration refresh token | `2592000` |

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

### Mode Docker

```bash
docker-compose up -d
docker-compose logs -f backend
docker-compose down
```

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

## 🐳 Déploiement

### Principes

Le déploiement reste basé sur Docker Compose pour les environnements simples.  
L'évolution multi-tenant n'impose pas de changement d'infrastructure majeur, mais nécessite :

- migrations Alembic ordonnées,
- backfill des données existantes vers un tenant par défaut,
- mise à jour des tests et seeds,
- surveillance des performances sur les index `tenant_id`.

### Sécurité

À prévoir en complément :
- permissions par rôle **et** par tenant,
- journalisation des changements de tenant actif,
- durcissement des contrôles d'accès,
- étude d'une activation future de **Row-Level Security PostgreSQL**.

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
| `tenants` | Entités propriétaires |
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
| `interactions` | Porte `tenant_id`, relation composite avec demande |
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