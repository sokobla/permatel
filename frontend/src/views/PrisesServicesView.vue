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
          Pointez les vacations des agents (début / fin) et suivez celles en cours.
        </p>
      </div>
    </div>

    <!-- ══ FORMULAIRE DE POINTAGE ════════════════════════════════════════ -->
    <PriseDeServiceForm @changed="loadData" @notify="onNotify" />

    <!-- ══ FILTRES ═══════════════════════════════════════════════════════ -->
    <div class="psv-filter-bar">
      <div class="psv-filter-group">
        <span class="psv-filter-lbl">DATE (À PARTIR DU)</span>
        <input v-model="fDate" type="date" class="psv-date" />
      </div>
      <div class="psv-filter-group">
        <span class="psv-filter-lbl">AGENT</span>
        <select v-model="fAgent" class="psv-select">
          <option :value="null">Tous</option>
          <option v-for="o in agentOptions" :key="o.id" :value="o.id">{{ o.label }}</option>
        </select>
      </div>
      <div class="psv-filter-group">
        <span class="psv-filter-lbl">CLIENT</span>
        <select v-model="fClient" class="psv-select">
          <option :value="null">Tous</option>
          <option v-for="o in clientOptions" :key="o.id" :value="o.id">{{ o.label }}</option>
        </select>
      </div>
      <div class="psv-filter-group">
        <span class="psv-filter-lbl">SITE</span>
        <select v-model="fSite" class="psv-select">
          <option :value="null">Tous</option>
          <option v-for="o in siteOptions" :key="o.id" :value="o.id">{{ o.label }}</option>
        </select>
      </div>
      <div class="psv-filter-group">
        <span class="psv-filter-lbl">STATUT</span>
        <button
          v-for="s in STATUTS"
          :key="s.value"
          :class="['psv-chip', fStatut === s.value ? 'psv-chip--active' : '']"
          @click="fStatut = fStatut === s.value ? null : s.value"
        >{{ s.label }}</button>
      </div>
      <button v-if="activeFiltersCount > 0" class="psv-filter-reset" @click="resetFilters">
        <v-icon size="11">mdi-close</v-icon> Réinitialiser
      </button>
    </div>

    <!-- ══ TABLE ══════════════════════════════════════════════════════════ -->
    <div class="psv-table-wrap">
      <table class="psv-table">
        <thead>
          <tr>
            <th class="psv-th">Agent</th>
            <th class="psv-th">Client</th>
            <th class="psv-th">Site</th>
            <th class="psv-th" style="width:140px">Début</th>
            <th class="psv-th" style="width:140px">Fin</th>
            <th class="psv-th" style="width:90px">Durée</th>
            <th class="psv-th" style="width:110px">Statut</th>
            <th class="psv-th" style="width:96px; text-align:right">Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filteredRows" :key="row.id" class="psv-data-row">
            <td class="psv-td">
              <div class="psv-cell-flex">
                <span class="psv-avatar">{{ initials(row.agent_nom) }}</span>
                <span class="psv-agent-name">{{ row.agent_nom ?? '—' }}</span>
              </div>
            </td>
            <td class="psv-td">{{ row.client_nom ?? `Client #${row.client_id}` }}</td>
            <td class="psv-td">
              <span class="psv-site">
                <v-icon size="11" color="#9aa0aa">mdi-map-marker-outline</v-icon>
                {{ row.site_nom ?? '—' }}
              </span>
            </td>
            <td class="psv-td psv-td--date">{{ formatDate(row.date_debut) }}</td>
            <td class="psv-td psv-td--date">{{ row.date_fin ? formatDate(row.date_fin) : '—' }}</td>
            <td class="psv-td psv-td--date">{{ formatDuration(row.duree_minutes, row.statut) }}</td>
            <td class="psv-td">
              <span :class="['psv-statut-chip', `psv-statut-chip--${row.statut}`]">
                <span class="psv-statut-chip__dot"></span>
                {{ row.statut === 'en_cours' ? 'En cours' : 'Terminée' }}
              </span>
            </td>
            <td class="psv-td" style="text-align:right">
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
                <v-icon size="28" color="#e0e0e0" class="psv-spin">mdi-loading</v-icon>
                <span>Chargement des prises de service…</span>
              </div>
            </td>
          </tr>
          <tr v-else-if="loadError">
            <td colspan="8">
              <div class="psv-empty" style="color:#e74c3c">
                <v-icon size="28" color="#e74c3c">mdi-alert-circle-outline</v-icon>
                <span>{{ loadError }}</span>
              </div>
            </td>
          </tr>
          <tr v-else-if="filteredRows.length === 0">
            <td colspan="8">
              <div class="psv-empty">
                <v-icon size="36" color="#e0e0e0">mdi-clipboard-text-clock-outline</v-icon>
                <span>Aucune prise de service ne correspond aux critères</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <v-snackbar v-model="snackbar.show" :color="snackbar.color" location="top" :timeout="3500">
      {{ snackbar.text }}
    </v-snackbar>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import {
  listPrisesDeService,
  endPriseDeService,
} from "@/services/priseDeServiceService";
import PriseDeServiceForm from "@/components/prises/PriseDeServiceForm.vue";

