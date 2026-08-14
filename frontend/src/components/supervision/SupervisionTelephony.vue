<template>
  <section class="stl-root">
    <!-- KPI -->
    <div class="stl-kpi-row">
      <div class="stl-kpi-card">
        <div class="stl-kpi-card__top">
          <div class="stl-kpi-card__icon">
            <v-icon size="14" color="#00a8a8">mdi-phone-in-talk-outline</v-icon>
          </div>
          <span class="stl-kpi-card__label">APPELS ({{ periodLabel }})</span>
        </div>
        <span class="stl-kpi-card__value">{{
          summary?.total_calls ?? "—"
        }}</span>
        <span class="stl-kpi-card__hint">{{ answeredHint }}</span>
      </div>
      <div class="stl-kpi-card">
        <div class="stl-kpi-card__top">
          <div class="stl-kpi-card__icon">
            <v-icon size="14" color="#00a8a8">mdi-check-circle-outline</v-icon>
          </div>
          <span class="stl-kpi-card__label">TAUX DE DÉCROCHÉ</span>
        </div>
        <span class="stl-kpi-card__value">{{
          summary?.decroche_rate_pct != null
            ? summary.decroche_rate_pct + "%"
            : "—"
        }}</span>
        <span class="stl-kpi-card__hint">{{ missedHint }}</span>
      </div>
      <div class="stl-kpi-card">
        <div class="stl-kpi-card__top">
          <div class="stl-kpi-card__icon">
            <v-icon size="14" color="#00a8a8">mdi-timer-outline</v-icon>
          </div>
          <span class="stl-kpi-card__label">TEMPS DE RÉPONSE MOYEN</span>
        </div>
        <span class="stl-kpi-card__value">{{
          summary?.avg_response_seconds != null
            ? Math.round(summary.avg_response_seconds) + "s"
            : "—"
        }}</span>
        <span class="stl-kpi-card__hint">Sur appels décrochés</span>
      </div>
      <div class="stl-kpi-card">
        <div class="stl-kpi-card__top">
          <div class="stl-kpi-card__icon">
            <v-icon size="14" color="#00a8a8">mdi-account-group-outline</v-icon>
          </div>
          <span class="stl-kpi-card__label">AGENTS EN LIGNE</span>
        </div>
        <span class="stl-kpi-card__value">{{ onlineAgentsCount }}</span>
        <span class="stl-kpi-card__hint"
          >sur {{ agents.length }} rapportés</span
        >
      </div>
    </div>

    <!-- Appels en cours -->
    <div class="stl-panel">
      <div class="stl-panel__head">
        <span
          class="stl-pulse-dot"
          :class="{ 'stl-pulse-dot--paused': !socketConnected }"
        ></span>
        <span class="stl-panel__title">APPELS EN COURS</span>
        <div class="stl-panel__spacer"></div>
        <span
          class="stl-live-badge"
          :class="{ 'stl-live-badge--off': !socketConnected }"
        >
          <v-icon size="8">mdi-circle</v-icon>
          {{ socketConnected ? "TEMPS RÉEL" : "DÉCONNECTÉ" }}
        </span>
      </div>
      <table class="stl-table" v-if="activeCalls.length">
        <thead>
          <tr>
            <th>Agent</th>
            <th>Appelant</th>
            <th>Destination</th>
            <th>Queue</th>
            <th>Statut</th>
            <th>Durée</th>
          </tr>
        </thead>
        <transition-group name="stl-row" tag="tbody">
          <tr v-for="c in activeCalls" :key="c.call_uuid">
            <td>
              <div
                v-if="c.agent_name || c.agent_login"
                class="stl-agent-cell"
                :title="
                  c.agent_inferred
                    ? 'Agent déduit du dernier poste connu (pas de contexte file sur cet appel)'
                    : null
                "
              >
                <span
                  class="stl-avatar"
                  :class="{ 'stl-avatar--inferred': c.agent_inferred }"
                  >{{ initials(c.agent_name || c.agent_login) }}</span
                >
                <div class="stl-call-text">
                  <div class="stl-call-title">
                    {{ c.agent_name || c.agent_login
                    }}<span v-if="c.agent_inferred" class="stl-call-sub">
                      (déduit)</span
                    >
                  </div>
                  <div v-if="c.agent_station" class="stl-call-sub stl-mono">
                    Poste {{ c.agent_station }}
                  </div>
                </div>
              </div>
              <span v-else class="stl-muted">—</span>
            </td>
            <td class="stl-mono">{{ c.caller || "—" }}</td>
            <td class="stl-mono">{{ c.callee || "—" }}</td>
            <td>
              <span v-if="c.queue_label" class="stl-mono">{{
                c.queue_label
              }}</span>
              <span v-else class="stl-muted">—</span>
            </td>
            <td>
              <span
                class="stl-status-badge"
                :class="`stl-status-${c.call_status}`"
              >
                <span class="stl-dot"></span
                >{{ CALL_STATUS_LABEL[c.call_status] || c.call_status }}
              </span>
            </td>
            <td>
              <div class="stl-mono">{{ formatDuration(c.started_at) }}</div>
              <div class="stl-call-sub">
                mis à jour {{ relativeTime(c.created_at) }}
              </div>
            </td>
          </tr>
        </transition-group>
      </table>
      <div v-else class="stl-empty-row">Aucun appel en cours.</div>
    </div>

    <!-- Files d'attente (uniquement celles avec activité, triées par volume décroissant) -->
    <div class="stl-panel">
      <div class="stl-panel__head">
        <span class="stl-panel__title">FILES D'ATTENTE</span>
        <div class="stl-panel__spacer"></div>
        <span class="stl-queue-count"
          >{{ queues.length }} active{{ queues.length > 1 ? "s" : "" }}</span
        >
      </div>
      <div v-if="queues.length" class="stl-queue-filter-row">
        <v-text-field
          v-model="queueFilter"
          placeholder="Filtrer par nom de file ou identifiant PBX…"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          prepend-inner-icon="mdi-magnify"
        />
      </div>
      <div v-if="queues.length">
        <transition-group name="stl-card" tag="div" class="stl-queue-list">
          <div
            v-for="q in filteredQueues"
            :key="q.queue_id"
            class="stl-queue-card"
          >
            <div class="stl-queue-card__top">
              <div class="stl-queue-card__id-block">
                <span class="stl-queue-card__swatch">{{
                  initials(q.alias)
                }}</span>
                <div>
                  <div class="stl-queue-card__alias">{{ q.alias }}</div>
                  <div class="stl-queue-card__raw-id">{{ q.queue_id }}</div>
                </div>
              </div>
              <span
                class="stl-queue-badge"
                :class="`stl-queue-badge--${abandonSeverity(q.abandon_rate_pct)}`"
              >
                <span class="stl-dot"></span>{{ q.abandon_rate_pct }}% abandon
              </span>
            </div>
            <div class="stl-queue-card__stats">
              <div class="stl-queue-stat">
                <span class="stl-queue-stat__label">Appels traités</span>
                <span class="stl-queue-stat__value">{{ q.total_calls }}</span>
              </div>
              <div class="stl-queue-stat">
                <span class="stl-queue-stat__label">Attente moyenne</span>
                <span class="stl-queue-stat__value">{{
                  q.avg_wait_seconds != null
                    ? Math.round(q.avg_wait_seconds) + "s"
                    : "—"
                }}</span>
              </div>
              <div class="stl-queue-stat">
                <span class="stl-queue-stat__label">Taux d'abandon</span>
                <span
                  class="stl-queue-stat__value"
                  :class="{ 'stl-abandon-warn': q.abandon_rate_pct >= 15 }"
                  >{{ q.abandon_rate_pct }}%</span
                >
              </div>
            </div>
            <details class="stl-queue-details">
              <summary>
                <v-icon size="14" class="stl-queue-details__chevron"
                  >mdi-chevron-right</v-icon
                >Détails
              </summary>
              <div class="stl-queue-details__body">
                <div class="stl-queue-gauge">
                  <div class="stl-queue-gauge__label">
                    <span>Taux d'abandon</span
                    ><span class="stl-mono">{{ q.abandon_rate_pct }}%</span>
                  </div>
                  <div class="stl-queue-gauge__track">
                    <div
                      class="stl-queue-gauge__fill"
                      :class="`stl-queue-gauge__fill--${abandonSeverity(q.abandon_rate_pct)}`"
                      :style="{
                        width: Math.min(q.abandon_rate_pct, 100) + '%',
                      }"
                    ></div>
                    <div
                      class="stl-queue-gauge__threshold"
                      style="left: 15%"
                    ></div>
                  </div>
                </div>
                <div class="stl-queue-breakdown">
                  <div class="stl-queue-breakdown__item">
                    <span class="stl-queue-breakdown__label">Décrochés</span>
                    <span
                      class="stl-queue-breakdown__value stl-queue-breakdown__value--good"
                    >
                      {{ q.total_calls - q.abandoned_calls }}
                    </span>
                  </div>
                  <div class="stl-queue-breakdown__item">
                    <span class="stl-queue-breakdown__label">Abandonnés</span>
                    <span
                      class="stl-queue-breakdown__value stl-queue-breakdown__value--bad"
                      >{{ q.abandoned_calls }}</span
                    >
                  </div>
                </div>
              </div>
            </details>
          </div>
        </transition-group>
        <div v-if="!filteredQueues.length" class="stl-empty-row">
          Aucune file ne correspond au filtre.
        </div>
      </div>
      <div v-else class="stl-empty-row">
        Aucune file d'attente active sur la période.
      </div>
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

      <transition-group
        v-if="agents.length"
        name="stl-card"
        tag="div"
        class="stl-agents-grid"
        :class="{ 'stl-agents-grid--list': agentsView === 'list' }"
      >
        <div v-for="a in agents" :key="a.agent_login" class="stl-agent-card">
          <div class="stl-agent-card__avatar-wrap">
            <span class="stl-agent-card__avatar">{{
              initials(a.agent_name || a.agent_login)
            }}</span>
            <span
              class="stl-agent-card__status-dot"
              :class="`stl-status-${a.presence}`"
            ></span>
          </div>
          <span class="stl-agent-card__name">{{
            a.agent_name || a.agent_login
          }}</span>
          <span
            class="stl-agent-card__presence"
            :class="`stl-presence-${a.presence}`"
          >
            <span class="stl-dot" :class="`stl-status-${a.presence}`"></span
            >{{ PRESENCE_LABEL[a.presence] }}
            <v-icon
              v-if="a.presence_inferred"
              size="11"
              class="stl-agent-card__inferred-icon"
              title="Statut estimé à partir d'un appel traité — aucun statut manuel (Disponible/Pause) n'a encore été reçu pour cet agent."
              >mdi-help-circle-outline</v-icon
            >
          </span>
          <span v-if="a.agent_station" class="stl-agent-card__queue"
            >Poste {{ a.agent_station }}</span
          >
          <span class="stl-agent-card__queue">{{
            formatLastSeen(a.last_seen_at)
          }}</span>
          <div
            class="stl-agent-card__bar-wrap"
            :title="`Appels traités (${periodLabel}), relatif à l'agent le plus sollicité (${maxCallsHandled})`"
          >
            <span class="stl-agent-card__bar-track">
              <span
                class="stl-agent-card__bar-fill"
                :style="{ width: workloadPct(a) + '%' }"
              ></span>
            </span>
            <span class="stl-agent-card__bar-value">{{ a.calls_handled }}</span>
          </div>
        </div>
      </transition-group>
      <div v-else class="stl-empty-row">
        Aucun agent n'a encore rapporté son état auprès du PBX.
      </div>

      <div v-if="agents.length" class="stl-agents-legend">
        <span class="stl-legend-item"
          ><span class="stl-dot stl-status-online"></span>Disponible</span
        >
        <span class="stl-legend-item"
          ><span class="stl-dot stl-status-on_call"></span>En appel</span
        >
        <span class="stl-legend-item"
          ><span class="stl-dot stl-status-away"></span>En pause</span
        >
        <span class="stl-legend-item"
          ><span class="stl-dot stl-status-offline"></span>Déconnecté</span
        >
        <span class="stl-panel__spacer"></span>
        <span class="stl-muted"
          >{{ onlineAgentsCount }} sur {{ agents.length }} agents en ligne</span
        >
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from "vue";
import { telephonyService } from "@/services/telephonyService";
import { useTelephonySocket } from "@/composables/useTelephonySocket";

