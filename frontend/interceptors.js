import apiClient from "./apiClient";
// Potentiellement, importer le store Pinia pour accéder au token de manière réactive.
// import { useAuthStore } from '@/stores/authStore';

export function setupInterceptors() {
  // const authStore = useAuthStore();

  apiClient.interceptors.request.use(
    (config) => {
      // Pour l'instant, on garde localStorage, mais l'idéal serait d'utiliser Pinia.
      const token = localStorage.getItem("accessToken");
      // const token = authStore.accessToken;

      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    },
  );
}