const STATUTS = [
  { value: "en_cours", label: "En cours" },
  { value: "terminee", label: "Terminée" },
];

const rows = ref([]);
const loading = ref(false);
const loadError = ref("");
const endingId = ref(null);

const fDate = ref("");
const fAgent = ref(null);
const fClient = ref(null);
const fSite = ref(null);
const fStatut = ref(null);

const snackbar = ref({ show: false, color: "success", text: "" });

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
  return [...map.values()].sort((a, b) => (a.label || "").localeCompare(b.label || ""));
}
const agentOptions = computed(() => distinct((r) => r.agent_id, (r) => r.agent_nom || `Agent #${r.agent_id}`));
const clientOptions = computed(() => distinct((r) => r.client_id, (r) => r.client_nom || `Client #${r.client_id}`));
const siteOptions = computed(() => distinct((r) => r.site_id, (r) => r.site_nom || `Site #${r.site_id}`));

const activeFiltersCount = computed(() =>
  [fDate.value, fAgent.value, fClient.value, fSite.value, fStatut.value].filter((v) => v != null && v !== "").length,
);

const filteredRows = computed(() => {
  let list = rows.value;
  if (fAgent.value != null) list = list.filter((r) => r.agent_id === fAgent.value);
  if (fClient.value != null) list = list.filter((r) => r.client_id === fClient.value);
  if (fSite.value != null) list = list.filter((r) => r.site_id === fSite.value);
  if (fStatut.value) list = list.filter((r) => r.statut === fStatut.value);
  if (fDate.value) {
    const from = new Date(fDate.value + "T00:00:00").getTime();
    list = list.filter((r) => r.date_debut && new Date(r.date_debut).getTime() >= from);
  }
  return list;
});

function resetFilters() {
  fDate.value = "";
  fAgent.value = null;
  fClient.value = null;
  fSite.value = null;
  fStatut.value = null;
}

async function onEndRow(row) {
  endingId.value = row.id;
  try {
    await endPriseDeService(row.id);
    onNotify({ type: "success", text: "Vacation terminée." });
    await loadData();
  } catch (err) {
    onNotify({ type: "error", text: err?.response?.data?.error || "Échec de la clôture." });
  } finally {
    endingId.value = null;
  }
}

function onNotify({ type, text }) {
  snackbar.value = { show: true, color: type === "error" ? "error" : "success", text };
}

// ── Formatage ──────────────────────────────────────────────────────────────
function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit" })
    + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}
