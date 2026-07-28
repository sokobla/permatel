/**
 * telephonyService — lecture tenant-scopée du module Téléphonie (Supervision).
 * Définitions : voir backend app/routes/telephony.py (source de vérité).
 */
import apiClient from "@/services/http/axios";

export const telephonyService = {
  /** Appels en cours (snapshot au chargement — le WebSocket pousse les deltas ensuite). */
  getActiveCalls() {
    return apiClient.get("/telephony/active-calls");
  },
  /** Volumes, taux de décroché, temps de réponse moyen, sur la période { from, to } (ISO). */
  getKpisSummary(params = {}) {
    return apiClient.get("/telephony/kpis/summary", { params });
  },
  /** Appels par file d'attente, temps d'attente moyen, taux d'abandon. */
  getKpisQueues(params = {}) {
    return apiClient.get("/telephony/kpis/queues", { params });
  },
  /** Présence agent (disponible/pause/hors-ligne) + appels traités sur la période. */
  getAgentsStatus(params = {}) {
    return apiClient.get("/telephony/agents/status", { params });
  },
};
