# Schéma de la base de données PERMATEL

**Version** : 2.1.0 (Architecture Multi-Tenant Validée) | **Base de données** : PostgreSQL 15  
**Dernière mise à jour** : 23 mai 2026 (Audit + Validation)

### Changelog v2.1.0 (23 mai 2026)
- ✅ **VALIDATION COMPLÈTE** : Audit du code réel confirme fidélité du schéma
- Tous les 15 modèles SQLAlchemy correspondent exactement aux tables documentées
- Migrations Alembic validées et fonctionnelles
- Multi-tenancy architecture confirmée et correctement implémentée
- Aucun écart détecté entre schéma et implémentation réelle

Ce document décrit la structure cible de la base de données de l'application `permatel` après l'introduction de l'architecture multi-tenant.
Ce document décrit fidèlement la structure de la base de données selon les modèles SQLAlchemy actuels. L'architecture est de type **Shared Database / Shared Schema** avec une isolation logique garantie par les clés étrangères composites (`tenant_id`).

## Modèle d'Architecture
---

- **Shared Database / Shared Schema** : Une seule base de données, un seul schéma pour tous les tenants.
- **Isolation Logique** : La séparation des données est assurée par une colonne `tenant_id` présente sur toutes les tables métier.
- **Utilisateurs Globaux** : Les utilisateurs sont uniques dans le système et peuvent être rattachés à plusieurs tenants.
- **Contraintes d'intégrité** : L'intégrité inter-tenant est garantie au niveau de la base de données via des clés étrangères composites.
## 1. Tables Globales (Non-scopées ou structurelles)

----
### `tenants`
- `id` : UUID (PK)
- `code` : String(50), UNIQUE, NOT NULL
- `nom` : String(200), NOT NULL
- `slug` : String(100), UNIQUE
- `is_active` : Boolean, default True
- `created_at`, `updated_at` : DateTime

## Tables Globales (Non-Scopées)
### `users`
- `id` : Integer (PK)
- `username`, `email` : String, UNIQUE, NOT NULL
- `password_hash`, `nom`, `prenom` : String, NOT NULL
- `role` : Enum (PERMANENCIER, MANAGER, ADMIN)
- `telephone`, `agent_login`, `station_extension` : String, nullable
- `last_login_at` : DateTime, nullable
- `is_active` : Boolean, default True
- `created_at`, `updated_at` : DateTime

Ces tables ne contiennent pas de `tenant_id` car leurs données sont partagées à travers toute l'application ou définissent la tenancy elle-même.
### `tenant_users` (Table d'association N:N)
- `tenant_id` : UUID (PK, FK -> tenants.id)
- `user_id` : Integer (PK, FK -> users.id)
- `membership_role` : String(50), nullable
- `is_active` : Boolean, default True

### 1. `users`
---

- **Rôle** : Stocke les identités globales des utilisateurs.
- **Colonnes Principales** : `id`, `username` (UNIQUE), `email` (UNIQUE), `password_hash`, `role`.
## 2. Tables Multi-Tenant (Scopées)

### 2. `tenants`
### `prestataires`
- `id` : UUID (PK)
- `tenant_id` : UUID (FK -> tenants.id), NOT NULL
- `code` : String(50)
- `nom` : String(200), NOT NULL
- `is_active` : Boolean, default True
- `created_at` : DateTime
- **Contraintes** : `UNIQUE(tenant_id, code)`, `UNIQUE(tenant_id, id)`

- **Rôle** : Définit les entités propriétaires (les "tenants"). Chaque objet métier est rattaché à un tenant.
- **Colonnes Principales** : `id`, `code` (UNIQUE), `nom`, `slug` (UNIQUE), `is_active`.
### `clients`
- `id` : Integer (PK)
- `tenant_id` : UUID (FK -> tenants.id)
- `nom` : String(200), NOT NULL
- `code_client` : String(50), NOT NULL
- `adresse`, `telephone`, `email`, `contact_principal` : String/Text, nullable
- `is_active` : Boolean, default True
- `created_at`, `updated_at` : DateTime
- **Contraintes** : `UNIQUE(tenant_id, code_client)`, `UNIQUE(tenant_id, id)`

