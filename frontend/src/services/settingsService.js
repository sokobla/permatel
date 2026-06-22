/**
 * settingsService — paramètres système (SMTP, valeurs de référence).
 *
 * Branché sur les endpoints backend tenant-scopés (/api/settings/*).
 * Lecture : utilisateur authentifié ; écriture : ADMIN.
 */
import apiClient from "@/services/http/axios";

export const settingsService = {
  // ── SMTP ───────────────────────────────────────────────────────────────────
  async getSmtp() {
    const { data } = await apiClient.get("/settings/smtp");
    return data;
  },
  async saveSmtp(payload) {
    const { data } = await apiClient.put("/settings/smtp", payload);
    return data;
  },
  async testSmtp(payload) {
    const { data } = await apiClient.post("/settings/smtp/test", payload);
    if (!data.ok) {
      throw new Error(data.error || "Échec du test de connexion.");
    }
    return data;
  },

  // ── IMAP (réception) ─────────────────────────────────────────────────────────
  async getImap() {
    const { data } = await apiClient.get("/settings/imap");
    return data;
  },
  async saveImap(payload) {
    const { data } = await apiClient.put("/settings/imap", payload);
    return data;
  },
  async testImap(payload) {
    const { data } = await apiClient.post("/settings/imap/test", payload);
    if (!data.ok) {
      throw new Error(data.error || "Échec du test IMAP.");
    }
    return data;
  },

  // ── Valeurs de référence ───────────────────────────────────────────────────
  async getReferenceValues(family) {
    const { data } = await apiClient.get("/settings/reference-values", {
      params: { family },
    });
    return data;
  },
  async createReferenceValue(family, label) {
    const { data } = await apiClient.post("/settings/reference-values", { family, label });
    return data;
  },
  async updateReferenceValue(family, id, patch) {
    const { data } = await apiClient.put(`/settings/reference-values/${id}`, patch);
    return data;
  },
  async deleteReferenceValue(family, id) {
    const { data } = await apiClient.delete(`/settings/reference-values/${id}`);
    return data;
  },
};
