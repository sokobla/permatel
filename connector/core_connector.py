# -*- coding: utf-8 -*-
"""
Core Connector — Phase 12.

Process Docker UNIQUE (cf. TELEPHONIE_INTEGRATION_PLAN.md §4) : orchestre
plusieurs PBXAdapter concurrents (une greenlet gevent par ligne
`pbx_connectors` active), un par PBX physique, quel que soit son type
(ESL aujourd'hui, AMI en Phase 14). Ce n'est PAS un process par PBX.

Boucle principale :
  1. GET /api/telephony/connectors/config (jeton technique partagé) au
     démarrage puis toutes les CONFIG_REFRESH_SECONDS.
  2. Réconciliation : démarre une greenlet PBXAdapter pour tout connecteur
     actif nouvellement vu, arrête celles dont le connecteur a disparu/été
     désactivé — sans redémarrer les adapters déjà en cours (config stable).
"""
# gevent monkey-patch AVANT tout import réseau (requests, socket…) — c'est ce
# qui rend `requests`/`greenswitch` coopératifs. Doit rester la toute
# première chose exécutée dans le process.
from gevent import monkey
monkey.patch_all()

import logging
import signal
from pathlib import Path

import gevent

import config
from adapters.esl_adapter import ESLAdapter
from ingest_client import IngestClient

logger = logging.getLogger("connector.core")

# Heartbeat consommé par le HEALTHCHECK Docker (pas de serveur HTTP dans ce
# process) : mis à jour à chaque cycle de réconciliation réussi.
HEARTBEAT_PATH = Path("/tmp/connector_heartbeat")

ADAPTER_CLASSES = {
    "ESL": ESLAdapter,
    # "AMI": AMIAdapter,  # Phase 14 — même process, ajouté ici le moment venu.
}


class CoreConnector:
    def __init__(self):
        self.ingest_client = IngestClient()
        self._running_adapters = {}  # connector_id -> (adapter, greenlet)
        self._stopping = False

    def start(self):
        if not config.TELEPHONY_CONNECTOR_TOKEN:
            raise SystemExit("TELEPHONY_CONNECTOR_TOKEN est requis.")

        logger.info(
            "Core Connector démarré (PERMATEL_API_URL=%s, refresh=%ss)",
            config.PERMATEL_API_URL, config.CONFIG_REFRESH_SECONDS,
        )
        gevent.signal_handler(signal.SIGTERM, self.stop)
        gevent.signal_handler(signal.SIGINT, self.stop)

        while not self._stopping:
            self._reconcile()
            HEARTBEAT_PATH.touch()
            gevent.sleep(config.CONFIG_REFRESH_SECONDS)

        self._stop_all_adapters()
        logger.info("Core Connector arrêté proprement.")

    def stop(self):
        logger.info("Signal d'arrêt reçu — fin de la boucle de réconciliation.")
        self._stopping = True

    def _reconcile(self):
        try:
            connectors = self.ingest_client.fetch_config()
        except Exception as exc:
            logger.warning("Impossible de récupérer la config PERMATEL (%s) — adapters existants conservés.", exc)
            return

        seen_ids = set()
        for connector_cfg in connectors:
            connector_id = connector_cfg["id"]
            seen_ids.add(connector_id)

            if connector_id in self._running_adapters:
                continue  # déjà en cours — pas de redémarrage sur simple refresh

            adapter_cls = ADAPTER_CLASSES.get(connector_cfg["type"])
            if adapter_cls is None:
                logger.warning(
                    "Connecteur '%s' de type '%s' non pris en charge — ignoré.",
                    connector_cfg["name"], connector_cfg["type"],
                )
                continue

            logger.info("Démarrage de l'adapter pour '%s' (%s)…", connector_cfg["name"], connector_cfg["type"])
            adapter = adapter_cls(connector_cfg, self.ingest_client)
            greenlet = gevent.spawn(adapter.run)
            self._running_adapters[connector_id] = (adapter, greenlet)

        # Connecteurs disparus/désactivés depuis le dernier refresh.
        for connector_id in list(self._running_adapters):
            if connector_id not in seen_ids:
                logger.info("Connecteur id=%s désactivé/supprimé — arrêt de l'adapter.", connector_id)
                adapter, greenlet = self._running_adapters.pop(connector_id)
                adapter.stop()
                greenlet.join(timeout=10)

    def _stop_all_adapters(self):
        for adapter, greenlet in self._running_adapters.values():
            adapter.stop()
        gevent.joinall([g for _, g in self._running_adapters.values()], timeout=15)
        self._running_adapters.clear()


def main():
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    CoreConnector().start()


if __name__ == "__main__":
    main()
