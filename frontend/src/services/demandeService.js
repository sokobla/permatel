import apiClient from "@/services/http/axios";

export async function listDemandes(params = {}) {
  const { data } = await apiClient.get("/demandes", { params });
  return data;
}

export async function getDemande(id) {
  const { data } = await apiClient.get(`/demandes/${id}`);
  return data;
}

export async function createDemande(payload) {
  const { data } = await apiClient.post("/demandes", payload);
  return data;
}

export async function updateDemande(id, payload) {
  const { data } = await apiClient.put(`/demandes/${id}`, payload);
  return data;
}

export async function patchDemandeStatus(id, statut) {
  const { data } = await apiClient.patch(`/demandes/${id}/status`, { statut });
  return data;
}

export async function pecDemande(id) {
  const { data } = await apiClient.patch(`/demandes/${id}/pec`);
  return data;
}

export async function deleteDemande(id) {
  const { data } = await apiClient.delete(`/demandes/${id}`);
  return data;
}

export async function getInteractions(demandeId) {
  const { data } = await apiClient.get(`/demandes/${demandeId}/interactions`);
  return data;
}