const TERMINAL_STATUSES = new Set([
  "ended",
  "missed",
  "abandoned",
  "technical_failure",
]);
const CALL_STATUS_LABEL = {
  ringing: "Sonnerie",
  early_media: "Pré-décroché",
  answered: "En cours",
  on_hold: "En attente",
};
const PRESENCE_LABEL = {
  online: "Disponible",
  on_call: "En appel",
  away: "En pause",
  offline: "Déconnecté",
};
// Types d'événement affectant la présence agent (même liste que
// _PRESENCE_SIGNAL_EVENT_TYPES côté backend, cf. telephony.py, + le
// CUSTOM esl_adapter::agent_pause_code du 13/08) — ne portent jamais de
// call_uuid, donc jamais traités par la fusion des appels ci-dessous.
// Sans ce chemin dédié, un changement de statut agent (y compris via le
// bouton self-service) ne se reflétait qu'au prochain sondage périodique
// (jusqu'à 30s de retard) au lieu d'être immédiat comme les appels.
const AGENT_PRESENCE_EVENT_TYPES = new Set([
  "CALLCENTER_AGENT_STATE_CHANGE",
  "CALLCENTER_MEMBER_ENRICHMENT",
  "CALLCENTER_BRIDGE_RECORDING",
  "CALLCENTER_AGENT_PAUSE_CODE",
]);

