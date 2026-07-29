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

# Colonnes de `api callcenter_config agent list`, CONFIRMÉES contre une
# sortie réelle en prod (29/07) — voir le log "agent list ... -> " :
# "name|instance_id|uuid|type|contact|status|state|max_no_answer|
#  wrap_up_time|reject_delay_time|busy_delay_time|no_answer_delay_time|
#  last_bridge_start|last_bridge_end|last_offered_call|last_status_change|
#  no_answer_count|calls_answered|talk_time|ready_time|external_calls_count"
# NB : la colonne "name" est en réalité l'uuid FusionPBX de l'agent
# (call_center_agents.call_center_agent_uuid), pas un nom lisible — c'est
# la même valeur que le header ESL 'CC-Agent'. La colonne "uuid" elle-même
# est vide dans toutes les lignes observées.
_AGENT_LIST_FIELDS = (
    "name", "instance_id", "uuid", "type", "contact", "status", "state",
    "max_no_answer", "wrap_up_time", "reject_delay_time", "busy_delay_time",
    "no_answer_delay_time", "last_bridge_start", "last_bridge_end",
    "last_offered_call", "last_status_change", "no_answer_count",
    "calls_answered", "talk_time", "ready_time", "external_calls_count",
)
# La première ligne de la réponse est l'en-tête de colonnes (pas une ligne
# d'agent) — détectée par son préfixe plutôt que sa position, au cas où
# FreeSWITCH omettrait l'en-tête quand aucun agent n'est configuré.
_AGENT_LIST_HEADER_PREFIX = "name|instance_id|uuid|type|contact|status|state"
# Extension + domaine dans le champ 'contact' (ex.
# "{...}user/22101005@africallpbx.fusion.cloud228.com") — même convention
# que l'extraction côté CDR (callflow originatee.destination_number).
# Un simple \d{2,} matcherait à tort des valeurs numériques internes du
# contact (ex. "call_timeout=20") : confirmé en prod (29/07), d'où l'ancrage
# strict sur le motif "user/<extension>@<domaine>".
_EXTENSION_RE = re.compile(r"user/(\d+)@([\w.-]+)")


