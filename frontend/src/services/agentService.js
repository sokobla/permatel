/**
 * agentService.js
 *
 * Service pour les opérations CRUD sur les agents de sécurité.
 * Les endpoints sont hypothétiques et devront correspondre au backend.
 */
import apiClient from "@/services/http/axios";

const resource = "/agents";

export const agentService = {
  /**
   * Récupère la liste paginée des agents.
   * @param {object} params - Paramètres de pagination, filtre, tri.
   * @returns {Promise}
   */
  getAgents(params) {
    return apiClient.get(resource, { params });
  },

  /**
   * Crée un nouvel agent.
   * @param {FormData|object} payload - Données de l'agent.
   * @returns {Promise}
   */
  createAgent(payload) {
    const headers =
      payload instanceof FormData
        ? { "Content-Type": "multipart/form-data" }
        : {};
    return apiClient.post(resource, payload, { headers });
  },

  /**
   * Met à jour un agent.
   * @param {string|number} agentId - ID de l'agent.
   * @param {FormData|object} payload - Données de l'agent.
   * @returns {Promise}
   */
  updateAgent(agentId, payload) {
    const headers =
      payload instanceof FormData
        ? { "Content-Type": "multipart/form-data" }
        : {};
    // Pour FormData avec PUT, certains backends préfèrent POST avec un champ _method
    return apiClient.post(`${resource}/${agentId}`, payload, { headers });
  },

  /**
   * Supprime un agent.
   * @param {string|number} agentId - ID de l'agent.
   * @returns {Promise}
   */
  deleteAgent(agentId) {
    return apiClient.delete(`${resource}/${agentId}`);
  },

  /**
   * Récupère la liste des prestataires pour les selects.
   */
  getPrestataires() {
    return apiClient.get("/prestataires", { params: { per_page: 1000 } }); // On charge tout pour un dropdown
  },
};
