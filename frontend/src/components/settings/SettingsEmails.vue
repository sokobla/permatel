<template>
  <div class="se-wrap">
    <v-card
      v-for="key in TEMPLATE_KEYS"
      :key="key"
      variant="flat"
      class="se-card"
      rounded="lg"
      border
    >
      <div class="se-head">
        <div>
          <h2 class="se-title">{{ LABELS[key] }}</h2>
          <p class="se-sub">{{ HINTS[key] }}</p>
        </div>
        <v-chip
          v-if="templates[key]?.is_customized"
          size="small"
          color="#00a8a8"
          variant="tonal"
        >
          Personnalisé
        </v-chip>
        <v-chip v-else size="small" color="#9aa0aa" variant="tonal"
          >Par défaut</v-chip
        >
      </div>

      <v-divider />

      <div class="se-body">
        <div v-if="loading" class="se-loading">
          <v-progress-circular indeterminate size="24" color="#00a8a8" />
          <span>Chargement du gabarit…</span>
        </div>

        <template v-else>
          <v-alert
            v-if="feedback[key].text"
            :type="feedback[key].type"
            variant="tonal"
            density="compact"
            border="start"
            class="mb-4"
            closable
            @click:close="feedback[key].text = ''"
          >
            {{ feedback[key].text }}
          </v-alert>

          <label class="se-label">Objet <span class="se-req">*</span></label>
          <v-text-field
            v-model="drafts[key].subject"
            variant="outlined"
            density="comfortable"
            hide-details="auto"
            class="mb-3"
          />

          <label class="se-label"
            >Corps (HTML) <span class="se-req">*</span></label
          >
          <v-textarea
            v-model="drafts[key].body_html"
            variant="outlined"
            density="comfortable"
            rows="10"
            auto-grow
            hide-details="auto"
          />

          <div class="se-vars">
            <span class="se-vars__label">Variables disponibles :</span>
            <v-chip
              v-for="v in templates[key]?.available_variables || []"
              :key="v"
              size="small"
              variant="outlined"
              class="se-var-chip"
              @click="insertVariable(key, v)"
            >
              {{ varLabel(v) }}
            </v-chip>
          </div>
        </template>
      </div>

      <v-divider />

      <v-card-actions class="se-actions">
        <v-btn
          variant="outlined"
          class="text-none"
          :disabled="loading || !templates[key]?.is_customized"
          @click="onReset(key)"
        >
          Réinitialiser au défaut
        </v-btn>
        <v-spacer />
        <v-btn
          variant="outlined"
          class="text-none"
          :loading="previewing[key]"
          :disabled="loading"
          prepend-icon="mdi-eye-outline"
          @click="onPreview(key)"
        >
          Aperçu
        </v-btn>
        <v-btn
          color="#00a8a8"
          variant="flat"
          class="text-none"
          :loading="saving[key]"
          :disabled="loading"
          @click="onSave(key)"
        >
          Enregistrer
        </v-btn>
      </v-card-actions>
    </v-card>

    <!-- Dialog aperçu -->
    <v-dialog v-model="previewOpen" max-width="640">
      <v-card class="se-preview-card" rounded="lg">
        <v-card-item class="se-preview-head">
          <v-card-title class="se-preview-title"
            >Aperçu — {{ preview.subject }}</v-card-title
          >
          <v-btn
            icon="mdi-close"
            variant="text"
            size="small"
            @click="previewOpen = false"
          />
        </v-card-item>
        <v-divider />
        <v-card-text class="se-preview-body">
          <iframe
            :srcdoc="preview.body_html"
            sandbox=""
            class="se-preview-frame"
          />
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from "vue";
import { emailTemplatesService } from "@/services/emailTemplatesService";

const TEMPLATE_KEYS = ["onboarding_welcome", "password_reset"];

const LABELS = {
  onboarding_welcome: "Email de bienvenue (onboarding)",
  password_reset: "Email de réinitialisation de mot de passe",
};

const HINTS = {
  onboarding_welcome:
    "Envoyé lors de la création d'un utilisateur avec activation par email.",
  password_reset:
    "Envoyé lorsqu'un utilisateur demande la réinitialisation de son mot de passe.",
};

const loading = ref(true);

// État par clé de gabarit : { [key]: {...} }
const templates = reactive({});
const drafts = reactive({});
const feedback = reactive({});
const saving = reactive({});
const previewing = reactive({});

