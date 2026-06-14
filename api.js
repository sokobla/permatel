import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:5000/api', // Corresponds to the Flask backend URL
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to add the auth token to requests
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken'); // Or get from Pinia store
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export default apiClient;