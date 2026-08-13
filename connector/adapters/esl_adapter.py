# -*- coding: utf-8 -*-
"""ESLAdapter — connecteur FusionPBX/FreeSWITCH via mod_event_socket (ESL).

Connexion "inbound" (le connecteur se connecte à FusionPBX comme un client,
port 8021 par défaut). Une greenlet gevent par PbxConnector de type ESL,
orchestrée par CoreConnector — jamais un process séparé (cf. §4 du plan).
"""
import logging
import re
import time

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

# Confirmé sur trafic réel (30/07) : quand mod_callcenter tente de sonner un
# agent pour un appel de file (événement 'agent-offering'), il crée un
# CHANNEL_CREATE outbound SÉPARÉ vers l'extension de cet agent (ex.
# Destination-Number=22101001) — un leg purement interne à la tentative de
# pont, jamais rattaché par un header CC-* et jamais bridgé si l'agent ne
# répond pas (Other-Leg-Unique-ID reste vide). Sans corrélation, ce leg
# apparaît comme un appel fantôme distinct dans /active-calls (confirmé :
# un appel de file réel produisait 3 lignes au lieu de 2). Fenêtre de
# validité courte : l'attribution extension -> tentative doit être consommée
# quasi immédiatement (le CHANNEL_CREATE suit l'agent-offering de quelques
# millisecondes sur trafic réel) ; expire pour ne jamais retenir une entrée
# périmée si un événement intermédiaire est perdu.
_PENDING_AGENT_RING_TTL_SECONDS = 30

