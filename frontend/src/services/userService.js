/**
 * userService — Service API utilisateurs
 *
 * Préfixes configurables via les variables d'environnement Vite :
 *   VITE_USERS_API_PREFIX   : ex. "/users"     (défaut : /users)
 *   VITE_ROLES_API_PREFIX   : ex. "/roles"     (défaut : /roles)
 *   VITE_TENANTS_API_PREFIX : ex. "/tenants"   (défaut : /tenants)
 *
 * Toutes les requêtes passent par l'instance axios centrale (apiClient)
 * qui gère le baseURL, les headers JWT et le refresh token.
 */
import apiClient from "@/services/http/axios";

const USERS = import.meta.env.VITE_USERS_API_PREFIX || "/users";
const ROLES = import.meta.env.VITE_ROLES_API_PREFIX || "/roles";
const TENANTS = import.meta.env.VITE_TENANTS_API_PREFIX || "/tenants";

export const userService = {
  /**
   * Récupère la liste paginée des utilisateurs.
   * @param {Object} params { page, per_page, search, status, sort_by, sort_order }
   */
  getUsers(params = {}) {
    return apiClient.get(USERS, { params });
  },

  /**
   * Récupère un utilisateur par son ID.
   * @param {number|string} id
   */
  getUser(id) {
    return apiClient.get(`${USERS}/${id}`);
  },

  /**
   * Crée un nouvel utilisateur.
   * Accepte un objet JSON ou un FormData (si l'avatar est fourni).
   * @param {Object|FormData} data
   */
  createUser(data) {
    console.log("Payload reçu pour création :", data);

    const config = {};
    // Si les données sont de type FormData, il est CRUCIAL de ne PAS définir
    // le header 'Content-Type'. Le navigateur doit le faire lui-même pour
    // inclure la délimitation (boundary) requise pour le multipart.
    // En passant `undefined`, on s'assure d'écraser un éventuel `Content-Type`
    // global défini par erreur dans l'instance axios.
    if (data instanceof FormData) {
      config.headers = { "Content-Type": undefined };
    }

    return apiClient.post(USERS, data, config);
  },

  /**
   * Met à jour un utilisateur existant.
   * @param {number|string} id
   * @param {Object|FormData} data
   */
  updateUser(id, data) {
    const config = {};
    if (data instanceof FormData) {
      config.headers = { "Content-Type": undefined };
    }
    // Comme pour createUser, laisser Axios gérer le Content-Type pour FormData.
    return apiClient.put(`${USERS}/${id}`, data, config);
  },

  /**
   * Supprime un utilisateur.
   * @param {number|string} id
   */
  deleteUser(id) {
    return apiClient.delete(`${USERS}/${id}`);
  },

  /**
   * Réinitialise le mot de passe d'un utilisateur.
   * @param {number|string} id
   * @param {string} new_password
   */
  resetPassword(id, new_password) {
    return apiClient.patch(`${USERS}/${id}/password`, { new_password });
  },
  /**
   * Récupère les rôles disponibles (pour le select du formulaire).
   * Réponse attendue : { roles: [{ value, label }] }
   */
  getRoles() {
    return apiClient.get(ROLES);
  },

  /**
   * Récupère les tenants disponibles (pour le select du formulaire).
   * Réponse attendue : { tenants: [{ id, name }] }
   */
  getTenants() {
    return apiClient.get(TENANTS);
  },
};
