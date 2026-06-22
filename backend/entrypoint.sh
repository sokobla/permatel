#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# PERMATEL — Entrypoint backend (production)
#   1. attend la disponibilité de la base,
#   2. applique les migrations Alembic (idempotent),
#   3. amorce le tenant Root + admin global (idempotent),
#   4. démarre Gunicorn.
# ─────────────────────────────────────────────────────────────────────────────
set -eu

: "${DATABASE_URL:?DATABASE_URL est requis}"
: "${JWT_SECRET_KEY:?JWT_SECRET_KEY est requis}"
: "${SETTINGS_ENCRYPTION_KEY:?SETTINGS_ENCRYPTION_KEY est requis}"

GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-60}"

echo "[entrypoint] Attente de la base de données…"
python - <<'PY'
import os, time, sys
import psycopg2
url = os.environ["DATABASE_URL"]
for i in range(30):
    try:
        psycopg2.connect(url).close()
        print("[entrypoint] Base disponible.")
        sys.exit(0)
    except Exception as exc:
        print(f"[entrypoint] DB indisponible ({i+1}/30): {exc}")
        time.sleep(2)
sys.exit("[entrypoint] Base injoignable — abandon.")
PY

echo "[entrypoint] Application des migrations…"
flask db upgrade heads

echo "[entrypoint] Amorce (tenant Root + admin global, idempotent)…"
flask seed

echo "[entrypoint] Démarrage de Gunicorn (workers=${GUNICORN_WORKERS})…"
exec gunicorn \
  --workers "${GUNICORN_WORKERS}" \
  --bind 0.0.0.0:5000 \
  --timeout "${GUNICORN_TIMEOUT}" \
  --access-logfile - \
  --error-logfile - \
  "app:create_app()"
