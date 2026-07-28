<template>
  <section class="stl-root">
    <!-- KPI -->
    <div class="stl-kpi-row">
      <div class="stl-kpi-card">
        <div class="stl-kpi-card__top">
          <div class="stl-kpi-card__icon"><v-icon size="14" color="#00a8a8">mdi-phone-in-talk-outline</v-icon></div>
          <span class="stl-kpi-card__label">APPELS ({{ periodLabel }})</span>
        </div>
        <span class="stl-kpi-card__value">{{ summary?.total_calls ?? "—" }}</span>
        <span class="stl-kpi-card__hint">{{ answeredHint }}</span>
      </div>
      <div class="stl-kpi-card">
        <div class="stl-kpi-card__top">
          <div class="stl-kpi-card__icon"><v-icon size="14" color="#00a8a8">mdi-check-circle-outline</v-icon></div>
          <span class="stl-kpi-card__label">TAUX DE DÉCROCHÉ</span>
        </div>
        <span class="stl-kpi-card__value">{{ summary?.decroche_rate_pct != null ? summary.decroche_rate_pct + "%" : "—" }}</span>
        <span class="stl-kpi-card__hint">{{ missedHint }}</span>
      </div>
      <div class="stl-kpi-card">
        <div class="stl-kpi-card__top">
          <div class="stl-kpi-card__icon"><v-icon size="14" color="#00a8a8">mdi-timer-outline</v-icon></div>
          <span class="stl-kpi-card__label">TEMPS DE RÉPONSE MOYEN</span>
        </div>
        <span class="stl-kpi-card__value">{{ summary?.avg_response_seconds != null ? Math.round(summary.avg_response_seconds) + "s" : "—" }}</span>
        <span class="stl-kpi-card__hint">Sur appels décrochés</span>
      </div>
      <div class="stl-kpi-card">
        <div class="stl-kpi-card__top">
          <div class="stl-kpi-card__icon"><v-icon size="14" color="#00a8a8">mdi-account-group-outline</v-icon></div>
          <span class="stl-kpi-card__label">AGENTS EN LIGNE</span>
        </div>
        <span class="stl-kpi-card__value">{{ onlineAgentsCount }}</span>
        <span class="stl-kpi-card__hint">sur {{ agents.length }} rapportés</span>
      </div>
    </div>

    <!-- Appels en cours -->
    <div class="stl-panel">
      <div class="stl-panel__head">
        <span class="stl-pulse-dot" :class="{ 'stl-pulse-dot--paused': !socketConnected }"></span>
        <span class="stl-panel__title">APPELS EN COURS</span>
        <div class="stl-panel__spacer"></div>
        <span class="stl-live-badge" :class="{ 'stl-live-badge--off': !socketConnected }">
          <v-icon size="8">mdi-circle</v-icon>
          {{ socketConnected ? "TEMPS RÉEL" : "DÉCONNECTÉ" }}
        </span>
      </div>
      <table class="stl-table" v-if="activeCalls.length">
        <thead>
          <tr>
            <th>Appelant</th>
            <th>Agent</th>
            <th>File</th>
            <th>Statut</th>
            <th>Mise à jour</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in activeCalls" :key="c.call_uuid">
            <td class="stl-mono">{{ c.caller || "—" }}</td>
            <td>
              <div v-if="c.agent_login" class="stl-agent-cell">
                <span class="stl-avatar">{{ initials(c.agent_login) }}</span>{{ c.agent_login }}
              </div>
              <span v-else class="stl-muted">—</span>
            </td>
            <td class="stl-mono">{{ c.queue_id || "—" }}</td>
            <td>
              <span class="stl-status-badge" :class="`stl-status-${c.call_status}`">
                <span class="stl-dot"></span>{{ CALL_STATUS_LABEL[c.call_status] || c.call_status }}
              </span>
            </td>
            <td class="stl-mono stl-muted">{{ relativeTime(c.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="stl-empty-row">Aucun appel en cours.</div>
    </div>

    <!-- Files d'attente -->
    <div class="stl-panel">
      <div class="stl-panel__head">
        <span class="stl-panel__title">FILES D'ATTENTE</span>
      </div>
      <div v-if="queues.length" class="stl-queues-grid">
        <div v-for="q in queues" :key="q.queue_id" class="stl-queue-card">
          <div class="stl-queue-card__name">{{ q.queue_id }}</div>
          <div class="stl-queue-card__row"><span>Appels traités</span><span>{{ q.total_calls }}</span></div>
          <div class="stl-queue-card__row"><span>Attente moyenne</span><span>{{ q.avg_wait_seconds != null ? Math.round(q.avg_wait_seconds) + "s" : "—" }}</span></div>
          <div class="stl-queue-card__row" :class="{ 'stl-abandon-warn': q.abandon_rate_pct >= 15 }">
            <span>Taux d'abandon</span><span>{{ q.abandon_rate_pct }}%</span>
          </div>
        </div>
      </div>
      <div v-else class="stl-empty-row">Aucune donnée de file sur la période.</div>
    </div>

    <!-- Agents -->
    <div class="stl-panel">
      <div class="stl-panel__head">
        <span class="stl-panel__title">AGENTS</span>
        <div class="stl-panel__spacer"></div>
        <div class="stl-view-toggle">
          <button
            class="stl-view-toggle__btn"
            :class="{ 'stl-view-toggle__btn--active': agentsView === 'grid' }"
            title="Vue grille"
            @click="agentsView = 'grid'"
          >
            <v-icon size="14">mdi-view-grid-outline</v-icon>
          </button>
          <button
            class="stl-view-toggle__btn"
            :class="{ 'stl-view-toggle__btn--active': agentsView === 'list' }"
            title="Vue liste"
            @click="agentsView = 'list'"
          >
            <v-icon size="14">mdi-view-sequential-outline</v-icon>
          </button>
        </div>
      </div>

      <div v-if="agents.length" class="stl-agents-grid" :class="{ 'stl-agents-grid--list': agentsView === 'list' }">
        <div v-for="a in agents" :key="a.agent_login" class="stl-agent-card">
          <div class="stl-agent-card__avatar-wrap">
            <span class="stl-agent-card__avatar">{{ initials(a.agent_login) }}</span>
            <span class="stl-agent-card__status-dot" :class="`stl-status-${a.presence}`"></span>
          </div>
          <span class="stl-agent-card__name">{{ a.agent_login }}</span>
          <span class="stl-agent-card__presence" :class="`stl-presence-${a.presence}`">
            <span class="stl-dot" :class="`stl-status-${a.presence}`"></span>{{ PRESENCE_LABEL[a.presence] }}
          </span>
          <span class="stl-agent-card__queue">{{ formatLastSeen(a.last_seen_at) }}</span>
          <div
            class="stl-agent-card__bar-wrap"
            :title="`Appels traités (${periodLabel}), relatif à l'agent le plus sollicité (${maxCallsHandled})`"
          >
            <span class="stl-agent-card__bar-track">
              <span class="stl-agent-card__bar-fill" :style="{ width: workloadPct(a) + '%' }"></span>
            </span>
            <span class="stl-agent-card__bar-value">{{ a.calls_handled }}</span>
          </div>
        </div>
      </div>
      <div v-else class="stl-empty-row">
        Aucun agent n'a encore rapporté son état auprès du PBX.
      </div>

      <div v-if="agents.length" class="stl-agents-legend">
        <span class="stl-legend-item"><span class="stl-dot stl-status-online"></span>Disponible</span>
        <span class="stl-legend-item"><span class="stl-dot stl-status-away"></span>En pause</span>
        <span class="stl-legend-item"><span class="stl-dot stl-status-offline"></span>Déconnecté</span>
        <span class="stl-panel__spacer"></span>
        <span class="stl-muted">{{ onlineAgentsCount }} sur {{ agents.length }} agents en ligne</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from "vue";
import { telephonyService } from "@/services/telephonyService";
import { useTelephonySocket } from "@/composables/useTelephonySocket";

const TERMINAL_STATUSES = new Set(["ended", "missed", "abandoned", "technical_failure"]);
const CALL_STATUS_LABEL = {
  ringing: "Sonnerie",
  early_media: "Pré-décroché",
  answered: "En cours",
  on_hold: "En attente",
};
const PRESENCE_LABEL = { online: "Disponible", away: "En pause", offline: "Déconnecté" };

const periodLabel = "aujourd'hui";
const summary = ref(null);
const queues = ref([]);
const agents = ref([]);
const activeCallsMap = reactive(new Map()); // call_uuid -> call dict, ordre d'insertion préservé
const activeCalls = computed(() => Array.from(activeCallsMap.values()));
const agentsView = ref("grid");

const answeredHint = computed(() => {
  if (!summary.value) return "";
  return `${summary.value.answered_calls} décrochés`;
});
const missedHint = computed(() => {
  if (!summary.value || !summary.value.total_calls) return "";
  const missed = summary.value.total_calls - summary.value.answered_calls;
  return missed > 0 ? `${missed} appels manqués/abandonnés` : "Aucun appel manqué";
});
const onlineAgentsCount = computed(() => agents.value.length ? agents.value.filter((a) => a.presence === "online").length : 0);
const maxCallsHandled = computed(() => Math.max(1, ...agents.value.map((a) => a.calls_handled)));

function workloadPct(agent) {
  if (agent.presence === "offline" && agent.calls_handled === 0) return 0;
  return Math.round((agent.calls_handled / maxCallsHandled.value) * 100);
}
function initials(login) {
  const parts = (login || "?").split(/[.\s_-]/).filter(Boolean);
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : login.slice(0, 2)).toUpperCase();
}
function relativeTime(iso) {
  if (!iso) return "—";
  const diffSec = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (diffSec < 60) return `il y a ${diffSec}s`;
  const min = Math.floor(diffSec / 60);
  return `il y a ${min} min`;
}
function formatLastSeen(iso) {
  if (!iso) return "—";
  return `vu ${relativeTime(iso)}`;
}

// ── Chargement ──────────────────────────────────────────────────────────
async function loadSummary() {
  try {
    const { data } = await telephonyService.getKpisSummary();
    summary.value = data;
  } catch {
    summary.value = null;
  }
}
async function loadQueues() {
  try {
    const { data } = await telephonyService.getKpisQueues();
    queues.value = data.queues || [];
  } catch {
    queues.value = [];
  }
}
async function loadAgents() {
  try {
    const { data } = await telephonyService.getAgentsStatus();
    agents.value = data.agents || [];
  } catch {
    agents.value = [];
  }
}
async function loadActiveCalls() {
  try {
    const { data } = await telephonyService.getActiveCalls();
    activeCallsMap.clear();
    for (const c of data.active_calls || []) activeCallsMap.set(c.call_uuid, c);
  } catch {
    activeCallsMap.clear();
  }
}

let refreshTimer = null;
function startPolling() {
  refreshTimer = setInterval(() => {
    loadSummary();
    loadQueues();
    loadAgents();
  }, 30000);
}

// ── Temps réel : appels (upsert/suppression par call_uuid) ────────────────
const telephonySocket = useTelephonySocket();
const socketConnected = telephonySocket.connected;
let lastProcessedIdx = 0;

function processIncomingEvents() {
  const evs = telephonySocket.events.value;
  for (; lastProcessedIdx < evs.length; lastProcessedIdx++) {
    const e = evs[lastProcessedIdx];
    if (!e.call_uuid) continue;
    if (TERMINAL_STATUSES.has(e.call_status)) {
      activeCallsMap.delete(e.call_uuid);
    } else if (e.call_status) {
      activeCallsMap.set(e.call_uuid, e);
    }
  }
}
let eventsWatcherTimer = null;

onMounted(() => {
  loadSummary();
  loadQueues();
  loadAgents();
  loadActiveCalls();
  startPolling();
  telephonySocket.connect();
  eventsWatcherTimer = setInterval(processIncomingEvents, 1000);
});
onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer);
  if (eventsWatcherTimer) clearInterval(eventsWatcherTimer);
  telephonySocket.disconnect();
});
</script>

