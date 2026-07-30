/**
 * emailTemplatesService — gabarits d'emails personnalisables du tenant
 * (onboarding_welcome, password_reset). Authentification admin de tenant
 * requise (mêmes règles que les réglages SMTP/IMAP).
 */
import apiClient from "@/services/http/axios";

export const emailTemplatesService = {
  /** Liste des deux gabarits connus, avec leur état (personnalisé ou défaut). */
  getTemplates() {
    return apiClient.get("/tenant/email-templates");
  },
  /** Détail d'un gabarit par clé ("onboarding_welcome" | "password_reset"). */
  getTemplate(key) {
    return apiClient.get(`/tenant/email-templates/${key}`);
  },
  /** Enregistre { subject, body_html } ; 400 si le gabarit Jinja2 est invalide. */
  updateTemplate(key, { subject, body_html }) {
    return apiClient.put(`/tenant/email-templates/${key}`, { subject, body_html });
  },
  /** Revient au gabarit système par défaut. */
  resetTemplate(key) {
    return apiClient.post(`/tenant/email-templates/${key}/reset`);
  },
  /**
   * Aperçu rendu avec des données d'exemple fixes.
   * @param {string} key
   * @param {{subject:string, body_html:string}|null} draft  Brouillon à prévisualiser,
   *   ou null/omis pour prévisualiser le gabarit actuellement enregistré.
   */
  previewTemplate(key, draft = null) {
    return apiClient.post(`/tenant/email-templates/${key}/preview`, draft || {});
  },
};
