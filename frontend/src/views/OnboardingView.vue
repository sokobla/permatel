<template>
  <div class="ai-page">
    <div class="ai-card">
      <div class="ai-head">
        <span class="ai-logo-chip"
          ><img :src="permatelLogo" alt="PERMATEL" class="ai-logo"
        /></span>
      </div>

      <div v-if="loading" class="ai-state">
        <v-progress-circular indeterminate color="#00a8a8" size="28" />
        <span>Vérification du lien d'activation…</span>
      </div>

      <div v-else-if="loadError" class="ai-state ai-state--err">
        <v-icon color="#c0392b" size="28">mdi-alert-circle-outline</v-icon>
        <p>{{ loadError }}</p>
        <router-link to="/login" class="ai-link"
          >Retour à la connexion</router-link
        >
      </div>

      <div v-else-if="done" class="ai-state ai-state--ok">
        <v-icon color="#00a8a8" size="28">mdi-check-circle-outline</v-icon>
        <p>Votre compte est activé. Vous pouvez vous connecter.</p>
        <router-link to="/login" class="ai-link">Se connecter</router-link>
      </div>

      <template v-else>
        <h1 class="ai-title">
          Bienvenue{{ invite.prenom ? ", " + invite.prenom : "" }}
        </h1>
        <p class="ai-sub">
          Activez votre compte <strong>{{ invite.email }}</strong> en
          définissant votre mot de passe.
        </p>

        <v-alert
          v-if="errorMessage"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-4"
          border="start"
        >
          {{ errorMessage }}
        </v-alert>

        <v-text-field
          v-model="form.password"
          label="Mot de passe (min. 12 caractères)"
          type="password"
          variant="outlined"
          density="comfortable"
        />
        <v-text-field
          v-model="form.confirm"
          label="Confirmer le mot de passe"
          type="password"
          variant="outlined"
          density="comfortable"
        />

        <v-btn
          :loading="submitting"
          color="#00a8a8"
          block
          size="large"
          class="text-none mt-2"
          @click="submit"
        >
          Activer mon compte
        </v-btn>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { useRoute } from "vue-router";
import { onboardingService } from "@/services/onboardingService";
import permatelLogo from "@/assets/logo-permatel.png";
import "@/assets/styles/public-page.css";

const route = useRoute();
const token = route.query.token;

const loading = ref(true);
const loadError = ref(null);
const submitting = ref(false);
const errorMessage = ref(null);
const done = ref(false);
const invite = reactive({ email: "", nom: "", prenom: "", expires_at: "" });
const form = reactive({ password: "", confirm: "" });

async function submit() {
  errorMessage.value = null;
  if (form.password.length < 12) {
    errorMessage.value =
      "Le mot de passe doit contenir au moins 12 caractères.";
    return;
  }
  if (form.password !== form.confirm) {
    errorMessage.value = "Les mots de passe ne correspondent pas.";
    return;
  }
  submitting.value = true;
  try {
    await onboardingService.completeOnboarding(token, form.password);
    done.value = true;
  } catch (err) {
    errorMessage.value = err?.response?.data?.error || "Échec de l'activation.";
  } finally {
    submitting.value = false;
  }
}

onMounted(async () => {
  if (!token) {
    loadError.value = "Lien d'activation invalide.";
    loading.value = false;
    return;
  }
  try {
    const { data } = await onboardingService.getOnboarding(token);
    Object.assign(invite, data);
  } catch (err) {
    loadError.value =
      err?.response?.data?.error || "Lien d'activation invalide ou expiré.";
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
/* Mise en page partagée (.ai-page/.ai-card/.ai-head/.ai-title/.ai-sub/
   .ai-state/.ai-link) : frontend/src/assets/styles/public-page.css. Le
   logo reste défini ici, sa taille diffère volontairement d'AcceptInviteView. */
.ai-logo-chip {
  display: inline-flex;
  align-items: center;
  background: #000b23;
  padding: 15px 27px;
  border-radius: 8px;
}
.ai-logo {
  display: block;
  height: 50px;
  width: auto;
}
</style>
