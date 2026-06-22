import apiClient from "@/services/http/axios";

export async function createInteraction(demandeId, { type_interaction, contenu, contact_id }) {
  const { data } = await apiClient.post("/interactions", {
    demande_id: demandeId,
    type_interaction,
    contenu,
    contact_id: contact_id ?? null,
  });
  return data;
}
