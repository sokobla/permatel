/**
 * Service d'authentification PERMATEL
 *
 * Centralise tous les appels API liés à l'authentification.
 * Ne jamais appeler apiClient directement depuis les composants ou le store
 * pour ces opérations — passer toujours par ce service.
 */
import apiClient from "@/services/http/axios";

export const authService = {
  /** Authentifie un utilisateur par username + password. */
  login(username, password) {
    return apiClient.post("/auth/login", { username, password });
  },

  /** Révoque les tokens et ferme la session côté serveur. */
  logout() {
    return apiClient.post("/auth/logout");
  },

  /**
   * Renouvelle l'access token via le refresh token.
   * Note : cet appel est géré directement par l'intercepteur (interceptor.js)
   * avec axios brut pour passer le refresh token dans le header.
   * Cette méthode reste disponible pour usage manuel si nécessaire.
   */
  refresh() {
    return apiClient.post("/auth/refresh");
  },

  /** Retourne le profil de l'utilisateur connecté. */
  getProfile() {
    return apiClient.get("/auth/me");
  },

  /**
   * Sélectionne le tenant actif après login (flow multi-tenant).
   * Retourne de nouveaux tokens JWT incluant le claim `tid`.
   *
   * @param {string} tenantId — UUID du tenant à activer
   */
  selectTenant(tenantId) {
    return apiClient.post("/auth/select-tenant", { tenant_id: tenantId });
  },

  /**
   * Liste les tenants accessibles par l'utilisateur courant
   * (tous les tenants actifs si super-admin, sinon ses appartenances).
   */
  getTenants() {
    return apiClient.get("/auth/tenants");
  },

  /** Disponibilités fonctionnelles du tenant actif (canaux, onglets, sections). */
  getFeatures() {
    return apiClient.get("/tenant/features");
  },
};
