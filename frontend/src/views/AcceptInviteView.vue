<template>
  <div class="ai-page">
    <div class="ai-card">
      <div class="ai-head">
        <span class="ai-mark"></span>
        <span class="ai-brand">PERMATEL</span>
      </div>

      <div v-if="loading" class="ai-state">
        <v-progress-circular indeterminate color="#00a8a8" size="28" />
        <span>Vérification de l'invitation…</span>
      </div>

      <div v-else-if="loadError" class="ai-state ai-state--err">
        <v-icon color="#c0392b" size="28">mdi-alert-circle-outline</v-icon>
        <p>{{ loadError }}</p>
        <router-link to="/login" class="ai-link">Retour à la connexion</router-link>
      </div>

      <div v-else-if="done" class="ai-state ai-state--ok">
        <v-icon color="#00a8a8" size="28">mdi-check-circle-outline</v-icon>
        <p>Votre accès est activé. Vous pouvez vous connecter.</p>
        <router-link to="/login" class="ai-link">Se connecter</router-link>
      </div>

      <template v-else>
        <h1 class="ai-title">Rejoindre {{ invite.tenant_name }}</h1>
        <p class="ai-sub">
          Invitation pour <strong>{{ invite.email }}</strong>
          (rôle : {{ invite.role }}).
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

        <template v-if="invite.requires_account">
          <v-text-field
            v-model="form.prenom"
            label="Prénom"
            variant="outlined"
            density="comfortable"
          />
          <v-text-field
            v-model="form.nom"
            label="Nom"
            variant="outlined"
            density="comfortable"
          />
          <v-text-field
            v-model="form.password"
            label="Mot de passe (min. 8 caractères)"
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
        </template>
        <p v-else class="ai-existing">
          Un compte existe déjà pour cet email. Cliquez pour rejoindre cet espace ;
          vous vous connecterez avec vos identifiants habituels.
        </p>

        <v-btn
          :loading="submitting"
          color="#00a8a8"
          block
          size="large"
          class="text-none mt-2"
          @click="submit"
        >
          {{ invite.requires_account ? "Activer mon compte" : "Rejoindre l'espace" }}
        </v-btn>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { useRoute } from "vue-router";
import { invitationService } from "@/services/invitationService";

const route = useRoute();
const token = route.query.token;

const loading = ref(true);
const loadError = ref(null);
const submitting = ref(false);
const errorMessage = ref(null);
const done = ref(false);
const invite = reactive({ email: "", tenant_name: "", role: "", requires_account: true });
const form = reactive({ nom: "", prenom: "", password: "", confirm: "" });

async function submit() {
  errorMessage.value = null;
  if (invite.requires_account) {
    if (!form.prenom.trim() || !form.nom.trim()) {
      errorMessage.value = "Nom et prénom requis.";
      return;
    }
    if (form.password.length < 8) {
      errorMessage.value = "Le mot de passe doit contenir au moins 8 caractères.";
      return;
    }
    if (form.password !== form.confirm) {
      errorMessage.value = "Les mots de passe ne correspondent pas.";
      return;
    }
  }
  submitting.value = true;
  try {
    const payload = invite.requires_account
      ? { nom: form.nom.trim(), prenom: form.prenom.trim(), password: form.password }
      : {};
    await invitationService.accept(token, payload);
    done.value = true;
  } catch (err) {
    errorMessage.value = err?.response?.data?.error || "Échec de l'acceptation.";
  } finally {
    submitting.value = false;
  }
}

onMounted(async () => {
  if (!token) {
    loadError.value = "Lien d'invitation invalide.";
    loading.value = false;
    return;
  }
  try {
    const { data } = await invitationService.get(token);
    Object.assign(invite, data);
  } catch (err) {
    loadError.value = err?.response?.data?.error || "Invitation invalide ou expirée.";
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
.ai-mark {
  width: 4px;
  height: 20px;
  background: #00a8a8;
  border-radius: 2px;
}
.ai-brand {
  font-family: "Fira Code", monospace;
  font-weight: 700;
  letter-spacing: 0.2em;
  color: #000b23;
}
.ai-title {
  font-size: 18px;
  font-weight: 800;
  color: #000b23;
  margin: 0 0 4px;
}
.ai-sub {
  font-size: 13px;
  color: #6b7280;
  margin: 0 0 18px;
}
.ai-existing {
  font-size: 13px;
  color: #374151;
  margin: 0 0 14px;
}
.ai-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
  padding: 16px 0;
  color: #374151;
  font-size: 13px;
}
.ai-link {
  color: #00a8a8;
  font-weight: 600;
  text-decoration: none;
}
</style>