const periodLabel = "aujourd'hui";
const summary = ref(null);
const queues = ref([]);
const queueFilter = ref("");
const filteredQueues = computed(() => {
  const term = (queueFilter.value || "").trim().toLowerCase();
  if (!term) return queues.value;
  return queues.value.filter(
    (q) =>
      (q.alias || "").toLowerCase().includes(term) ||
      (q.queue_id || "").toLowerCase().includes(term),
  );
});
function abandonSeverity(pct) {
  if (pct >= 15) return "bad";
  if (pct >= 10) return "warn";
  return "good";
}
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
  return missed > 0
    ? `${missed} appels manqués/abandonnés`
    : "Aucun appel manqué";
});
const onlineAgentsCount = computed(() =>
  agents.value.length
    ? agents.value.filter(
        (a) => a.presence === "online" || a.presence === "on_call",
      ).length
    : 0,
);
const maxCallsHandled = computed(() =>
  Math.max(1, ...agents.value.map((a) => a.calls_handled)),
);

function workloadPct(agent) {
  if (agent.presence === "offline" && agent.calls_handled === 0) return 0;
  return Math.round((agent.calls_handled / maxCallsHandled.value) * 100);
}
function initials(login) {
  const parts = (login || "?").split(/[.\s_-]/).filter(Boolean);
  return (
    parts.length > 1 ? parts[0][0] + parts[1][0] : login.slice(0, 2)
  ).toUpperCase();
}
function relativeTime(iso) {
  if (!iso) return "—";
  const diffSec = Math.max(
    0,
    Math.floor((Date.now() - new Date(iso).getTime()) / 1000),
  );
  if (diffSec < 60) return `il y a ${diffSec}s`;
  const min = Math.floor(diffSec / 60);
  return `il y a ${min} min`;
}
function formatLastSeen(iso) {
  if (!iso) return "—";
  return `vu ${relativeTime(iso)}`;
}

