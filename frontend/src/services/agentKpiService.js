/**
 * agentKpiService — KPI & score des agents de sécurité.
 * Définitions : voir backend app/services/agent_kpis.py (source de vérité).
 */
import apiClient from "@/services/http/axios";

export const agentKpiService = {
  /** KPI d'un agent sur une période { from, to } (ISO). Défaut backend : 30j. */
  getAgentKpis(agentId, params = {}) {
    return apiClient.get(`/agents/${agentId}/kpis`, { params });
  },
  /** KPI agrégés de tous les agents (tableau de bord, staff). */
  getAgentsKpis(params = {}) {
    return apiClient.get("/agents/kpis", { params });
  },
  /** Répartition des agents par qualification */
  getAgentsStats() {
    return apiClient.get("/agents/stats");
  },
};
