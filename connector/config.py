# -*- coding: utf-8 -*-
"""Configuration du Core Connector — pilotée par variables d'environnement."""
import os

PERMATEL_API_URL = os.environ.get("PERMATEL_API_URL", "http://backend:5000/api").rstrip("/")
TELEPHONY_CONNECTOR_TOKEN = os.environ.get("TELEPHONY_CONNECTOR_TOKEN")

# Signal "Sync" quasi temps réel (bouton Paramètres > Téléphonie) — Redis
# pub/sub. Optionnel : si absent/injoignable, le connecteur fonctionne quand
# même (filet de secours : sync_requested_at repris au prochain sondage
# périodique de GET /connectors/config, cf. CONFIG_REFRESH_SECONDS).
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_SYNC_CHANNEL = "telephony:sync"

# Fréquence de rechargement de la config (pbx_connectors/pbx_domains_tenants)
# depuis PERMATEL — un changement dans l'UI admin (Phase 11) est pris en
# compte au plus tard après ce délai, sans redémarrage du connecteur.
CONFIG_REFRESH_SECONDS = int(os.environ.get("CONFIG_REFRESH_SECONDS", 60))

# Backoff de reconnexion ESL (secondes) : exponentiel, borné.
ESL_RECONNECT_BACKOFF_INITIAL = float(os.environ.get("ESL_RECONNECT_BACKOFF_INITIAL", 2))
ESL_RECONNECT_BACKOFF_MAX = float(os.environ.get("ESL_RECONNECT_BACKOFF_MAX", 60))

# Rafraîchissement de l'annuaire agents (uuid FreeSWITCH -> extension/domaine),
# construit via `api callcenter_config agent list <queue>@<domain>` (confirmé
# via trafic réel le 29/07 que les événements agent-status-change ne portent
# ni domaine ni identifiant exploitable directement — voir esl_adapter.py).
AGENT_DIRECTORY_REFRESH_SECONDS = int(os.environ.get("AGENT_DIRECTORY_REFRESH_SECONDS", 300))

# Timeout HTTP pour l'ingestion vers PERMATEL.
INGEST_HTTP_TIMEOUT = float(os.environ.get("INGEST_HTTP_TIMEOUT", 5))

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
