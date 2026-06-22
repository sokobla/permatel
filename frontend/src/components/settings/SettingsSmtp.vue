<template>
  <v-card variant="flat" class="smtp-card" rounded="lg" border>
    <div class="smtp-head">
      <div>
        <h2 class="smtp-title">Configuration SMTP</h2>
        <p class="smtp-sub">Serveur d'envoi des emails sortants (notifications, alertes).</p>
      </div>
      <v-chip v-if="configured" size="small" color="#22c55e" variant="tonal">Configuré</v-chip>
      <v-chip v-else size="small" color="#9aa0aa" variant="tonal">Non configuré</v-chip>
    </div>

    <v-divider />

    <div class="smtp-body">
      <div v-if="loading" class="smtp-loading">
        <v-progress-circular indeterminate size="24" color="#00a8a8" />
        <span>Chargement de la configuration…</span>
      </div>

      <v-form v-else ref="formRef">
        <v-alert
          v-if="feedback.text"
          :type="feedback.type"
          variant="tonal"
          density="compact"
          border="start"
          class="mb-4"
          closable
          @click:close="feedback.text = ''"
        >
          {{ feedback.text }}
        </v-alert>

        <v-row dense>
          <v-col cols="12" sm="8">
            <label class="smtp-label">Hôte SMTP <span class="smtp-req">*</span></label>
            <v-text-field
              v-model="form.host" placeholder="smtp.exemple.com"
              variant="outlined" density="comfortable"
              :rules="[rules.required]" hide-details="auto"
            />
          </v-col>
          <v-col cols="12" sm="4">
            <label class="smtp-label">Port <span class="smtp-req">*</span></label>
            <v-text-field
              v-model.number="form.port" type="number" placeholder="587"
              variant="outlined" density="comfortable"
              :rules="[rules.required, rules.port]" hide-details="auto"
            />
          </v-col>

          <v-col cols="12" sm="6">
            <label class="smtp-label">Nom d'utilisateur</label>
            <v-text-field
              v-model="form.username" placeholder="apikey / login"
              variant="outlined" density="comfortable"
              autocomplete="off" hide-details="auto"
            />
          </v-col>
          <v-col cols="12" sm="6">
            <label class="smtp-label">Mot de passe</label>
            <v-text-field
              v-model="form.password"
              :type="showPwd ? 'text' : 'password'"
              :append-inner-icon="showPwd ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
              placeholder="••••••••"
              variant="outlined" density="comfortable"
              autocomplete="new-password" hide-details="auto"
              @click:append-inner="showPwd = !showPwd"
            />
          </v-col>

          <v-col cols="12" sm="8">
            <label class="smtp-label">Adresse expéditeur <span class="smtp-req">*</span></label>
            <v-text-field
              v-model="form.from_address" placeholder="no-reply@exemple.com"
              variant="outlined" density="comfortable"
              prepend-inner-icon="mdi-email-outline"
              :rules="[rules.required, rules.email]" hide-details="auto"
            />
          </v-col>
          <v-col cols="12" sm="4">
            <label class="smtp-label">Chiffrement</label>
            <v-select
              v-model="form.security"
              :items="SECURITY_OPTIONS" item-title="label" item-value="value"
              variant="outlined" density="comfortable" hide-details="auto"
            />
          </v-col>
        </v-row>
      </v-form>
    </div>

    <v-divider />

    <v-card-actions class="smtp-actions">
      <v-btn
        variant="outlined" class="text-none" :loading="testing" :disabled="loading || saving"
        prepend-icon="mdi-connection" @click="onTest"
      >
        Tester la configuration
      </v-btn>
      <v-spacer />
      <v-btn
        color="#00a8a8" variant="flat" class="text-none" :loading="saving" :disabled="loading || testing"
        @click="onSave"
      >
        Enregistrer
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { settingsService } from "@/services/settingsService";

const SECURITY_OPTIONS = [
  { value: "none", label: "Aucun" },
  { value: "tls", label: "STARTTLS" },
  { value: "ssl", label: "SSL/TLS" },
];

const form = reactive({ host: "", port: 587, username: "", password: "", from_address: "", security: "tls" });
const formRef = ref(null);
const loading = ref(false);
const saving = ref(false);
const testing = ref(false);
const showPwd = ref(false);
const feedback = reactive({ type: "success", text: "" });

const configured = computed(() => !!form.host && !!form.from_address);

const rules = {
  required: (v) => (v !== "" && v !== null && v !== undefined) || "Champ requis.",
  email: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v || "") || "Email invalide.",
  port: (v) => (Number(v) > 0 && Number(v) <= 65535) || "Port invalide.",
};

function setFeedback(type, text) { feedback.type = type; feedback.text = text; }

async function load() {
  loading.value = true;
  try {
    Object.assign(form, await settingsService.getSmtp());
  } catch {
    setFeedback("error", "Impossible de charger la configuration.");
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  const { valid } = await formRef.value.validate();
  if (!valid) return;
  saving.value = true;
  setFeedback("success", "");
  try {
    await settingsService.saveSmtp({ ...form });
    setFeedback("success", "Configuration SMTP enregistrée.");
  } catch {
    setFeedback("error", "Échec de l'enregistrement.");
  } finally {
    saving.value = false;
  }
}

async function onTest() {
  const { valid } = await formRef.value.validate();
  if (!valid) return;
  testing.value = true;
  setFeedback("success", "");
  try {
    const res = await settingsService.testSmtp({ ...form });
    setFeedback("success", res.message || "Test réussi.");
  } catch (err) {
    setFeedback("error", err?.message || "Échec du test de connexion.");
  } finally {
    testing.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.smtp-card { font-family: "Fira Sans", sans-serif; }
.smtp-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 20px; }
.smtp-title { font-size: 15px; font-weight: 700; color: #000b23; margin: 0; }
.smtp-sub { font-size: 12.5px; color: #6b7280; margin: 2px 0 0; }
.smtp-body { padding: 18px 20px; }
.smtp-loading { display: flex; align-items: center; gap: 10px; color: #6b7280; font-size: 13px; padding: 18px 0; }
.smtp-label { display: block; font-size: 12px; font-weight: 600; color: #15223a; margin-bottom: 4px; }
.smtp-req { color: #e74c3c; }
.smtp-actions { padding: 12px 16px; }
</style>
