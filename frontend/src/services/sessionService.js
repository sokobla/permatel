/**
 * sessionService — supervision & révocation des sessions utilisateurs.
 */
import apiClient from "@/services/http/axios";

export const sessionService = {
  /**
   * Sessions du tenant actif (supervision, STAFF).
   * @param {Object} params { status: 'live' | 'all' }
   */
  getMonitoring(params = {}) {
    return apiClient.get("/auth/sessions/monitoring", { params });
  },

  /** Révoque une session par son id. */
  revokeSession(id) {
    return apiClient.delete(`/auth/sessions/${id}`);
  },

  /** Sessions de l'utilisateur courant. */
  getMySessions() {
    return apiClient.get("/auth/sessions");
  },

  /**
   * KPI agrégés de sessions pour le tenant actif.
   * @param {Object} params { from: ISO, to: ISO, user_id?: number }
   */
  getMonitoringStats(params = {}) {
    return apiClient.get("/auth/sessions/stats", { params });
  },

  /** Export CSV des sessions du tenant actif (mêmes filtres que getMonitoring) — réponse blob. */
  exportMonitoringCsv(params = {}) {
    return apiClient.get("/auth/sessions/monitoring/export", {
      params,
      responseType: "blob",
    });
  },

  /** Vue journalière consolidée : une ligne par (utilisateur, date). */
  getMonitoringDaily(params = {}) {
    return apiClient.get("/auth/sessions/monitoring/daily", { params });
  },

  /** Export CSV de la vue journalière consolidée — réponse blob. */
  exportMonitoringDailyCsv(params = {}) {
    return apiClient.get("/auth/sessions/monitoring/daily/export", {
      params,
      responseType: "blob",
    });
  },

  /** Liste des utilisateurs rattachés à un tenant (pour filtrer les KPI). */
  getTenantUsers(tenantId) {
    return apiClient.get(`/tenants/${tenantId}/users`);
  },
};
