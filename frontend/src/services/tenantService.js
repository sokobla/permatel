/**
 * tenantService — lecture/écriture d'un tenant (paramètres généraux).
 */
import apiClient from "@/services/http/axios";

export const tenantService = {
  getTenant(id) {
    return apiClient.get(`/tenants/${id}`);
  },
  /** payload : objet JSON, ou FormData ({ data: JSON, logo: File }). */
  updateTenant(id, payload) {
    const cfg =
      payload instanceof FormData
        ? { headers: { "Content-Type": "multipart/form-data" } }
        : undefined;
    return apiClient.put(`/tenants/${id}`, payload, cfg);
  },
};
