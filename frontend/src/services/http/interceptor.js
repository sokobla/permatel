/**
 * Intercepteurs Axios PERMATEL
 *
 * Request interceptor :
 *   Injecte l'access token JWT dans Authorization sur chaque requete sortante.
 *
 * Response interceptor (gestion des 401) :
 *   1. Requete deja en retry  -> logout silencieux (evite boucle infinie).
 *   2. Requete vers /auth/refresh qui echoue -> refresh token invalide,
 *      logout silencieux + redirect /login.
 *   3. Refresh deja en cours  -> mettre la requete en file d'attente,
 *      la rejouer quand le refresh se termine (evite N appels concurrents).
 *   4. Cas standard           -> lancer le refresh, rejouer la requete,
 *      debloquer la file. En cas d'echec : logout + redirect /login.
 *
 * Note : le refresh appelle axios directement (pas apiClient) afin de passer
 * le refresh token dans Authorization sans passer par le request interceptor
 * qui injecterait l'access token (maintenant invalide).
 */
import axios from "axios";
import apiClient from "./axios";
import { useAuthStore } from "@/store/auth";
import router from "@/router";

// --- Etat interne du mecanisme de refresh -----------------------------------

/** Vrai quand un appel /auth/refresh est deja en cours. */
let isRefreshing = false;

/**
 * File d'attente des requetes ayant recu un 401 pendant un refresh en cours.
 * Chaque entree : { resolve, reject } d'une Promise enveloppant la requete.
 */
let failedQueue = [];

/**
 * Resout ou rejette toutes les requetes en attente apres le refresh.
 *
 * @param {Error|null} error     - null si le refresh a reussi
 * @param {string|null} newToken - nouveau access token, ou null si echec
 */
function processQueue(error, newToken = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(newToken);
    }
  });
  failedQueue = [];
}

// --- Installation des intercepteurs -----------------------------------------

/**
 * Configure les intercepteurs request et response sur l'instance apiClient.
 * Doit etre appele dans main.js APRES app.use(pinia).
 */
export function setupInterceptors() {
  // -- Request interceptor : injection du Bearer token ----------------------
  apiClient.interceptors.request.use(
    (config) => {
      const authStore = useAuthStore();
      if (authStore.accessToken) {
        config.headers["Authorization"] = `Bearer ${authStore.accessToken}`;
      }
      return config;
    },
    (error) => Promise.reject(error),
  );

  // -- Response interceptor : gestion des 401 --------------------------------
  apiClient.interceptors.response.use(
    // Succes : laisser passer sans modification.
    (response) => response,

    // Erreur : traiter les 401 uniquement.
    async (error) => {
      const originalRequest = error.config;

      // Cas 1 : pas un 401 ou pas de config (erreur reseau, etc.)
      if (!error.response || error.response.status !== 401) {
        return Promise.reject(error);
      }

      // Cas 2 : cette requete est deja un retry -> eviter la boucle infinie.
      if (originalRequest._retry) {
        return Promise.reject(error);
      }

      // Cas 3 : le 401 vient du endpoint /auth/refresh lui-meme.
      // Le refresh token est expire ou revoque -> deconnexion immediate.
      if (
        originalRequest.url &&
        originalRequest.url.includes("/auth/refresh")
      ) {
        const authStore = useAuthStore();
        authStore.logoutSilent();
        router.push({ name: "Login" });
        return Promise.reject(error);
      }

      // Cas 4 : un refresh est deja en cours -> mettre en file d'attente.
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((newToken) => {
          originalRequest.headers["Authorization"] = `Bearer ${newToken}`;
          return apiClient(originalRequest);
        });
      }

      // Cas 5 : demarrer un nouveau refresh.
      originalRequest._retry = true;
      isRefreshing = true;

      const authStore = useAuthStore();

      // Cas 5a : pas de refresh token disponible -> logout immediat.
      if (!authStore.refreshToken) {
        isRefreshing = false;
        authStore.logoutSilent();
        router.push({ name: "Login" });
        return Promise.reject(error);
      }

      try {
        // Appel direct avec le refresh token dans Authorization.
        // On n'utilise pas apiClient pour ne pas injecter l'access token expire.
        const refreshResponse = await axios.post(
          `${apiClient.defaults.baseURL}/auth/refresh`,
          {},
          {
            headers: {
              Authorization: `Bearer ${authStore.refreshToken}`,
            },
          },
        );

        const newAccessToken = refreshResponse.data.access_token;

        // Mettre a jour le store avec le nouveau token.
        authStore.setAccessToken(newAccessToken);

        // Debloquer toutes les requetes en attente.
        processQueue(null, newAccessToken);

        // Rejouer la requete originale avec le nouveau token.
        originalRequest.headers["Authorization"] = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Le refresh a echoue : rejeter la file et deconnecter.
        processQueue(refreshError, null);
        authStore.logoutSilent();
        router.push({ name: "Login" });
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    },
  );
}
