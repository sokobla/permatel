/**
 * Métadonnées d'affichage des intégrations (nom, icône, description).
 *
 * L'ÉTAT (disponible/inactif) n'est PAS défini ici : il est dérivé des canaux
 * du tenant côté backend (app/services/tenant_features.py) et exposé via
 * `authStore.featureMap.integrations` (clés : slack, telephony).
 */
export const INTEGRATIONS = {
  slack: {
    key: "slack",
    name: "Slack",
    icon: "mdi-slack",
    color: "#4A154B",
    tint: "rgba(74,21,75,0.08)",
    desc: "Recevez les alertes d'anomalies et notifications d'équipe dans vos canaux Slack.",
  },
  telephony: {
    key: "telephony",
    name: "Téléphonie",
    icon: "mdi-phone-in-talk-outline",
    color: "#00a8a8",
    tint: "rgba(0,168,168,0.1)",
    desc: "Couplez la téléphonie (ESL/VoIP) pour le suivi des appels entrants et la traçabilité.",
  },
};

export const integrationList = () => Object.values(INTEGRATIONS);
