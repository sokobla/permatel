<template>
  <div class="psv-root">
    <!-- ══ HEADER ════════════════════════════════════════════════════════ -->
    <div class="psv-hdr">
      <div class="psv-hdr-left">
        <div class="psv-hdr-title-row">
          <span class="psv-hdr-marker"></span>
          <h1 class="psv-title">Prises de service</h1>
        </div>
        <p class="psv-subtitle">
          Pointez les vacations des agents (début / fin) et suivez celles en
          cours.
        </p>
      </div>
      <button
        class="psv-export-btn"
        :disabled="filteredRows.length === 0"
        @click="exportCsv"
      >
        <v-icon size="13">mdi-tray-arrow-down</v-icon> Exporter CSV
      </button>
    </div>

    <!-- ══ FORMULAIRE DE POINTAGE ════════════════════════════════════════ -->
    <PriseDeServiceForm @changed="loadData" @notify="onNotify" />

    <!-- ══ FILTRES ═══════════════════════════════════════════════════════ -->
    <div class="psv-filter-bar">
      <div class="psv-filter-group">
        <label class="psv-filter-lbl" for="psv-date-input">DATE (À PARTIR DU)</label>
        <input id="psv-date-input" v-model="fDate" type="date" class="psv-date" />
      </div>
      <div class="psv-filter-group">
        <label class="psv-filter-lbl" for="psv-agent-select">AGENT</label>
        <select id="psv-agent-select" v-model="fAgent" class="psv-select">
          <option :value="null">Tous</option>
          <option v-for="o in agentOptions" :key="o.id" :value="o.id">
            {{ o.label }}
          </option>
        </select>
      </div>
      <div class="psv-filter-group">
        <label class="psv-filter-lbl" for="psv-client-select">CLIENT</label>
        <select id="psv-client-select" v-model="fClient" class="psv-select">
          <option :value="null">Tous</option>
          <option v-for="o in clientOptions" :key="o.id" :value="o.id">
            {{ o.label }}
          </option>
        </select>
      </div>
      <div class="psv-filter-group">
        <label class="psv-filter-lbl" for="psv-site-select">SITE</label>
        <select id="psv-site-select" v-model="fSite" class="psv-select">
          <option :value="null">Tous</option>
          <option v-for="o in siteOptions" :key="o.id" :value="o.id">
            {{ o.label }}
          </option>
        </select>
      </div>
      <div class="psv-filter-group">
        <span class="psv-filter-lbl" aria-hidden="true">STATUT</span>
        <button
          v-for="s in STATUTS"
          :key="String(s.value)"
          :class="['psv-chip', fStatut === s.value ? 'psv-chip--active' : '']"
          :aria-pressed="fStatut === s.value"
          @click="fStatut = s.value"
        >
          {{ s.label }}
        </button>
      </div>
      <button
        v-if="activeFiltersCount > 0"
        class="psv-filter-reset"
        @click="resetFilters"
      >
        <v-icon size="11">mdi-close</v-icon> Réinitialiser
      </button>
    </div>

    <!-- ══ COUNT BAR ═════════════════════════════════════════════════════ -->
    <div class="psv-count-bar" aria-live="polite" aria-atomic="true">
      <span class="psv-count-item psv-count-item--encours">
        <span class="psv-count-dot psv-count-dot--encours"></span>
        <strong>{{ countEncours }}</strong>&nbsp;en cours
      </span>
      <span class="psv-count-sep" aria-hidden="true">·</span>
      <span class="psv-count-item">
        <strong>{{ countTerminee }}</strong>&nbsp;terminées
      </span>
      <span class="psv-count-total">
        ({{ filteredRows.length }} affichée{{ filteredRows.length !== 1 ? "s" : "" }})
      </span>
    </div>

    <!-- ══ TABLE ══════════════════════════════════════════════════════════ -->
    <div class="psv-table-wrap">
      <table class="psv-table">
        <thead>
          <tr>
            <th class="psv-th">Agent</th>
            <th class="psv-th">Client</th>
            <th class="psv-th">Site</th>
            <th class="psv-th" style="width: 140px">Début</th>
            <th class="psv-th" style="width: 140px">Fin</th>
            <th class="psv-th" style="width: 90px">Durée</th>
            <th class="psv-th" style="width: 110px">Statut</th>
            <th class="psv-th" style="width: 96px; text-align: right">
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filteredRows" :key="row.id" class="psv-data-row">
            <td class="psv-td">
              <div class="psv-cell-flex">
                <span class="psv-avatar">{{ initials(row.agent_nom) }}</span>
                <div class="psv-agent-name">{{ row.agent_nom ?? "—" }}</div>
              </div>
            </td>
            <td class="psv-td">{{ row.client_nom ?? "—" }}</td>
            <td class="psv-td">{{ row.site_nom ?? "—" }}</td>
            <td class="psv-td psv-td--date">
              {{ formatDate(row.date_debut) }}
            </td>
            <td class="psv-td psv-td--date">
              {{ row.date_fin ? formatDate(row.date_fin) : "—" }}
            </td>
            <td class="psv-td psv-td--date">
              {{ formatDuration(row) }}
            </td>
            <td class="psv-td">
              <span
                :class="['psv-statut-chip', `psv-statut-chip--${row.statut}`]"
              >
                <span class="psv-statut-chip__dot"></span>
                {{ row.statut === "en_cours" ? "En cours" : "Terminée" }}
              </span>
            </td>
            <td class="psv-td" style="text-align: right">
              <button
                v-if="row.statut === 'en_cours'"
                class="psv-end-btn"
                :disabled="endingId === row.id"
                @click="onEndRow(row)"
              >
                <v-icon size="12">mdi-stop-circle-outline</v-icon>
                Terminer
              </button>
            </td>
          </tr>

          <tr v-if="loading">
            <td colspan="8">
              <div class="psv-empty">
                <v-icon size="28" color="#e0e0e0" class="psv-spin"
                  >mdi-loading</v-icon
                >
                <span>Chargement des prises de service…</span>
              </div>
            </td>
          </tr>
          <tr v-else-if="loadError">
            <td colspan="8">
              <div class="psv-empty" style="color: #e74c3c">
                <v-icon size="28" color="#e74c3c"
                  >mdi-alert-circle-outline</v-icon
                >
                <span>{{ loadError }}</span>
              </div>
            </td>
          </tr>
          <tr v-else-if="filteredRows.length === 0">
            <td colspan="8">
              <div class="psv-empty">
                <v-icon size="36" color="#e0e0e0"
                  >mdi-clipboard-text-clock-outline</v-icon
                >
                <span>Aucune prise de service ne correspond aux critères</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ══ DIALOGUE FIN DE VACATION ══════════════════════════════════════ -->
    <v-dialog
      v-model="endDialog.show"
      max-width="380"
      :persistent="endingId !== null"
    >
      <div class="end-dlg">
        <div class="end-dlg-hdr">
          <span class="end-dlg-title">Terminer la vacation</span>
        </div>
        <div class="end-dlg-body">
          <p class="end-dlg-desc">
            Précisez l'heure de fin. Par défaut, l'heure actuelle est utilisée.
          </p>
          <div class="end-dlg-field">
            <label class="end-dlg-lbl" for="end-date-fin">HEURE DE FIN</label>
            <input
              id="end-date-fin"
              v-model="endDialog.dateFin"
              type="datetime-local"
              class="end-dlg-input"
            />
          </div>
        </div>
        <div class="end-dlg-actions">
          <button
            class="end-dlg-btn-ghost"
            :disabled="endingId !== null"
            @click="endDialog.show = false"
          >
            Annuler
          </button>
          <button
            class="end-dlg-btn-primary"
            :disabled="endingId !== null"
            @click="confirmEndRow"
          >
            <span v-if="endingId !== null" class="end-dlg-spinner"></span>
            <v-icon v-else size="12">mdi-check</v-icon>
            Terminer
          </button>
        </div>
      </div>
    </v-dialog>

    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      location="top"
      :timeout="snackbar.timeout"
    >
      {{ snackbar.text }}
      <template #actions>
        <v-btn variant="text" size="small" @click="snackbar.show = false">
          ×
        </v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import {
  listPrisesDeService,
  endPriseDeService,
} from "@/services/priseDeServiceService";
import PriseDeServiceForm from "@/components/prises/PriseDeServiceForm.vue";
import { arrayToCsv } from "@/utils/downloadBlob";

