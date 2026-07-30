/**
 * onboardingService — activation de compte via lien d'onboarding (sans authentification).
 */
import apiClient from "@/services/http/axios";

export const onboardingService = {
  /** Détails minimaux (email, nom, prénom, expiration) d'un token d'onboarding. */
  getOnboarding(token) {
    return apiClient.get(`/onboarding/${token}`);
  },
  /** Complète l'onboarding : définit le mot de passe (min. 12 caractères). */
  completeOnboarding(token, password) {
    return apiClient.post(`/onboarding/${token}/complete`, { password });
  },
};