function formatDuration(min, statut) {
  if (min == null) return "—";
  const h = Math.floor(min / 60);
  const m = min % 60;
  const txt = h > 0 ? `${h}h ${String(m).padStart(2, "0")}` : `${m} min`;
  return statut === "en_cours" ? `${txt}…` : txt;
}
function initials(name) {
  if (!name) return "?";
  return name.split(" ").filter(Boolean).map((p) => p[0]).join("").slice(0, 2).toUpperCase();
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
.psv-hdr { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.psv-hdr-title-row { display: flex; align-items: center; gap: 9px; margin-bottom: 4px; }
.psv-hdr-marker { width: 3px; height: 18px; background: #00a8a8; border-radius: 1px; }
.psv-title { font-size: 1.05rem; font-weight: 800; letter-spacing: 0.1em; color: #000b23; text-transform: uppercase; margin: 0; }
.psv-subtitle { font-size: 11px; color: #999; margin: 0; padding-left: 12px; }

/* Filter bar */
.psv-filter-bar {
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 3px; padding: 10px 12px;
}
.psv-filter-group { display: flex; align-items: center; gap: 6px; }
.psv-filter-lbl { font-family: "Fira Code", monospace; font-size: 8px; font-weight: 700; letter-spacing: 0.1em; color: #ccc; text-transform: uppercase; white-space: nowrap; }
.psv-date, .psv-select {
  height: 28px; border: 1px solid #e5e7eb; border-radius: 4px; background: #fff;
  font-size: 11.5px; color: #1a1a2e; padding: 0 6px; outline: none; max-width: 170px;
}
.psv-date:focus, .psv-select:focus { border-color: #00a8a8; }
.psv-chip {
  height: 22px; padding: 0 9px; border: 1px solid rgba(0,0,0,0.1); border-radius: 11px;
  background: transparent; font-size: 10px; font-weight: 500; color: #555; cursor: pointer; transition: all .12s;
}
.psv-chip:hover { border-color: #00a8a8; color: #00a8a8; }
.psv-chip--active { background: #000b23; border-color: #000b23; color: #fff; }
.psv-filter-reset {
  display: inline-flex; align-items: center; gap: 4px; margin-left: auto; height: 22px; padding: 0 8px;
  border: none; border-radius: 3px; background: rgba(231,76,60,0.08); font-size: 10px; font-weight: 600; color: #e74c3c; cursor: pointer;
}

/* Table */
.psv-table-wrap { background: #fff; border: 1px solid rgba(0,0,0,0.08); border-radius: 3px; overflow: hidden; }
.psv-table { width: 100%; border-collapse: collapse; }
.psv-th {
  padding: 9px 12px; text-align: left; font-size: 9px; font-weight: 800; letter-spacing: 0.12em;
  color: #bbb; text-transform: uppercase; background: #fafafa; border-bottom: 1px solid rgba(0,0,0,0.07); white-space: nowrap;
}
.psv-data-row { border-bottom: 1px solid rgba(0,0,0,0.05); transition: background .1s; }
.psv-data-row:hover { background: rgba(0,168,168,0.025); }
.psv-data-row:last-child { border-bottom: none; }
.psv-td { padding: 8px 12px; font-size: 11.5px; color: #333; vertical-align: middle; white-space: nowrap; }
.psv-td--date { font-family: "Fira Code", monospace; font-size: 10.5px; color: #888; }
.psv-cell-flex { display: flex; align-items: center; gap: 6px; }
.psv-avatar {
  display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%;
  background: rgba(0,168,168,0.12); font-family: "Fira Code", monospace; font-size: 8px; font-weight: 700; color: #00a8a8; flex-shrink: 0;
}
.psv-agent-name { font-weight: 600; color: #000b23; }
.psv-site { display: inline-flex; align-items: center; gap: 4px; color: #777; }

.psv-statut-chip { display: inline-flex; align-items: center; gap: 5px; height: 20px; padding: 0 8px; border-radius: 10px; font-size: 10px; font-weight: 600; }
.psv-statut-chip__dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.psv-statut-chip--en_cours { background: rgba(243,156,18,0.12); color: #f39c12; }
.psv-statut-chip--terminee { background: rgba(39,174,96,0.1); color: #27ae60; }

.psv-end-btn {
  display: inline-flex; align-items: center; gap: 4px; height: 24px; padding: 0 9px; border-radius: 3px;
  border: 1px solid rgba(0,11,35,0.15); background: #fff; font-size: 10px; font-weight: 600; color: #000b23; cursor: pointer; transition: all .12s;
}
.psv-end-btn:hover:not(:disabled) { background: #000b23; color: #fff; border-color: #000b23; }
.psv-end-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.psv-empty { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 48px 0; color: #ccc; font-size: 12px; }
.psv-spin { animation: psv-rotate 0.8s linear infinite; }
@keyframes psv-rotate { to { transform: rotate(360deg); } }
</style>
