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
     désactivé — sans redémarrer les adapters déjà en cours (config stable),
     sauf si `sync_requested_at` a changé (bouton "Sync", filet de secours
     du signal Redis temps réel — voir _SyncListener).
  3. Heartbeat de statut (POST /connectors/status) à chaque cycle.
"""
# gevent monkey-patch AVANT tout import réseau (requests, socket…) — c'est ce
# qui rend `requests`/`greenswitch`/`redis` coopératifs. Doit rester la toute
# première chose exécutée dans le process.
from gevent import monkey
monkey.patch_all()

import json
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


class _SyncListener:
    """Écoute Redis pub/sub (canal `telephony:sync`) pour appliquer un
    "Sync" quasi instantanément, sans attendre le prochain sondage
    périodique. Best-effort : si Redis est absent/injoignable, le connecteur
    fonctionne quand même — le filet de secours (`sync_requested_at` dans le
    payload de config, comparé à chaque cycle) prend le relais.

    Porte aussi (13/08) le dispatch des jobs d'exécution à distance
    (login/logout/changement de statut agent) — même canal, format de
    payload différent : un entier brut (`str(connector_id)`, motif
    historique du signal Sync) reste traité comme avant ; un objet JSON
    avec `job_type` est dispatché vers `on_job_requested`. Pas de nouveau
    canal Redis, pour ne rien changer côté backend au-delà du contenu déjà
    publié sur `SYNC_CHANNEL`."""

    def __init__(self, on_sync_requested, on_job_requested):
        self._on_sync_requested = on_sync_requested
        self._on_job_requested = on_job_requested
        self._greenlet = None

    def start(self):
        if not config.REDIS_URL:
            logger.info("REDIS_URL non configuré — Sync appliqué au prochain sondage périodique uniquement.")
            return
        self._greenlet = gevent.spawn(self._run)

    def stop(self):
        if self._greenlet is not None:
            gevent.kill(self._greenlet)

    def _run(self):
        try:
            import redis as redis_lib
        except ImportError:  # pragma: no cover - redis toujours présent en prod
            logger.warning("Bibliothèque redis absente — Sync temps réel désactivé.")
            return

        while True:
            try:
                client = redis_lib.from_url(config.REDIS_URL, socket_connect_timeout=5)
                pubsub = client.pubsub()
                pubsub.subscribe(config.REDIS_SYNC_CHANNEL)
                logger.info("Abonné au canal Redis '%s' (signal Sync temps réel).", config.REDIS_SYNC_CHANNEL)
                for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    raw = message["data"]
                    # Payload job (JSON, objet avec 'job_type') vs signal Sync
                    # historique (entier brut) — tenté dans cet ordre car un
                    # entier brut n'est jamais un JSON d'objet valide, aucune
                    # ambiguïté possible entre les deux formats.
                    job = None
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict) and "job_type" in parsed:
                            job = parsed
                    except (TypeError, ValueError):
                        pass
                    if job is not None:
                        self._on_job_requested(job)
                        continue
                    try:
                        connector_id = int(raw)
                    except (TypeError, ValueError):
                        continue
                    self._on_sync_requested(connector_id)
            except Exception as exc:  # noqa: BLE001 - reconnexion Redis, ne doit jamais tuer le process
                logger.warning("Connexion Redis (Sync) interrompue (%s) — nouvelle tentative dans 5s.", exc)
                gevent.sleep(5)


class CoreConnector:
    def __init__(self):
        self.ingest_client = IngestClient()
        self._running_adapters = {}  # connector_id -> (adapter, greenlet)
        self._last_sync_requested_at = {}  # connector_id -> dernière valeur vue
        self._stopping = False
        self._sync_listener = _SyncListener(self._on_sync_requested, self._on_job_requested)

    def start(self):
        if not config.TELEPHONY_CONNECTOR_TOKEN:
            raise SystemExit("TELEPHONY_CONNECTOR_TOKEN est requis.")

        logger.info(
            "Core Connector démarré (PERMATEL_API_URL=%s, refresh=%ss)",
            config.PERMATEL_API_URL, config.CONFIG_REFRESH_SECONDS,
        )
        gevent.signal_handler(signal.SIGTERM, self.stop)
        gevent.signal_handler(signal.SIGINT, self.stop)
        self._sync_listener.start()

        while not self._stopping:
            self._reconcile()
            self._send_status_heartbeat()
            HEARTBEAT_PATH.touch()
            gevent.sleep(config.CONFIG_REFRESH_SECONDS)

        self._sync_listener.stop()
        self._stop_all_adapters()
        logger.info("Core Connector arrêté proprement.")

    def stop(self):
        logger.info("Signal d'arrêt reçu — fin de la boucle de réconciliation.")
        self._stopping = True

    def _on_sync_requested(self, connector_id: int):
        """Callback du _SyncListener (signal Redis) — greenlet séparée de la
        boucle de réconciliation, donc thread-safe côté gevent (coopératif,
        pas de vrai parallélisme)."""
        entry = self._running_adapters.get(connector_id)
        if entry is None:
            return
        adapter, _greenlet = entry
        adapter.force_reconnect()

    def _on_job_requested(self, job: dict):
        """Callback du _SyncListener pour un job d'exécution à distance
        (13/08) — login/logout/changement de statut d'un agent. Même
        garantie que `_on_sync_requested` : greenlet séparée, best-effort,
        job perdu silencieusement (journalisé) si le connecteur visé n'est
        pas/plus en cours d'exécution ici."""
        connector_id = job.get("connector_id")
        entry = self._running_adapters.get(connector_id)
        if entry is None:
            logger.warning(
                "Job PBX reçu pour un connecteur non actif ici (connector_id=%s, job_type=%s) — abandonné.",
                connector_id, job.get("job_type"),
            )
            return
        adapter, _greenlet = entry
        adapter.execute_job(job)

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
            sync_requested_at = connector_cfg.get("sync_requested_at")

            if connector_id in self._running_adapters:
                # Filet de secours : le signal Redis a pu être manqué (connecteur
                # en redémarrage au moment de la publication) — détecté ici au
                # prochain sondage périodique via le changement d'horodatage.
                if sync_requested_at and sync_requested_at != self._last_sync_requested_at.get(connector_id):
                    logger.info("Connecteur id=%s : sync_requested_at modifié — reconnexion forcée.", connector_id)
                    self._on_sync_requested(connector_id)
                self._last_sync_requested_at[connector_id] = sync_requested_at
                # Roster PERMATEL (User.agent_login) rafraîchi à chaque cycle
                # même sans Sync — un adapter déjà en cours n'est jamais
                # redémarré pour ça (no-op par défaut sur PBXAdapter, cf. base.py).
                adapter, _greenlet = self._running_adapters[connector_id]
                adapter.update_known_agent_logins(connector_cfg.get("known_agent_logins") or [])
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
            self._last_sync_requested_at[connector_id] = sync_requested_at

        # Connecteurs disparus/désactivés depuis le dernier refresh.
        for connector_id in list(self._running_adapters):
            if connector_id not in seen_ids:
                logger.info("Connecteur id=%s désactivé/supprimé — arrêt de l'adapter.", connector_id)
                adapter, greenlet = self._running_adapters.pop(connector_id)
                adapter.stop()
                greenlet.join(timeout=10)
                self._last_sync_requested_at.pop(connector_id, None)

    def _send_status_heartbeat(self):
        if not self._running_adapters:
            return
        statuses = {
            str(connector_id): {"connected": adapter.is_connected, "error": adapter.last_error}
            for connector_id, (adapter, _greenlet) in self._running_adapters.items()
        }
        self.ingest_client.send_status(statuses)

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
