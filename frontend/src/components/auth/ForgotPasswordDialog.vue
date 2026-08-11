<template>
  <v-card class="fp-card" rounded="lg">
    <!-- En-tête -->
    <v-card-item class="fp-head">
      <div class="fp-head__row">
        <div>
          <v-card-title class="fp-title">Mot de passe oublié</v-card-title>
          <v-card-subtitle class="fp-subtitle">
            Recevez un lien de réinitialisation par email.
          </v-card-subtitle>
        </div>
        <v-btn icon="mdi-close" variant="text" size="small" @click="emit('close')" />
      </div>
    </v-card-item>

    <v-divider />

    <!-- État succès -->
    <v-card-text v-if="success" class="fp-success">
      <v-icon size="44" color="#22c55e">mdi-check-circle-outline</v-icon>
      <h3 class="fp-success__title">Demande envoyée</h3>
      <p class="fp-success__text">
        Si un compte existe pour cette adresse, un email de réinitialisation a
        été envoyé.
      </p>
      <v-btn color="#00a8a8" variant="flat" class="text-none" @click="emit('close')">
        Fermer
      </v-btn>
    </v-card-text>

    <!-- Formulaire -->
    <template v-else>
      <v-card-text class="fp-body">
        <v-alert
          v-if="errorMessage"
          type="error"
          variant="tonal"
          density="compact"
          border="start"
          class="mb-4"
          closable
          @click:close="errorMessage = null"
        >
          {{ errorMessage }}
        </v-alert>

        <v-form ref="formRef" @submit.prevent="submit">
          <label class="fp-label">Email <span class="fp-req">*</span></label>
          <v-text-field
            v-model="email"
            placeholder="vous@entreprise.com"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-email-outline"
            :rules="[rules.required, rules.email]"
            hide-details="auto"
          />
        </v-form>
      </v-card-text>

      <v-divider />

      <v-card-actions class="fp-actions">
        <v-btn variant="text" class="text-none" :disabled="loading" @click="emit('close')">
          Annuler
        </v-btn>
        <v-spacer />
        <v-btn
          color="#00a8a8"
          variant="flat"
          class="text-none fp-submit"
          :loading="loading"
          @click="submit"
        >
          Envoyer le lien
        </v-btn>
      </v-card-actions>
    </template>
  </v-card>
</template>

<script setup>
import { ref } from "vue";
import { passwordResetService } from "@/services/passwordResetService";

const emit = defineEmits(["close"]);

const email = ref("");
const formRef = ref(null);
const loading = ref(false);
const success = ref(false);
const errorMessage = ref(null);

const rules = {
  required: (v) => (!!v && String(v).trim().length > 0) || "Champ requis.",
  email: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v || "") || "Email invalide.",
};

async function submit() {
  errorMessage.value = null;
  const { valid } = await formRef.value.validate();
  if (!valid) return;

  loading.value = true;
  try {
    // Réponse toujours 200, quel que soit le résultat (anti-énumération) :
    // ne jamais distinguer "email inconnu" de "email envoyé" dans l'UI.
    await passwordResetService.forgotPassword(email.value);
    success.value = true;
  } catch {
    errorMessage.value = "L'envoi a échoué. Veuillez réessayer.";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.fp-card { font-family: "Fira Sans", sans-serif; }

.fp-head { padding: 18px 20px 12px; }
.fp-head__row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.fp-title {
  font-family: "Fira Code", monospace;
  font-size: 20px;
  font-weight: 700;
  color: #000b23;
  letter-spacing: 0.02em;
}
.fp-subtitle {
  font-size: 12.5px;
  color: #6b7280;
  white-space: normal;
  margin-top: 2px;
}

.fp-body { padding: 18px 20px; }

.fp-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #15223a;
  margin-bottom: 4px;
}
.fp-req { color: #e74c3c; }

.fp-actions { padding: 12px 16px; }
.fp-submit { min-width: 150px; }

.fp-success {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 10px;
  padding: 32px 24px 28px;
}
.fp-success__title { font-size: 18px; font-weight: 700; color: #000b23; margin: 4px 0 0; }
.fp-success__text { font-size: 15px; color: #6b7280; max-width: 340px; margin: 0 0 8px; }
</style>
