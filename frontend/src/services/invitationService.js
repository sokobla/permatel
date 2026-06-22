/**
 * invitationService — acceptation publique d'une invitation (sans authentification).
 */
import apiClient from "@/services/http/axios";

export const invitationService = {
  /** Détails minimaux d'une invitation (tenant, email, type de compte). */
  get(token) {
    return apiClient.get(`/invitations/${token}`);
  },
  /** Accepte l'invitation : { nom, prenom, password } pour un nouveau compte. */
  accept(token, payload = {}) {
    return apiClient.post(`/invitations/${token}/accept`, payload);
  },
};
