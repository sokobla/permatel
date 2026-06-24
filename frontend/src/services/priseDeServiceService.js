import apiClient from "@/services/http/axios";

const BASE = "/prises-de-service";

// ── Prises de service ────────────────────────────────────────────────────────
export async function listPrisesDeService(params = {}) {
  const { data } = await apiClient.get(BASE, { params });
  return Array.isArray(data) ? data : data.items ?? [];
}

export async function startPriseDeService(payload) {
  const { data } = await apiClient.post(`${BASE}/start`, payload);
  return data;
}

// Termine la vacation EN COURS d'un agent
export async function endCurrentPriseDeService(agentId) {
  const { data } = await apiClient.post(`${BASE}/end`, { agent_id: agentId });
  return data;
}

// Termine une vacation précise (action de ligne)
export async function endPriseDeService(id) {
  const { data } = await apiClient.post(`${BASE}/${id}/end`);
  return data;
}

export async function getPriseDeServiceStats(params = {}) {
  const { data } = await apiClient.get(`${BASE}/stats`, { params });
  return data;
}

// ── Référentiels pour les autocomplete (réutilise les endpoints existants) ────
export async function fetchAgents() {
  const { data } = await apiClient.get("/agents", { params: { per_page: 500 } });
  return (data.agents ?? data.items ?? []).map((a) => ({
    id: a.id,
    label: `${a.prenom ?? ""} ${a.nom ?? ""}`.trim() + (a.matricule ? ` (${a.matricule})` : ""),
  }));
}

export async function fetchClients() {
  const { data } = await apiClient.get("/clients", { params: { per_page: 500 } });
  return (data.clients ?? data.items ?? []).map((c) => ({ id: c.id, label: c.nom }));
}

export async function fetchSites(clientId) {
  const params = { per_page: 500 };
  if (clientId) params.client_id = clientId;
  const { data } = await apiClient.get("/sites", { params });
  return (data.sites ?? data.items ?? []).map((s) => ({
    id: s.id,
    label: s.nom,
    client_id: s.client_id,
  }));
}