// Horloge de rafraîchissement pour la colonne Durée (tick chaque seconde,
// simple compteur consommé par formatDuration ci-dessous pour forcer le
// recalcul — la durée elle-même dérive toujours de started_at, pas d'un
// état stocké séparément).
const durationTick = ref(0);
let durationTimer = null;
function formatDuration(startedAtIso) {
  void durationTick.value; // dépendance réactive volontaire
  if (!startedAtIso) return "—";
  const elapsed = Math.max(
    0,
    Math.floor((Date.now() - new Date(startedAtIso).getTime()) / 1000),
  );
  const h = String(Math.floor(elapsed / 3600)).padStart(2, "0");
  const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0");
  const s = String(elapsed % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
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
    // Recharge périodiquement l'état complet backend-résolu (agent_name/
    // agent_station/queue_label) : sans ça, un appel arrivé uniquement via
    // socket depuis le dernier chargement complet reste bloqué sur ses
    // valeurs brutes (uuid CC-Agent, id de file nu) indéfiniment.
    loadActiveCalls();
  }, 30000);
}

// ── Temps réel : appels (upsert/suppression par call_uuid) ────────────────
const telephonySocket = useTelephonySocket();
const socketConnected = telephonySocket.connected;
let lastProcessedIdx = 0;

// Debounce court : un seul job self-service (ex. agent_login) peut
// produire coup sur coup un CALLCENTER_AGENT_STATE_CHANGE ET un
// CALLCENTER_AGENT_PAUSE_CODE — on ne veut qu'un seul rafraîchissement,
// pas un par événement.
let agentsRefreshTimer = null;
function scheduleAgentsRefresh() {
  if (agentsRefreshTimer) return;
  agentsRefreshTimer = setTimeout(() => {
    agentsRefreshTimer = null;
    loadAgents();
  }, 300);
}