const STATUTS = [
  { value: null, label: "Toutes" },
  { value: "en_cours", label: "En cours" },
  { value: "terminee", label: "Terminée" },
];

function todayIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function nowLocalIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const DEFAULT_STATUT = "en_cours";
const DEFAULT_DATE = todayIso();

const rows = ref([]);
const loading = ref(false);
const loadError = ref("");
const endingId = ref(null);
const endDialog = ref({ show: false, rowId: null, dateFin: "" });

const fDate = ref(DEFAULT_DATE);
const fAgent = ref(null);
const fClient = ref(null);
const fSite = ref(null);
const fStatut = ref(DEFAULT_STATUT);

const snackbar = ref({ show: false, color: "success", text: "", timeout: 3500 });

// Reactive tick for live elapsed-time computation (refreshes every 60s)
const elapsedTick = ref(0);
let _tickTimer = null;
onMounted(() => {
  _tickTimer = setInterval(() => { elapsedTick.value++; }, 60000);
});
onUnmounted(() => {
  if (_tickTimer) clearInterval(_tickTimer);
});

async function loadData() {
  loading.value = true;
  loadError.value = "";
  try {
    rows.value = await listPrisesDeService();
  } catch {
    loadError.value = "Impossible de charger les prises de service.";
  } finally {
    loading.value = false;
  }
}

