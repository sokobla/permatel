import apiClient from "@/services/http/axios";

export async function searchContacts({ name = "", phone = "", page = 1, perPage = 20 } = {}) {
  const search = [name, phone].filter(Boolean).join(" ").trim();
  const { data } = await apiClient.get("/contacts", {
    params: { search, page, per_page: perPage },
  });
  return data;
}

export async function getContactsForClient(clientId, { perPage = 50 } = {}) {
  const { data } = await apiClient.get("/contacts", {
    params: { client_id: clientId, per_page: perPage },
  });
  return data;
}

export async function createContact(payload) {
  const { data } = await apiClient.post("/contacts", payload);
  return data;
}