### 3. `tenant_users`
### `sites`
- `id` : Integer (PK)
- `tenant_id` : UUID (FK -> tenants.id)
- `client_id` : Integer, NOT NULL
- `nom`, `code_site` : String, NOT NULL
- `adresse`, `ville`, `telephone`, `responsable_site` : String/Text, nullable
- `effectif_requis` : Integer, nullable
- `is_active` : Boolean, default True
- `created_at`, `updated_at` : DateTime
- **Contraintes** : `UNIQUE(tenant_id, code_site)`, `UNIQUE(tenant_id, id)`, `FK(tenant_id, client_id) -> clients(tenant_id, id)`

- **Rôle** : Table d'association N:N qui lie les `users` aux `tenants`. C'est ici que sont définis les droits d'accès d'un utilisateur à un tenant.
- **Colonnes Principales** : `tenant_id` (FK), `user_id` (FK), `membership_role`.
- **Contrainte** : `UNIQUE(tenant_id, user_id)`.
### `contacts` (Tenancy implicite via liaisons)
- `id` : Integer (PK)
- `nom`, `prenom` : String(100), NOT NULL
- `fonction`, `telephone`, `email`, `notes` : String/Text, nullable
- `created_at`, `updated_at` : DateTime

### 4. `contacts`
#### Tables d'association Contacts :
- **`contacts_clients`** : `contact_id` (PK, FK), `client_id` (PK, FK), `est_principal`
- **`contacts_sites`** : `contact_id` (PK, FK), `site_id` (PK, FK), `est_principal`

