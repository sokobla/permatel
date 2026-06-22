import apiClient from "@/services/http/axios";

export async function getSitesForClient(clientId, { perPage = 50 } = {}) {
  const { data } = await apiClient.get("/sites", {
    params: { client_id: clientId, per_page: perPage, status: "true" },
  });
  return data;
}

export async function createSite(payload) {
  const { data } = await apiClient.post("/sites", payload);
  return data;
}