// ── Options de filtres (dérivées des données) ──────────────────────────────
function distinct(getId, getLabel) {
  const map = new Map();
  for (const r of rows.value) {
    const id = getId(r);
    if (id != null && !map.has(id)) map.set(id, { id, label: getLabel(r) });
  }
  return [...map.values()].sort((a, b) =>
    (a.label || "").localeCompare(b.label || ""),
  );
}
const agentOptions = computed(() =>
  distinct(
    (r) => r.agent_id,
    (r) => r.agent_nom || `Agent #${r.agent_id}`,
  ),
);
const clientOptions = computed(() =>
  distinct(
    (r) => r.client_id,
    (r) => r.client_nom || `Client #${r.client_id}`,
  ),
);
const siteOptions = computed(() =>
  distinct(
    (r) => r.site_id,
    (r) => r.site_nom || `Site #${r.site_id}`,
  ),
);

const countEncours = computed(
  () => rows.value.filter((r) => r.statut === "en_cours").length,
);
const countTerminee = computed(
  () => rows.value.filter((r) => r.statut === "terminee").length,
);

const activeFiltersCount = computed(
  () =>
    [
      fDate.value !== DEFAULT_DATE ? fDate.value : null,
      fAgent.value,
      fClient.value,
      fSite.value,
      fStatut.value !== DEFAULT_STATUT ? fStatut.value : null,
    ].filter((v) => v != null && v !== "").length,
);

const filteredRows = computed(() => {
  let list = rows.value;
  if (fAgent.value != null)
    list = list.filter((r) => r.agent_id === fAgent.value);
  if (fClient.value != null)
    list = list.filter((r) => r.client_id === fClient.value);
  if (fSite.value != null) list = list.filter((r) => r.site_id === fSite.value);
  if (fStatut.value) list = list.filter((r) => r.statut === fStatut.value);
  if (fDate.value) {
    const from = new Date(fDate.value + "T00:00:00").getTime();
    list = list.filter(
      (r) => r.date_debut && new Date(r.date_debut).getTime() >= from,
    );
  }
  return list;
});

function exportCsv() {
  arrayToCsv(
    [
      "agent",
      "client",
      "site",
      "date_debut",
      "date_fin",
      "duree_minutes",
      "statut",
    ],
    filteredRows.value.map((r) => [
      r.agent_nom,
      r.client_nom,
      r.site_nom,
      r.date_debut,
      r.date_fin,
      r.duree_minutes,
      r.statut,
    ]),
    `prises_de_service_${new Date().toISOString().slice(0, 10)}.csv`,
  );
}

