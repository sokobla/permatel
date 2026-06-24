<template>
  <div class="df-root pds-root">

    <!-- ══ HEADER ══════════════════════════════════════════════════════ -->
    <div class="pds-hdr">
      <p class="pds-ctx">
        <span>WORKSPACE</span>
        <span class="pds-ctx__sep">›</span>
        <span>NOUVELLE DEMANDE</span>
        <span class="pds-ctx__sep">›</span>
        <span class="pds-ctx__active">PRISE DE SERVICE</span>
      </p>
      <div class="pds-title-row">
        <div class="pds-title-left">
          <span class="pds-marker"></span>
          <h2 class="pds-title">PRISE DE SERVICE</h2>
        </div>
        <button class="pds-close-btn" title="Fermer" @click="emit('cancel')">
          <v-icon size="15">mdi-close</v-icon>
        </button>
      </div>
    </div>

    <!-- Bandeau erreur -->
    <div v-if="error" class="pds-error-bar">
      <v-icon size="13" color="#e74c3c">mdi-alert-circle-outline</v-icon>
      {{ error }}
    </div>

    <!-- ══ CORPS ════════════════════════════════════════════════════════ -->
    <div class="pds-body">
      <!-- Agent (verrouillé sur le contact) -->
      <div class="form-group">
        <label class="form-label">AGENT</label>
        <div class="pds-agent">
          <v-icon size="14" color="#00a8a8">mdi-shield-account-outline</v-icon>
          <span class="pds-agent-name">{{ agentNom || '—' }}</span>
          <span class="pds-agent-badge">CONTACT AGENT</span>
        </div>
      </div>

      <div class="pds-grid">
        <div class="form-group">
          <label class="form-label">CLIENT <span class="pds-required">*</span></label>
          <ClientCombobox
            @client-selected="onClientSelected"
            @client-cleared="onClientCleared"
          />
        </div>
        <div class="form-group">
          <label class="form-label">SITE <span class="pds-required">*</span></label>
          <SiteSelect
            :client-id="clientId"
            @site-selected="onSiteSelected"
            @site-cleared="onSiteCleared"
          />
        </div>
      </div>

      <p class="pds-hint">
        <v-icon size="12" color="#9aa0aa">mdi-information-outline</v-icon>
        « Débuter » crée une vacation en cours (un agent ne peut en avoir qu'une).
        « Terminer » clôture la vacation en cours de cet agent.
      </p>
    </div>

    <!-- ══ FOOTER ══════════════════════════════════════════════════════ -->
    <div class="pds-footer">
      <button class="pds-btn-cancel" :disabled="busy" @click="emit('cancel')">
        ANNULER
      </button>
      <button
        v-if="hasOpenVacation"
        class="pds-btn-end"
        :disabled="busy"
        @click="onEnd"
      >
        <v-icon size="13">mdi-stop-circle-outline</v-icon>
        TERMINER LA VACATION
      </button>
      <button class="pds-btn-start" :disabled="busy || !canStart" @click="onStart">
        <span v-if="starting" class="pds-spinner"></span>
        <v-icon v-else size="13">mdi-play-circle-outline</v-icon>
        DÉBUTER LA VACATION
      </button>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import ClientCombobox from "@/components/workspace/ClientCombobox.vue";
import SiteSelect from "@/components/workspace/SiteSelect.vue";
import {
  startPriseDeService,
  endCurrentPriseDeService,
  listPrisesDeService,
} from "@/services/priseDeServiceService";

const props = defineProps({
  contactId: { type: Number, default: null },
  agentId: { type: Number, default: null },
  agentNom: { type: String, default: "" },
});
const emit = defineEmits(["submitted", "cancel"]);

const clientId = ref(null);
const siteId = ref(null);
const starting = ref(false);
const ending = ref(false);
const error = ref("");
const hasOpenVacation = ref(false);

const busy = computed(() => starting.value || ending.value);
const canStart = computed(() => !!(props.agentId && clientId.value && siteId.value));

// Vérifie si l'agent a déjà une vacation en cours (→ bouton "Terminer").
async function checkOpenVacation() {
  hasOpenVacation.value = false;
  if (!props.agentId) return;
  try {
    const open = await listPrisesDeService({ agent_id: props.agentId, statut: "en_cours" });
    hasOpenVacation.value = open.length > 0;
  } catch {
    hasOpenVacation.value = false;
  }
}

onMounted(checkOpenVacation);

function onClientSelected(client) {
  clientId.value = client.id;
  siteId.value = null;
}
function onClientCleared() {
  clientId.value = null;
  siteId.value = null;
}
function onSiteSelected(site) {
  siteId.value = site.id;
}
function onSiteCleared() {
  siteId.value = null;
}

function apiError(err, fallback) {
  return err?.response?.data?.error || fallback;
}

async function onStart() {
  error.value = "";
  if (!props.agentId) {
    error.value = "Ce contact n'est pas rattaché à un agent.";
    return;
  }
  if (!canStart.value) {
    error.value = "Veuillez sélectionner un client et un site.";
    return;
  }
  starting.value = true;
  try {
    const pds = await startPriseDeService({
      agent_id: props.agentId,
      client_id: clientId.value,
      site_id: siteId.value,
    });
    emit("submitted", pds);
  } catch (err) {
    error.value = apiError(err, "Impossible de démarrer la vacation.");
  } finally {
    starting.value = false;
  }
}

async function onEnd() {
  error.value = "";
  if (!props.agentId) {
    error.value = "Ce contact n'est pas rattaché à un agent.";
    return;
  }
  ending.value = true;
  try {
    const pds = await endCurrentPriseDeService(props.agentId);
    emit("submitted", pds);
  } catch (err) {
    error.value = apiError(err, "Aucune vacation en cours pour cet agent.");
  } finally {
    ending.value = false;
  }
}
</script>

<style scoped>
.pds-root { display: flex; flex-direction: column; background: #fff; }
.pds-hdr { padding: 14px 18px 10px; border-bottom: 1px solid rgba(0,0,0,0.06); }
.pds-ctx {
  font-family: "Fira Code", monospace; font-size: 9px; font-weight: 600; letter-spacing: 0.1em;
  color: #bbb; margin: 0 0 8px; display: flex; align-items: center; gap: 6px;
}
.pds-ctx__sep { color: #ddd; }
.pds-ctx__active { color: #00a8a8; }
.pds-title-row { display: flex; align-items: center; justify-content: space-between; }
.pds-title-left { display: flex; align-items: center; gap: 9px; }
.pds-marker { width: 3px; height: 16px; background: #00a8a8; border-radius: 1px; }
.pds-title { font-size: 0.95rem; font-weight: 800; letter-spacing: 0.08em; color: #000b23; margin: 0; }
.pds-close-btn { border: none; background: none; cursor: pointer; color: #aaa; display: inline-flex; }
.pds-close-btn:hover { color: #e74c3c; }

.pds-error-bar {
  display: flex; align-items: center; gap: 6px; margin: 10px 18px 0; padding: 8px 10px;
  background: rgba(231,76,60,0.08); border-radius: 4px; font-size: 11.5px; color: #e74c3c;
}

.pds-body { padding: 16px 18px; display: flex; flex-direction: column; gap: 14px; }
.form-group { display: flex; flex-direction: column; gap: 5px; }
.form-label {
  font-family: "Fira Code", monospace; font-size: 9px; font-weight: 700; letter-spacing: 0.1em;
  color: #999; text-transform: uppercase;
}
.pds-required { color: #e74c3c; }
.pds-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

.pds-agent {
  display: inline-flex; align-items: center; gap: 8px; height: 36px; padding: 0 12px;
  background: rgba(0,168,168,0.06); border: 1px solid rgba(0,168,168,0.2); border-radius: 4px;
}
.pds-agent-name { font-size: 13px; font-weight: 600; color: #000b23; }
.pds-agent-badge {
  font-family: "Fira Code", monospace; font-size: 8px; font-weight: 700; letter-spacing: 0.08em;
  color: #00a8a8; background: rgba(0,168,168,0.12); padding: 2px 6px; border-radius: 3px; margin-left: auto;
}

.pds-hint { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #9aa0aa; margin: 0; }

.pds-footer {
  display: flex; align-items: center; justify-content: flex-end; gap: 8px;
  padding: 12px 18px; border-top: 1px solid rgba(0,0,0,0.06);
}
.pds-footer button {
  display: inline-flex; align-items: center; gap: 5px; height: 32px; padding: 0 14px; border-radius: 4px;
  font-family: "Fira Sans", sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; cursor: pointer;
  transition: all .15s; border: 1px solid transparent;
}
.pds-footer button:disabled { opacity: 0.45; cursor: not-allowed; }
.pds-btn-cancel { background: #fff; border-color: rgba(0,0,0,0.14); color: #666; }
.pds-btn-cancel:hover:not(:disabled) { background: rgba(0,0,0,0.04); }
.pds-btn-end { background: #fff; border-color: rgba(0,11,35,0.18); color: #000b23; }
.pds-btn-end:hover:not(:disabled) { background: #000b23; color: #fff; }
.pds-btn-start { background: #00a8a8; color: #fff; }
.pds-btn-start:hover:not(:disabled) { background: #009090; }

.pds-spinner {
  width: 12px; height: 12px; border: 2px solid rgba(255,255,255,0.4); border-top-color: #fff;
  border-radius: 50%; animation: pds-spin 0.7s linear infinite;
}
@keyframes pds-spin { to { transform: rotate(360deg); } }

@media (max-width: 720px) {
  .pds-grid { grid-template-columns: 1fr; }
  .pds-footer { flex-wrap: wrap; }
}
</style>
