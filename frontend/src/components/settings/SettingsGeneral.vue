<template>
  <v-card variant="flat" class="sg-card" rounded="lg" border>
    <div class="sg-head">
      <div>
        <h2 class="sg-title">Général</h2>
        <p class="sg-sub">Identité du tenant et email de support.</p>
      </div>
    </div>
    <v-divider />

    <div class="sg-body">
      <div v-if="loading" class="sg-loading">
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

        <!-- Logo -->
        <label class="sg-label">Logo</label>
        <div class="sg-logo-row">
          <div class="sg-logo-preview">
            <img v-if="logoPreview" :src="logoPreview" alt="Logo" />
            <span v-else class="sg-logo-ph">{{ initials(form.nom) || '—' }}</span>
          </div>
          <div class="sg-logo-actions">
            <v-btn variant="outlined" size="small" class="text-none" @click="logoInput?.click()">
              {{ logoPreview ? 'Changer' : 'Choisir un fichier' }}
            </v-btn>
            <v-btn v-if="logoPreview" variant="text" size="small" class="text-none" @click="clearLogo">Retirer</v-btn>
            <input ref="logoInput" type="file" accept="image/png,image/jpeg,image/webp" class="sg-hidden" @change="onLogo" />
          </div>
        </div>
        <p class="sg-hint">PNG, JPG ou WEBP — 2 Mo max.</p>
        <p v-if="logoError" class="sg-field-error">{{ logoError }}</p>

        <!-- Nom -->
        <label class="sg-label">Nom du tenant <span class="sg-req">*</span></label>
        <v-text-field
          v-model="form.nom" variant="outlined" density="comfortable"
          placeholder="Nom de l'organisation" :rules="[rules.required]" hide-details="auto"
        />

        <!-- Email support -->
        <label class="sg-label">Email support</label>
        <v-text-field
          v-model="form.support_email" variant="outlined" density="comfortable"
          placeholder="support@organisation.com" prepend-inner-icon="mdi-lifebuoy"
          :rules="[rules.emailOptional]" hide-details="auto"
        />
        <p class="sg-hint">Destinataire des demandes « Contacter le support ».</p>
      </v-form>
    </div>

    <v-divider />
    <v-card-actions class="sg-actions">
      <v-spacer />
      <v-btn color="#00a8a8" variant="flat" class="text-none" :loading="saving" :disabled="loading" @click="save">
        Enregistrer
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { tenantService } from "@/services/tenantService";
import { useAuthStore } from "@/store/auth";

const authStore = useAuthStore();
const BACKEND_ORIGIN = (import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api").replace(/\/api\/?$/, "");

const form = reactive({ nom: "", support_email: "" });
const formRef = ref(null);
const loading = ref(false);
const saving = ref(false);
const feedback = reactive({ type: "success", text: "" });

const logoInput = ref(null);
const logoFile = ref(null);
const logoPreview = ref(null);
const removeLogo = ref(false);
const logoError = ref("");

const rules = {
  required: (v) => (!!v && v.trim().length > 0) || "Champ requis.",
  emailOptional: (v) => !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) || "Email invalide.",
};

function initials(name) {
  if (!name) return "";
  return name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
}
function fileUrl(p) {
  if (!p) return null;
  return /^(https?:|blob:)/.test(p) ? p : BACKEND_ORIGIN + p;
}

function onLogo(e) {
  logoError.value = "";
  const f = e.target.files?.[0];
  if (!f) return;
  if (!["image/png", "image/jpeg", "image/webp"].includes(f.type)) {
    logoError.value = "Format non supporté."; return;
  }
  if (f.size > 2 * 1024 * 1024) { logoError.value = "Fichier trop volumineux (2 Mo max)."; return; }
  logoFile.value = f;
  logoPreview.value = URL.createObjectURL(f);
  removeLogo.value = false;
}
function clearLogo() {
  logoFile.value = null; logoPreview.value = null; removeLogo.value = true;
  if (logoInput.value) logoInput.value.value = "";
}

async function load() {
  const tid = authStore.activeTenantId;
  if (!tid) return;
  loading.value = true;
  try {
    const { data } = await tenantService.getTenant(tid);
    form.nom = data.nom ?? "";
    form.support_email = data.support_email ?? "";
    logoPreview.value = data.logo_url ? fileUrl(data.logo_url) : null;
  } catch {
    feedback.type = "error"; feedback.text = "Impossible de charger les paramètres.";
  } finally {
    loading.value = false;
  }
}

async function save() {
  feedback.text = "";
  const { valid } = await formRef.value.validate();
  if (!valid) return;
  saving.value = true;
  try {
    const payload = { nom: form.nom.trim(), support_email: form.support_email.trim() || null };
    let body = payload;
    if (logoFile.value || removeLogo.value) {
      const fd = new FormData();
      if (removeLogo.value && !logoFile.value) payload.logo_url = null;
      fd.append("data", JSON.stringify(payload));
      if (logoFile.value) fd.append("logo", logoFile.value);
      body = fd;
    }
    const { data } = await tenantService.updateTenant(authStore.activeTenantId, body);
    // Met à jour le store pour refléter le logo/nom dans l'app-bar
    const t = authStore.tenants?.find((x) => x.id === authStore.activeTenantId);
    if (t) { t.nom = data.nom; t.logo_url = data.logo_url; }
    logoFile.value = null; removeLogo.value = false;
    if (data.logo_url) logoPreview.value = fileUrl(data.logo_url);
    feedback.type = "success"; feedback.text = "Paramètres enregistrés.";
  } catch (err) {
    feedback.type = "error";
    feedback.text = err?.response?.data?.error || "Échec de l'enregistrement.";
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.sg-card { font-family: "Fira Sans", sans-serif; }
.sg-head { padding: 16px 20px; }
.sg-title { font-size: 15px; font-weight: 700; color: #000b23; margin: 0; }
.sg-sub { font-size: 12.5px; color: #6b7280; margin: 2px 0 0; }
.sg-body { padding: 18px 20px; max-width: 560px; }
.sg-loading { display: flex; align-items: center; gap: 10px; color: #6b7280; font-size: 13px; }
.sg-label { display: block; font-size: 12px; font-weight: 600; color: #15223a; margin: 14px 0 4px; }
.sg-req { color: #e74c3c; }
.sg-hint { font-size: 11px; color: #6b7280; margin: 4px 0 0; }
.sg-field-error { font-size: 12px; color: #e74c3c; margin: 4px 0 0; }
.sg-logo-row { display: flex; align-items: center; gap: 14px; }
.sg-logo-preview {
  width: 64px; height: 64px; border-radius: 8px; border: 1px solid #e5e7eb;
  background: #f7f7f8; overflow: hidden; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.sg-logo-preview img { width: 100%; height: 100%; object-fit: cover; }
.sg-logo-ph { font-family: "Fira Code", monospace; font-size: 16px; font-weight: 700; color: #6b7280; }
.sg-logo-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.sg-hidden { display: none; }
.sg-actions { padding: 12px 16px; }
</style>
