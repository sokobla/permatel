<template>
  <!-- === MONITORING DES SESSIONS === -->
  <section class="sm-root">
    <!-- Barre d'actions -->
    <header class="sm-toolbar">
      <div class="sm-toolbar__title">
        <h2 class="sm-title">SESSIONS UTILISATEURS</h2>
        <span class="sm-count">({{ rowCount }})</span>
      </div>
      <div class="sm-toolbar__actions">
        <!-- Mode : session / journalier -->
        <div class="sm-seg">
          <button
            v-for="m in MODES"
            :key="m.key"
            :class="['sm-seg__btn', { 'sm-seg__btn--on': mode === m.key }]"
            @click="setMode(m.key)"
          >
            {{ m.label }}
          </button>
        </div>

        <!-- Scope (session uniquement) -->
        <div v-if="mode === 'session'" class="sm-seg">
          <button
            v-for="opt in SCOPES"
            :key="opt.key"
            :class="['sm-seg__btn', { 'sm-seg__btn--on': scope === opt.key }]"
            @click="setScope(opt.key)"
          >
            {{ opt.label }}
          </button>
        </div>

        <!-- Filtres date (vue journalière) -->
        <template v-if="mode === 'daily'">
          <input v-model="filterFrom" type="date" class="sm-date" title="Du" />
          <input v-model="filterTo" type="date" class="sm-date" title="Au" />
        </template>

        <button class="sm-btn sm-btn--ghost" :disabled="loading" @click="fetch">
          <span :class="{ 'sm-spin': loading }">⟳</span> ACTUALISER
        </button>
        <button
          class="sm-btn sm-btn--ghost"
          :disabled="loading || rowCount === 0"
          @click="exportCsv"
        >
          ↓ CSV
        </button>
      </div>
    </header>

    <!-- Erreur -->
    <div v-if="loadError" class="sm-banner sm-banner--error">
      {{ loadError }}
    </div>

    <!-- ══ VUE PAR SESSION ══════════════════════════════════════════════════ -->
    <div v-if="mode === 'session'" class="sm-table-wrap">
      <table class="sm-table">
        <thead>
          <tr>
            <th class="sm-th">UTILISATEUR</th>
            <th class="sm-th">RÔLE</th>
            <th class="sm-th">STATUT</th>
            <th class="sm-th">IP</th>
            <th class="sm-th">DÉBUT</th>
            <th class="sm-th">DERNIÈRE ACTIVITÉ</th>
            <th class="sm-th">TEMPS (ACTIF / PAUSE)</th>
            <th class="sm-th sm-th--right">ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="loading">
            <tr v-for="n in 4" :key="`sk-${n}`" class="sm-row">
              <td v-for="c in 8" :key="c" class="sm-td"><span class="sm-skel"></span></td>
            </tr>
          </template>
          <tr v-else-if="sessions.length === 0" class="sm-row">
            <td colspan="8">
              <div class="sm-empty">
                <p class="sm-empty__title">Aucune session {{ scope === "live" ? "active" : "" }}.</p>
                <p class="sm-empty__sub">Les sessions du tenant courant apparaîtront ici.</p>
              </div>
            </td>
          </tr>
          <tr
            v-for="s in sessions"
            :key="s.id"
            class="sm-row"
            :class="{ 'sm-row--me': s.is_current }"
          >
            <td class="sm-td">
              <div class="sm-user">
                <span class="sm-user__name">{{ s.full_name || s.username || "—" }}</span>
                <span class="sm-user__sub">
                  @{{ s.username
                  }}<span v-if="s.is_current" class="sm-tag-me">CETTE SESSION</span>
                </span>
              </div>
            </td>
            <td class="sm-td"><span class="sm-role">{{ s.role || "—" }}</span></td>
            <td class="sm-td">
              <span :class="['sm-badge', `sm-badge--${s.status}`]">
                <span class="sm-badge__dot"></span>{{ STATUT_LABELS[s.status] ?? s.status }}
              </span>
            </td>
            <td class="sm-td sm-mono">
              <span v-if="s.country_code" class="sm-flag">{{ countryFlag(s.country_code) }}</span>
              {{ s.ip_address || "—" }}
            </td>
            <td class="sm-td sm-mono">{{ formatDate(s.session_start) }}</td>
            <td class="sm-td sm-mono">{{ formatRelative(s.last_activity_at) }}</td>
            <td class="sm-td sm-mono">
              {{ formatMinutes(s.active_minutes) }} / {{ formatMinutes(s.pause_minutes) }}
            </td>
            <td class="sm-td sm-td--right">
              <template v-if="canRevoke(s)">
                <button
                  v-if="confirmId !== s.id"
                  class="sm-btn sm-btn--danger sm-btn--xs"
                  :disabled="revokingId === s.id"
                  @click="confirmId = s.id"
                >RÉVOQUER</button>
                <template v-else>
                  <span class="sm-confirm">Confirmer ?</span>
                  <button
                    class="sm-btn sm-btn--danger sm-btn--xs"
                    :disabled="revokingId === s.id"
                    @click="revoke(s)"
                  >OUI</button>
                  <button class="sm-btn sm-btn--ghost sm-btn--xs" @click="confirmId = null">NON</button>
                </template>
              </template>
              <span v-else class="sm-na">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ══ VUE JOURNALIÈRE CONSOLIDÉE ══════════════════════════════════════ -->
    <div v-else class="sm-table-wrap">
      <table class="sm-table">
        <thead>
          <tr>
            <th class="sm-th">UTILISATEUR</th>
            <th class="sm-th">RÔLE</th>
            <th class="sm-th">IP</th>
            <th class="sm-th">DATE</th>
            <th class="sm-th">CONNEXION</th>
            <th class="sm-th">DÉCONNEXION</th>
            <th class="sm-th">DURÉE</th>
            <th class="sm-th">PAUSE TOTALE</th>
            <th class="sm-th">PAUSE MOY.</th>
            <th class="sm-th">STATUT</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="loading">
            <tr v-for="n in 5" :key="`sk-${n}`" class="sm-row">
              <td v-for="c in 10" :key="c" class="sm-td"><span class="sm-skel"></span></td>
            </tr>
          </template>
          <tr v-else-if="dailyRows.length === 0" class="sm-row">
            <td colspan="10">
              <div class="sm-empty">
                <p class="sm-empty__title">Aucune donnée pour la période sélectionnée.</p>
                <p class="sm-empty__sub">Ajustez les filtres de date ou actualisez.</p>
              </div>
            </td>
          </tr>
          <tr v-for="r in dailyRows" :key="`${r.user_id}-${r.date}`" class="sm-row">
            <td class="sm-td">
              <div class="sm-user">
                <span class="sm-user__name">{{ r.full_name || r.username || "—" }}</span>
                <span class="sm-user__sub">@{{ r.username }}</span>
              </div>
            </td>
            <td class="sm-td"><span class="sm-role">{{ r.role || "—" }}</span></td>
            <td class="sm-td sm-mono">{{ r.ip_address || "—" }}</td>
            <td class="sm-td sm-mono">{{ formatDay(r.date) }}</td>
            <td class="sm-td sm-mono">{{ formatTime(r.first_connexion) }}</td>
            <td class="sm-td sm-mono">{{ r.last_deconnexion ? formatTime(r.last_deconnexion) : "—" }}</td>
            <td class="sm-td sm-mono">{{ formatMinutes(r.active_minutes) }}</td>
            <td class="sm-td sm-mono">{{ formatMinutes(r.pause_minutes_total) }}</td>
            <td class="sm-td sm-mono">{{ formatMinutes(r.pause_minutes_avg) }}</td>
            <td class="sm-td">
              <span :class="['sm-badge', `sm-badge--${r.statut}`]">
                <span class="sm-badge__dot"></span>{{ STATUT_LABELS[r.statut] ?? r.statut }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { sessionService } from "@/services/sessionService";
import { useAuthStore } from "@/store/auth";
import { countryFlag } from "@/utils/countryFlag";
import { downloadBlob } from "@/utils/downloadBlob";

const authStore = useAuthStore();

// ── State ──────────────────────────────────────────────────────────────────
const sessions = ref([]);
const dailyRows = ref([]);
const loading = ref(false);
const loadError = ref("");
const mode = ref("daily");         // "session" | "daily"
const scope = ref("live");         // session-mode only
const filterFrom = ref("");
const filterTo = ref("");
const confirmId = ref(null);
const revokingId = ref(null);

const MODES = [
  { key: "daily",   label: "PAR JOURNÉE" },
  { key: "session", label: "PAR SESSION" },
];
const SCOPES = [
  { key: "live", label: "ACTIVES" },
  { key: "all",  label: "TOUTES"  },
];
const STATUT_LABELS = {
  active:  "Active",
  paused:  "En pause",
  ended:   "Terminée",
  expired: "Expirée",
  revoked: "Révoquée",
};

const rowCount = computed(() =>
  mode.value === "daily" ? dailyRows.value.length : sessions.value.length,
);

// ── Data fetching ──────────────────────────────────────────────────────────
async function fetch() {
  loading.value = true;
  loadError.value = "";
  confirmId.value = null;
  try {
    if (mode.value === "daily") {
      const params = {};
      if (filterFrom.value) params.from = filterFrom.value;
      if (filterTo.value) params.to = filterTo.value;
      const { data } = await sessionService.getMonitoringDaily(params);
      dailyRows.value = data.rows ?? [];
    } else {
      const { data } = await sessionService.getMonitoring({ status: scope.value });
      sessions.value = data.sessions ?? [];
    }
  } catch (err) {
    loadError.value = err?.response?.data?.error || "Impossible de charger les sessions.";
  } finally {
    loading.value = false;
  }
}

async function exportCsv() {
  try {
    if (mode.value === "daily") {
      const params = {};
      if (filterFrom.value) params.from = filterFrom.value;
      if (filterTo.value) params.to = filterTo.value;
      const resp = await sessionService.exportMonitoringDailyCsv(params);
      downloadBlob(resp.data, `sessions_journalieres_${today()}.csv`);
    } else {
      const resp = await sessionService.exportMonitoringCsv({ status: scope.value });
      downloadBlob(resp.data, `sessions_${today()}.csv`);
    }
  } catch {
    loadError.value = "Échec de l'export CSV.";
  }
}

function today() {
  return new Date().toISOString().slice(0, 10).replace(/-/g, "");
}

// ── Actions ────────────────────────────────────────────────────────────────
async function revoke(s) {
  revokingId.value = s.id;
  try {
    await sessionService.revokeSession(s.id);
    confirmId.value = null;
    if (s.is_current) { await authStore.logout(); return; }
    await fetch();
  } catch (err) {
    loadError.value = err?.response?.data?.error || "Échec de la révocation.";
  } finally {
    revokingId.value = null;
  }
}

function setMode(k) {
  if (mode.value === k) return;
  mode.value = k;
  fetch();
}
function setScope(k) {
  if (scope.value === k) return;
  scope.value = k;
  fetch();
}
function canRevoke(s) {
  return ["active", "paused"].includes(s.status);
}

// ── Formatters ─────────────────────────────────────────────────────────────
function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return (
    d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" }) +
    " " +
    d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
  );
}
function formatDay(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}
function formatTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}
function formatMinutes(min) {
  if (min == null || Number.isNaN(min)) return "—";
  const total = Math.round(min);
  if (total === 0) return "0 min";
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h > 0 ? `${h}h${String(m).padStart(2, "0")}` : `${m} min`;
}
function formatRelative(iso) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(diff)) return "—";
  const min = Math.floor(diff / 60000);
  if (min < 1) return "à l'instant";
  if (min < 60) return `il y a ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `il y a ${h} h`;
  return `il y a ${Math.floor(h / 24)} j`;
}

onMounted(fetch);
</script>

<style scoped>
.sm-root {
  --teal: #00a8a8;
  --danger: #e74c3c;
  --authority: #000b23;
  --muted: #6b7280;
  --border: #e5e7eb;
  --ok: #22c55e;
  font-family: "Fira Sans", sans-serif;
}
.sm-mono {
  font-family: "Fira Code", monospace;
  font-size: 13px;
}
.sm-flag { margin-right: 4px; }

/* Toolbar */
.sm-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.sm-toolbar__title {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.sm-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--authority);
  margin: 0;
}
.sm-count {
  font-size: 15px;
  color: var(--muted);
}
.sm-toolbar__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.sm-seg {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
}
.sm-seg__btn {
  border: none;
  background: #fff;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--muted);
  cursor: pointer;
  white-space: nowrap;
}
.sm-seg__btn--on {
  background: var(--teal);
  color: #fff;
}

.sm-date {
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
  color: var(--authority);
  background: #fff;
  outline: none;
}
.sm-date:focus { border-color: var(--teal); }

/* Boutons */
.sm-btn {
  border: 1px solid transparent;
  border-radius: 4px;
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  cursor: pointer;
  padding: 6px 12px;
  white-space: nowrap;
}
.sm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.sm-btn--ghost {
  background: transparent;
  border-color: var(--border);
  color: var(--authority);
}
.sm-btn--ghost:not(:disabled):hover { background: #f7f7f8; }
.sm-btn--danger { background: var(--danger); color: #fff; }
.sm-btn--danger:not(:disabled):hover { filter: brightness(0.93); }
.sm-btn--xs { padding: 4px 9px; font-size: 12px; margin-left: 4px; }

.sm-spin {
  display: inline-block;
  animation: sm-rot 0.8s linear infinite;
}
@keyframes sm-rot { to { transform: rotate(360deg); } }

/* Bandeau */
.sm-banner {
  padding: 10px 14px;
  border-radius: 4px;
  font-size: 15px;
  margin-bottom: 12px;
}
.sm-banner--error {
  background: rgba(231, 76, 60, 0.08);
  border: 1px solid rgba(231, 76, 60, 0.3);
  color: #a93226;
}

/* Tableau */
.sm-table-wrap {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  overflow-x: auto;
}
.sm-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 860px;
}
.sm-th {
  text-align: left;
  padding: 11px 14px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  background: #fafafa;
}
.sm-th--right { text-align: right; }
.sm-row:hover { background: #f7f8fa; }
.sm-row--me { background: rgba(0, 168, 168, 0.04); }
.sm-td {
  padding: 10px 14px;
  font-size: 14px;
  color: #1a1a2e;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
  white-space: nowrap;
}
.sm-table tbody tr:last-child .sm-td { border-bottom: none; }
.sm-td--right { text-align: right; white-space: nowrap; }

.sm-user { display: flex; flex-direction: column; }
.sm-user__name { font-weight: 600; }
.sm-user__sub {
  font-size: 13px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 6px;
}
.sm-tag-me {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--teal);
  background: rgba(0, 168, 168, 0.1);
  padding: 1px 5px;
  border-radius: 3px;
}
.sm-role { font-size: 13px; font-weight: 600; color: var(--muted); }

.sm-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
}
.sm-badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--muted);
  flex-shrink: 0;
}
.sm-badge--active  { background: rgba(34, 197, 94, 0.12); color: #15803d; }
.sm-badge--active .sm-badge__dot { background: var(--ok); }
.sm-badge--paused  { background: rgba(243, 156, 18, 0.12); color: #b7770d; }
.sm-badge--paused .sm-badge__dot { background: #f39c12; }
.sm-badge--ended,
.sm-badge--expired { background: #f4f6f7; color: #707b7c; }
.sm-badge--revoked { background: rgba(231, 76, 60, 0.1); color: #a93226; }
.sm-badge--revoked .sm-badge__dot { background: var(--danger); }

.sm-confirm { font-size: 13px; font-weight: 600; color: #a93226; }
.sm-na { color: var(--muted); }

.sm-skel {
  display: block;
  height: 13px;
  border-radius: 4px;
  background: linear-gradient(90deg, #ececec 25%, #f4f4f4 37%, #ececec 63%);
  background-size: 400% 100%;
  animation: sm-shim 1.3s ease infinite;
}
@keyframes sm-shim {
  0%   { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}

.sm-empty { text-align: center; padding: 40px 16px; }
.sm-empty__title { font-size: 16px; font-weight: 600; color: var(--authority); margin: 0 0 4px; }
.sm-empty__sub { font-size: 14px; color: var(--muted); margin: 0; }
</style>