# Cooldown avant de retenter un rafraîchissement CIBLÉ de l'annuaire agents
# suite à un 'agent-status-change' pour un uuid inconnu (13/08) — sans lui,
# un agent PBX jamais déclaré côté PERMATEL (poste de test, ancien agent non
# nettoyé) déclencherait un `agent list` à CHAQUE changement de statut tant
# qu'il reste inconnu. Volontairement plus court que
# AGENT_DIRECTORY_REFRESH_SECONDS (rafraîchissement périodique, 300s par
# défaut) : le but ici est justement de rattraper vite un agent légitime
# qui vient d'être déclaré côté PERMATEL, ou un annuaire simplement pas
# encore à jour — pas de remplacer le cycle périodique.
_UNKNOWN_AGENT_REFRESH_COOLDOWN_SECONDS = 60


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

        # uuid FreeSWITCH (CC-Agent) -> {"domain":..., "extension":...} —
        # construit via _refresh_agent_directory(), nécessaire car les
        # événements agent-status-change ne portent ni domaine ni identifiant
        # exploitable directement (confirmé sur trafic réel, voir
        # _on_callcenter_info). `extension` n'est que le poste physique
        # actuellement associé (le `contact` FreeSWITCH, ex. "22101001") —
        # peut changer si l'agent se loggue sur un autre poste ; l'identité
        # stable transmise en aval (agent.login) est l'UUID lui-même,
        # jamais l'extension (voir _on_agent_status_event et consorts).
        self._agent_directory = {}
        self._agent_directory_greenlet = None
        # extension -> (CC-Member-Session-UUID, horodatage) : posé par
        # agent-offering, consommé par le prochain CHANNEL_CREATE outbound
        # vers cette extension (voir _consume_pending_agent_ring) pour tagger
        # ce leg de tentative comme lié au même appel physique plutôt que de
        # le laisser apparaître comme un appel fantôme.
        self._pending_agent_rings = {}
        # uuid inconnu -> horodatage (time.monotonic()) de la dernière
        # tentative de rafraîchissement ciblé de l'annuaire déclenchée pour
        # lui (cf. _on_agent_status_event) — débounce pour ne pas appeler
        # 'agent list' à chaque événement d'un agent qui restera inconnu
        # (poste de test jamais nettoyé côté PBX, etc.).
        self._unknown_agent_refresh_attempts = {}
        # Roster faisant autorité côté PERMATEL : `User.agent_login` contient
        # désormais l'UUID FusionPBX de l'agent (CC-Agent / colonne "name" de
        # 'agent list'), PAS l'extension — un agent PBX découvert via
        # 'agent list' n'est retenu dans l'annuaire QUE si son UUID figure
        # dans ce roster, pour ne jamais attribuer de présence à un agent PBX
        # non déclaré côté PERMATEL (poste de test, agent non nettoyé côté
        # PBX, etc.).
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
            # bien l'uuid attendu — vu en prod (29/07, avant le passage à un
            # roster par uuid) un cas où `agent list` résolvait bien l'agent
            # mais où il était quand même écarté comme "inconnu" faute de
            # visibilité ici.
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
            if agent_uuid not in self._known_agent_logins:
                logger.warning(
                    "[%s] Agent PBX uuid=%s (extension=%s) ignoré : non déclaré côté PERMATEL "
                    "(aucun User.agent_login avec cet uuid pour ce tenant).",
                    self.connector_config["name"], agent_uuid, extension,
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
                "variable_dnis=%s variable_ani=%s variable_sip_to_user=%s "
                "Hangup-Cause=%s variable_billsec=%s variable_record_file_path=%s",
                self.connector_config["name"], headers.get("Event-Name"),
                headers.get("Unique-ID"), headers.get("Other-Leg-Unique-ID"),
                headers.get("Call-Direction"), headers.get("Caller-Caller-ID-Number"),
                headers.get("Caller-Destination-Number"), headers.get("variable_dnis"),
                headers.get("variable_ani"), headers.get("variable_sip_to_user"),
                headers.get("Hangup-Cause"), headers.get("variable_billsec"),
                headers.get("variable_record_file_path"),
            )
            domain = self._resolve_domain(headers)
            if not domain:
                return  # pas de domaine FusionPBX sur ce canal (config PBX incomplète)
            payload = normalize_fn(headers, domain)
            if payload:
                # Tentative de sonnerie agent pour un appel de file (voir
                # _on_member_enrichment_event) : ce leg outbound n'est jamais
                # lié par Other-Leg-Unique-ID s'il n'aboutit pas
                # (bridge-agent-fail) — sans ce raccroc, il apparaît comme un
                # appel fantôme distinct dans /active-calls. Ne s'applique
                # qu'au CHANNEL_CREATE : c'est le seul événement du leg où
                # cette tentative est encore en attente (posée juste avant),
                # et une fois taggé, la fusion backend (linked_call_uuid)
                # n'a plus besoin d'être reposée sur ANSWER/HANGUP_COMPLETE.
                if (
                    headers.get("Event-Name") == "CHANNEL_CREATE"
                    and headers.get("Call-Direction") == "outbound"
                ):
                    member_session_uuid = self._consume_pending_agent_ring(
                        headers.get("Caller-Destination-Number")
                    )
                    if member_session_uuid:
                        payload["call"]["linked_call_uuid"] = member_session_uuid
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

        # Confirmé sur trafic réel (30/07) : 'bridge-agent-start' est la
        # SEULE source du chemin d'enregistrement d'un appel de file — porté
        # par 'variable_execute_on_pre_bridge' sur le leg agent, déjà résolu
        # par FreeSWITCH avec l'UUID du leg membre comme nom de fichier
        # ('variable_record_file_path' reste None partout, y compris ici).
        if action == "bridge-agent-start":
            self._on_bridge_recording_event(headers)
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

    def _retry_after_targeted_refresh(self, agent_uuid, raw_status):
        """Rattrapage (13/08) : un 'agent-status-change' pour un uuid absent
        de l'annuaire ne signifie pas forcément un agent illégitime — ça peut
        être un annuaire simplement pas encore à jour (cycle périodique pas
        encore passé) ou un agent qui vient tout juste d'être déclaré côté
        PERMATEL (`User.agent_login`). Plutôt que d'attendre jusqu'à
        AGENT_DIRECTORY_REFRESH_SECONDS (300s par défaut), on retente un
        rafraîchissement immédiat une seule fois, borné par un cooldown par
        uuid pour ne pas marteler `agent list` pour un agent qui restera
        durablement inconnu (poste de test, agent non nettoyé côté PBX).
        Retourne l'entrée d'annuaire si la reconfirmation aboutit, sinon
        None (et journalise dans les deux cas)."""
        now = time.monotonic()
        last_attempt = self._unknown_agent_refresh_attempts.get(agent_uuid)
        if last_attempt is not None and now - last_attempt < _UNKNOWN_AGENT_REFRESH_COOLDOWN_SECONDS:
            logger.warning(
                "[%s] agent-status-change pour un agent absent de l'annuaire (uuid=%s, statut=%r) — "
                "déjà retenté récemment, abandonné (cooldown %ss).",
                self.connector_config["name"], agent_uuid, raw_status,
                _UNKNOWN_AGENT_REFRESH_COOLDOWN_SECONDS,
            )
            return None

        self._unknown_agent_refresh_attempts[agent_uuid] = now
        logger.info(
            "[%s] agent-status-change pour un agent absent de l'annuaire (uuid=%s, statut=%r) — "
            "rafraîchissement immédiat de l'annuaire avant abandon.",
            self.connector_config["name"], agent_uuid, raw_status,
        )
        self._refresh_agent_directory()
        entry = self._agent_directory.get(agent_uuid)
        if entry is not None:
            logger.info(
                "[%s] agent uuid=%s retrouvé après rafraîchissement ciblé — événement transmis.",
                self.connector_config["name"], agent_uuid,
            )
        else:
            logger.warning(
                "[%s] agent-status-change pour un agent absent de l'annuaire (uuid=%s, statut=%r) — "
                "toujours inconnu après rafraîchissement immédiat : non déclaré côté PERMATEL, ou "
                "annuaire non rafraîchi (plusieurs domaines configurés sur ce connecteur, cf. "
                "_refresh_agent_directory).",
                self.connector_config["name"], agent_uuid, raw_status,
            )
        return entry

    def _on_agent_status_event(self, headers, action):
        if action == "agent-status-get":
            return  # lecture passive (ex. rafraîchissement d'un écran admin), pas une transition réelle

        agent_uuid = headers.get("CC-Agent")
        entry = self._agent_directory.get(agent_uuid)
        if entry is None:
            entry = self._retry_after_targeted_refresh(agent_uuid, headers.get("CC-Agent-Status"))
        if entry is None:
            return  # toujours inconnu après tentative de rattrapage (ou debounced) — abandonné, déjà journalisé

        # agent.login = l'uuid lui-même (identité stable, == User.agent_login
        # désormais) — PAS entry["extension"], qui n'est que le poste
        # physique actuellement associé et peut changer sans que ce soit un
        # changement d'agent. L'extension est quand même transmise à part
        # (agent.station, poste observé en direct) — cf. normalizer.py.
        payload = normalizer.normalize_agent_status_change(headers, entry["domain"], agent_uuid, entry["extension"])
        self.ingest_client.send(payload)

    def _on_member_enrichment_event(self, headers):
        """'agent-offering' — enrichit l'appel déjà connu (même call_uuid
        que le leg entrant, via CC-Member-Session-UUID) avec l'agent, la
        file et le vrai numéro composé. Domaine résolu via l'annuaire agents
        si l'agent y figure, sinon via l'unique domaine configuré sur ce
        connecteur (même repli qu'ailleurs) — jamais deviné silencieusement."""
        agent_uuid = headers.get("CC-Agent")
        entry = self._agent_directory.get(agent_uuid) if agent_uuid else None
        if agent_uuid and entry is None:
            # Rattrapage (13/08, même motif que _on_agent_status_event) :
            # cet événement alimente désormais aussi la détection de
            # présence côté PERMATEL (agents_status), donc perdre l'identité
            # ici faute d'annuaire à jour a le même coût qu'un statut manuel
            # jamais reçu.
            entry = self._retry_after_targeted_refresh(agent_uuid, None)
        domain = entry["domain"] if entry else None
        # agent.login = l'uuid lui-même (== User.agent_login désormais), pas
        # l'extension/poste physique — voir _on_agent_status_event.
        agent_login = agent_uuid if entry else None

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

        # Poser la tentative AVANT d'envoyer l'enrichissement : mod_callcenter
        # origine le CHANNEL_CREATE de la tentative de pont quelques
        # millisecondes après cet événement (confirmé sur trafic réel 30/07),
        # donc l'ordre importe peu ici, mais autant l'enregistrer dès que
        # l'extension est connue plutôt que d'attendre l'envoi réseau.
        extension = entry["extension"] if entry else None
        if extension:
            self._pending_agent_rings[extension] = (headers.get("CC-Member-Session-UUID"), time.monotonic())

        payload = normalizer.normalize_member_enrichment(
            headers, domain, agent_login, entry["extension"] if entry else None,
        )
        self.ingest_client.send(payload)

    def _consume_pending_agent_ring(self, extension):
        """Consomme (une seule fois) la tentative de sonnerie en attente pour
        cette extension, posée par _on_member_enrichment_event — None si
        aucune tentative en attente ou si elle a expiré (voir
        _PENDING_AGENT_RING_TTL_SECONDS)."""
        entry = self._pending_agent_rings.pop(extension, None)
        if not entry:
            return None
        member_session_uuid, posed_at = entry
        if time.monotonic() - posed_at > _PENDING_AGENT_RING_TTL_SECONDS:
            return None
        return member_session_uuid

    def _on_bridge_recording_event(self, headers):
        """'bridge-agent-start' — même contexte que 'agent-offering' (pas de
        'variable_domain_name', résolution du domaine/agent via l'annuaire
        agents ou repli sur l'unique domaine configuré), mais porte le seul
        chemin d'enregistrement exploitable pour un appel de file (voir
        normalizer.normalize_bridge_recording)."""
        agent_uuid = headers.get("CC-Agent")
        entry = self._agent_directory.get(agent_uuid) if agent_uuid else None
        if agent_uuid and entry is None:
            # Rattrapage (13/08, même motif que _on_agent_status_event) —
            # voir le commentaire équivalent dans _on_member_enrichment_event.
            entry = self._retry_after_targeted_refresh(agent_uuid, None)
        domain = entry["domain"] if entry else None
        # agent.login = l'uuid lui-même (== User.agent_login désormais), pas
        # l'extension/poste physique — voir _on_agent_status_event.
        agent_login = agent_uuid if entry else None

        if not domain:
            domains = list(self._supervised_queues.keys())
            domain = domains[0] if len(domains) == 1 else None

        if not domain:
            logger.warning(
                "[%s] bridge-agent-start abandonné : domaine non résolvable (agent uuid=%r absent de "
                "l'annuaire, et plusieurs domaines configurés sur ce connecteur).",
                self.connector_config["name"], agent_uuid,
            )
            return

        queue_id = headers.get("CC-Queue")
        if not self._is_supervised_queue(domain, queue_id):
            return  # queue non supervisée pour ce tenant — pas transmis

        payload = normalizer.normalize_bridge_recording(
            headers, domain, agent_login, entry["extension"] if entry else None,
        )
        if payload is None:
            logger.warning(
                "[%s] bridge-agent-start sans chemin d'enregistrement exploitable (CC-Member-Session-UUID "
                "ou variable_execute_on_pre_bridge absent/non reconnu) — abandonné.",
                self.connector_config["name"],
            )
            return
        self.ingest_client.send(payload)
