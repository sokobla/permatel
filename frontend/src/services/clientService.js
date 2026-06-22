import apiClient from "@/services/http/axios";

export async function searchClients({ search = "", page = 1, perPage = 20 } = {}) {
  const { data } = await apiClient.get("/clients", {
    params: { search, page, per_page: perPage },
  });
  return data;
}

export async function getClient(clientId) {
  const { data } = await apiClient.get(`/clients/${clientId}`);
  return data;
}

export async function createClient(payload) {
  const { data } = await apiClient.post("/clients", payload);
  return data;
}
