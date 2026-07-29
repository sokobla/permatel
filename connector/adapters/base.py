# -*- coding: utf-8 -*-
"""Contrat commun à tous les PBXAdapter (ESL aujourd'hui, AMI en Phase 14).

Orchestrés par le même Core Connector (un seul process, cf.
TELEPHONIE_INTEGRATION_PLAN.md §4) : chaque adapter tourne dans sa propre
greenlet gevent, indépendante des autres, et ne doit jamais laisser une
exception remonter jusqu'au CoreConnector (elle romprait la supervision des
autres PBX) — `run()` doit boucler indéfiniment en absorbant ses propres
erreurs (reconnexion, backoff).
"""


class PBXAdapter:
    def __init__(self, connector_config: dict, ingest_client):
        self.connector_config = connector_config
        self.ingest_client = ingest_client
        self._stopping = False
        self.last_error = None

    def run(self):
        """Boucle bloquante (tourne dans sa propre greenlet). Ne retourne
        qu'après appel à `stop()`."""
        raise NotImplementedError

    def stop(self):
        self._stopping = True

    def force_reconnect(self):
        """Bouton "Sync" (Paramètres > Téléphonie) — force une reconnexion
        immédiate sans attendre le prochain sondage périodique de config.
        Implémentation par défaut : no-op (adapter ne gérant pas de notion
        de connexion persistante)."""
        pass

    def update_known_agent_logins(self, logins):
        """Roster PERMATEL faisant autorité (User.agent_login), rafraîchi
        par CoreConnector à chaque sondage périodique sans redémarrer
        l'adapter. Implémentation par défaut : no-op (adapter ne résolvant
        pas d'identité agent, ex. futur AMIAdapter avant implémentation)."""
        pass

    @property
    def is_connected(self) -> bool:
        """État live rapporté au heartbeat (POST /connectors/status)."""
        return False
