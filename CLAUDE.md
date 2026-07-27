# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PERMATEL is a full-stack multi-tenant SaaS for managing security-agent operations: anomaly/order/planning/admin requests ("demandes"), clients/sites/contacts, security agents, an email channel, sessions/audit, and reporting. Backend: Flask + SQLAlchemy + PostgreSQL. Frontend: Vue 3 + Vuetify + Pinia + Vite.

> The root `README.md`, `PROJECT_STRUCTURE.md`, and `DATABASE_SCHEMA.md` are long-running changelog-style docs and contain **stale/contradictory sections** (older content wasn't deleted when new changelog entries were prepended, so "à implémenter" markers coexist with features that are actually shipped). Treat their changelog headers as the most reliable part; verify implementation status against the actual code (`backend/app/routes/`, `backend/app/models/`) rather than trusting the prose tables.

## Commands

### Backend (from `backend/`)
```bash
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
cp .env.example .env

flask run                          # dev server (hot reload)
pytest -v                          # all tests
pytest tests/test_clients.py -v    # single file
pytest tests/test_users.py::test_login_valide_retourne_200 -v  # single test
pytest --cov=app tests/            # coverage

flask db upgrade heads             # apply migrations (multi-head safe)
flask db migrate -m "message"      # generate a migration after model changes
flask init-db                      # create schema if empty, then seed Root tenant + global admin
flask seed                         # idempotent: Root tenant + global admin only (no demo data)
flask sessions-sweep                # expire inactive sessions + purge token blocklist
flask sla-backfill / flask sla-sweep
flask notifications-dispatch
flask mail-fetch                   # IMAP polling for inbound mail
flask superadmin list|create|promote|demote|reset-password|disable|enable
flask seed-prestataires --tenant-code <CODE> --no-dry-run --yes
flask seed-agents --tenant-code <CODE> [--prestataire-code <CODE>] --no-dry-run --yes
```
Note: `create_app()` auto-runs migrations/seeding on startup (empty DB → `db.create_all()` + seed; existing DB → `flask db upgrade heads` if `AUTO_MIGRATE` is set) — this runs every time the app factory is invoked, including under `pytest` against the in-memory SQLite test DB.

### Frontend (from `frontend/`)
```bash
npm install
npm run dev      # or `npm run serve` — both just run vite
npm run build
npm run lint      # eslint . --ext .js,.vue
```

### Docker / production
`docker-compose.yml` is production-oriented (Traefik + Gunicorn + Nginx, hardened). Local day-to-day dev is `flask run` + `npm run dev`, not Docker. See README.md § Déploiement for the full TLS/secrets/cron runbook and the `/dockerdeploy` skill for the pre-flight checklist (gitlinks, UTF-16 requirements.txt, Traefik Docker API version, etc.) before deploying.

## Architecture

### Multi-tenancy model
Shared database, shared schema, isolation by `tenant_id` column (UUID PK on `tenants`). Key rules, enforced app-side (no RLS yet):
- `users` and `tenant_users` (membership + `membership_role`) are global/non-tenant-scoped; a user can belong to multiple tenants.
- Every business table (`clients`, `sites`, `agents_securite`, `demandes`, `interactions`, `fichiers`, `emails`, …) carries `tenant_id` and composite FKs (`FK(tenant_id, x_id) -> x(tenant_id, id)`) so cross-tenant linking is rejected at the DB level, not just in application code.
- `contacts` has no direct `tenant_id` — tenancy is implicit via its `contacts_clients`/`contacts_sites` association tables.
- **Active tenant** is carried in the JWT as the `tid` claim. `backend/app/utils/decorators.py::_load_tenant_context()` resolves it into `flask.g.{user,tenant,tenant_id,is_super_admin,is_tenant_admin,tenant_membership}` on every request. Global `ADMIN` role bypasses membership checks and can access any active tenant; everyone else must have an active `TenantUser` row for the `tid` in the token.
- Route decorators: `@tenant_required` (valid tenant context) and `@tenant_admin_required` (context + `is_tenant_admin`, i.e. global ADMIN or `membership_role == 'admin'`).
- New business tables/columns must answer: does it belong to a tenant, does it need a direct `tenant_id`, can it reference another tenant's row, what isolation rule applies?

### Backend structure (`backend/app/`)
- `__init__.py` — the `create_app()` factory: initializes SQLAlchemy/JWT/CORS/Migrate, auto-runs schema creation+seed or migrations at startup, registers all blueprints, defines Flask CLI commands (`init-db`, `seed`, `sessions-sweep`, `sla-*`, `notifications-dispatch`, `mail-fetch`, `reencrypt-secrets`, `backfill-qualifications`, plus `seed-prestataires`/`seed-agents`/`superadmin` from `app/scripts/`), and installs global error handlers that convert `IntegrityError`→409, `DataError`→400, and swallow all other exceptions into a generic 500 (never leak stack traces).
- `models/` — one file per SQLAlchemy model. `demande.py` implements **single-table inheritance**: `Demande` is the polymorphic base (discriminator `type_demande`), with `DemandeAnomalie`/`DemandeCommande`/`DemandePlanning`/`DemandeAdmin` subclasses adding type-specific columns on the same table.
- `routes/` — one Flask blueprint per resource, registered in `__init__.py`. Business routes are wrapped with `@tenant_required`/`@tenant_admin_required`; `auth.py` and `support.py` are pre-auth/public.
- `services/` — cross-cutting business logic that doesn't belong to a single route: `tenant_features.py` (derives which Workspace tabs/config sections a tenant sees from its `channel_telephonie/email/chat` flags), `agent_kpis.py` (anomaly-vs-incident scoring per agent), `sla.py`, `notifications.py`, `reencrypt.py` (re-encrypts Fernet-sealed secrets after a key rotation).
- `utils/` — `decorators.py` (tenant context, above), `crypto.py` (Fernet encryption for SMTP/IMAP secrets + email content/attachments — key is `SETTINGS_ENCRYPTION_KEY`, must stay stable in prod or encrypted data becomes unreadable), `login_throttle.py` (anti-brute-force on `/auth/login`), `mailer.py`, `invitations.py`.
- `scripts/` — CLI-invoked one-off/maintenance scripts (seeding, session sweep, mail fetch, superadmin management), wired into `app.cli` from `__init__.py`.
- Auth: JWT via Flask-JWT-Extended; access token carries `role` (global `UserRole`: PERMANENCIER/MANAGER/ADMIN) and `tid` (active tenant UUID); revocation via `token_blocklist` table checked in `@jwt.token_in_blocklist_loader`; `user_sessions` tracks JTI/IP/user-agent/status (`active/paused/ended/expired/revoked`).

### Frontend structure (`frontend/src/`)
- `views/` — one Vue file per routed page (Workspace, Dashboard, Reports, Agents, Clients/Sites/Contacts, Settings, Tenants, Supervision, …).
- `components/<domain>/` — grouped by feature area (`dashboard/`, `workspace/`, `settings/`, `agents/`, `sla/`, `supervision/`, `notifications/`, `prises/`).
- `services/` — one file per backend resource, thin Axios wrappers (`http/axios.js` + `http/interceptor.js` handle base config and token refresh/attach).
- `composables/` — reusable reactive data-fetching hooks (`useAgents`, `useClients`, `useSites`, `useUsers`, `usePartners`, `useDashboardDemandesData`, `useIdleLogout`).
- `store/auth.js` (Pinia, persisted) — holds user/token/active-tenant state and exposes `isGlobalAdmin`, `isTenantAdmin`, `features` (from `/api/tenant/features`), `selectTenant`/`switchTenant`.
- `router/index.js` — route guards layered in order: auth required → tenant-selection required (if user belongs to >1 tenant and none active) → `meta.roles` check (`ALL`/`STAFF`/`ADMIN` role sets) → `meta.requiresMemberAdmin` (tenant-admin capability) before entering a route.

### Testing
pytest against SQLite in-memory (`TestingConfig`), fixtures in `backend/tests/conftest.py` provide `default_tenant`, role-specific users (`user_permanencier/manager/admin/inactive`), `agent_securite`, and JWT helpers (`tokens_permanencier`, `auth_headers`, `refresh_headers`). `test_isolation.py` specifically covers cross-tenant access rejection — extend it when adding new tenant-scoped resources.
