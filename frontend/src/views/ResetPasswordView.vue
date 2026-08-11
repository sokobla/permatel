<template>
  <div class="ai-page">
    <div class="ai-card">
      <div class="ai-head">
        <span class="ai-logo-chip"><img :src="permatelLogo" alt="PERMATEL" class="ai-logo" /></span>
      </div>

      <div v-if="loading" class="ai-state">
        <v-progress-circular indeterminate color="#00a8a8" size="28" />
        <span>Vérification du lien de réinitialisation…</span>
      </div>

      <div v-else-if="loadError" class="ai-state ai-state--err">
        <v-icon color="#c0392b" size="28">mdi-alert-circle-outline</v-icon>
        <p>{{ loadError }}</p>
        <router-link to="/login" class="ai-link">Retour à la connexion</router-link>
      </div>

      <div v-else-if="done" class="ai-state ai-state--ok">
        <v-icon color="#00a8a8" size="28">mdi-check-circle-outline</v-icon>
        <p>Votre mot de passe a été réinitialisé. Vous pouvez vous connecter.</p>
        <router-link to="/login" class="ai-link">Se connecter</router-link>
      </div>

      <template v-else>
        <h1 class="ai-title">Réinitialiser votre mot de passe</h1>
        <p class="ai-sub">Choisissez un nouveau mot de passe pour votre compte.</p>

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
          label="Nouveau mot de passe (min. 12 caractères)"
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
          Réinitialiser le mot de passe
        </v-btn>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { useRoute } from "vue-router";
import { passwordResetService } from "@/services/passwordResetService";
import permatelLogo from "@/assets/logo-permatel.png";

const route = useRoute();
const token = route.query.token;

const loading = ref(true);
const loadError = ref(null);
const submitting = ref(false);
const errorMessage = ref(null);
const done = ref(false);
const form = reactive({ password: "", confirm: "" });

async function submit() {
  errorMessage.value = null;
  if (form.password.length < 12) {
    errorMessage.value = "Le mot de passe doit contenir au moins 12 caractères.";
    return;
  }
  if (form.password !== form.confirm) {
    errorMessage.value = "Les mots de passe ne correspondent pas.";
    return;
  }
  submitting.value = true;
  try {
    await passwordResetService.resetPassword(token, form.password);
    done.value = true;
  } catch (err) {
    errorMessage.value = err?.response?.data?.error || "Échec de la réinitialisation.";
  } finally {
    submitting.value = false;
  }
}

onMounted(async () => {
  if (!token) {
    loadError.value = "Lien de réinitialisation invalide.";
    loading.value = false;
    return;
  }
  try {
    await passwordResetService.checkResetToken(token);
  } catch (err) {
    loadError.value = err?.response?.data?.error || "Lien de réinitialisation invalide ou expiré.";
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.ai-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f2f2f2;
  padding: 24px;
  font-family: "Fira Sans", sans-serif;
}
.ai-card {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 28px;
}
.ai-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
}
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
.ai-title {
  font-size: 20px;
  font-weight: 800;
  color: #000b23;
  margin: 0 0 4px;
}
.ai-sub {
  font-size: 15px;
  color: #6b7280;
  margin: 0 0 18px;
}
.ai-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
  padding: 16px 0;
  color: #374151;
  font-size: 15px;
}
.ai-link {
  color: #00a8a8;
  font-weight: 600;
  text-decoration: none;
}
</style>
