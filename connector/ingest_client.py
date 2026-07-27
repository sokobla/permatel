# -*- coding: utf-8 -*-
"""Client HTTP vers l'API d'ingestion PERMATEL (POST /api/telephony/events/ingest).

Sous gevent (monkey-patché dans core_connector.py avant tout import réseau),
`requests` devient coopératif automatiquement — aucun adaptateur dédié requis
(contrairement à psycopg2 côté backend, qui a besoin d'un patch explicite
puisque libpq fait ses appels réseau hors du module `socket` Python).
"""
import logging

import requests

import config

logger = logging.getLogger("connector.ingest")


class IngestClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "X-Connector-Token": config.TELEPHONY_CONNECTOR_TOKEN,
            "Content-Type": "application/json",
        })
        self._url = f"{config.PERMATEL_API_URL}/telephony/events/ingest"

    def send(self, payload: dict) -> bool:
        """Envoie un événement normalisé. Retourne True si accepté (2xx)."""
        try:
            resp = self.session.post(self._url, json=payload, timeout=config.INGEST_HTTP_TIMEOUT)
        except requests.RequestException as exc:
            logger.warning("Échec d'envoi de l'événement (réseau) : %s", exc)
            return False

        if resp.status_code == 404:
            # Domaine PBX non rattaché à un tenant (pbx_domains_tenants) —
            # pas la peine de retenter, la config doit être corrigée côté UI.
            logger.warning(
                "Domaine PBX inconnu de PERMATEL (pbx_domain=%r) — événement ignoré.",
                payload.get("pbx_domain"),
            )
            return False
        if resp.status_code == 401:
            logger.error("Jeton connecteur rejeté par PERMATEL (401) — vérifier TELEPHONY_CONNECTOR_TOKEN.")
            return False
        if not resp.ok:
            logger.warning("Ingestion refusée (%s) : %s", resp.status_code, resp.text[:300])
            return False
        return True

    def fetch_config(self) -> list:
        """GET /telephony/connectors/config — connecteurs actifs + domaines rattachés."""
        url = f"{config.PERMATEL_API_URL}/telephony/connectors/config"
        resp = self.session.get(url, timeout=config.INGEST_HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("connectors", [])
