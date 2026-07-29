# -*- coding: utf-8 -*-
"""ESLAdapter — connecteur FusionPBX/FreeSWITCH via mod_event_socket (ESL).

Connexion "inbound" (le connecteur se connecte à FusionPBX comme un client,
port 8021 par défaut). Une greenlet gevent par PbxConnector de type ESL,
orchestrée par CoreConnector — jamais un process séparé (cf. §4 du plan).
"""
import logging

import gevent
from gevent.event import Event
from greenswitch import InboundESL
from greenswitch.esl import NotConnectedError

import config
import normalizer
from adapters.base import PBXAdapter

logger = logging.getLogger("connector.esl")

# Formats FreeSWITCH bruts souscrits — CUSTOM callcenter::info regroupe les
# événements de files d'attente (mod_callcenter).
_SUBSCRIBE_CMD = (
    "event plain CHANNEL_CREATE CHANNEL_PROGRESS_MEDIA CHANNEL_ANSWER "
    "CHANNEL_HANGUP_COMPLETE CUSTOM callcenter::info"
)


class ESLAdapter(PBXAdapter):
    def __init__(self, connector_config: dict, ingest_client):
        super().__init__(connector_config, ingest_client)
        self._esl = None
        self._disconnect_event = Event()
        self.last_error = None
        # domaine -> ensemble des queue_id supervisées ; liste vide = pas de
        # filtre (toutes les queues du domaine sont transmises).
        self._supervised_queues = {
            d["pbx_domain"]: set(d.get("queue_ids") or [])
            for d in connector_config.get("domains", [])
        }

    @property
    def is_connected(self) -> bool:
        return bool(self._esl is not None and self._esl.connected)

    def run(self):
        backoff = config.ESL_RECONNECT_BACKOFF_INITIAL
        while not self._stopping:
            try:
                self._connect_and_subscribe()
                self.last_error = None
                backoff = config.ESL_RECONNECT_BACKOFF_INITIAL  # connexion OK, reset backoff
                self._disconnect_event.clear()
                self._disconnect_event.wait()  # bloque jusqu'à déconnexion (ou stop()/force_reconnect())
            except (NotConnectedError, OSError) as exc:
                self.last_error = str(exc)
                logger.warning(
                    "[%s] Connexion ESL échouée (%s) — nouvelle tentative dans %.0fs",
                    self.connector_config["name"], exc, backoff,
                )
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("[%s] Erreur inattendue dans l'adapter ESL", self.connector_config["name"])
            finally:
                # SEULE et unique place qui ferme la connexion ESL (voir
                # _hard_disconnect) — stop()/force_reconnect() ne font que
                # réveiller ce wait() via l'event, jamais toucher la socket
                # elles-mêmes, pour éviter un double-stop concurrent.
                self._hard_disconnect()

            if self._stopping:
                break
            gevent.sleep(backoff)
            backoff = min(backoff * 2, config.ESL_RECONNECT_BACKOFF_MAX)

    def stop(self):
        super().stop()
        self._disconnect_event.set()  # débloque la boucle run() -> _hard_disconnect() + sortie

    def force_reconnect(self):
        """Bouton "Sync" (signal Redis) — casse la connexion ESL en cours,
        `run()` reboucle et reconnecte après `ESL_RECONNECT_BACKOFF_INITIAL`
        (backoff déjà réinitialisé par la connexion en cours si elle avait
        réussi), sans attendre le prochain sondage périodique de config.

        Ne touche JAMAIS `self._esl` directement : appelé depuis une autre
        greenlet que `run()` (réconciliation périodique ou listener Redis),
        un appel concurrent à ESLProtocol.stop() (qui envoie 'exit' et
        attend une réponse SANS timeout) créerait une course avec le
        `finally` de run() — les deux peuvent alors rester bloqués
        indéfiniment sur la même réponse jamais reçue deux fois. Seul
        run()/_hard_disconnect() ferme la socket, dans sa propre greenlet.
        """
        logger.info("[%s] Reconnexion forcée (Sync).", self.connector_config["name"])
        self._disconnect_event.set()

    def _hard_disconnect(self):
        """Ferme la socket ESL directement plutôt que via
        ESLProtocol.stop() (qui envoie 'exit' et bloque sans timeout sur la
        réponse — dangereux si FreeSWITCH ne répond pas, ex. connexion déjà
        morte côté réseau). On veut juste rompre la connexion pour
        reconnecter, pas négocier un arrêt propre. Appelée uniquement
        depuis run(), jamais depuis un autre greenlet."""
        esl = self._esl
        self._esl = None
        if esl is None:
            return
        try:
            esl._run = False
            if esl.sock is not None:
                esl.sock.close()
        except Exception:
            pass

    def _connect_and_subscribe(self):
        cfg = self.connector_config
        logger.info("[%s] Connexion à %s:%s (ESL)…", cfg["name"], cfg["host"], cfg["port"])
        self._esl = InboundESL(host=cfg["host"], port=cfg["port"], password=cfg.get("password") or "")
        self._esl.connect()

        self._esl.register_handle("DISCONNECT", self._on_disconnect)
        self._esl.register_handle("CHANNEL_CREATE", self._make_handler(normalizer.normalize_channel_create))
        self._esl.register_handle(
            "CHANNEL_PROGRESS_MEDIA", self._make_handler(normalizer.normalize_channel_progress_media)
        )
        self._esl.register_handle("CHANNEL_ANSWER", self._make_handler(normalizer.normalize_channel_answer))
        self._esl.register_handle(
            "CHANNEL_HANGUP_COMPLETE", self._make_handler(normalizer.normalize_channel_hangup)
        )
        # Dispatché par greenswitch sous la clé Event-Subclass pour les
        # événements CUSTOM (voir process_events() dans greenswitch/esl.py).
        self._esl.register_handle("callcenter::info", self._on_callcenter_info)

        self._esl.send(_SUBSCRIBE_CMD)
        logger.info("[%s] Connecté et souscrit aux événements.", cfg["name"])

    def _on_disconnect(self, _event):
        logger.warning("[%s] Déconnecté de FreeSWITCH.", self.connector_config["name"])
        self._disconnect_event.set()

    def _resolve_domain(self, headers: dict) -> str | None:
        """FusionPBX porte le domaine multi-tenant sur `variable_domain_name`."""
        domain = headers.get("variable_domain_name")
        if domain and domain in self._supervised_queues:
            return domain
        # Domaine hors config PERMATEL (pas de rattachement pbx_domains_tenants)
        # — laissé passer quand même : l'API d'ingestion loggera/écartera avec
        # un 404 explicite plutôt que de filtrer silencieusement ici.
        return domain

    def _make_handler(self, normalize_fn):
        def _handler(event):
            headers = event.headers
            domain = self._resolve_domain(headers)
            if not domain:
                return  # pas de domaine FusionPBX sur ce canal (config PBX incomplète)
            payload = normalize_fn(headers, domain)
            if payload:
                self.ingest_client.send(payload)

        return _handler

    def _on_callcenter_info(self, event):
        headers = event.headers
        domain = self._resolve_domain(headers)
        if not domain:
            return

        queue_id = headers.get("CC-Queue")
        supervised = self._supervised_queues.get(domain)
        if supervised and queue_id not in supervised:
            return  # queue non supervisée pour ce tenant — pas transmis

        payload = normalizer.normalize_callcenter_info(headers, domain)
        if payload:
            self.ingest_client.send(payload)
        else:
            # Diagnostic : normalize_callcenter_info() ne reconnaît que
            # 'queue-enter' et 'agent-state-change' — tout autre CC-Action
            # (ex. un éventuel 'agent-status-change' distinct pour les
            # changements de statut manuels Available/On Break/Logged Out,
            # non confirmé à ce jour) est ici silencieusement abandonné en
            # amont. On journalise systématiquement les en-têtes complets
            # d'un événement callcenter::info non reconnu pour repérer une
            # action manquante plutôt que de perdre l'information sans trace.
            logger.warning(
                "[%s] callcenter::info non reconnu — CC-Action=%r, en-têtes=%r",
                self.connector_config["name"], headers.get("CC-Action"), dict(headers),
            )
