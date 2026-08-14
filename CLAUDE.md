# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PERMATEL is a full-stack multi-tenant SaaS for managing security-agent operations: anomaly/order/planning/admin requests ("demandes"), clients/sites/contacts, security agents, an email channel, sessions/audit, and reporting. Backend: Flask + SQLAlchemy + PostgreSQL. Frontend: Vue 3 + Vuetify + Pinia + Vite.

> The root `README.md`, `PROJECT_STRUCTURE.md`, and `DATABASE_SCHEMA.md` are long-running changelog-style docs and contain **stale/contradictory sections** (older content wasn't deleted when new changelog entries were prepended, so "à implémenter" markers coexist with features that are actually shipped). Treat their changelog headers as the most reliable part; verify implementation status against the actual code (`backend/app/routes/`, `backend/app/models/`) rather than trusting the prose tables.

> `AUDIT_PERMATEL.md`, `ODOO_INTEGRATION_PLAN.md`, `TELEPHONIE_INTEGRATION_PLAN.md`, and `docs/cdc/` are **planning/audit documents, not implementation status** — treat their changelog/phase tables as the most reliable status source (they're actively maintained per-phase), but verify against actual code for anything not covered here. Updated 2026-08-14 (Odoo status unchanged; Téléphonie extended beyond Phase 14, see below):
> - **Odoo**: genuinely not started — zero `odoo_*` code anywhere (models, routes, connector). `ODOO_INTEGRATION_PLAN.md`'s "implémentation non démarrée" status is accurate.
> - **Téléphonie**: Phases 11–14 are built and live — `backend/app/routes/telephony.py` (ingestion, KPIs, active calls, CDR webhook, agent presence), `backend/app/models/pbx.py` (`PbxConnector`/`PbxConnectorDomain`, tenant-scoped), a standalone `connector/` process (ESL adapter for FusionPBX, its own test suite), WebSocket live updates, and `Supervision > Téléphonie` / `Rapports > Téléphonie` frontend tabs — see `TELEPHONIE_INTEGRATION_PLAN.md` §7–9 for the authoritative phase-by-phase detail. Only **Phase 15 (Asterisk/AMI connector)** is not started; FusionPBX/ESL is production-connected. Don't assume telephony is dormant because an older note here said so — verify against `telephony.py`/`connector/` directly if in doubt.
> - **Téléphonie — remote execution (13-14/08, not a numbered phase, extends Phase 12's connector)**: PERMATEL can now trigger `agent_login`/`agent_logout`/`agent_status_change` jobs on FusionPBX (`_dispatch_pbx_job`, Redis pub/sub, no persisted job table — the connector's ESL connection is already permanent/synchronous). Pause codes (`pbx_pause_codes`, tenant-scoped, protected `"0"` row) are carried as a real FreeSWITCH CUSTOM event (`sendevent`) — **the only unconfirmed-against-real-traffic piece of this feature**, see `TELEPHONIE_INTEGRATION_PLAN.md` §8.10. `UserSession.status` now actually gets set to `PAUSED`/`ACTIVE` in lockstep with PBX presence (the enum value existed for a long time but was dead code before this — see the `user_sessions` note below).

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

flask db heads                     # list current head(s) — run BEFORE creating a new migration
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
Note: `create_app()` auto-runs migrations/seeding on startup (empty DB → `db.create_all()` + seed; existing DB → `flask db upgrade heads` if `AUTO_MIGRATE` is set) — this runs every time the app factory is invoked, including under `pytest` against the in-memory SQLite test DB. Guarded by a Postgres advisory lock (no-op under SQLite) so concurrent Gunicorn workers don't race the same migration/seed on startup.

⚠️ **Before running `flask db migrate` for a new model change, always run `flask db heads` first and confirm there is exactly one head.** Parallel work (multiple sessions/branches touching models around the same time) has produced diverging migration heads at least 4 times in this project's history, each requiring a manual merge migration (`down_revision = (head_a, head_b)`) after the fact — cheap to avoid up front, annoying to untangle later. If `flask db heads` ever shows more than one, resolve it with a merge migration before adding new work on top.

Redis (`REDIS_URL` config var) backs the login anti-brute-force counter (`app/utils/login_throttle.py`) with a graceful in-memory fallback if unset/unreachable — required in multi-worker production so the lockout threshold isn't diluted per-worker; optional for local dev.

Optional `GEOIP_DB_PATH` (default `/app/geoip/GeoLite2-Country.mmdb`) points at a local MaxMind GeoLite2-Country `.mmdb` file for the IP-flag feature in Sessions reports (`app/utils/geoip.py`) — lookup is 100% offline, no IP ever leaves the server. The `.mmdb` itself is never committed (MaxMind license forbids redistribution) and isn't part of this repo; `docker-compose.yml` bind-mounts `./backend/geoip/` read-only into the backend container. Missing file = graceful no-op (no flag shown), never an error.

### Frontend (from `frontend/`)
```bash
npm install
npm run dev      # or `npm run serve` — both just run vite
npm run build
npm run lint      # eslint . --ext .js,.vue
```

### Docker / production
`docker-compose.yml` is production-oriented (Gunicorn + Nginx + Postgres + Redis, hardened). **Traefik is not part of this compose file** — it's a separate, shared reverse-proxy stack (`traefik/docker-compose.yml`, see `traefik/README.md`) meant to run once per server and front multiple applications via the external `traefik_public` Docker network; PERMATEL's `frontend` container just joins that network and carries `traefik.*` labels. Local day-to-day dev is `flask run` + `npm run dev`, not Docker. See README.md § Déploiement for the full TLS/secrets/cron runbook and the `/dockerdeploy` skill for the pre-flight checklist (gitlinks, UTF-16 requirements.txt, Traefik Docker API version, etc.) before deploying.

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
- `utils/` — `decorators.py` (tenant context, above), `crypto.py` (Fernet encryption; two patterns coexist: manual `encrypt_secret()`/`decrypt_secret()` used by `SmtpSetting`, and the `EncryptedText` SQLAlchemy `TypeDecorator` used transparently on `Email.subject/body_text/body_html` — prefer `EncryptedText` for new encrypted columns, key is `SETTINGS_ENCRYPTION_KEY`, must stay stable in prod or encrypted data becomes unreadable, `services/reencrypt.py` handles key rotation), `login_throttle.py` (anti-brute-force on `/auth/login`, Redis-backed with in-memory fallback), `geoip.py` (MaxMind GeoLite2 country lookup for the IP-flag feature, `GEOIP_DB_PATH`, graceful no-op if the `.mmdb` file is absent), `mailer.py`, `invitations.py`.
- Migration convention: French docstring explaining intent, explicit data-safety guards (abort with offending IDs rather than silently dropping/guessing on a NOT NULL tightening or new FK — see `a3178519ad55_tenant_id_not_null_clients_sites.py`), and a standing preference for `String` over native Postgres `ENUM` on any column expected to grow new values (`c5e10bf50c26_use_varchar_for_enums.py` converted several columns for exactly this reason — follow suit for new status/type columns rather than reaching for `Enum`).
- `scripts/` — CLI-invoked one-off/maintenance scripts (seeding, session sweep, mail fetch, superadmin management), wired into `app.cli` from `__init__.py`.
- Auth: JWT via Flask-JWT-Extended; access token carries `role` (global `UserRole`: PERMANENCIER/MANAGER/ADMIN) and `tid` (active tenant UUID); revocation via `token_blocklist` table checked in `@jwt.token_in_blocklist_loader`; `user_sessions` tracks JTI/IP/user-agent/status (`active/paused/ended/expired/revoked`) — `paused` is driven by PBX presence (`On Break` ↔ `Available`, `_record_and_broadcast_agent_status_event()` in `routes/telephony.py`, called from self-service status + `routes/auth.py` login/logout), not something the sweep or the session lifecycle sets on its own.

### Frontend structure (`frontend/src/`)
- `views/` — one Vue file per routed page (Workspace, Dashboard, Reports, Agents, Clients/Sites/Contacts, Settings, Tenants, Supervision, …).
- `components/<domain>/` — grouped by feature area (`dashboard/`, `workspace/`, `settings/`, `agents/`, `sla/`, `supervision/`, `notifications/`, `prises/`).
- `services/` — one file per backend resource, thin Axios wrappers (`http/axios.js` + `http/interceptor.js` handle base config and token refresh/attach).
- `composables/` — reusable reactive data-fetching hooks (`useAgents`, `useClients`, `useSites`, `useUsers`, `usePartners`, `useDashboardDemandesData`, `useIdleLogout`).
- `store/auth.js` (Pinia, persisted) — holds user/token/active-tenant state and exposes `isGlobalAdmin`, `isTenantAdmin`, `features` (from `/api/tenant/features`), `selectTenant`/`switchTenant`.
- `router/index.js` — route guards layered in order: auth required → tenant-selection required (if user belongs to >1 tenant and none active) → `meta.roles` check (`ALL`/`STAFF`/`ADMIN` role sets) → `meta.requiresMemberAdmin` (tenant-admin capability) before entering a route.

### Testing
pytest against SQLite in-memory (`TestingConfig`), fixtures in `backend/tests/conftest.py` provide `default_tenant`, role-specific users (`user_permanencier/manager/admin/inactive`), `agent_securite`, and per-role JWT helpers (`tokens_permanencier`/`auth_headers`, `tokens_manager`/`auth_headers_manager`, `tokens_admin`/`auth_headers_admin`, `refresh_headers`) — match the fixture to the route's actual `@role_required`, since e.g. `/api/users` and `/api/contacts` DELETE are ADMIN-only and will 403 under the default `auth_headers` (PERMANENCIER). Note the global-ADMIN quirk: unlike a single-tenant standard user, ADMIN is *never* auto-selected into a tenant at login (even with only one accessible), so `tokens_admin` must explicitly call `/api/auth/select-tenant` to get a token carrying `tid` before hitting any `@tenant_required` route. `test_isolation.py` specifically covers cross-tenant access rejection — extend it when adding new tenant-scoped resources.
