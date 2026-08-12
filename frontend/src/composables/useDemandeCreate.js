import { ref } from "vue";
import { createDemande } from "@/services/demandeService";

/**
 * Boilerplate de soumission partagé par les formulaires de création de
 * demande (Anomalie/Commande/Planning/Admin) — extrait le 12/08 (audit) :
 * les 4 formulaires redéclaraient chacun `submitting`/`submitError` et un
 * bloc try/catch identique autour de `createDemande()`.
 *
 * La validation des champs et la construction du payload restent propres
 * à chaque formulaire (elles diffèrent réellement) — seule la mécanique
 * d'appel/état de soumission est mutualisée ici.
 *
 * @param {(event: "submitted", demande: object) => void} emit
 */
export function useDemandeCreate(emit) {
  const submitting = ref(false);
  const submitError = ref("");

  async function submit(payload) {
    submitError.value = "";
    submitting.value = true;
    try {
      const demande = await createDemande(payload);
      emit("submitted", demande);
      return demande;
    } catch (err) {
      submitError.value = err?.response?.data?.error ?? "Erreur lors de la création.";
      return null;
    } finally {
      submitting.value = false;
    }
  }

  return { submitting, submitError, submit };
}
