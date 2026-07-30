<template>
  <div class="cdr-root">
    <div class="cdr-subtabs">
      <button
        class="cdr-subtab"
        :class="{ 'cdr-subtab--active': subTab === 'calls' }"
        @click="subTab = 'calls'"
      >
        Historique des appels
      </button>
      <button
        class="cdr-subtab"
        :class="{ 'cdr-subtab--active': subTab === 'recordings' }"
        @click="subTab = 'recordings'"
      >
        Enregistrements
      </button>
    </div>

    <v-alert
      v-if="feedback.text"
      :type="feedback.type"
      variant="tonal"
      density="compact"
      class="mt-3"
      closable
      @click:close="feedback.text = ''"
    >
      {{ feedback.text }}
    </v-alert>

    <!-- ═══════════ HISTORIQUE DES APPELS ═══════════ -->
    <template v-if="subTab === 'calls'">
      <v-card variant="flat" class="cdr-filters" rounded="lg" border>
        <div class="cdr-filters__row">
          <div class="cdr-field">
            <label>DU</label>
            <input v-model="callsFilters.from" type="date" class="cdr-date" />
          </div>
          <div class="cdr-field">
            <label>AU</label>
            <input v-model="callsFilters.to" type="date" class="cdr-date" />
          </div>
          <v-select
            v-model="callsFilters.call_status"
            :items="STATUS_OPTIONS"
            item-title="label"
            item-value="value"
            label="Statut"
            variant="outlined"
            density="compact"
            hide-details
            clearable
            style="max-width: 170px"
          />
          <v-select
            v-model="callsFilters.direction"
            :items="DIRECTION_OPTIONS"
            item-title="label"
            item-value="value"
            label="Direction"
            variant="outlined"
            density="compact"
            hide-details
            clearable
            style="max-width: 150px"
          />
          <v-text-field
            v-model="callsFilters.queue_id"
            label="File"
            variant="outlined"
            density="compact"
            hide-details
            clearable
            style="max-width: 160px"
          />
          <v-text-field
            v-model="callsFilters.agent_login"
            label="Agent"
            variant="outlined"
            density="compact"
            hide-details
            clearable
            style="max-width: 150px"
          />
          <v-text-field
            v-model="callsFilters.search"
            label="Recherche (appelant, appelé)"
            variant="outlined"
            density="compact"
            hide-details
            clearable
            style="max-width: 210px"
          />
          <v-spacer />
          <v-btn variant="text" class="text-none" @click="resetCallsFilters">Réinitialiser</v-btn>
          <v-btn
            color="#00a8a8"
            variant="flat"
            class="text-none"
            prepend-icon="mdi-tray-arrow-down"
            :loading="exportingCsv"
            @click="exportCsv"
          >
            Exporter CSV
          </v-btn>
        </div>
      </v-card>

      <v-card variant="flat" class="mt-3" rounded="lg" border>
        <v-data-table-server
          v-model:items-per-page="callsPerPage"
          v-model:page="callsPage"
          :headers="CALLS_HEADERS"
          :items="calls"
          :items-length="callsTotal"
          :loading="callsLoading"
          density="comfortable"
          @update:options="fetchCalls"
        >
          <template #[`item.started_at`]="{ item }">
            <span class="cdr-mono">{{ formatDateTime(item.started_at) }}</span>
          </template>
          <template #[`item.direction`]="{ item }">
            <span class="cdr-dir">
              <v-icon size="13">{{ item.direction === "outbound" ? "mdi-phone-forward-outline" : "mdi-phone-incoming-outline" }}</v-icon>
              {{ item.direction === "outbound" ? "Sortant" : "Entrant" }}
            </span>
          </template>
          <template #[`item.agent_name`]="{ item }">
            <span v-if="item.agent_name">{{ item.agent_name }}</span>
            <span v-else class="cdr-muted">—</span>
          </template>
          <template #[`item.agent_station`]="{ item }">
            <span v-if="item.agent_station" class="cdr-mono">{{ item.agent_station }}</span>
            <span v-else class="cdr-muted">—</span>
          </template>
          <template #[`item.call_status`]="{ item }">
            <v-chip size="small" variant="tonal" :color="statusColor(item.call_status)">
              <v-icon start size="10">mdi-circle</v-icon>
              {{ STATUS_LABEL[item.call_status] || item.call_status }}
            </v-chip>
          </template>
          <template #[`item.duration`]="{ item }">
            <span class="cdr-mono">{{ formatDuration(item.duration) }}</span>
          </template>
          <template #no-data>
            <div class="cdr-empty">Aucun appel sur cette période/ces filtres.</div>
          </template>
        </v-data-table-server>
      </v-card>
    </template>

    <!-- ═══════════ ENREGISTREMENTS ═══════════ -->
    <template v-else>
      <v-alert type="warning" variant="tonal" density="compact" class="mb-3">
        Écoute/téléchargement disponibles uniquement si FusionPBX expose le fichier via une URL
        accessible (http/https). Un chemin de fichier local PBX est signalé comme indisponible
        plutôt que de proposer un téléchargement cassé.
      </v-alert>

      <v-card variant="flat" class="cdr-filters" rounded="lg" border>
        <div class="cdr-filters__row">
          <div class="cdr-field">
            <label>DU</label>
            <input v-model="recFilters.from" type="date" class="cdr-date" />
          </div>
          <div class="cdr-field">
            <label>AU</label>
            <input v-model="recFilters.to" type="date" class="cdr-date" />
          </div>
          <v-text-field
            v-model="recFilters.queue_id"
            label="File"
            variant="outlined"
            density="compact"
            hide-details
            clearable
            style="max-width: 160px"
          />
          <v-text-field
            v-model="recFilters.agent_login"
            label="Agent"
            variant="outlined"
            density="compact"
            hide-details
            clearable
            style="max-width: 150px"
          />
          <v-text-field
            v-model="recFilters.search"
            label="Recherche (appelant, appelé)"
            variant="outlined"
            density="compact"
            hide-details
            clearable
            style="max-width: 210px"
          />
          <v-spacer />
          <v-btn variant="text" class="text-none" @click="resetRecFilters">Réinitialiser</v-btn>
        </div>
      </v-card>

      <div v-if="selectedRecordings.length" class="cdr-bulkbar">
        <span>{{ selectedRecordings.length }} sélectionné(s)</span>
        <v-spacer />
        <v-btn
          color="#00a8a8"
          variant="flat"
          class="text-none"
          size="small"
          prepend-icon="mdi-folder-zip-outline"
          :loading="exportingBulk"
          @click="exportSelectedRecordings"
        >
          Télécharger la sélection (zip)
        </v-btn>
      </div>

      <v-card variant="flat" class="mt-3" rounded="lg" border>
        <v-data-table-server
          v-model:items-per-page="recPerPage"
          v-model:page="recPage"
          v-model="selectedRecordings"
          :headers="RECORDINGS_HEADERS"
          :items="recordings"
          :items-length="recTotal"
          :loading="recLoading"
          item-value="call_uuid"
          show-select
          density="comfortable"
          @update:options="fetchRecordings"
        >
          <template #[`item.started_at`]="{ item }">
            <span class="cdr-mono">{{ formatDateTime(item.started_at) }}</span>
          </template>
          <template #[`item.agent_name`]="{ item }">
            <span v-if="item.agent_name">{{ item.agent_name }}</span>
            <span v-else class="cdr-muted">—</span>
          </template>
          <template #[`item.agent_station`]="{ item }">
            <span v-if="item.agent_station" class="cdr-mono">{{ item.agent_station }}</span>
            <span v-else class="cdr-muted">—</span>
          </template>
          <template #[`item.duration`]="{ item }">
            <span class="cdr-mono">{{ formatDuration(item.duration) }}</span>
          </template>
          <template #[`item.actions`]="{ item }">
            <v-btn
              icon="mdi-download-outline"
              variant="text"
              size="x-small"
              :disabled="!item.recording_available"
              :title="item.recording_available ? 'Télécharger' : 'Indisponible (chemin local PBX)'"
              :loading="downloadingId === item.call_uuid"
              @click="downloadOne(item)"
            />
          </template>
          <template #no-data>
            <div class="cdr-empty">Aucun enregistrement sur cette période/ces filtres.</div>
          </template>
        </v-data-table-server>

        <div v-if="recordings.length" class="cdr-bulkbar cdr-bulkbar--footer">
          <v-spacer />
          <v-btn
            variant="outlined"
            class="text-none"
            size="small"
            prepend-icon="mdi-folder-zip-outline"
            :loading="exportingBulk"
            @click="exportAllFilteredRecordings"
          >
            Télécharger tout le résultat filtré (zip)
          </v-btn>
        </div>
      </v-card>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive } from "vue";