function processIncomingEvents() {
  const evs = telephonySocket.events.value;
  for (; lastProcessedIdx < evs.length; lastProcessedIdx++) {
    const e = evs[lastProcessedIdx];
    if (AGENT_PRESENCE_EVENT_TYPES.has(e.event_type)) scheduleAgentsRefresh();
    if (!e.call_uuid) continue;
    if (TERMINAL_STATUSES.has(e.call_status)) {
      activeCallsMap.delete(e.call_uuid);
      continue;
    }
    // Fusion par coalescence : un événement d'enrichissement (ex.
    // CALLCENTER_MEMBER_ENRICHMENT — agent-offering) n'apporte que
    // l'agent/la file/le vrai numéro composé, sans statut ni appelant — ne
    // doit jamais écraser un état déjà connu avec du vide.
    const existing = activeCallsMap.get(e.call_uuid);
    if (!existing && !e.call_status) continue; // pas assez d'info pour créer une ligne
    const agentLogin = e.agent_login || existing?.agent_login || null;
    // Un événement brut poussé par le socket ne porte que l'uuid CC-Agent
    // (event.to_dict(), pas d'alias résolu) — /active-calls, elle, résout
    // agent_name/agent_station côté backend. On complète donc via
    // l'annuaire /agents/status déjà chargé côté client (rafraîchi toutes
    // les 30s), pour qu'un appel arrivé UNIQUEMENT par socket depuis le
    // dernier chargement complet affiche quand même un nom lisible.
    const agentAlias = agentLogin
      ? agents.value.find((a) => a.agent_login === agentLogin)
      : null;
    const queueId = e.queue_id || existing?.queue_id || null;
    const merged = {
      call_uuid: e.call_uuid,
      call_direction: e.call_direction || existing?.call_direction || null,
      call_status: e.call_status || existing?.call_status || null,
      caller: e.caller || existing?.caller || null,
      callee: e.callee || existing?.callee || null,
      agent_login: agentLogin,
      agent_name: agentAlias?.agent_name || existing?.agent_name || agentLogin,
      agent_station:
        agentAlias?.agent_station || existing?.agent_station || null,
      queue_id: queueId,
      // /active-calls résout "Alias (id)" côté backend (_format_queue_label) ;
      // un événement brut poussé par le socket ne porte que l'id nu — on
      // réutilise l'étiquette déjà résolue si connue (chargement complet
      // précédent), sinon on affiche l'id nu en attendant le prochain
      // rafraîchissement périodique de loadActiveCalls().
      queue_label:
        existing?.queue_label || (queueId ? queueId.split("@")[0] : null),
      linked_call_uuid:
        e.linked_call_uuid || existing?.linked_call_uuid || null,
      started_at: existing?.started_at || e.created_at || null,
      created_at: e.created_at || existing?.created_at || null,
    };
    // Fusion des legs bridgés — même règle que côté backend (/active-calls) :
    // Other-Leg-Unique-ID n'est fiable qu'une fois le pont établi, on ne
    // garde que le leg "inbound" (numéro humainement lisible).
    if (
      merged.linked_call_uuid &&
      merged.call_direction === "outbound" &&
      activeCallsMap.has(merged.linked_call_uuid)
    ) {
      activeCallsMap.delete(e.call_uuid);
      continue;
    }
    activeCallsMap.set(e.call_uuid, merged);
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
  durationTimer = setInterval(() => {
    durationTick.value++;
  }, 1000);
});
onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer);
  if (eventsWatcherTimer) clearInterval(eventsWatcherTimer);
  if (durationTimer) clearInterval(durationTimer);
  if (agentsRefreshTimer) clearTimeout(agentsRefreshTimer);
  telephonySocket.disconnect();
});
</script>