class ESLAdapter(PBXAdapter):
    def __init__(self, connector_config: dict, ingest_client):
        super().__init__(connector_config, ingest_client)
        self._esl = None
        self._disconnect_event = Event()
        self.last_error = None
        # domaine -> ensemble des queue_id supervisées ; liste vide = pas de
        # filtre (toutes les queues du domaine sont transmises). Chaque
        # entrée `queue_ids` est `{"id": "8001", "alias": "Support"}` — seul
        # `id` intéresse le connecteur (l'alias est un libellé d'affichage
        # PERMATEL, jamais transmis à FreeSWITCH) ; compat ancien format
        # (chaîne nue) pour les domaines pas encore ré-enregistrés. Chaque
        # `id` est en plus re-scindé sur ',' : confirmé en prod (29/07)
        # qu'une saisie de plusieurs files en une fois dans l'ancien champ
        # combobox pouvait produire UNE entrée "8001, 8002, ..." au lieu de
        # plusieurs entrées distinctes — `agent list <ceci>@<domaine>` est
        # alors rejeté par FreeSWITCH ('-ERR Invalid!').
        self._supervised_queues = {}
        for d in connector_config.get("domains", []):
            queues = set()
            for raw in (d.get("queue_ids") or []):
                raw_id = raw.get("id") if isinstance(raw, dict) else raw
                if not raw_id:
                    continue
                for part in str(raw_id).split(","):
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
        # Roster faisant autorité côté PERMATEL (User.agent_login peuplé,
        # cf. GET /connectors/config) — une extension résolue depuis
        # FreeSWITCH n'est retenue dans l'annuaire QUE si elle y figure,
        # pour ne jamais attribuer de présence à une extension PBX sans
        # agent PERMATEL réel derrière (poste de test, agent non nettoyé
        # côté PBX, etc.).
        self._known_agent_logins = set(connector_config.get("known_agent_logins") or [])

    def update_known_agent_logins(self, logins) -> None:
        """Rafraîchi par CoreConnector à chaque sondage périodique (le
        roster PERMATEL peut changer sans redémarrage de l'adapter, ex.
        ajout d'un nouvel agent) — n'affecte que les futures résolutions,
        l'annuaire lui-même n'est pas recalculé immédiatement (attend le
        prochain cycle de _refresh_agent_directory)."""
        self._known_agent_logins = set(logins or [])

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
        `api callcenter_config agent list` (liste globale, SANS scope par
        file).

        Confirmé en prod (29/07) : `agent list <queue>@<domaine>` est
        accepté sans erreur mais ne retourne jamais aucune ligne d'agent
        ('+OK' brut) — ce filtre n'existe pas. mod_callcenter documente
        `agent list [<agent_name>]` : un nom d'agent précis, ou rien du
        tout pour lister tous les agents — jamais une file.

        Limitation connue : un seul domaine par connecteur supporté ici —
        `agent list` global ne permet pas de savoir à quel domaine chaque
        agent appartient s'il y en a plusieurs de configurés sur le même
        connecteur. Journalisé plutôt que deviné.
        """
        if not self._known_agent_logins:
            logger.warning(
                "[%s] Aucun agent_login connu côté PERMATEL pour ce tenant — l'annuaire "
                "restera vide quel que soit le contenu réel de FusionPBX (configurer "
                "le champ Login Agent CC des utilisateurs concernés).",
                self.connector_config["name"],
            )
        else:
            # Journalisé systématiquement (pas seulement si vide) pour pouvoir
            # confirmer, sans deviner, que le roster reçu de PERMATEL contient
            # bien l'extension attendue — vu en prod (29/07) un cas où
            # `agent list` résolvait la bonne extension mais où elle était
            # quand même écartée comme "inconnue" faute de visibilité ici.
            logger.info(
                "[%s] known_agent_logins courant (%d) : %s",
                self.connector_config["name"], len(self._known_agent_logins),
                sorted(self._known_agent_logins),
            )

        domains = list(self._supervised_queues.keys())
        if not domains:
            self._agent_directory = {}
            return
        if len(domains) > 1:
            logger.warning(
                "[%s] Plusieurs domaines configurés (%s) — 'agent list' n'étant pas "
                "filtrable par domaine, l'annuaire agents n'est pas rafraîchi (un "
                "seul domaine par connecteur supporté à ce jour).",
                self.connector_config["name"], domains,
            )
            return

        directory = {}
        self._fetch_agent_list(domains[0], directory)
        self._agent_directory = directory
        logger.info(
            "[%s] Annuaire agents rafraîchi : %d agent(s) résolu(s).",
            self.connector_config["name"], len(directory),
        )

    def _fetch_agent_list(self, domain, directory):
        try:
            response = self._esl.send("api callcenter_config agent list")
        except Exception as exc:
            logger.warning("[%s] Échec de 'agent list' : %s", self.connector_config["name"], exc)
            return

        raw = (getattr(response, "data", None) or "").strip()
        # Journalisé systématiquement (pas seulement en cas d'erreur) tant que
        # le format de colonnes ci-dessus n'a pas été confirmé contre une
        # sortie réelle — à retirer une fois _AGENT_LIST_FIELDS validé.
        logger.info("[%s] agent list -> %r", self.connector_config["name"], raw)
        if not raw or raw.startswith("-ERR"):
            return

        for line in raw.splitlines():
            line = line.strip()
            if not line or line == "+OK" or line.startswith(_AGENT_LIST_HEADER_PREFIX):
                continue
            fields = line.split("|")
            if len(fields) < 3:
                continue
            row = dict(zip(_AGENT_LIST_FIELDS, fields))
            agent_uuid = row.get("name")
            contact = row.get("contact") or ""
            match = _EXTENSION_RE.search(contact)
            if not agent_uuid or not match:
                logger.warning(
                    "[%s] Ligne 'agent list' ininterprétable (uuid ou extension manquant) : %r",
                    self.connector_config["name"], line,
                )
                continue
            extension, contact_domain = match.group(1), match.group(2)
            if contact_domain != domain:
                # `agent list` est global : il renvoie aussi les agents des
                # AUTRES domaines hébergés sur le même FreeSWITCH (confirmé
                # en prod 29/07, ex. domaine "pge.fusion.cloud228.com" vu
                # aux côtés du domaine configuré) — on ne garde que ceux du
                # domaine réellement configuré pour ce connecteur.
                continue
            if extension not in self._known_agent_logins:
                logger.warning(
                    "[%s] Extension '%s' (agent PBX uuid=%s) ignorée : aucun User PERMATEL "
                    "avec ce Login Agent CC pour ce tenant.",
                    self.connector_config["name"], extension, agent_uuid,
                )
                continue
            directory[agent_uuid] = {"domain": domain, "extension": extension}

    def _is_supervised_queue(self, domain: str, queue_id: str | None) -> bool:
        """Confirmé en prod (29/07) : `CC-Queue` est toujours au format
        `<id>@<domaine>` (ex. "8004@africallpbx.fusion.cloud228.com"), alors
        que `_supervised_queues` ne stocke que l'id nu ("8004", venant de la
        config `queue_ids`) — comparer les deux bruts aurait rejeté à tort
        TOUT événement de file en production (bug latent, jamais détecté car
        jusqu'ici seul `agent-status-change`, qui ne passe pas par ce
        filtre, avait été testé contre du trafic réel)."""
        supervised = self._supervised_queues.get(domain)
        if not supervised:
            return True  # pas de filtre configuré pour ce domaine
        queue_bare = (queue_id or "").split("@", 1)[0]
        return queue_bare in supervised

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
            # Diagnostic temporaire (à retirer une fois la corrélation de legs
            # confirmée) : dump inconditionnel pour identifier, sur trafic réel,
            # le header liant les deux legs d'un appel bridgé (Other-Leg-Unique-ID
            # ou équivalent) et la variable portant le DNIS/ANI réel sur les
            # appels entrants — ni l'un ni l'autre n'a jamais été observé à ce
            # jour, uniquement supposé depuis la doc FreeSWITCH.
            logger.info(
                "[%s] %s -> Unique-ID=%s Other-Leg-Unique-ID=%s Call-Direction=%s "
                "Caller-Caller-ID-Number=%s Caller-Destination-Number=%s "
                "variable_dnis=%s variable_ani=%s variable_sip_to_user=%s",
                self.connector_config["name"], headers.get("Event-Name"),
                headers.get("Unique-ID"), headers.get("Other-Leg-Unique-ID"),
                headers.get("Call-Direction"), headers.get("Caller-Caller-ID-Number"),
                headers.get("Caller-Destination-Number"), headers.get("variable_dnis"),
                headers.get("variable_ani"), headers.get("variable_sip_to_user"),
            )
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

        # Diagnostic temporaire (à retirer une fois la corrélation de legs
        # confirmée) : Other-Leg-Unique-ID et variable_dnis/variable_ani
        # confirmés vides sur trafic réel (29/07) — piste abandonnée. On
        # journalise maintenant TOUS les en-têtes de TOUTE action
        # callcenter::info, y compris celles abandonnées faute de
        # 'variable_domain_name' (agent-offering, bridge-agent-fail,
        # members-count…) qui n'étaient jusqu'ici jamais inspectées : l'une
        # d'elles porte peut-être l'identifiant qui relie les legs.
        logger.info(
            "[%s] callcenter::info CC-Action=%r en-têtes=%r",
            self.connector_config["name"], action, dict(headers),
        )

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

        # Confirmé sur trafic réel (29/07) : 'agent-offering' ne porte pas
        # non plus 'variable_domain_name', mais porte en revanche
        # CC-Member-Session-UUID (== Unique-ID du leg entrant déjà en base),
        # CC-Member-DNIS (le vrai numéro composé, jamais réécrit contrairement
        # à Caller-Destination-Number) et CC-Agent — de quoi enrichir l'appel
        # déjà connu sans avoir besoin d'un contexte de canal.
        if action == "agent-offering":
            self._on_member_enrichment_event(headers)
            return

        domain = self._resolve_domain(headers)
        if not domain:
            logger.warning(
                "[%s] callcenter::info (CC-Action=%r) abandonné : 'variable_domain_name' absent des en-têtes.",
                self.connector_config["name"], action,
            )
            return

        queue_id = headers.get("CC-Queue")
        if not self._is_supervised_queue(domain, queue_id):
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

    def _on_member_enrichment_event(self, headers):
        """'agent-offering' — enrichit l'appel déjà connu (même call_uuid
        que le leg entrant, via CC-Member-Session-UUID) avec l'agent, la
        file et le vrai numéro composé. Domaine résolu via l'annuaire agents
        si l'agent y figure, sinon via l'unique domaine configuré sur ce
        connecteur (même repli qu'ailleurs) — jamais deviné silencieusement."""
        agent_uuid = headers.get("CC-Agent")
        entry = self._agent_directory.get(agent_uuid) if agent_uuid else None
        domain = entry["domain"] if entry else None
        agent_login = entry["extension"] if entry else None

        if not domain:
            domains = list(self._supervised_queues.keys())
            domain = domains[0] if len(domains) == 1 else None

        if not domain:
            logger.warning(
                "[%s] agent-offering abandonné : domaine non résolvable (agent uuid=%r absent de "
                "l'annuaire, et plusieurs domaines configurés sur ce connecteur).",
                self.connector_config["name"], agent_uuid,
            )
            return

        if not headers.get("CC-Member-Session-UUID"):
            logger.warning(
                "[%s] agent-offering sans CC-Member-Session-UUID — abandonné.",
                self.connector_config["name"],
            )
            return

        queue_id = headers.get("CC-Queue")
        if not self._is_supervised_queue(domain, queue_id):
            return  # queue non supervisée pour ce tenant — pas transmis

        payload = normalizer.normalize_member_enrichment(headers, domain, agent_login)
        self.ingest_client.send(payload)
