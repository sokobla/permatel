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
        <span>Vérification de l'invitation…</span>
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
        <p>Votre accès est activé. Vous pouvez vous connecter.</p>
        <router-link to="/login" class="ai-link">Se connecter</router-link>
      </div>

      <template v-else>
        <h1 class="ai-title">Rejoindre {{ invite.tenant_name }}</h1>
        <p class="ai-sub">
          Invitation pour <strong>{{ invite.email }}</strong> (rôle :
          {{ invite.role }}).
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
          Un compte existe déjà pour cet email. Cliquez pour rejoindre cet
          espace ; vous vous connecterez avec vos identifiants habituels.
        </p>

        <v-btn
          :loading="submitting"
          color="#00a8a8"
          block
          size="large"
          class="text-none mt-2"
          @click="submit"
        >
          {{
            invite.requires_account
              ? "Activer mon compte"
              : "Rejoindre l'espace"
          }}
        </v-btn>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { useRoute } from "vue-router";
import { invitationService } from "@/services/invitationService";
import permatelLogo from "@/assets/logo-permatel.png";
import "@/assets/styles/public-page.css";

const route = useRoute();
const token = route.query.token;

const loading = ref(true);
const loadError = ref(null);
const submitting = ref(false);
const errorMessage = ref(null);
const done = ref(false);
const invite = reactive({
  email: "",
  tenant_name: "",
  role: "",
  requires_account: true,
});
const form = reactive({ nom: "", prenom: "", password: "", confirm: "" });

async function submit() {
  errorMessage.value = null;
  if (invite.requires_account) {
    if (!form.prenom.trim() || !form.nom.trim()) {
      errorMessage.value = "Nom et prénom requis.";
      return;
    }
    if (form.password.length < 8) {
      errorMessage.value =
        "Le mot de passe doit contenir au moins 8 caractères.";
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
      ? {
          nom: form.nom.trim(),
          prenom: form.prenom.trim(),
          password: form.password,
        }
      : {};
    await invitationService.accept(token, payload);
    done.value = true;
  } catch (err) {
    errorMessage.value =
      err?.response?.data?.error || "Échec de l'acceptation.";
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
    loadError.value =
      err?.response?.data?.error || "Invitation invalide ou expirée.";
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
/* Mise en page partagée (.ai-page/.ai-card/.ai-head/.ai-title/.ai-sub/
   .ai-state/.ai-link) : frontend/src/assets/styles/public-page.css. Le
   logo reste défini ici (taille distincte des autres pages publiques,
   décision produit du 02/08), ainsi que .ai-existing, propre à cette vue. */
.ai-logo-chip {
  display: inline-flex;
  align-items: center;
  background: #000b23;
  padding: 10px 18px;
  border-radius: 8px;
}
.ai-logo {
  display: block;
  height: 33px;
  width: auto;
}
.ai-existing {
  font-size: 15px;
  color: #374151;
  margin: 0 0 14px;
}
</style>
