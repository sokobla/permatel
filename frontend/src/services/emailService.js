/**
 * emailService — canal Mail (Phase 1 : envoi sortant + pièces jointes).
 */
import apiClient from "@/services/http/axios";

export const emailService = {
  /**
   * Envoie un email. Si `attachments` (File[]) est fourni, envoi en multipart.
   * @param {Object} payload { to_contact_id?, to?, subject, body, demande_id?, attachments? }
   */
  async sendEmail(payload) {
    const { attachments, ...fields } = payload;
    if (attachments && attachments.length) {
      const fd = new FormData();
      fd.append("data", JSON.stringify(fields));
      attachments.forEach((f) => fd.append("attachments", f));
      const { data } = await apiClient.post("/emails", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    }
    const { data } = await apiClient.post("/emails", fields);
    return data;
  },

  async listEmails(params = { direction: "outbound" }) {
    const { data } = await apiClient.get("/emails", { params });
    return data;
  },

  /** Force une collecte IMAP des nouveaux emails (tenant courant). */
  async fetchNow() {
    const { data } = await apiClient.post("/emails/fetch");
    return data;
  },

  async getEmail(id) {
    const { data } = await apiClient.get(`/emails/${id}`);
    return data;
  },

  /** Met à jour le statut (non_lu/lu/traite/archive/spam) ou le rattachement. */
  async updateStatus(id, patch) {
    const { data } = await apiClient.patch(`/emails/${id}`, patch);
    return data;
  },

  /** Rattache l'email à une demande (crée une interaction de suivi). */
  async linkDemande(id, demandeId) {
    const { data } = await apiClient.post(`/emails/${id}/link-demande`, {
      demande_id: demandeId,
    });
    return data;
  },

  /** Télécharge une pièce jointe (blob) et déclenche la sauvegarde navigateur. */
  async downloadAttachment(emailId, att) {
    const res = await apiClient.get(`/emails/${emailId}/attachments/${att.id}/download`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = att.filename;
    a.click();
    URL.revokeObjectURL(url);
  },

  /** KPI emails (Reports › onglet Email). */
  async getStats(params = {}) {
    const { data } = await apiClient.get("/emails/stats", { params });
    return data;
  },
};
