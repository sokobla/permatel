<template>
  <div class="pdf-card">
    <div class="pdf-hdr">
      <span class="pdf-hdr-marker"></span>
      <h2 class="pdf-title">Pointer une vacation</h2>
    </div>

    <!-- Open-vacation indicator for selected agent -->
    <div v-if="agentId && checkingVacation" class="pdf-vacation-bar pdf-vacation-bar--checking">
      <v-icon size="12" color="#9aa0aa">mdi-loading</v-icon>
      Vérification de l'état de l'agent…
    </div>
    <div v-else-if="agentId && openVacation" class="pdf-vacation-bar">
      <v-icon size="12" color="#b37400">mdi-clock-alert-outline</v-icon>
      Vacation en cours depuis
      <strong>{{ formatOpenTime(openVacation.date_debut) }}</strong> —
      seule l'action <em>Terminer</em> est disponible.
    </div>

    <!-- Start confirmation step -->
    <div v-if="confirmingStart" class="pdf-confirm">
      <p class="pdf-confirm-msg">
        <v-icon size="13" color="#00a8a8">mdi-information-outline</v-icon>
        Démarrer la vacation de <strong>{{ agentLabel }}</strong> chez
        <strong>{{ clientLabel }}</strong> / <strong>{{ siteLabel }}</strong>
        à <strong>{{ dateDebut }}</strong> ?
      </p>
      <div class="pdf-confirm-actions">
        <button class="pdf-btn-ghost" :disabled="loadingStart" @click="confirmingStart = false">
          Modifier
        </button>
        <button class="pdf-btn-primary" :disabled="loadingStart" @click="executeStart">
          <span v-if="loadingStart" class="pdf-spinner"></span>
          <v-icon v-else size="13">mdi-check</v-icon>
          Confirmer
        </button>
      </div>
    </div>

    <template v-else>
      <div class="pdf-grid">
        <v-autocomplete
          v-model="agentId"
          :items="agents"
          item-title="label"
          item-value="id"
          label="Agent"
          prepend-inner-icon="mdi-shield-account-outline"
          density="compact"
          variant="outlined"
          hide-details
          :loading="loadingRefs || checkingVacation"
          clearable
          @update:model-value="onAgentChange"
        />
        <v-autocomplete
          v-model="clientId"
          :items="clients"
          item-title="label"
          item-value="id"
          label="Client"
          prepend-inner-icon="mdi-domain"
          density="compact"
          variant="outlined"
          hide-details
          :loading="loadingRefs"
          clearable
          @update:model-value="onClientChange"
        />
        <v-autocomplete
          v-model="siteId"
          :items="filteredSites"
          item-title="label"
          item-value="id"
          label="Site"
          prepend-inner-icon="mdi-map-marker-outline"
          density="compact"
          variant="outlined"
          hide-details
          :disabled="!clientId"
          clearable
        />
      </div>

      <div class="pdf-times">
        <div class="pdf-field-group">
          <label class="pdf-field-lbl" for="pdf-debut">HEURE DE DÉBUT</label>
          <input
            id="pdf-debut"
            v-model="dateDebut"
            type="datetime-local"
            class="pdf-time-input"
          />
        </div>
        <div class="pdf-field-group">
          <label class="pdf-field-lbl" for="pdf-fin">HEURE DE FIN</label>
          <input
            id="pdf-fin"
            v-model="dateFin"
            type="datetime-local"
            class="pdf-time-input"
          />
        </div>
      </div>

      <div class="pdf-actions">
        <button
          class="pdf-btn-primary"
          :disabled="!canStart || loadingEnd || !!openVacation"
          @click="onStart"
        >
          <v-icon size="13">mdi-play-circle-outline</v-icon>
          Débuter la vacation
        </button>
        <button
          class="pdf-btn-secondary"
          :disabled="!agentId || loadingStart || !openVacation"
          @click="onEnd"
        >
          <span v-if="loadingEnd" class="pdf-spinner"></span>
          <v-icon v-else size="13">mdi-stop-circle-outline</v-icon>
          Terminer la vacation
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import {
  startPriseDeService,
  endCurrentPriseDeService,
  fetchAgents,
  fetchClients,
  fetchSites,
  listPrisesDeService,
} from "@/services/priseDeServiceService";

const emit = defineEmits(["changed", "notify"]);

const agents = ref([]);
const clients = ref([]);
const sites = ref([]);
const loadingRefs = ref(false);

const agentId = ref(null);
const clientId = ref(null);
const siteId = ref(null);

function nowLocalIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const dateDebut = ref(nowLocalIso());
const dateFin = ref(nowLocalIso());

const loadingStart = ref(false);
const loadingEnd = ref(false);
const confirmingStart = ref(false);

// Pre-flight open-vacation check
const checkingVacation = ref(false);
const openVacation = ref(null);

async function checkOpenVacation(id) {
  openVacation.value = null;
  if (!id) return;
  checkingVacation.value = true;
  try {
    const list = await listPrisesDeService({ agent_id: id, statut: "en_cours" });
    openVacation.value = list.length > 0 ? list[0] : null;
  } catch {
    openVacation.value = null;
  } finally {
    checkingVacation.value = false;
  }
}

function formatOpenTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function onAgentChange(val) {
  confirmingStart.value = false;
  checkOpenVacation(val);
}

