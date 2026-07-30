/**
 * passwordResetService — réinitialisation de mot de passe (sans authentification).
 */
import apiClient from "@/services/http/axios";

export const passwordResetService = {
  /** Déclenche l'envoi d'un email de réinitialisation. Toujours 200 (anti-énumération). */
  forgotPassword(email) {
    return apiClient.post("/auth/forgot-password", { email });
  },
  /** Vérifie la validité d'un token de réinitialisation avant d'afficher le formulaire. */
  checkResetToken(token) {
    return apiClient.get(`/auth/reset-password/${token}`);
  },
  /** Définit le nouveau mot de passe (min. 12 caractères). */
  resetPassword(token, password) {
    return apiClient.post(`/auth/reset-password/${token}`, { password });
  },
};
