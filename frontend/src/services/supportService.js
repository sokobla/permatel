/**
 * supportService — envoi des demandes de contact support.
 * Endpoint public (utilisable depuis LoginView, pré-authentification).
 */
import apiClient from "@/services/http/axios";

export const supportService = {
  /**
   * @param {Object} payload { nom, prenom, email, entreprise, objet, message }
   */
  async sendSupportRequest(payload) {
    const { data } = await apiClient.post("/support", payload);
    return data;
  },
};
