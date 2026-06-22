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

  /** Liste des utilisateurs rattachés à un tenant (pour filtrer les KPI). */
  getTenantUsers(tenantId) {
    return apiClient.get(`/tenants/${tenantId}/users`);
  },
};
