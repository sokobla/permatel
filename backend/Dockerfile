# ─────────────────────────────────────────────────────────────────────────────
# PERMATEL — Backend (production)
# Image multi-stage : build des wheels isolé, image finale minimale, non-root,
# servie par Gunicorn. Les migrations + l'amorce sont jouées par l'entrypoint.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1 : build des dépendances ──────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
# Compile les dépendances en wheels (pas de toolchain dans l'image finale)
RUN pip install --upgrade pip wheel \
 && pip wheel --wheel-dir=/wheels -r requirements.txt


# ── Stage 2 : image d'exécution ───────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_APP=app

# tini : gestion correcte des signaux (PID 1) ; pas de recommandés.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

# Utilisateur non privilégié
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

# Installe les dépendances depuis les wheels pré-construits
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
 && rm -rf /wheels

# Code applicatif
COPY . .

# Dossier d'uploads (volume monté en prod) accessible à l'utilisateur non-root
RUN mkdir -p /app/app/uploads \
 && chmod +x /app/entrypoint.sh \
 && chown -R appuser:appuser /app

USER appuser
EXPOSE 5000

# Healthcheck applicatif (sans dépendance externe : urllib)
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:5000/health').status==200 else sys.exit(1)" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
