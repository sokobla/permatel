# -*- coding: utf-8 -*-
"""ESLAdapter — connecteur FusionPBX/FreeSWITCH via mod_event_socket (ESL).

Connexion "inbound" (le connecteur se connecte à FusionPBX comme un client,
port 8021 par défaut). Une greenlet gevent par PbxConnector de type ESL,
orchestrée par CoreConnector — jamais un process séparé (cf. §4 du plan).
"""
import logging
import re

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

# Colonnes de `api callcenter_config agent list <queue>@<domain>`, d'après
# la convention documentée de mod_callcenter — NON reconfirmée contre une
# sortie réelle à ce jour (le format exact sera visible dans le log
# "agent list ... -> " au premier rafraîchissement en production ; à
# corriger ici si les valeurs ne correspondent pas aux colonnes attendues).
_AGENT_LIST_FIELDS = (
    "agent_name", "agent_type", "contact", "status", "state",
    "max_no_answer", "wrap_up_time", "reject_delay_time", "busy_delay_time",
    "no_answer_delay_time", "last_bridge_start", "last_bridge_end",
    "last_offered_call", "no_answer_count", "calls_answered",
    "calls_abandoned", "talk_time", "ready_time", "external_calls_count",
)
# Extension numérique dans le champ 'contact' (ex. "user/22101005@domaine"
# ou "sofia/internal/22101005@domaine") — même convention que l'extraction
# côté CDR (callflow originatee.destination_number).
_EXTENSION_RE = re.compile(r"(\d{2,})")