<style scoped>
.stl-root {
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-family: "Fira Sans", sans-serif;
}
.stl-muted {
  color: #9aa0aa;
}
.stl-mono {
  font-family: "Fira Code", ui-monospace, monospace;
  font-size: 12.5px;
}

.stl-kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.stl-kpi-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stl-kpi-card__top {
  display: flex;
  align-items: center;
  gap: 7px;
}
.stl-kpi-card__icon {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 168, 168, 0.1);
  flex-shrink: 0;
}
.stl-kpi-card__label {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #9aa0aa;
}
.stl-kpi-card__value {
  font-size: 26px;
  font-weight: 700;
  color: #000b23;
  font-variant-numeric: tabular-nums;
}
.stl-kpi-card__hint {
  font-size: 10.5px;
  color: #6b7280;
}

.stl-panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.stl-panel__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
}
.stl-panel__title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #1a1a2e;
}
.stl-panel__spacer {
  flex: 1;
}

.stl-pulse-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.6);
  animation: stl-pulse 1.8s infinite;
}
.stl-pulse-dot--paused {
  background: #9aa0aa;
  animation: none;
}
@keyframes stl-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.55);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(34, 197, 94, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0);
  }
}
.stl-live-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #15803d;
  background: rgba(34, 197, 94, 0.12);
  padding: 3px 8px;
  border-radius: 12px;
}
.stl-live-badge--off {
  color: #6b7280;
  background: #eef0f3;
}

.stl-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.stl-table thead th {
  text-align: left;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #9aa0aa;
  padding: 8px 16px;
  border-bottom: 1px solid #e5e7eb;
  white-space: nowrap;
}
.stl-table tbody tr {
  border-bottom: 1px solid #eceef1;
}
.stl-table tbody tr:last-child {
  border-bottom: none;
}
.stl-table td {
  padding: 8px 16px;
  vertical-align: middle;
}
.stl-agent-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stl-avatar {
  width: 22px;
  height: 22px;
  border-radius: 8px;
  background: #00a8a8;
  color: #fff;
  font-size: 9.5px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stl-avatar--inferred {
  background: transparent;
  color: #00a8a8;
  border: 1.5px dashed #00a8a8;
}
.stl-call-cell {
  display: flex;
  align-items: flex-start;
  gap: 9px;
}
.stl-call-icon {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}
.stl-call-text {
  min-width: 0;
}
.stl-call-title {
  font-weight: 600;
  color: #1a1a2e;
}
.stl-call-sub {
  font-size: 10.5px;
  color: #9aa0aa;
  margin-top: 2px;
}
.stl-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 999px;
  transition:
    background-color 0.35s ease,
    color 0.35s ease;
}
.stl-status-badge .stl-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  transition: background-color 0.35s ease;
}
.stl-status-ringing {
  background: rgba(245, 158, 11, 0.14);
  color: #b45309;
}
.stl-status-ringing .stl-dot {
  background: #f59e0b;
}
.stl-status-early_media {
  background: rgba(14, 165, 233, 0.14);
  color: #0369a1;
}
.stl-status-early_media .stl-dot {
  background: #0ea5e9;
}
.stl-status-answered {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}
.stl-status-answered .stl-dot {
  background: #22c55e;
}
.stl-status-on_hold {
  background: #eef0f3;
  color: #6b7280;
}
.stl-status-on_hold .stl-dot {
  background: #9aa0aa;
}
.stl-empty-row {
  text-align: center;
  padding: 28px 16px;
  color: #9aa0aa;
  font-size: 14px;
}

