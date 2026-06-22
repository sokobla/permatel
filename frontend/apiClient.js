import axios from "axios";

// Crée une instance d'Axios avec une configuration de base.
// Le baseURL est récupéré des variables d'environnement de Vite.
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api",
  headers: {
    "Content-Type": "application/json",
  },
});

export default apiClient;