class ESLAdapter(PBXAdapter):
    def __init__(self, connector_config: dict, ingest_client):
        super().__init__(connector_config, ingest_client)
        self._esl = None
        self._disconnect_event = Event()
        self.last_error = None
        # domaine -> ensemble des queue_id supervisées ; liste vide = pas de
        # filtre (toutes les queues du domaine sont transmises). Chaque
        # entrée est re-scindée sur ',' : confirmé en prod (29/07) qu'une
        # saisie de plusieurs files en une fois dans le champ "Entrée pour
        # ajouter" du formulaire (`queue_ids` combobox) peut produire UNE
        # entrée "8001, 8002, 8003, 8004, 8005" au lieu de 5 entrées
        # distinctes — `agent list <ceci>@<domaine>` est alors rejeté par
        # FreeSWITCH ('-ERR Invalid!') puisqu'il n'accepte qu'une seule file
        # à la fois. Tolérant à cette saisie plutôt que de forcer une
        # correction manuelle préalable dans Paramètres > Téléphonie.
        self._supervised_queues = {}
        for d in connector_config.get("domains", []):
            queues = set()
            for raw_queue_id in (d.get("queue_ids") or []):
                for part in str(raw_queue_id).split(","):
                    part = part.strip()
                    if part:
                        queues.add(part)
            self._supervised_queues[d["pbx_domain"]] = queues
        # uuid FreeSWITCH (CC-Agent) -> {"domain":..., "extension":..., "queue":...}
        # — construit via _refresh_agent_directory(), nécessaire car les
        # événements agent-status-change ne portent ni domaine ni extension
        # exploitable directement (confirmé sur trafic réel, voir
        # _on_callcenter_info).
        self._agent_directory = {}
        self._agent_directory_greenlet = None

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
                self._agent_directory_greenlet = gevent.spawn(self._agent_directory_refresh_loop)
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
                if self._agent_directory_greenlet is not None:
                    gevent.kill(self._agent_directory_greenlet)
                    self._agent_directory_greenlet = None
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
        self._refresh_agent_directory()

    def _agent_directory_refresh_loop(self):
        while self.is_connected:
            gevent.sleep(config.AGENT_DIRECTORY_REFRESH_SECONDS)
            if self.is_connected:
                self._refresh_agent_directory()

    def _refresh_agent_directory(self):
        """Construit l'annuaire uuid FreeSWITCH -> extension/domaine via
        `api callcenter_config agent list <queue>@<domain>`, une requête
        synchrone par file supervisée (scoper par domaine+file donne le
        domaine "gratuitement" — pas besoin que FreeSWITCH le reporte sur
        l'événement, ce qu'il ne fait pas pour agent-status-change).

        Limitation connue : un domaine sans `queue_ids` configurés (pas de
        filtre explicite) n'est pas rafraîchi ici — il n'existe pas de
        moyen de lister "toutes les files d'un domaine" sans connaître
        leurs noms au préalable. Se contente de le journaliser plutôt que
        de deviner.
        """
        directory = {}
        for domain, queues in self._supervised_queues.items():
            if not queues:
                logger.warning(
                    "[%s] Domaine '%s' sans file explicite — annuaire agents non "
                    "rafraîchi pour ce domaine (queue_ids requis).",
                    self.connector_config["name"], domain,
                )
                continue
            for queue in queues:
                self._fetch_agent_list(domain, queue, directory)
        self._agent_directory = directory
        logger.info(
            "[%s] Annuaire agents rafraîchi : %d agent(s) résolu(s).",
            self.connector_config["name"], len(directory),
        )

    def _fetch_agent_list(self, domain, queue, directory):
        try:
            response = self._esl.send(f"api callcenter_config agent list {queue}@{domain}")
        except Exception as exc:
            logger.warning(
                "[%s] Échec de 'agent list' pour %s@%s : %s",
                self.connector_config["name"], queue, domain, exc,
            )
            return

        raw = (getattr(response, "data", None) or "").strip()
        # Journalisé systématiquement (pas seulement en cas d'erreur) tant que
        # le format de colonnes ci-dessus n'a pas été confirmé contre une
        # sortie réelle — à retirer une fois _AGENT_LIST_FIELDS validé.
        logger.info(
            "[%s] agent list %s@%s -> %r", self.connector_config["name"], queue, domain, raw,
        )
        if not raw or raw.startswith("-ERR"):
            return

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            fields = line.split("|")
            if len(fields) < 3:
                continue
            row = dict(zip(_AGENT_LIST_FIELDS, fields))
            agent_uuid = row.get("agent_name")
            contact = row.get("contact") or ""
            match = _EXTENSION_RE.search(contact)
            if not agent_uuid or not match:
                logger.warning(
                    "[%s] Ligne 'agent list' ininterprétable (uuid ou extension manquant) : %r",
                    self.connector_config["name"], line,
                )
                continue
            directory[agent_uuid] = {"domain": domain, "extension": match.group(1), "queue": queue}

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
        action = headers.get("CC-Action")

        # Confirmé sur trafic FusionPBX réel (29/07) : les événements de
        # statut agent ('agent-status-change'/'agent-status-get') ne portent
        # NI 'variable_domain_name' NI d'identifiant exploitable dans
        # 'CC-Agent' (un UUID interne FusionPBX) — contrairement à
        # 'queue-enter', qui reste lié à un canal d'appel actif et passe par
        # le chemin habituel (_resolve_domain). Traités à part, résolus via
        # l'annuaire agents (_refresh_agent_directory), AVANT toute
        # tentative de lecture de 'variable_domain_name' qui n'existera
        # jamais sur ce type d'événement.
        if action in ("agent-status-change", "agent-status-get"):
            self._on_agent_status_event(headers, action)
            return

        domain = self._resolve_domain(headers)
        if not domain:
            logger.warning(
                "[%s] callcenter::info (CC-Action=%r) abandonné : 'variable_domain_name' absent des en-têtes.",
                self.connector_config["name"], action,
            )
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
            # 'queue-enter' et 'agent-state-change' — toute autre CC-Action
            # est ici silencieusement abandonnée en amont. On journalise
            # systématiquement les en-têtes complets d'un événement
            # callcenter::info non reconnu pour repérer une action
            # manquante plutôt que de perdre l'information sans trace.
            logger.warning(
                "[%s] callcenter::info non reconnu — CC-Action=%r, en-têtes=%r",
                self.connector_config["name"], action, dict(headers),
            )

    def _on_agent_status_event(self, headers, action):
        if action == "agent-status-get":
            return  # lecture passive (ex. rafraîchissement d'un écran admin), pas une transition réelle

        agent_uuid = headers.get("CC-Agent")
        entry = self._agent_directory.get(agent_uuid)
        if entry is None:
            logger.warning(
                "[%s] agent-status-change pour un agent absent de l'annuaire (uuid=%s, statut=%r) — "
                "annuaire pas encore rafraîchi, ou agent hors des files supervisées.",
                self.connector_config["name"], agent_uuid, headers.get("CC-Agent-Status"),
            )
            return

        payload = normalizer.normalize_agent_status_change(headers, entry["domain"], entry["extension"])
        self.ingest_client.send(payload)
