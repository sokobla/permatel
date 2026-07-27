# ─────────────────────────────────────────────────────────────────────────────
# PERMATEL — Core Connector Téléphonie (Phase 12)
# Process Docker UNIQUE orchestrant plusieurs PBXAdapter (ESL aujourd'hui,
# AMI en Phase 14) — voir TELEPHONIE_INTEGRATION_PLAN.md §4.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip wheel \
 && pip wheel --wheel-dir=/wheels -r requirements.txt


FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 connectoruser

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
 && rm -rf /wheels

COPY . .

RUN chown -R connectoruser:connectoruser /app
USER connectoruser

# Pas de serveur HTTP dans ce process : healthcheck via fichier heartbeat
# rafraîchi à chaque cycle de réconciliation (core_connector.py).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD find /tmp/connector_heartbeat -newermt "-90 seconds" | grep -q . || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "core_connector.py"]
