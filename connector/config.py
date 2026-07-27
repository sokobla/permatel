# -*- coding: utf-8 -*-
"""Configuration du Core Connector — pilotée par variables d'environnement."""
import os

PERMATEL_API_URL = os.environ.get("PERMATEL_API_URL", "http://backend:5000/api").rstrip("/")
TELEPHONY_CONNECTOR_TOKEN = os.environ.get("TELEPHONY_CONNECTOR_TOKEN")

# Fréquence de rechargement de la config (pbx_connectors/pbx_domains_tenants)
# depuis PERMATEL — un changement dans l'UI admin (Phase 11) est pris en
# compte au plus tard après ce délai, sans redémarrage du connecteur.
CONFIG_REFRESH_SECONDS = int(os.environ.get("CONFIG_REFRESH_SECONDS", 60))

# Backoff de reconnexion ESL (secondes) : exponentiel, borné.
ESL_RECONNECT_BACKOFF_INITIAL = float(os.environ.get("ESL_RECONNECT_BACKOFF_INITIAL", 2))
ESL_RECONNECT_BACKOFF_MAX = float(os.environ.get("ESL_RECONNECT_BACKOFF_MAX", 60))

# Timeout HTTP pour l'ingestion vers PERMATEL.
INGEST_HTTP_TIMEOUT = float(os.environ.get("INGEST_HTTP_TIMEOUT", 5))

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