import { telephonyService } from "@/services/telephonyService";

const feedback = reactive({ text: "", type: "success" });

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}
function daysAgoIso(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

const subTab = ref("calls");

const STATUS_LABEL = {
  ended: "Décroché",
  missed: "Manqué",
  abandoned: "Abandonné",
  technical_failure: "Échec technique",
};
const STATUS_OPTIONS = [
  { value: "ended", label: "Décroché" },
  { value: "missed", label: "Manqué" },
  { value: "abandoned", label: "Abandonné" },
  { value: "technical_failure", label: "Échec technique" },
];
const DIRECTION_OPTIONS = [
  { value: "inbound", label: "Entrant" },
  { value: "outbound", label: "Sortant" },
];

function statusColor(status) {
  if (status === "ended") return "#22c55e";
  if (status === "technical_failure") return "#f59e0b";
  return "#e74c3c";
}
function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("fr-FR");
}
function formatDuration(sec) {
  if (!sec && sec !== 0) return "—";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
async function blobErrorMessage(err, fallback) {
  const blob = err?.response?.data;
  if (blob instanceof Blob) {
    try {
      const text = await blob.text();
      const parsed = JSON.parse(text);
      if (parsed?.error) return parsed.error;
    } catch {
      /* corps non-JSON, on garde le message par défaut */
    }
  }
  return err?.response?.data?.error || fallback;
}
function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ── Historique des appels ──────────────────────────────────────────────

const CALLS_HEADERS = [
  { title: "Date / heure", key: "started_at", sortable: false },
  { title: "Appelant", key: "caller", sortable: false },
  { title: "Appelé", key: "callee", sortable: false },
  { title: "Direction", key: "direction", sortable: false },
  { title: "Agent", key: "agent_name", sortable: false },
  { title: "Poste", key: "agent_station", sortable: false },
  { title: "File", key: "queue_id", sortable: false },
  { title: "Statut", key: "call_status", sortable: false },
  { title: "Durée", key: "duration", sortable: false },
];

const callsFilters = reactive({
  from: daysAgoIso(7),
  to: todayIso(),
  call_status: null,
  direction: null,
  queue_id: "",
  agent_login: "",
  search: "",
});
const calls = ref([]);
const callsTotal = ref(0);
const callsPage = ref(1);
const callsPerPage = ref(25);
const callsLoading = ref(false);
const exportingCsv = ref(false);

function callsParams() {
  const p = { page: callsPage.value, per_page: callsPerPage.value };
  if (callsFilters.from) p.from = callsFilters.from;
  if (callsFilters.to) p.to = callsFilters.to;
  if (callsFilters.call_status) p.call_status = callsFilters.call_status;
  if (callsFilters.direction) p.direction = callsFilters.direction;
  if (callsFilters.queue_id) p.queue_id = callsFilters.queue_id;
  if (callsFilters.agent_login) p.agent_login = callsFilters.agent_login;
  if (callsFilters.search) p.search = callsFilters.search;
  return p;
}

async function fetchCalls(options) {
  if (options) {
    callsPage.value = options.page;
    callsPerPage.value = options.itemsPerPage;
  }
  callsLoading.value = true;
  try {
    const { data } = await telephonyService.getCalls(callsParams());
    calls.value = data.calls || [];
    callsTotal.value = data.total || 0;
  } catch (err) {
    feedback.type = "error";
    feedback.text = err?.response?.data?.error || "Impossible de charger l'historique des appels.";
  } finally {
    callsLoading.value = false;
  }
}
function resetCallsFilters() {
  Object.assign(callsFilters, {
    from: daysAgoIso(7), to: todayIso(), call_status: null, direction: null,
    queue_id: "", agent_login: "", search: "",
  });
  callsPage.value = 1;
  fetchCalls();
}

async function exportCsv() {
  exportingCsv.value = true;
  try {
    const { data } = await telephonyService.exportCallsCsv(callsParams());
    triggerBlobDownload(data, `appels_${callsFilters.from}_${callsFilters.to}.csv`);
  } catch (err) {
    feedback.type = "error";
    feedback.text = await blobErrorMessage(err, "L'export CSV a échoué.");
  } finally {
    exportingCsv.value = false;
  }
}

// ── Enregistrements ──────────────────────────────────────────────────────

const RECORDINGS_HEADERS = [
  { title: "Date / heure", key: "started_at", sortable: false },
  { title: "Appelant", key: "caller", sortable: false },
  { title: "Appelé", key: "callee", sortable: false },
  { title: "Agent", key: "agent_name", sortable: false },
  { title: "Poste", key: "agent_station", sortable: false },
  { title: "File", key: "queue_id", sortable: false },
  { title: "Durée", key: "duration", sortable: false },
  { title: "", key: "actions", sortable: false, align: "end" },
];

const recFilters = reactive({
  from: daysAgoIso(7),
  to: todayIso(),
  queue_id: "",
  agent_login: "",
  search: "",
});
const recordings = ref([]);
const recTotal = ref(0);
const recPage = ref(1);
const recPerPage = ref(25);
const recLoading = ref(false);
const selectedRecordings = ref([]);
const exportingBulk = ref(false);
const downloadingId = ref(null);

function recParams() {
  const p = { page: recPage.value, per_page: recPerPage.value };
  if (recFilters.from) p.from = recFilters.from;
  if (recFilters.to) p.to = recFilters.to;
  if (recFilters.queue_id) p.queue_id = recFilters.queue_id;
  if (recFilters.agent_login) p.agent_login = recFilters.agent_login;
  if (recFilters.search) p.search = recFilters.search;
  return p;
}

async function fetchRecordings(options) {
  if (options) {
    recPage.value = options.page;
    recPerPage.value = options.itemsPerPage;
  }
  recLoading.value = true;
  try {
    const { data } = await telephonyService.getRecordings(recParams());
    recordings.value = data.recordings || [];
    recTotal.value = data.total || 0;
  } catch (err) {
    feedback.type = "error";
    feedback.text = err?.response?.data?.error || "Impossible de charger les enregistrements.";
  } finally {
    recLoading.value = false;
  }
}
function resetRecFilters() {
  Object.assign(recFilters, { from: daysAgoIso(7), to: todayIso(), queue_id: "", agent_login: "", search: "" });
  recPage.value = 1;
  fetchRecordings();
}

async function downloadOne(item) {
  downloadingId.value = item.call_uuid;
  try {
    const { data } = await telephonyService.downloadRecording(item.call_uuid);
    triggerBlobDownload(data, `enregistrement_${item.call_uuid}`);
  } catch (err) {
    feedback.type = "error";
    feedback.text = await blobErrorMessage(err, "Le téléchargement a échoué.");
  } finally {
    downloadingId.value = null;
  }
}

async function exportSelectedRecordings() {
  exportingBulk.value = true;
  try {
    const { data } = await telephonyService.exportRecordingsBulk(selectedRecordings.value, recParams());
    triggerBlobDownload(data, `enregistrements_${recFilters.from}_${recFilters.to}.zip`);
  } catch (err) {
    feedback.type = "error";
    feedback.text = await blobErrorMessage(err, "L'export groupé a échoué.");
  } finally {
    exportingBulk.value = false;
  }
}
async function exportAllFilteredRecordings() {
  exportingBulk.value = true;
  try {
    const { data } = await telephonyService.exportRecordingsBulk(null, recParams());
    triggerBlobDownload(data, `enregistrements_${recFilters.from}_${recFilters.to}.zip`);
  } catch (err) {
    feedback.type = "error";
    feedback.text = await blobErrorMessage(err, "L'export groupé a échoué.");
  } finally {
    exportingBulk.value = false;
  }
}
</script>

<style scoped>
.cdr-root { font-family: "Fira Sans", sans-serif; }
.cdr-mono { font-family: "Fira Code", ui-monospace, monospace; font-size: 12.5px; }
.cdr-muted { color: #9aa0aa; }

.cdr-subtabs {
  display: inline-flex;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.cdr-subtab {
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #6b7280;
  background: #fff;
  cursor: pointer;
  border: none;
  font-family: inherit;
}
.cdr-subtab:first-child { border-right: 1px solid #e5e7eb; }
.cdr-subtab--active { background: rgba(0, 168, 168, 0.1); color: #00a8a8; }

.cdr-filters { padding: 14px 16px; }
.cdr-filters__row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.cdr-field { display: flex; flex-direction: column; gap: 3px; }
.cdr-field label { font-size: 10px; font-weight: 700; letter-spacing: 0.05em; color: #9aa0aa; }
.cdr-date {
  font-family: inherit; font-size: 13px; padding: 6px 8px; border: 1px solid #c7c9d1;
  border-radius: 4px; color: #1a1a2e; height: 40px;
}

.cdr-dir { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: #6b7280; }
.cdr-empty { text-align: center; padding: 28px 16px; color: #9aa0aa; font-size: 12.5px; }

.cdr-bulkbar {
  display: flex; align-items: center; gap: 10px; padding: 8px 4px; font-size: 12.5px; color: #1a1a2e;
}
.cdr-bulkbar--footer { padding: 10px 16px; border-top: 1px solid #e5e7eb; }
</style>