.stl-queue-count {
  font-size: 10.5px;
  color: #9aa0aa;
  font-family: "Fira Code", monospace;
}
.stl-queue-filter-row {
  padding: 10px 16px 0;
}
.stl-queue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px 16px;
}
.stl-queue-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px 14px;
}
.stl-queue-card:has(.stl-queue-details[open]) {
  border-color: #00a8a8;
}
.stl-queue-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.stl-queue-card__id-block {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}
.stl-queue-card__swatch {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(0, 168, 168, 0.1);
  color: #00a8a8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}
.stl-queue-card__alias {
  font-size: 15px;
  font-weight: 700;
  color: #1a1a2e;
}
.stl-queue-card__raw-id {
  font-family: "Fira Code", monospace;
  font-size: 10.5px;
  color: #9aa0aa;
  margin-top: 1px;
}

.stl-queue-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10.5px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 12px;
  white-space: nowrap;
  flex-shrink: 0;
}
.stl-queue-badge .stl-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.stl-queue-badge--good {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}
.stl-queue-badge--good .stl-dot {
  background: #22c55e;
}
.stl-queue-badge--warn {
  background: rgba(245, 158, 11, 0.14);
  color: #b45309;
}
.stl-queue-badge--warn .stl-dot {
  background: #f59e0b;
}
.stl-queue-badge--bad {
  background: rgba(231, 76, 60, 0.12);
  color: #b91c1c;
}
.stl-queue-badge--bad .stl-dot {
  background: #e74c3c;
}

.stl-queue-card__stats {
  display: flex;
  gap: 24px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #eceef1;
  flex-wrap: wrap;
}
.stl-queue-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stl-queue-stat__label {
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #9aa0aa;
  text-transform: uppercase;
}
.stl-queue-stat__value {
  font-family: "Fira Code", monospace;
  font-size: 15px;
  font-weight: 600;
  color: #1a1a2e;
}
.stl-abandon-warn {
  color: #e74c3c !important;
}

.stl-queue-details summary {
  list-style: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 13px;
  font-weight: 600;
  color: #00a8a8;
  margin-top: 8px;
  user-select: none;
  width: fit-content;
}
.stl-queue-details summary::-webkit-details-marker {
  display: none;
}
.stl-queue-details__chevron {
  transition: transform 0.15s ease;
}
.stl-queue-details[open] .stl-queue-details__chevron {
  transform: rotate(90deg);
}
.stl-queue-details__body {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #eceef1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.stl-queue-gauge {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.stl-queue-gauge__label {
  display: flex;
  justify-content: space-between;
  font-size: 10.5px;
  color: #6b7280;
}
.stl-queue-gauge__track {
  height: 6px;
  border-radius: 4px;
  background: #f2f2f2;
  border: 1px solid #eceef1;
  overflow: hidden;
  position: relative;
}
.stl-queue-gauge__fill {
  height: 100%;
  border-radius: 4px;
}
.stl-queue-gauge__fill--good {
  background: #22c55e;
}
.stl-queue-gauge__fill--warn {
  background: #f59e0b;
}
.stl-queue-gauge__fill--bad {
  background: #e74c3c;
}
.stl-queue-gauge__threshold {
  position: absolute;
  top: -2px;
  bottom: -2px;
  width: 1px;
  background: #9aa0aa;
}
.stl-queue-breakdown {
  display: flex;
  gap: 16px;
}
.stl-queue-breakdown__item {
  flex: 1;
  background: #fafafa;
  border: 1px solid #eceef1;
  border-radius: 8px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.stl-queue-breakdown__label {
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #9aa0aa;
  text-transform: uppercase;
}
.stl-queue-breakdown__value {
  font-family: "Fira Code", monospace;
  font-size: 16px;
  font-weight: 700;
}
.stl-queue-breakdown__value--good {
  color: #22c55e;
}
.stl-queue-breakdown__value--bad {
  color: #e74c3c;
}

.stl-view-toggle {
  display: flex;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
}
.stl-view-toggle__btn {
  width: 28px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  color: #9aa0aa;
  border: none;
  cursor: pointer;
}
.stl-view-toggle__btn:first-child {
  border-right: 1px solid #e5e7eb;
}
.stl-view-toggle__btn--active {
  background: rgba(0, 168, 168, 0.1);
  color: #00a8a8;
}

.stl-agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  padding: 16px;
}
.stl-agents-grid--list {
  grid-template-columns: 1fr;
}
.stl-agent-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-align: center;
  background: #fafafa;
}
.stl-agents-grid--list .stl-agent-card {
  flex-direction: row;
  text-align: left;
  gap: 12px;
  padding: 10px 14px;
}
.stl-agents-grid--list .stl-agent-card__avatar-wrap {
  margin-bottom: 0;
}
.stl-agents-grid--list .stl-agent-card__name {
  flex: 0 0 110px;
}
.stl-agents-grid--list .stl-agent-card__presence {
  flex: 0 0 100px;
}
.stl-agents-grid--list .stl-agent-card__queue {
  flex: 0 0 140px;
  margin-bottom: 0;
}
.stl-agents-grid--list .stl-agent-card__bar-wrap {
  width: auto;
  flex: 1;
}