TEMPLATE_KEYS.forEach((key) => {
  templates[key] = null;
  drafts[key] = { subject: "", body_html: "" };
  feedback[key] = { type: "success", text: "" };
  saving[key] = false;
  previewing[key] = false;
});

const previewOpen = ref(false);
const preview = reactive({ subject: "", body_html: "" });

function setFeedback(key, type, text) {
  feedback[key].type = type;
  feedback[key].text = text;
}

function insertVariable(key, variable) {
  drafts[key].body_html = `${drafts[key].body_html}{{ ${variable} }}`;
}

/** Libellé affiché sur le chip de variable, ex. "{{ prenom }}". */
function varLabel(variable) {
  return `{{ ${variable} }}`;
}

async function load() {
  loading.value = true;
  try {
    const { data } = await emailTemplatesService.getTemplates();
    (data.templates || []).forEach((tpl) => {
      templates[tpl.template_key] = tpl;
      drafts[tpl.template_key] = {
        subject: tpl.subject || "",
        body_html: tpl.body_html || "",
      };
    });
  } catch {
    TEMPLATE_KEYS.forEach((key) =>
      setFeedback(key, "error", "Impossible de charger le gabarit."),
    );
  } finally {
    loading.value = false;
  }
}

async function onSave(key) {
  saving[key] = true;
  setFeedback(key, "success", "");
  try {
    const { data } = await emailTemplatesService.updateTemplate(key, {
      ...drafts[key],
    });
    templates[key] = data.template;
    drafts[key] = {
      subject: data.template.subject || "",
      body_html: data.template.body_html || "",
    };
    setFeedback(key, "success", data.message || "Gabarit enregistré.");
  } catch (err) {
    setFeedback(
      key,
      "error",
      err?.response?.data?.error || "Échec de l'enregistrement.",
    );
  } finally {
    saving[key] = false;
  }
}

async function onReset(key) {
  if (!window.confirm("Réinitialiser ce gabarit au contenu par défaut ?"))
    return;
  saving[key] = true;
  setFeedback(key, "success", "");
  try {
    const { data } = await emailTemplatesService.resetTemplate(key);
    templates[key] = data.template;
    drafts[key] = {
      subject: data.template.subject || "",
      body_html: data.template.body_html || "",
    };
    setFeedback(key, "success", data.message || "Gabarit réinitialisé.");
  } catch (err) {
    setFeedback(
      key,
      "error",
      err?.response?.data?.error || "Échec de la réinitialisation.",
    );
  } finally {
    saving[key] = false;
  }
}

async function onPreview(key) {
  previewing[key] = true;
  setFeedback(key, "success", "");
  try {
    const { data } = await emailTemplatesService.previewTemplate(key, {
      ...drafts[key],
    });
    preview.subject = data.subject;
    preview.body_html = data.body_html;
    previewOpen.value = true;
  } catch (err) {
    setFeedback(
      key,
      "error",
      err?.response?.data?.error || "Échec de l'aperçu.",
    );
  } finally {
    previewing[key] = false;
  }
}

onMounted(load);
</script>

<style scoped>
.se-wrap {
  display: flex;
  flex-direction: column;
  gap: 20px;
  font-family: "Fira Sans", sans-serif;
}
.se-card {
  font-family: "Fira Sans", sans-serif;
}
.se-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
}
.se-title {
  font-size: 17px;
  font-weight: 700;
  color: #000b23;
  margin: 0;
}
.se-sub {
  font-size: 12.5px;
  color: #6b7280;
  margin: 2px 0 0;
}
.se-body {
  padding: 18px 20px;
}
.se-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #6b7280;
  font-size: 15px;
  padding: 18px 0;
}
.se-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #15223a;
  margin-bottom: 4px;
}
.se-req {
  color: #e74c3c;
}
.se-actions {
  padding: 12px 16px;
}
.se-vars {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}
.se-vars__label {
  font-size: 11.5px;
  font-weight: 600;
  color: #6b7280;
  margin-right: 4px;
}
.se-var-chip {
  cursor: pointer;
  font-family: "Fira Code", monospace;
  font-size: 13px;
}

.se-preview-card {
  font-family: "Fira Sans", sans-serif;
}
.se-preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
}
.se-preview-title {
  font-size: 16px;
  font-weight: 700;
  color: #000b23;
  padding: 0;
}
.se-preview-body {
  padding: 0;
}
.se-preview-frame {
  width: 100%;
  height: 420px;
  border: none;
  background: #fff;
}
</style>
