<template>
  <v-card class="cs-card" rounded="lg">
    <!-- En-tête -->
    <v-card-item class="cs-head">
      <div class="cs-head__row">
        <div>
          <v-card-title class="cs-title">Contacter le support</v-card-title>
          <v-card-subtitle class="cs-subtitle">
            Décrivez votre problème, notre équipe vous répond rapidement.
          </v-card-subtitle>
        </div>
        <v-btn icon="mdi-close" variant="text" size="small" @click="emit('close')" />
      </div>
    </v-card-item>

    <v-divider />

    <!-- État succès -->
    <v-card-text v-if="success" class="cs-success">
      <v-icon size="44" color="#22c55e">mdi-check-circle-outline</v-icon>
      <h3 class="cs-success__title">Demande envoyée</h3>
      <p class="cs-success__text">
        Merci, votre demande a bien été transmise. Vous recevrez une réponse à
        l'adresse <strong>{{ form.email }}</strong>.
      </p>
      <v-btn color="#00a8a8" variant="flat" class="text-none" @click="emit('close')">
        Fermer
      </v-btn>
    </v-card-text>

    <!-- Formulaire -->
    <template v-else>
      <v-card-text class="cs-body">
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
          <v-row dense>
            <v-col cols="12" sm="6">
              <label class="cs-label">Nom <span class="cs-req">*</span></label>
              <v-text-field
                v-model="form.nom"
                placeholder="Dupont"
                variant="outlined"
                density="comfortable"
                :rules="[rules.required]"
                hide-details="auto"
              />
            </v-col>
            <v-col cols="12" sm="6">
              <label class="cs-label">Prénom <span class="cs-req">*</span></label>
              <v-text-field
                v-model="form.prenom"
                placeholder="Jean"
                variant="outlined"
                density="comfortable"
                :rules="[rules.required]"
                hide-details="auto"
              />
            </v-col>

            <v-col cols="12">
              <label class="cs-label">Email <span class="cs-req">*</span></label>
              <v-text-field
                v-model="form.email"
                placeholder="vous@entreprise.com"
                variant="outlined"
                density="comfortable"
                prepend-inner-icon="mdi-email-outline"
                :rules="[rules.required, rules.email]"
                hide-details="auto"
              />
            </v-col>

            <v-col cols="12">
              <label class="cs-label">Entreprise</label>
              <v-text-field
                v-model="form.entreprise"
                placeholder="Nom de votre société"
                variant="outlined"
                density="comfortable"
                prepend-inner-icon="mdi-domain"
                hide-details="auto"
              />
            </v-col>

            <!-- Objet : radio-chips (choix exclusif) -->
            <v-col cols="12">
              <label class="cs-label">Objet de la demande <span class="cs-req">*</span></label>
              <v-chip-group
                v-model="form.objet"
                mandatory
                column
                selected-class="cs-chip--on"
                class="cs-chips"
              >
                <v-chip
                  v-for="opt in OBJETS"
                  :key="opt.value"
                  :value="opt.value"
                  variant="outlined"
                  filter
                  class="cs-chip"
                >
                  {{ opt.label }}
                </v-chip>
              </v-chip-group>
            </v-col>

            <v-col cols="12">
              <label class="cs-label">Message <span class="cs-req">*</span></label>
              <v-textarea
                v-model="form.message"
                placeholder="Décrivez votre problème ou votre demande…"
                variant="outlined"
                density="comfortable"
                rows="4"
                auto-grow
                :rules="[rules.required, rules.minLen]"
                hide-details="auto"
              />
            </v-col>
          </v-row>
        </v-form>
      </v-card-text>

      <v-divider />

      <v-card-actions class="cs-actions">
        <v-btn variant="text" class="text-none" :disabled="loading" @click="emit('close')">
          Annuler
        </v-btn>
        <v-spacer />
        <v-btn
          color="#00a8a8"
          variant="flat"
          class="text-none cs-submit"
          :loading="loading"
          @click="submit"
        >
          Envoyer la demande
        </v-btn>
      </v-card-actions>
    </template>
  </v-card>
</template>

<script setup>
import { ref, reactive } from "vue";
import { supportService } from "@/services/supportService";

const emit = defineEmits(["close", "submitted"]);

const OBJETS = [
  { value: "identifiant_oublie", label: "Identifiant oublié" },
  { value: "mot_de_passe_oublie", label: "Mot de passe oublié" },
  { value: "autre", label: "Autre" },
];

const form = reactive({
  nom: "",
  prenom: "",
  email: "",
  entreprise: "",
  objet: "identifiant_oublie",
  message: "",
});

const formRef = ref(null);
const loading = ref(false);
const success = ref(false);
const errorMessage = ref(null);

const rules = {
  required: (v) => (!!v && String(v).trim().length > 0) || "Champ requis.",
  email: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v || "") || "Email invalide.",
  minLen: (v) => (v || "").trim().length >= 10 || "Minimum 10 caractères.",
};

async function submit() {
  errorMessage.value = null;
  const { valid } = await formRef.value.validate();
  if (!valid) return;

  loading.value = true;
  try {
    await supportService.sendSupportRequest({ ...form });
    success.value = true;
    emit("submitted", { ...form });
  } catch (err) {
    errorMessage.value =
      err?.response?.data?.error || "L'envoi a échoué. Veuillez réessayer.";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.cs-card { font-family: "Fira Sans", sans-serif; }

.cs-head { padding: 18px 20px 12px; }
.cs-head__row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.cs-title {
  font-family: "Fira Code", monospace;
  font-size: 18px;
  font-weight: 700;
  color: #000b23;
  letter-spacing: 0.02em;
}
.cs-subtitle {
  font-size: 12.5px;
  color: #6b7280;
  white-space: normal;
  margin-top: 2px;
}

.cs-body { padding: 18px 20px; }

.cs-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #15223a;
  margin-bottom: 4px;
}
.cs-req { color: #e74c3c; }

/* Radio-chips */
.cs-chips { margin-top: 2px; }
.cs-chip {
  font-size: 12.5px;
  font-weight: 600;
  border-color: rgba(0, 0, 0, 0.18);
}
.cs-chip.cs-chip--on {
  background: rgba(0, 168, 168, 0.1) !important;
  border-color: #00a8a8 !important;
  color: #007a7a !important;
}

.cs-actions { padding: 12px 16px; }
.cs-submit { min-width: 170px; }

/* Succès */
.cs-success {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 10px;
  padding: 32px 24px 28px;
}
.cs-success__title { font-size: 16px; font-weight: 700; color: #000b23; margin: 4px 0 0; }
.cs-success__text { font-size: 13px; color: #6b7280; max-width: 340px; margin: 0 0 8px; }
</style>