<style scoped>
.stl-root { display: flex; flex-direction: column; gap: 16px; font-family: "Fira Sans", sans-serif; }
.stl-muted { color: #9aa0aa; }
.stl-mono { font-family: "Fira Code", ui-monospace, monospace; font-size: 12.5px; }

.stl-kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.stl-kpi-card {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 6px;
}
.stl-kpi-card__top { display: flex; align-items: center; gap: 7px; }
.stl-kpi-card__icon {
  width: 26px; height: 26px; border-radius: 6px; display: flex; align-items: center;
  justify-content: center; background: rgba(0, 168, 168, 0.1); flex-shrink: 0;
}
.stl-kpi-card__label { font-size: 10.5px; font-weight: 700; letter-spacing: 0.04em; color: #9aa0aa; }
.stl-kpi-card__value { font-size: 24px; font-weight: 700; color: #000b23; font-variant-numeric: tabular-nums; }
.stl-kpi-card__hint { font-size: 10.5px; color: #6b7280; }

.stl-panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }
.stl-panel__head { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-bottom: 1px solid #e5e7eb; }
.stl-panel__title { font-size: 12px; font-weight: 700; letter-spacing: 0.04em; color: #1a1a2e; }
.stl-panel__spacer { flex: 1; }

.stl-pulse-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34,197,94,0.6); animation: stl-pulse 1.8s infinite;
}
.stl-pulse-dot--paused { background: #9aa0aa; animation: none; }
@keyframes stl-pulse {
  0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.55); }
  70% { box-shadow: 0 0 0 6px rgba(34,197,94,0); }
  100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}
.stl-live-badge {
  display: inline-flex; align-items: center; gap: 5px; font-size: 10px; font-weight: 700;
  letter-spacing: 0.04em; color: #15803d; background: rgba(34,197,94,0.12);
  padding: 3px 8px; border-radius: 12px;
}
.stl-live-badge--off { color: #6b7280; background: #eef0f3; }

.stl-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.stl-table thead th {
  text-align: left; font-size: 9.5px; font-weight: 700; letter-spacing: 0.05em; color: #9aa0aa;
  padding: 8px 16px; border-bottom: 1px solid #e5e7eb; white-space: nowrap;
}
.stl-table tbody tr { border-bottom: 1px solid #eceef1; }
.stl-table tbody tr:last-child { border-bottom: none; }
.stl-table td { padding: 8px 16px; vertical-align: middle; }
.stl-agent-cell { display: flex; align-items: center; gap: 8px; }
.stl-avatar {
  width: 22px; height: 22px; border-radius: 50%; background: #00a8a8; color: #fff;
  font-size: 9.5px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.stl-status-badge {
  display: inline-flex; align-items: center; gap: 5px; font-size: 10px; font-weight: 700;
  padding: 3px 8px; border-radius: 4px;
}
.stl-status-badge .stl-dot { width: 6px; height: 6px; border-radius: 50%; }
.stl-status-ringing { background: rgba(245,158,11,0.14); color: #b45309; }
.stl-status-ringing .stl-dot { background: #f59e0b; }
.stl-status-early_media { background: rgba(14,165,233,0.14); color: #0369a1; }
.stl-status-early_media .stl-dot { background: #0ea5e9; }
.stl-status-answered { background: rgba(34,197,94,0.12); color: #15803d; }
.stl-status-answered .stl-dot { background: #22c55e; }
.stl-status-on_hold { background: #eef0f3; color: #6b7280; }
.stl-status-on_hold .stl-dot { background: #9aa0aa; }
.stl-empty-row { text-align: center; padding: 28px 16px; color: #9aa0aa; font-size: 12px; }

.stl-queues-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0; }
.stl-queue-card { padding: 14px 16px; border-right: 1px solid #e5e7eb; }
.stl-queue-card:last-child { border-right: none; }
.stl-queue-card__name { font-size: 12px; font-weight: 700; color: #1a1a2e; margin-bottom: 8px; }
.stl-queue-card__row { display: flex; justify-content: space-between; font-size: 11.5px; margin-bottom: 4px; color: #6b7280; }
.stl-queue-card__row span:last-child { font-family: "Fira Code", monospace; font-weight: 600; color: #1a1a2e; }
.stl-abandon-warn span { color: #e74c3c !important; }

.stl-view-toggle { display: flex; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; }
.stl-view-toggle__btn {
  width: 28px; height: 26px; display: flex; align-items: center; justify-content: center;
  background: #fff; color: #9aa0aa; border: none; cursor: pointer;
}
.stl-view-toggle__btn:first-child { border-right: 1px solid #e5e7eb; }
.stl-view-toggle__btn--active { background: rgba(0,168,168,0.1); color: #00a8a8; }

.stl-agents-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; padding: 16px; }
.stl-agents-grid--list { grid-template-columns: 1fr; }
.stl-agent-card {
  border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px;
  display: flex; flex-direction: column; align-items: center; gap: 4px; text-align: center;
  background: #fafafa;
}
.stl-agents-grid--list .stl-agent-card { flex-direction: row; text-align: left; gap: 12px; padding: 10px 14px; }
.stl-agents-grid--list .stl-agent-card__avatar-wrap { margin-bottom: 0; }
.stl-agents-grid--list .stl-agent-card__name { flex: 0 0 110px; }
.stl-agents-grid--list .stl-agent-card__presence { flex: 0 0 100px; }
.stl-agents-grid--list .stl-agent-card__queue { flex: 0 0 140px; margin-bottom: 0; }
.stl-agents-grid--list .stl-agent-card__bar-wrap { width: auto; flex: 1; }

.stl-agent-card__avatar-wrap { position: relative; margin-bottom: 6px; }
.stl-agent-card__avatar {
  width: 46px; height: 46px; border-radius: 50%; background: #00a8a8; color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700;
}
.stl-agent-card__status-dot {
  position: absolute; bottom: 1px; right: 1px; width: 11px; height: 11px; border-radius: 50%;
  border: 2px solid #fafafa;
}
.stl-agent-card__name { font-size: 13px; font-weight: 700; color: #1a1a2e; }
.stl-agent-card__presence { font-size: 10.5px; font-weight: 600; display: flex; align-items: center; gap: 4px; }
.stl-agent-card__queue { font-size: 10px; color: #9aa0aa; margin-bottom: 4px; }
.stl-agent-card__bar-wrap { width: 100%; display: flex; align-items: center; gap: 6px; font-size: 10px; color: #9aa0aa; }
.stl-agent-card__bar-track { flex: 1; height: 5px; border-radius: 3px; background: #e5e7eb; overflow: hidden; }
.stl-agent-card__bar-fill { height: 100%; border-radius: 3px; background: #00a8a8; }
.stl-agent-card__bar-value { font-family: "Fira Code", monospace; font-weight: 600; }

.stl-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; }
.stl-status-online { background: #22c55e; }
.stl-status-away { background: #f59e0b; }
.stl-status-offline { background: #9aa0aa; }
.stl-presence-online { color: #15803d; }
.stl-presence-away { color: #b45309; }
.stl-presence-offline { color: #6b7280; }

.stl-agents-legend {
  display: flex; align-items: center; gap: 16px; padding: 10px 16px;
  border-top: 1px solid #e5e7eb; font-size: 11px; color: #6b7280;
}
.stl-legend-item { display: flex; align-items: center; gap: 5px; }
</style>