function resetFilters() {
  fDate.value = DEFAULT_DATE;
  fAgent.value = null;
  fClient.value = null;
  fSite.value = null;
  fStatut.value = DEFAULT_STATUT;
}

function onEndRow(row) {
  endDialog.value = { show: true, rowId: row.id, dateFin: nowLocalIso() };
}

async function confirmEndRow() {
  const { rowId, dateFin } = endDialog.value;
  endingId.value = rowId;
  try {
    await endPriseDeService(rowId, dateFin || undefined);
    endDialog.value.show = false;
    onNotify({ type: "success", text: "Vacation terminée." });
    await loadData();
  } catch (err) {
    onNotify({
      type: "error",
      text: err?.response?.data?.error || "Échec de la clôture.",
    });
  } finally {
    endingId.value = null;
  }
}

function onNotify({ type, text }) {
  snackbar.value = {
    show: true,
    color: type === "error" ? "error" : "success",
    text,
    timeout: type === "error" ? -1 : 3500,
  };
}

// ── Formatage ──────────────────────────────────────────────────────────────
function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return (
    d.toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }) +
    " " +
    d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
  );
}
function formatDuration(row) {
  if (row.statut === "en_cours") {
    void elapsedTick.value; // reactive dependency for live tick
    const ms = Date.now() - new Date(row.date_debut).getTime();
    const min = Math.max(0, Math.floor(ms / 60000));
    const h = Math.floor(min / 60);
    const m = min % 60;
    return h > 0 ? `${h}h ${String(m).padStart(2, "0")}…` : `${m} min…`;
  }
  const min = row.duree_minutes;
  if (min == null) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h ${String(m).padStart(2, "0")}` : `${m} min`;
}
function initials(name) {
  if (!name) return "?";
  return name
    .split(" ")
    .filter(Boolean)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

onMounted(loadData);
</script>

<style scoped>
.psv-root {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px;
  background: #f2f2f2;
  min-height: 100%;
  font-family: "Fira Sans", sans-serif;
}

/* Header */
.psv-hdr {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.psv-hdr-title-row {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 4px;
}
.psv-hdr-marker {
  width: 3px;
  height: 18px;
  background: #00a8a8;
  border-radius: 1px;
}
.psv-title {
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #000b23;
  text-transform: uppercase;
  margin: 0;
}
.psv-subtitle {
  font-size: 13px;
  color: #999;
  margin: 0;
  padding-left: 12px;
}

/* Export button (header zone) */
.psv-export-btn {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  gap: 5px;
  height: 30px;
  padding: 0 12px;
  border: none;
  border-radius: 3px;
  background: #00a8a8;
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #fff;
  cursor: pointer;
  transition: background 0.12s;
  white-space: nowrap;
}
.psv-export-btn:hover:not(:disabled) {
  background: #008f8f;
}
.psv-export-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.psv-export-btn:focus-visible {
  outline: 2px solid #00a8a8;
  outline-offset: 2px;
}

/* Filter bar */
.psv-filter-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 3px;
  padding: 10px 12px;
}
.psv-filter-group {
  display: flex;
  align-items: center;
  gap: 6px;
}
.psv-filter-lbl {
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #666;
  text-transform: uppercase;
  white-space: nowrap;
}
.psv-date,
.psv-select {
  height: 28px;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  background: #fff;
  font-size: 11.5px;
  color: #1a1a2e;
  padding: 0 6px;
  outline: none;
  max-width: 170px;
  transition: border-color 0.15s;
}
.psv-date:focus-visible,
.psv-select:focus-visible {
  border-color: #00a8a8;
  box-shadow: 0 0 0 2px rgba(0, 168, 168, 0.15);
}
.psv-chip {
  height: 22px;
  padding: 0 9px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 11px;
  background: transparent;
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 500;
  color: #555;
  cursor: pointer;
  transition: all 0.12s;
}
.psv-chip:hover {
  border-color: #00a8a8;
  color: #00a8a8;
}
.psv-chip--active {
  background: #000b23;
  border-color: #000b23;
  color: #fff;
}
.psv-filter-reset {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  height: 22px;
  padding: 0 8px;
  border: none;
  border-radius: 3px;
  background: rgba(231, 76, 60, 0.08);
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: #e74c3c;
  cursor: pointer;
}

/* Count bar */
.psv-count-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 3px;
  font-size: 12px;
  color: #555;
}
.psv-count-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.psv-count-item--encours {
  color: #f39c12;
}
.psv-count-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.psv-count-sep {
  color: #ccc;
  font-size: 14px;
}
.psv-count-total {
  margin-left: auto;
  color: #aaa;
  font-size: 11px;
}

/* Table */
.psv-table-wrap {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 3px;
  overflow: hidden;
}
.psv-table {
  width: 100%;
  border-collapse: collapse;
}
.psv-th {
  padding: 9px 12px;
  text-align: left;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #555;
  text-transform: uppercase;
  background: #fafafa;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  white-space: nowrap;
}
.psv-data-row {
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  transition: background 0.1s;
}
.psv-data-row:hover {
  background: rgba(0, 168, 168, 0.025);
}
.psv-data-row:last-child {
  border-bottom: none;
}
.psv-td {
  padding: 8px 12px;
  font-size: 11.5px;
  color: #333;
  vertical-align: middle;
  white-space: nowrap;
}
.psv-td--date {
  font-family: "Fira Code", monospace;
  font-size: 10.5px;
  color: #888;
}
.psv-cell-flex {
  display: flex;
  align-items: center;
  gap: 6px;
}
.psv-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: rgba(0, 168, 168, 0.12);
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-weight: 700;
  color: #00a8a8;
  flex-shrink: 0;
}
.psv-agent-name {
  font-weight: 600;
  color: #000b23;
}

.psv-statut-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}
.psv-statut-chip__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.psv-statut-chip--en_cours {
  background: rgba(243, 156, 18, 0.12);
  color: #f39c12;
}
.psv-statut-chip--terminee {
  background: rgba(39, 174, 96, 0.1);
  color: #27ae60;
}

.psv-end-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  border-radius: 3px;
  border: 1px solid rgba(0, 11, 35, 0.15);
  background: #fff;
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: #000b23;
  cursor: pointer;
  transition: all 0.12s;
}
.psv-end-btn:hover:not(:disabled) {
  background: #000b23;
  color: #fff;
  border-color: #000b23;
}
.psv-end-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.psv-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 48px 0;
  color: #ccc;
  font-size: 14px;
}
.psv-spin {
  animation: psv-rotate 0.8s linear infinite;
}
@keyframes psv-rotate {
  to {
    transform: rotate(360deg);
  }
}

/* End vacation dialog — bespoke, no Vuetify card utilities */
.end-dlg {
  background: #fff;
  border-radius: 3px;
  overflow: hidden;
  font-family: "Fira Sans", sans-serif;
}
.end-dlg-hdr {
  background: #000b23;
  padding: 14px 18px;
}
.end-dlg-title {
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #fff;
  text-transform: uppercase;
}
.end-dlg-body {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.end-dlg-desc {
  margin: 0;
  font-size: 12.5px;
  color: #555;
  line-height: 1.5;
}
.end-dlg-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.end-dlg-lbl {
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #555;
  text-transform: uppercase;
}
.end-dlg-input {
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
.end-dlg-input:focus-visible {
  border-color: #00a8a8;
}
.end-dlg-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 18px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
}
.end-dlg-btn-ghost {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 14px;
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
.end-dlg-btn-ghost:hover:not(:disabled) {
  border-color: #888;
  color: #444;
}
.end-dlg-btn-ghost:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.end-dlg-btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
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
}
.end-dlg-btn-primary:hover:not(:disabled) {
  background: #0a0c14;
}
.end-dlg-btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.end-dlg-btn-primary:focus-visible {
  outline: 2px solid #00a8a8;
  outline-offset: 2px;
}
.end-dlg-spinner {
  width: 11px;
  height: 11px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: end-dlg-spin 0.7s linear infinite;
}
@keyframes end-dlg-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