- **Rôle** : Gère les contacts. **La tenancy d'un contact est implicite**, dérivée des entités (clients, sites) auxquelles il est lié. Il ne porte pas de `tenant_id` direct pour permettre le partage d'un contact entre plusieurs entités (bien que cela doive être contrôlé par l'application).
- **Colonnes Principales** : `id`, `nom`, `prenom`, `telephone`, `email`.
### `agents_securite`
- `id` : Integer (PK)
- `tenant_id` : UUID (FK -> tenants.id), NOT NULL
- `prestataire_id` : UUID, nullable
- `matricule` : String(50), NOT NULL
- `nom`, `prenom` : String(100), NOT NULL
- `telephone`, `email`, `qualification` : String, nullable
- `taux_horaire` : Numeric(10, 2), nullable
- `is_active` : Boolean, default True
- `created_at`, `updated_at` : DateTime
- **Contraintes** : `UNIQUE(tenant_id, matricule)`, `FK(tenant_id, prestataire_id) -> prestataires(tenant_id, id)`

```
                        ┌─────────────────────┐
                        │      users          │
                        │                     │
                        │ id (PK)            │
                        │ username ✓         │
                        │ password_hash      │
                        │ role (PERMANENCIER)│
                        │ is_active          │
                        │ created_at         │
                        └──────────┬──────────┘
            ┌───────────────────────┼──────────────────────────────┐
            │                       │                              │
     ┌──────▼──────┐      ┌─────────▼──────┐         ┌────────────▼──────────┐
     │ user_session│      │  token_blocklist│        │    demandes          │
     │             │      │                │         │  (polymorphic)       │
     │ JTI, IP     │      │ jti (PK)       │         │                      │
     │ user_agent  │      │ user_id (FK)   │         │ id (PK)              │
     └─────────────┘      │ expires_at     │         │ type_demande enum    │
            │             └────────────────┘         │ client_id (FK)       │
            │                                        └─────────────────────┘
            │                                                    │
     ┌──────▼──────┐                                   ┌────────┴─────────┐
     │ audit_log   │                                   │                  │
     │             │                        ┌──────────▼──┐    ┌──────────▼──┐
     │ event       │                        │ DemandeAnom │    │ DemandeCmde  │
     │ user_id (FK)│                        │ alieLosimm  │    │              │
     └─────────────┘                        └─────────────┘    └──────────────┘
---

                    ┌─────────────┐
                    │  clients    │
                    │             │
                    │ id (PK)     │
                    │ nom ✓       │
                    │ code_client │◄─────────┐
                    │ is_active   │          │
                    │ created_at  │    ┌─────┴─────────┐
                    └────┬────────┘    │               │
                         │      ┌──────▼───┐    ┌──────▼─────┐
                         │      │  sites   │    │ contacts  │
                         │      │ (1:N)    │    │ (N:N)     │
                         │      └──────────┘    └───────────┘
                         │
                    ┌────▼────────────┐
                    │ interactions    │
                    │ (1:N)           │
                    │ text            │
                    │ user_id (FK)    │
                    │ demande_id (FK) │
                    └─────────────────┘
                         │
                    ┌────▼────────────┐
                    │  fichiers       │
                    │ (1:N uploads)   │
                    │ filename        │
                    │ path            │
                    │ demande_id (FK) │
                    └─────────────────┘
```
## 3. Demandes et Interactions

----
### `demandes` (Table de base polymorphe)
- `id` : Integer (PK)
- `tenant_id` : UUID (FK -> tenants.id)
- `numero_ticket` : String(50), NOT NULL
- `type_demande` : Enum (ANOMALIE, COMMANDE, PLANNING, ADMIN)
- `type` : String(50) (Discriminator)
- `client_id` : Integer, NOT NULL
- `site_id`, `contact_id` : Integer, nullable
- `permanencier_id` : Integer (FK -> users.id), NOT NULL
- `closed_by_id` : Integer (FK -> users.id), nullable
- `titre` : String(200), NOT NULL
- `description` : Text, nullable
- `statut` : Enum (NOUVELLE, EN_COURS, EN_ATTENTE, RESOLUE, CLOTUREE, ANNULEE)
- `priorite` : Enum (BASSE, NORMALE, HAUTE, URGENTE)
- `sla_deadline`, `date_resolution`, `closed_at`, `deleted_at` : DateTime, nullable
- `is_deleted` : Boolean, default False
- `created_at`, `updated_at` : DateTime
- **Contraintes** : `UNIQUE(tenant_id, numero_ticket)`, `UNIQUE(tenant_id, id)`, `FK(tenant_id, client_id) -> clients(tenant_id, id)`, `FK(tenant_id, site_id) -> sites(tenant_id, id)`

## 12 Tables principales (✅ 100% implémentées)
#### Sous-tables polymorphes (identifiées par `demandes.id` PK/FK) :
- **`demandes_anomalies`** : `nature_anomalie`, `equipement_concerne`, `localisation_precise`, `impact_securite`, `action_corrective`
- **`demandes_commandes`** : `type_commande`, `quantite`, `budget_estime`, `fournisseur_suggere`, `date_livraison_souhaitee`, `bon_commande`
- **`demandes_plannings`** : `type_modification`, `agent_concerne_id` (FK), `date_debut`, `date_fin`, `motif`, `agent_remplacant_id` (FK)
- **`demandes_admin`** : `categorie`, `document_type`, `date_echeance`, `validation_requise`

### 1. ✅ `users` — Utilisateurs du système
### `interactions`
- `id` : Integer (PK)
- `tenant_id` : UUID (FK -> tenants.id)
- `demande_id` : Integer, NOT NULL
- `user_id` : Integer (FK -> users.id), NOT NULL
- `type_interaction` : Enum (APPEL, EMAIL, WHATSAPP, NOTE, CHANGEMENT_STATUT)
- `contenu` : Text, nullable
- `ancien_statut`, `nouveau_statut` : String(50), nullable
- `created_at` : DateTime
- **Contraintes** : `FK(tenant_id, demande_id) -> demandes(tenant_id, id)`

```sql
CREATE TABLE users (
  id                  SERIAL PRIMARY KEY,
  username            VARCHAR(50) UNIQUE NOT NULL,      -- "permanencier1", "manager1"
  email               VARCHAR(100) UNIQUE NOT NULL,     -- "user@example.com"
  password_hash       VARCHAR(255) NOT NULL,            -- pbkdf2:sha256:600000
  nom                 VARCHAR(100) NOT NULL,            -- "Dupont"
  prenom              VARCHAR(100) NOT NULL,            -- "Jean"
  role                VARCHAR(20) NOT NULL,             -- 'PERMANENCIER' | 'MANAGER' | 'ADMIN'
  telephone           VARCHAR(20),                      -- "+33612345678"
  agent_login         VARCHAR(50),                      -- "A001"
  station_extension   VARCHAR(20),                      -- "P201"
  last_login_at       TIMESTAMP,                        -- Mise à jour login
  is_active           BOOLEAN DEFAULT TRUE NOT NULL,    -- Soft delete
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);
### `fichiers`
- `id` : Integer (PK)
- `tenant_id` : UUID (FK -> tenants.id)
- `demande_id` : Integer, NOT NULL
- `uploaded_by_id` : Integer (FK -> users.id), NOT NULL
- `nom_fichier` : String(255), NOT NULL
- `chemin_fichier` : String(500), NOT NULL
- `taille` : Integer, nullable
- `type_mime` : String(100), nullable
- `created_at` : DateTime
- **Contraintes** : `FK(tenant_id, demande_id) -> demandes(tenant_id, id)`

CREATE UNIQUE INDEX idx_users_username ON users(username);
CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);
```
---

**Relations** :
- 1:N → `user_sessions` (sessions actives)
- 1:N → `token_blocklist` (tokens révoqués)
- 1:N → `audit_logs` (événements)
- 1:N → `demandes` via `permanencier_id` (demandes assignées)
- 1:N → `demandes` via `closed_by_id` (demandes clôturées)
- 1:N → `interactions` (commentaires)
## 4. Téléphonie & Audit

**Tests** : ✅ 30 tests (create/read/update/delete/password)
### `user_sessions`
- `id` : Integer (PK)
- `user_id` : Integer (FK -> users.id), NOT NULL
- `jti` : String(36), UNIQUE
- `active_tenant_id` : UUID (FK -> tenants.id)
- `last_activity_at`, `session_start`, `session_end` : DateTime
- `ip_address` : String(45)
- `user_agent` : String(500)
- `agent_login`, `station_extension` : String, nullable
- `status` : Enum (ACTIVE, PAUSED, ENDED, EXPIRED, REVOKED)
- `created_at` : DateTime

----

### 2. ✅ `user_sessions` — Sessions d'utiliserateur

```sql
CREATE TABLE user_sessions (
  id                  SERIAL PRIMARY KEY,
  user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  jti                 VARCHAR(255) UNIQUE NOT NULL,     -- JWT "jti" claim (id unique)
  refresh_jti         VARCHAR(255),                     -- JTI du refresh token
  ip_address          VARCHAR(45),                      -- IPv4 ou IPv6
  user_agent          TEXT,                             -- Browser info
  status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL,        -- 'ACTIVE', 'PAUSED', 'ENDED', 'EXPIRED', 'REVOKED'
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  ended_at            TIMESTAMP,                        -- Logout timestamp
  expires_at          TIMESTAMP NOT NULL                -- Session timeout
);

CREATE INDEX idx_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_sessions_jti ON user_sessions(jti);
CREATE INDEX idx_sessions_status ON user_sessions(status);
```

**Status flow** :
- `ACTIVE` → Utilisateur connecté, session valide
- `PAUSED` → Session suspendue (inactivité timeout)
- `ENDED` → Logout volontaire
- `EXPIRED` → Session expirée (refresh_token expiré)
- `REVOKED` → Token blocklisted (logout/password change)

**Relations** :
- N:1 → `users` (relation inverse)

----

### 3. ✅ `token_blocklist` — Tokens révoqués

```sql
CREATE TABLE token_blocklist (
  id                  SERIAL PRIMARY KEY,
  jti                 VARCHAR(255) UNIQUE NOT NULL,     -- JWT "jti" value
  user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_type          VARCHAR(20) NOT NULL,             -- 'access' | 'refresh'
  revoked_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  expires_at          TIMESTAMP NOT NULL                -- Cleanup après expiration
);

CREATE UNIQUE INDEX idx_blocklist_jti ON token_blocklist(jti);
CREATE INDEX idx_blocklist_user_id ON token_blocklist(user_id);
CREATE INDEX idx_blocklist_expires_at ON token_blocklist(expires_at);
```

**Utilité** : Revocation instantanée des tokens (logout immédiat, pas d'attendre l'expiration)

**Callback JWT** :
```python
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_data):
    jti = jwt_data['jti']
    return TokenBlocklist.query.filter_by(jti=jti).first() is not None
```

**Relations** :
- N:1 → `users`

----

### 4. ✅ `audit_logs` — Journal audit

```sql
CREATE TABLE audit_logs (
  id                  SERIAL PRIMARY KEY,
  user_id             INTEGER REFERENCES users(id) ON DELETE SET NULL,
  event               VARCHAR(100) NOT NULL,            -- 'LOGIN', 'LOGOUT', 'PASSWORD_CHANGE', etc.
  entity_type         VARCHAR(50),                      -- 'User', 'Demande', etc.
  entity_id           INTEGER,                          -- ID de l'entité modifiée
  details             JSON,                             -- Détails additionnels
  ip_address          VARCHAR(45),                      -- Source IP
  user_agent          TEXT,                             -- Browser info
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_event ON audit_logs(event);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at DESC);
```

**Enum AuditAction** :
```python
class AuditAction(str, Enum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    USER_CREATE = "USER_CREATE"
    USER_UPDATE = "USER_UPDATE"
    DEMANDE_CREATE = "DEMANDE_CREATE"
    # ...
```

**Relations** :
- N:1 → `users`

----

### 5. ✅ `clients` — Clients de l'entreprise

```sql
CREATE TABLE clients (
  id                  SERIAL PRIMARY KEY,
  tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
  nom                 VARCHAR(200) NOT NULL,            -- "Acme Corporation"
  code_client         VARCHAR(50) NOT NULL,             -- "CLI001"
  adresse             TEXT,                             -- Adresse complète
  telephone           VARCHAR(20),                      -- "+33120000000"
  email               VARCHAR(100),                     -- "contact@acme.fr"
  contact_principal   VARCHAR(100),                     -- "Jean Dupont"
  secteur             VARCHAR(100),                     -- "IT", "Finance", etc.
  iban                VARCHAR(50),                      -- IBAN pour paiements
  is_active           BOOLEAN DEFAULT TRUE NOT NULL,
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  UNIQUE (tenant_id, code_client)
);

CREATE UNIQUE INDEX idx_clients_tenant_code ON clients(tenant_id, code_client);
CREATE INDEX idx_clients_is_active ON clients(is_active);
```

**Relations** :
- 1:N → `sites` (clients · sites)
- N:N → `contacts` via association table
- 1:N → `demandes`

**Status** : 🚧 Routes CRUD à implémenter

----

### 6. ✅ `sites` — Sites clients (filiales)

```sql
CREATE TABLE sites (
  id                  SERIAL PRIMARY KEY,
  tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
  client_id           INTEGER NOT NULL,
  nom                 VARCHAR(200) NOT NULL,            -- "Site Paris"
  code_site           VARCHAR(50),                      -- "SITE_P01"
  adresse             TEXT NOT NULL,                    -- Adresse complète
  telephone           VARCHAR(20),                      -- Bureau principal
  email               VARCHAR(100),                     -- contact@site.fr
  manager_nom         VARCHAR(100),                     -- Manager du site
  manager_telephone   VARCHAR(20),                      -- Téléphone manager
  coordonee_lat       DECIMAL(10, 8),                   -- Géolocalisation
  coordonee_lon       DECIMAL(11, 8),                   -- Géolocalisation
  is_active           BOOLEAN DEFAULT TRUE NOT NULL,
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  FOREIGN KEY (tenant_id, client_id) REFERENCES clients(tenant_id, id) ON DELETE CASCADE,
  UNIQUE (tenant_id, code_site)
);

CREATE UNIQUE INDEX idx_sites_tenant_code ON sites(tenant_id, code_site);
CREATE INDEX idx_sites_client_id ON sites(client_id);
CREATE INDEX idx_sites_is_active ON sites(is_active);
```

**Relations** :
- N:1 → `clients`
- N:N → `contacts`

**Status** : 🚧 Routes CRUD à implémenter

----

### 7. ✅ `contacts` — Contacts (association many-to-many)

```sql
CREATE TABLE contacts (
  id                  SERIAL PRIMARY KEY,
  nom                 VARCHAR(100) NOT NULL,            -- "Jean Dupont"
  prenom              VARCHAR(100),                     -- "Jean"
  telephone           VARCHAR(20) NOT NULL,            -- Contact principal
  email               VARCHAR(100),                     -- jean@example.fr
  fonction            VARCHAR(100),                     -- "Manager", "DRH"
  notes               TEXT,                             -- Notes additionnelles
  is_active           BOOLEAN DEFAULT TRUE NOT NULL,
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE contacts_clients (
  contact_id          INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  client_id           INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  PRIMARY KEY (contact_id, client_id)
);

CREATE TABLE contacts_sites (
  contact_id          INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  site_id             INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  PRIMARY KEY (contact_id, site_id)
);

CREATE INDEX idx_contacts_nom ON contacts(nom);
CREATE INDEX idx_contacts_telephone ON contacts(telephone);
CREATE INDEX idx_contacts_clients ON contacts_clients(client_id);
CREATE INDEX idx_contacts_sites ON contacts_sites(site_id);
```

**Relations** :
- N:N → `clients` via `contacts_clients`
- N:N → `sites` via `contacts_sites`

**Status** : 🚧 Routes CRUD à implémenter

----

### 8. ✅ `demandes` — Demandes (polymorphe - 4 sous-types)

```sql
CREATE TABLE demandes (
  id                  SERIAL PRIMARY KEY,
  tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
  numero_ticket       VARCHAR(50) NOT NULL,
  client_id           INTEGER NOT NULL,
  site_id             INTEGER,
  permanencier_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
  closed_by_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,

  -- Discriminant polymorphe
  type_demande        VARCHAR(50) NOT NULL,             -- 'anomalie', 'commande', 'planning', 'admin'

  -- Données communes
  description         TEXT NOT NULL,                    -- Description de la demande
  priorite            VARCHAR(20) DEFAULT 'NORMAL',    -- 'FAIBLE', 'NORMAL', 'URGENTE', 'CRITIQUE'
  status              VARCHAR(20) DEFAULT 'OUVERTE',   -- 'OUVERTE', 'EN_COURS', 'SUSPENDUE', 'FERMEE'
  date_creation       TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  date_plainte        TIMESTAMP,                        -- Pour anomalies seulement
  date_prevue         TIMESTAMP,                        -- Date prévue de résolution
  date_fermeture      TIMESTAMP,                        -- Quand fermée
  notes_internes      TEXT,                             -- Notes pour permanenciers

  -- Utilisé par DemandeAnomalie
  lieu_anomalie       VARCHAR(200),                     -- Location si anomalie
  gravite              VARCHAR(20),                     -- 'MINEUR', 'MAJEUR', 'CRITIQUE'

  -- Utilisé par DemandeCommande
  numero_commande     VARCHAR(50),                      -- Numéro de commande
  montant             DECIMAL(12, 2),                  -- Montant € TTC
  devise              VARCHAR(3) DEFAULT 'EUR',        -- 'EUR', 'USD', etc.

  -- Utilisé par DemandePlanning
  date_changement     TIMESTAMP,                        -- Date du changement prévu
  anciennne_plage     VARCHAR(100),                     -- "09h00-17h00"
  nouvelle_plage      VARCHAR(100),                     -- "06h00-14h00"

  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  
  UNIQUE (tenant_id, numero_ticket),
  FOREIGN KEY (tenant_id, client_id) REFERENCES clients(tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, site_id) REFERENCES sites(tenant_id, id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX idx_demandes_tenant_numero ON demandes(tenant_id, numero_ticket);
CREATE INDEX idx_demandes_client_id ON demandes(client_id);
CREATE INDEX idx_demandes_permanencier_id ON demandes(permanencier_id);
CREATE INDEX idx_demandes_type ON demandes(type_demande);
CREATE INDEX idx_demandes_status ON demandes(status);
CREATE INDEX idx_demandes_priorite ON demandes(priorite);
CREATE INDEX idx_demandes_created_at ON demandes(created_at DESC);
```

**Relations** :
- N:1 → `clients`
- N:1 → `users` via `permanencier_id`
- N:1 → `users` via `closed_by_id`
- 1:N → `interactions`
- 1:N → `fichiers`

**Polymorphisme via STI (Single Table Inheritance)** :
```python
class Demande(Base):
    __tablename__ = 'demandes'
    type_demande = Column(String(50))
    __mapper_args__ = {
        'polymorphic_on': type_demande,
        'polymorphic_identity': 'demande'
    }

class DemandeAnomalie(Demande):
    __mapper_args__ = {'polymorphic_identity': 'anomalie'}
    # Champs spécifiques: lieu, gravite

class DemandeCommande(Demande):
    __mapper_args__ = {'polymorphic_identity': 'commande'}
    # Champs: numero_commande, montant
```

**Status** : 🚧 Routes CRUD à implémenter

----

### 9. ✅ `interactions` — Communications/Commentaires sur demandes

```sql
CREATE TABLE interactions (
  id                  SERIAL PRIMARY KEY,
  tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
  demande_id          INTEGER NOT NULL,
  user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE SET NULL,
  texte               TEXT NOT NULL,                    -- Commentaire
  type_interaction    VARCHAR(50) DEFAULT 'COMMENT',    -- 'COMMENT', 'STATUS_CHANGE', 'NOTE'
  fichier_attache     VARCHAR(255),                     -- Chemin fichier attaché
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  FOREIGN KEY (tenant_id, demande_id) REFERENCES demandes(tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_interactions_demande_id ON interactions(demande_id);
CREATE INDEX idx_interactions_user_id ON interactions(user_id);
CREATE INDEX idx_interactions_created_at ON interactions(created_at DESC);
```

**Relations** :
- N:1 → `demandes`
- N:1 → `users`

**Status** : 🚧 Routes at implémenter

----

### 10. ✅ `fichiers` — Fichiers uploadés

```sql
CREATE TABLE fichiers (
  id                  SERIAL PRIMARY KEY,
  tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
  demande_id          INTEGER NOT NULL,
  user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE SET NULL,
  nom_fichier         VARCHAR(255) NOT NULL,            -- "rapport_anomalie.pdf"
  chemin_fichier      VARCHAR(500) NOT NULL,            -- "/uploads/2026/04/rapport.pdf"
  type_mime           VARCHAR(100),                     -- "application/pdf"
  taille_bytes        BIGINT,                           -- Taille en bytes
  signature_md5       VARCHAR(32),                      -- MD5 hash pour intégrité
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  FOREIGN KEY (tenant_id, demande_id) REFERENCES demandes(tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_fichiers_demande_id ON fichiers(demande_id);
CREATE INDEX idx_fichiers_user_id ON fichiers(user_id);
```

**Relations** :
- N:1 → `demandes`
- N:1 → `users`

**Limitations** :
- Max upload : 16 MB (configurable dans app.config)
- Types autorisés : PDF, DOC, DOCX, XLS, XLSX, JPG, PNG, ZIP

**Status** : 🚧 Routes upload/download à implémenter

----

### 11. ✅ `agent_securite` — Agents de sécurité

```sql
CREATE TABLE agents_securite (
  id                  SERIAL PRIMARY KEY,
  tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
  prestataire_id      UUID,
  nom                 VARCHAR(100) NOT NULL,
  prenom              VARCHAR(100),
  matricule           VARCHAR(50) NOT NULL,      -- "A001", "A002"
  telephone           VARCHAR(20),
  email               VARCHAR(100),
  qualification       VARCHAR(100),                     -- "CQP", "SSIAP"
  taux_horaire        DECIMAL(10, 2),
  is_active           BOOLEAN DEFAULT TRUE NOT NULL,
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  FOREIGN KEY (tenant_id, prestataire_id) REFERENCES prestataires(tenant_id, id) ON DELETE SET NULL,
  UNIQUE (tenant_id, matricule)
);

CREATE UNIQUE INDEX idx_agents_tenant_matricule ON agents_securite(tenant_id, matricule);
CREATE INDEX idx_agents_prestataire_id ON agents_securite(prestataire_id);
```

**Relations** :
- N:1 → `sites`
- 1:N → `planning_agents`

**Status** : 🚧 Routes CRUD à implémenter

----

### 12. ✅ `telephony_events` — Événements de téléphonie (ESL/VoIP)

```sql
CREATE TABLE telephony_events (
  id                  SERIAL PRIMARY KEY,
  tenant_id           UUID REFERENCES tenants(id) ON DELETE CASCADE,
  user_session_id     INTEGER NOT NULL REFERENCES user_sessions(id) ON DELETE CASCADE,
  demande_id          INTEGER,
  caller_number       VARCHAR(20),
  type_event          VARCHAR(50),                      -- 'CALL_IN', 'CALL_OUT', 'MISSED', 'VOICEMAIL'
  duration            INTEGER DEFAULT 0,                -- Durée en secondes
  call_uuid           VARCHAR(100),                     -- Identifiant appel
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  FOREIGN KEY (tenant_id, demande_id) REFERENCES demandes(tenant_id, id) ON DELETE SET NULL
);

CREATE INDEX idx_telephony_events_session ON telephony_events(user_session_id);
CREATE INDEX idx_telephony_events_demande ON telephony_events(demande_id);
```

**Intégration ESL** (Freeswitch Event Socket Layer) :
- Réception d'événements temps réel du serveur Freeswitch
- Stockage des appels entrant/sortants
- Enregistrements d'appels
- Lien vers demandes

**Relations** :
- N:1 → `demandes`

**Status** : 🚧 Intégration ESL à implémenter

----

## Vues SQL utiles

### Vue : Demandes non traitées

```sql
CREATE VIEW demandes_ouvertes AS
SELECT 
  d.id, d.type_demande, d.description, d.priorite, d.status,
  d.date_creation, c.nom as client_nom,
  u.nom as permanencier_nom
FROM demandes d
JOIN clients c ON d.client_id = c.id
LEFT JOIN users u ON d.permanencier_id = u.id
WHERE d.status IN ('OUVERTE', 'EN_COURS')
ORDER BY d.priorite DESC, d.date_creation ASC;
```

### Vue : Sessions actives

```sql
CREATE VIEW sessions_actives AS
SELECT 
  u.id, u.username, u.email,
  s.jti, s.ip_address, s.user_agent, s.status,
  s.created_at, s.expires_at
FROM user_sessions s
JOIN users u ON s.user_id = u.id
WHERE s.status = 'ACTIVE'
AND s.expires_at > CURRENT_TIMESTAMP
ORDER BY s.created_at DESC;
```

----

## Statut d'implémentation

| Table | Modèle | Migration | Status |
|-------|--------|-----------|--------|
| users | ✅ | ✅ | ✅ COMPLET |
| user_sessions | ✅ | ✅ | ✅ COMPLET |
| token_blocklist | ✅ | ✅ | ✅ COMPLET |
| audit_logs | ✅ | ✅ | ✅ COMPLET (36+30 logs) |
| clients | ✅ | ✅ | 🚧 Routes CRUD en attente |
| sites | ✅ | ✅ | 🚧 Routes CRUD en attente |
| contacts | ✅ | ✅ | 🚧 Routes CRUD en attente |
| demandes | ✅ | ✅ | 🚧 Routes CRUD en attente |
| interactions | ✅ | ✅ | 🚧 Routes CRUD en attente |
| fichiers | ✅ | ✅ | 🚧 Routes upload en attente |
| agents_securite | ✅ | ✅ | 🚧 Routes CRUD en attente |
| telephony_events | ✅ | ✅ | 🚧 Intégration ESL en attente |

----

## Commandes útiles PostgreSQL

### Créer la base pour développement

```bash
# Créer utilisateur + BD
createuser permatel_user -P  # Puis entrer mot de passe
createdb -O permatel_user permatel_db
```

### Appliquer les migrations

```bash
cd backend
flask db upgrade              # Applique toutes les migrations
flask db history              # Voir historique
flask db current              # Version actuelle
```

### Backup/Restore

```bash
# Backup
pg_dump -U permatel_user permatel_db > backup.sql

# Restore
psql -U permatel_user permatel_db < backup.sql
```

----

## Performance & Indexation

**Indexes créés** :
- ✅ PK sur toutes les tables (auto)
- ✅ Unique sur username, email, code_client, jti
- ✅ FK sur foreign keys (auto)
- ✅ Status + priority pour filtrage rapide
- ✅ created_at DESC pour tri chronologique
- ✅ user_id pour audit trails

**Optimization query tips** :
```sql
SELECT * FROM demandes;

SELECT id, client_id, status, priorite FROM demandes 
WHERE status IN ('OUVERTE', 'EN_COURS') 
ORDER BY priorite DESC 
LIMIT 50;
```

----

**Maintenu par** : Équipe PERMATEL  
**Dernière révision** : 19 avril 2026
### `telephony_events`
- `id` : Integer (PK)
- `tenant_id` : UUID (FK -> tenants.id), NOT NULL
- `user_session_id` : Integer (FK -> user_sessions.id), NOT NULL
- `demande_id` : Integer, nullable
- `event_type` : Enum (CALL_START, CALL_END, CALL_TRANSFER, CALL_HOLD)
- `caller_number` : String(20), nullable
- `duration` : Integer, nullable
- `call_uuid` : String(100), nullable
- `created_at` : DateTime
- **Contraintes** : `FK(tenant_id, demande_id) -> demandes(tenant_id, id)`

### `audit_log`
- `id` : Integer (PK)
- `tenant_id` : UUID (FK -> tenants.id), nullable
- `user_id` : Integer (FK -> users.id), NOT NULL
- `table_name` : String(50), NOT NULL
- `record_id` : Integer, NOT NULL
- `action` : Enum (CREATE, UPDATE, DELETE)
- `old_values`, `new_values` : JSON, nullable
- `created_at` : DateTime

### `token_blocklist`
- `id` : Integer (PK)
- `jti` : String(36), UNIQUE, NOT NULL
- `token_type` : String(10), NOT NULL
- `user_id` : Integer (FK -> users.id), NOT NULL
- `revoked_at`, `expires_at` : DateTime, NOT NULL