const canStart = computed(
  () => !!(agentId.value && clientId.value && siteId.value),
);
const filteredSites = computed(() =>
  clientId.value
    ? sites.value.filter((s) => s.client_id === clientId.value)
    : sites.value,
);

const agentLabel = computed(
  () => agents.value.find((a) => a.id === agentId.value)?.label ?? "—",
);
const clientLabel = computed(
  () => clients.value.find((c) => c.id === clientId.value)?.label ?? "—",
);
const siteLabel = computed(
  () => filteredSites.value.find((s) => s.id === siteId.value)?.label ?? "—",
);

function onClientChange() {
  if (
    siteId.value &&
    !filteredSites.value.some((s) => s.id === siteId.value)
  ) {
    siteId.value = null;
  }
}

function notify(type, text) {
  emit("notify", { type, text });
}
function apiError(err, fallback) {
  return err?.response?.data?.error || fallback;
}

function resetForm() {
  agentId.value = null;
  clientId.value = null;
  siteId.value = null;
  dateDebut.value = nowLocalIso();
  dateFin.value = nowLocalIso();
  openVacation.value = null;
  confirmingStart.value = false;
}

function onStart() {
  if (!canStart.value) {
    notify("error", "Veuillez sélectionner un agent, un client et un site.");
    return;
  }
  confirmingStart.value = true;
}

async function executeStart() {
  loadingStart.value = true;
  try {
    await startPriseDeService({
      agent_id: agentId.value,
      client_id: clientId.value,
      site_id: siteId.value,
      date_debut: dateDebut.value || undefined,
    });
    notify("success", "Vacation démarrée.");
    resetForm();
    emit("changed");
  } catch (err) {
    confirmingStart.value = false;
    notify("error", apiError(err, "Impossible de démarrer la vacation."));
  } finally {
    loadingStart.value = false;
  }
}

async function onEnd() {
  if (!agentId.value) {
    notify(
      "error",
      "Sélectionnez l'agent dont la vacation doit être terminée.",
    );
    return;
  }
  loadingEnd.value = true;
  try {
    await endCurrentPriseDeService(agentId.value, dateFin.value || undefined);
    notify("success", "Vacation terminée.");
    resetForm();
    emit("changed");
  } catch (err) {
    notify("error", apiError(err, "Aucune vacation en cours pour cet agent."));
  } finally {
    loadingEnd.value = false;
  }
}

onMounted(async () => {
  loadingRefs.value = true;
  try {
    [agents.value, clients.value, sites.value] = await Promise.all([
      fetchAgents(),
      fetchClients(),
      fetchSites(),
    ]);
  } catch {
    notify("error", "Échec du chargement des référentiels.");
  } finally {
    loadingRefs.value = false;
  }
});
</script>

<style scoped>
.pdf-card {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 3px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.pdf-hdr {
  display: flex;
  align-items: center;
  gap: 9px;
}
.pdf-hdr-marker {
  width: 3px;
  height: 16px;
  background: #00a8a8;
  border-radius: 1px;
}
.pdf-title {
  font-size: 0.95rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #000b23;
  text-transform: uppercase;
  margin: 0;
}

/* Vacation status bar */
.pdf-vacation-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  background: rgba(245, 166, 35, 0.08);
  border: 1px solid rgba(245, 166, 35, 0.25);
  border-radius: 3px;
  font-size: 12px;
  color: #7c5200;
  font-family: "Fira Sans", sans-serif;
}
.pdf-vacation-bar--checking {
  background: rgba(0, 0, 0, 0.03);
  border-color: rgba(0, 0, 0, 0.08);
  color: #888;
}

/* Confirmation banner */
.pdf-confirm {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: rgba(0, 168, 168, 0.05);
  border: 1px solid rgba(0, 168, 168, 0.2);
  border-radius: 3px;
}
.pdf-confirm-msg {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin: 0;
  font-size: 12.5px;
  color: #333;
  line-height: 1.5;
}
.pdf-confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.pdf-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.pdf-times {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.pdf-field-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.pdf-field-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #555;
  text-transform: uppercase;
}
.pdf-time-input {
  height: 32px;
  padding: 0 9px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  color: #222;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
  box-sizing: border-box;
}
.pdf-time-input:focus-visible {
  border-color: #00a8a8;
}

/* Action buttons */
.pdf-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.pdf-btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  background: #009090;
  color: #fff;
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.1em;
  border: 1px solid transparent;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}
.pdf-btn-primary:hover:not(:disabled) {
  background: #0a0c14;
}
.pdf-btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.pdf-btn-primary:focus-visible {
  outline: 2px solid #00a8a8;
  outline-offset: 2px;
}

.pdf-btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  background: #fff;
  color: #000b23;
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.1em;
  border: 1px solid rgba(0, 11, 35, 0.18);
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}
.pdf-btn-secondary:hover:not(:disabled) {
  background: #000b23;
  color: #fff;
}
.pdf-btn-secondary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.pdf-btn-secondary:focus-visible {
  outline: 2px solid #00a8a8;
  outline-offset: 2px;
}

.pdf-btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 12px;
  background: transparent;
  color: #666;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 3px;
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s;
}
.pdf-btn-ghost:hover:not(:disabled) {
  border-color: #888;
  color: #444;
}
.pdf-btn-ghost:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pdf-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: pdf-spin 0.7s linear infinite;
}
@keyframes pdf-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 720px) {
  .pdf-grid,
  .pdf-times {
    grid-template-columns: 1fr;
  }
}
</style>
