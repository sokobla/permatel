<template>
  <v-card variant="flat" class="imap-card" rounded="lg" border>
    <div class="imap-head">
      <div>
        <h2 class="imap-title">Réception IMAP</h2>
        <p class="imap-sub">Boîte de service relevée pour collecter les emails entrants.</p>
      </div>
      <v-chip size="small" :color="form.inbound_enabled ? '#22c55e' : '#9aa0aa'" variant="tonal">
        {{ form.inbound_enabled ? "Réception active" : "Réception inactive" }}
      </v-chip>
    </div>

    <v-divider />

    <div class="imap-body">
      <div v-if="loading" class="imap-loading">
        <v-progress-circular indeterminate size="24" color="#00a8a8" />
        <span>Chargement…</span>
      </div>

      <v-form v-else ref="formRef">
        <v-alert
          v-if="feedback.text" :type="feedback.type" variant="tonal" density="compact"
          border="start" class="mb-4" closable @click:close="feedback.text = ''"
        >
          {{ feedback.text }}
        </v-alert>

        <div class="imap-switch">
          <v-switch
            v-model="form.inbound_enabled" color="#00a8a8" density="compact"
            hide-details inset label="Activer la collecte des emails entrants"
          />
        </div>

        <v-row dense>
          <v-col cols="12" sm="8">
            <label class="imap-label">Hôte IMAP <span v-if="form.inbound_enabled" class="imap-req">*</span></label>
            <v-text-field
              v-model="form.imap_host" placeholder="imap.exemple.com"
              variant="outlined" density="comfortable" :rules="hostRules" hide-details="auto"
            />
          </v-col>
          <v-col cols="12" sm="4">
            <label class="imap-label">Port</label>
            <v-text-field
              v-model.number="form.imap_port" type="number" placeholder="993"
              variant="outlined" density="comfortable" :rules="[rules.port]" hide-details="auto"
            />
          </v-col>

          <v-col cols="12" sm="6">
            <label class="imap-label">Nom d'utilisateur</label>
            <v-text-field
              v-model="form.imap_username" placeholder="boite@exemple.com"
              variant="outlined" density="comfortable" autocomplete="off" hide-details="auto"
            />
          </v-col>
          <v-col cols="12" sm="6">
            <label class="imap-label">Mot de passe</label>
            <v-text-field
              v-model="form.imap_password"
              :type="showPwd ? 'text' : 'password'"
              :append-inner-icon="showPwd ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
              :placeholder="hasPassword ? '•••••••• (inchangé)' : '••••••••'"
              variant="outlined" density="comfortable" autocomplete="new-password"
              hide-details="auto" @click:append-inner="showPwd = !showPwd"
            />
          </v-col>

          <v-col cols="12" sm="4">
            <label class="imap-label">Chiffrement</label>
            <v-select
              v-model="form.imap_security" :items="SECURITY_OPTIONS"
              item-title="label" item-value="value"
              variant="outlined" density="comfortable" hide-details="auto"
            />
          </v-col>
        </v-row>

        <p class="imap-note">
          La collecte s'exécute via la tâche planifiée <code>flask mail-fetch</code> (à venir).
          Cette configuration prépare la réception centralisée par tenant.
        </p>
      </v-form>
    </div>

    <v-divider />
    <v-card-actions class="imap-actions">
      <v-btn
        variant="outlined" class="text-none" :loading="testing" :disabled="loading || saving"
        prepend-icon="mdi-connection" @click="onTest"
      >
        Tester la connexion
      </v-btn>
      <v-spacer />
      <v-btn color="#00a8a8" variant="flat" class="text-none" :loading="saving" :disabled="loading || testing" @click="onSave">
        Enregistrer
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { settingsService } from "@/services/settingsService";

const SECURITY_OPTIONS = [
  { value: "ssl", label: "SSL/TLS" },
  { value: "starttls", label: "STARTTLS" },
  { value: "none", label: "Aucun" },
];

const form = reactive({
  imap_host: "", imap_port: 993, imap_username: "", imap_password: "",
  imap_security: "ssl", inbound_enabled: false,
});
const hasPassword = ref(false);
const formRef = ref(null);
const loading = ref(false);
const saving = ref(false);
const testing = ref(false);
const showPwd = ref(false);
const feedback = reactive({ type: "success", text: "" });

const rules = {
  required: (v) => (v !== "" && v !== null && v !== undefined) || "Champ requis.",
  port: (v) => (Number(v) > 0 && Number(v) <= 65535) || "Port invalide.",
};
// Hôte requis seulement si la réception est activée
const hostRules = computed(() => (form.inbound_enabled ? [rules.required] : []));

function setFeedback(type, text) { feedback.type = type; feedback.text = text; }

async function load() {
  loading.value = true;
  try {
    const data = await settingsService.getImap();
    Object.assign(form, {
      imap_host: data.imap_host || "",
      imap_port: data.imap_port || 993,
      imap_username: data.imap_username || "",
      imap_security: data.imap_security || "ssl",
      inbound_enabled: !!data.inbound_enabled,
      imap_password: "",
    });
    hasPassword.value = !!data.has_imap_password;
  } catch {
    setFeedback("error", "Impossible de charger la configuration IMAP.");
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
    const data = await settingsService.saveImap({ ...form });
    hasPassword.value = !!data.has_imap_password;
    form.imap_password = "";
    setFeedback("success", "Configuration IMAP enregistrée.");
  } catch (err) {
    setFeedback("error", err?.response?.data?.error || "Échec de l'enregistrement.");
  } finally {
    saving.value = false;
  }
}

async function onTest() {
  testing.value = true;
  setFeedback("success", "");
  try {
    const res = await settingsService.testImap({ ...form });
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
.imap-card { font-family: "Fira Sans", sans-serif; }
.imap-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 20px; }
.imap-title { font-size: 15px; font-weight: 700; color: #000b23; margin: 0; }
.imap-sub { font-size: 12.5px; color: #6b7280; margin: 2px 0 0; }
.imap-body { padding: 18px 20px; }
.imap-loading { display: flex; align-items: center; gap: 10px; color: #6b7280; font-size: 13px; padding: 18px 0; }
.imap-switch { margin-bottom: 10px; }
.imap-label { display: block; font-size: 12px; font-weight: 600; color: #15223a; margin-bottom: 4px; }
.imap-req { color: #e74c3c; }
.imap-note { font-size: 11.5px; color: #6b7280; margin: 14px 0 0; line-height: 1.5; }
.imap-note code { font-family: "Fira Code", monospace; background: #f2f4f6; padding: 1px 5px; border-radius: 4px; }
.imap-actions { padding: 12px 16px; }
</style>
