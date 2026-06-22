/**
 * partnerService — Service API pour les prestataires
 */
import apiClient from "@/services/http/axios";

const PARTNERS_PREFIX = "/prestataires";

export const partnerService = {
  /**
   * Récupère la liste paginée des prestataires.
   * @param {Object} params { page, per_page, search, status, sort_by, sort_order }
   */
  getPartners(params = {}) {
    return apiClient.get(PARTNERS_PREFIX, { params });
  },

  /**
   * Crée un nouveau prestataire.
   * @param {FormData} data - Les données du formulaire, y compris le logo.
   */
  createPartner(data) {
    return apiClient.post(PARTNERS_PREFIX, data, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  /**
   * Met à jour un prestataire existant.
   * @param {string} id - L'UUID du prestataire.
   * @param {FormData} data - Les données du formulaire.
   */
  updatePartner(id, data) {
    // On utilise POST pour la mise à jour avec FormData, car c'est plus simple
    // et mieux supporté que PUT avec multipart. Le backend est configuré pour l'accepter.
    return apiClient.post(`${PARTNERS_PREFIX}/${id}`, data, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  /**
   * Désactive un prestataire (soft delete).
   * @param {string} id - L'UUID du prestataire.
   */
  deactivatePartner(id) {
    return apiClient.patch(`${PARTNERS_PREFIX}/${id}/status`, { is_active: false });
  },
};