.stl-agent-card__avatar-wrap {
  position: relative;
  margin-bottom: 6px;
}
.stl-agent-card__avatar {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: #00a8a8;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
}
.stl-agent-card__status-dot {
  position: absolute;
  bottom: 1px;
  right: 1px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 2px solid #fafafa;
}
.stl-agent-card__name {
  font-size: 15px;
  font-weight: 700;
  color: #1a1a2e;
}
.stl-agent-card__presence {
  font-size: 10.5px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 4px;
}
.stl-agent-card__inferred-icon {
  color: #9aa0aa;
  cursor: help;
}
.stl-agent-card__queue {
  font-size: 12px;
  color: #9aa0aa;
  margin-bottom: 4px;
}
.stl-agent-card__bar-wrap {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #9aa0aa;
}
.stl-agent-card__bar-track {
  flex: 1;
  height: 5px;
  border-radius: 3px;
  background: #e5e7eb;
  overflow: hidden;
}
.stl-agent-card__bar-fill {
  height: 100%;
  border-radius: 3px;
  background: #00a8a8;
}
.stl-agent-card__bar-value {
  font-family: "Fira Code", monospace;
  font-weight: 600;
}

.stl-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.stl-status-online {
  background: #22c55e;
}
.stl-status-on_call {
  background: #0ea5e9;
}
.stl-status-away {
  background: #f59e0b;
}
.stl-status-offline {
  background: #9aa0aa;
}
.stl-presence-online {
  color: #15803d;
}
.stl-presence-on_call {
  color: #0369a1;
}
.stl-presence-away {
  color: #b45309;
}
.stl-presence-offline {
  color: #6b7280;
}

.stl-agents-legend {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  border-top: 1px solid #e5e7eb;
  font-size: 13px;
  color: #6b7280;
}
.stl-legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

/* ── Animations temps réel — arrivée/fin d'appel, réordonnancement,
   changement de statut (validé en maquette avant implémentation). ── */
.stl-row-enter-active {
  transition:
    opacity 0.32s ease,
    transform 0.32s ease,
    background-color 0.9s ease;
}
.stl-row-enter-from {
  opacity: 0;
  transform: translateY(-6px);
}
.stl-row-enter-to {
  background-color: rgba(0, 168, 168, 0.14);
}
.stl-row-move {
  transition: transform 0.32s ease;
}
/* Pas de position:absolute ici : <tr> ignore ce positionnement dans la
   plupart des moteurs de rendu (mise en page table), contrairement aux
   cartes en grille/flex ci-dessous — juste un fondu à la sortie. */
.stl-row-leave-active {
  transition: opacity 0.28s ease;
}
.stl-row-leave-to {
  opacity: 0;
}

.stl-card-enter-active {
  transition:
    opacity 0.32s ease,
    transform 0.32s ease;
}
.stl-card-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.stl-card-move {
  transition: transform 0.32s ease;
}
.stl-card-leave-active {
  transition:
    opacity 0.24s ease,
    transform 0.24s ease;
  position: absolute;
}
.stl-card-leave-to {
  opacity: 0;
  transform: scale(0.96);
}

@media (prefers-reduced-motion: reduce) {
  .stl-pulse-dot,
  .stl-row-enter-active,
  .stl-row-move,
  .stl-row-leave-active,
  .stl-card-enter-active,
  .stl-card-move,
  .stl-card-leave-active,
  .stl-status-badge,
  .stl-status-badge .stl-dot {
    animation: none !important;
    transition: none !important;
  }
}
</style>
