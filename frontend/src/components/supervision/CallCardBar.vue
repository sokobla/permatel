<template>
  <Transition name="ccb-bar">
    <div v-if="activeCall" class="ccb-outer">
      <div class="ccb-inner">
        <!-- Bandeau replié — toujours visible tant qu'un appel est actif -->
        <div class="ccb-collapsed" @click="expanded = !expanded">
          <span class="ccb-pulse"></span>
          <span class="ccb-avatar">{{ initials(activeCall.agent_name || activeCall.agent_login) }}</span>
          <span class="ccb-name">{{ activeCall.caller || "—" }}</span>
          <span class="ccb-num">{{ activeCall.callee || "" }}</span>
          <span class="ccb-dur">{{ formatDuration(activeCall.started_at) }}</span>
          <button class="ccb-cta" @click.stop="goToCreateDemande">
            <v-icon size="12" color="#fff">mdi-plus</v-icon>
            Créer une demande
          </button>
          <v-icon size="16" class="ccb-chevron" :class="{ 'ccb-chevron--open': expanded }">
            mdi-chevron-down
          </v-icon>
        </div>

        <!-- Détails dépliés — animés en hauteur (grid-template-rows), jamais démontés -->
        <div class="ccb-details-wrap" :class="{ 'ccb-details-wrap--open': expanded }">
          <div class="ccb-details-inner">
            <div class="ccb-card">
              <div class="ccb-card__head">
                <span class="ccb-card__avatar">{{ initials(activeCall.agent_name || activeCall.agent_login) }}</span>
                <div class="ccb-card__id">
                  <span class="ccb-card__name">{{ activeCall.caller || "—" }}</span>
                  <div class="ccb-card__contactline">
                    <span class="item" v-if="activeCall.agent_name">
                      <v-icon size="12">mdi-account-outline</v-icon>{{ activeCall.agent_name }}
                    </span>
                    <span class="item" v-if="activeCall.callee">
                      <v-icon size="12">mdi-phone-outline</v-icon>{{ activeCall.callee }}
                    </span>
                  </div>
                </div>
                <span class="ccb-card__spacer"></span>
                <span class="ccb-card__status-pill">
                  <span class="ccb-dot"></span>{{ CALL_STATUS_LABEL[activeCall.call_status] || "Appel en cours" }}
                </span>
              </div>

              <div class="ccb-card__stats">
                <div class="ccb-card__stat">
                  <div class="ccb-card__stat-label">Poste</div>
                  <div class="ccb-card__stat-value">{{ activeCall.agent_station || "—" }}</div>
                </div>
                <div class="ccb-card__stat">
                  <div class="ccb-card__stat-label">File</div>
                  <div class="ccb-card__stat-value">{{ activeCall.queue_label || "—" }}</div>
                </div>
                <div class="ccb-card__stat">
                  <div class="ccb-card__stat-label">Durée</div>
                  <div class="ccb-card__stat-value ccb-card__stat-value--live">
                    {{ formatDuration(activeCall.started_at) }}
                  </div>
                </div>
              </div>

              <div class="ccb-card__actions">
                <button class="ccb-btn-primary" @click="goToCreateDemande">
                  <v-icon size="14" color="#fff">mdi-plus</v-icon>
                  Créer une nouvelle demande
                </button>
                <button class="ccb-btn-secondary" @click="expanded = false">Réduire</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth";
import { useTelephonySocket } from "@/composables/useTelephonySocket";
import { telephonyService } from "@/services/telephonyService";

const router = useRouter();
const authStore = useAuthStore();
const telephonySocket = useTelephonySocket();

const CALL_STATUS_LABEL = {
  ringing: "Sonnerie",
  early_media: "Sonnerie",
  answered: "Appel en cours",
  on_hold: "En attente",
};
const TERMINAL_STATUSES = new Set(["ended", "missed", "abandoned", "technical_failure"]);

// Un seul appel actif suivi à la fois — celui de l'agent connecté (agent_login
// == User.agent_login). Si plusieurs call_uuid concurrents portaient le même
// agent_login (cas rare de file), on ne garde que le plus récemment mis à jour.
const activeCall = ref(null);
const expanded = ref(false);
const durationTick = ref(0);
let durationTimer = null;
let lastProcessedIdx = 0;

function myAgentLogin() {
  return authStore.user?.agent_login || null;
}

function formatDuration(startedAtIso) {
  if (!startedAtIso) return "00:00:00";
  void durationTick.value; // force la ré-évaluation chaque seconde
  const started = new Date(startedAtIso).getTime();
  if (Number.isNaN(started)) return "00:00:00";
  const elapsed = Math.max(0, Math.floor((Date.now() - started) / 1000));
  const h = String(Math.floor(elapsed / 3600)).padStart(2, "0");
  const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0");
  const s = String(elapsed % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

function initials(name) {
  if (!name) return "?";
  return name
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

async function loadInitialActiveCall() {
  const login = myAgentLogin();
  if (!login) return;
  try {
    const { data } = await telephonyService.getActiveCalls();
    const mine = (data.active_calls || []).find((c) => c.agent_login === login);
    if (mine) {
      activeCall.value = mine;
      expanded.value = true;
    }
  } catch {
    // Best-effort : le bandeau restera vide tant qu'aucun événement socket
    // ne confirme un appel actif — pas d'état d'erreur affiché pour ça.
  }
}

function processIncomingEvents() {
  const login = myAgentLogin();
  const evs = telephonySocket.events.value;
  for (; lastProcessedIdx < evs.length; lastProcessedIdx++) {
    const e = evs[lastProcessedIdx];
    if (!login || e.agent_login !== login) continue;

    if (TERMINAL_STATUSES.has(e.call_status)) {
      if (activeCall.value?.call_uuid === e.call_uuid) {
        activeCall.value = null;
      }
      continue;
    }
    if (!e.call_status) continue; // enrichissement sans statut, pas assez pour (dé)clencher la carte

    const isNewCall = !activeCall.value || activeCall.value.call_uuid !== e.call_uuid;
    activeCall.value = {
      call_uuid: e.call_uuid,
      caller: e.caller || activeCall.value?.caller || null,
      callee: e.callee || activeCall.value?.callee || null,
      call_status: e.call_status,
      agent_login: e.agent_login,
      agent_name: activeCall.value?.agent_name || null,
      agent_station: activeCall.value?.agent_station || null,
      queue_label: activeCall.value?.queue_label || null,
      started_at: activeCall.value?.started_at || e.created_at || new Date().toISOString(),
    };
    if (isNewCall) expanded.value = true; // nouvel appel = notification dépliée
  }
}

function goToCreateDemande() {
  if (!activeCall.value) return;
  router.push({
    path: "/workspace",
    query: {
      new_demande: "1",
      caller: activeCall.value.caller || undefined,
      callee: activeCall.value.callee || undefined,
    },
  });
}

let eventsWatcherTimer = null;

onMounted(() => {
  telephonySocket.connect();
  loadInitialActiveCall();
  eventsWatcherTimer = setInterval(processIncomingEvents, 1000);
  durationTimer = setInterval(() => {
    durationTick.value++;
  }, 1000);
});
onUnmounted(() => {
  if (eventsWatcherTimer) clearInterval(eventsWatcherTimer);
  if (durationTimer) clearInterval(durationTimer);
  telephonySocket.disconnect();
});
</script>

<style scoped>
.ccb-outer {
  overflow: hidden;
}
.ccb-inner {
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

/* ── Apparition / disparition du bandeau entier ─────────────────────────
   Technique grid-template-rows (0fr <-> 1fr) : anime une hauteur "auto"
   sans mesure JS, fluide quel que soit le contenu (replié ou déplié). */
.ccb-bar-enter-active,
.ccb-bar-leave-active {
  display: grid;
  grid-template-rows: 1fr;
  transition:
    grid-template-rows 0.32s ease,
    opacity 0.32s ease;
}
.ccb-bar-enter-from,
.ccb-bar-leave-to {
  grid-template-rows: 0fr;
  opacity: 0;
}
.ccb-bar-enter-to,
.ccb-bar-leave-from {
  grid-template-rows: 1fr;
  opacity: 1;
}

.ccb-collapsed {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 16px;
  background: rgba(34, 197, 94, 0.1);
  cursor: pointer;
  font-family: "Fira Sans", sans-serif;
}
.ccb-pulse {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22c55e;
  flex-shrink: 0;
  animation: ccb-pulse 1.8s infinite;
}
@keyframes ccb-pulse {
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
.ccb-avatar {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: #00a8a8;
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ccb-name {
  font-size: 12px;
  font-weight: 700;
  color: #000b23;
  white-space: nowrap;
}
.ccb-num {
  font-family: "Fira Code", monospace;
  font-size: 11px;
  color: #9aa0aa;
  white-space: nowrap;
}
.ccb-dur {
  font-family: "Fira Code", monospace;
  font-size: 11.5px;
  font-weight: 700;
  color: #22c55e;
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}
.ccb-cta {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  font-weight: 700;
  color: #fff;
  background: #00a8a8;
  border-radius: 999px;
  padding: 5px 11px;
  white-space: nowrap;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}
.ccb-cta:hover {
  background: #00918f;
}
.ccb-chevron {
  color: #9aa0aa;
  transition: transform 0.2s ease;
  flex-shrink: 0;
}
.ccb-chevron--open {
  transform: rotate(180deg);
}

/* ── Repli / dépli des détails — même technique grid-rows, sans démontage
   (les enfants ne sont jamais retirés du DOM, juste comprimés à 0). ── */
.ccb-details-wrap {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s ease;
}
.ccb-details-wrap--open {
  grid-template-rows: 1fr;
}
.ccb-details-inner {
  overflow: hidden;
  min-height: 0;
}

.ccb-card {
  padding: 16px 18px;
  font-family: "Fira Sans", sans-serif;
}
.ccb-card__head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.ccb-card__avatar {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: #00a8a8;
  color: #fff;
  font-weight: 700;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ccb-card__id {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.ccb-card__name {
  font-size: 13.5px;
  font-weight: 700;
  color: #000b23;
}
.ccb-card__contactline {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 11.5px;
  color: #9aa0aa;
}
.ccb-card__contactline .item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.ccb-card__spacer {
  flex: 1;
}
.ccb-card__status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  font-weight: 700;
  color: #22c55e;
  background: rgba(34, 197, 94, 0.12);
  border-radius: 999px;
  padding: 4px 10px;
  white-space: nowrap;
}
.ccb-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.ccb-card__stats {
  display: flex;
  margin-top: 13px;
  border-top: 1px solid #e5e7eb;
}
.ccb-card__stat {
  flex: 1;
  padding: 10px 16px;
  border-right: 1px solid #e5e7eb;
}
.ccb-card__stat:last-child {
  border-right: none;
}
.ccb-card__stat-label {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #9aa0aa;
  text-transform: uppercase;
}
.ccb-card__stat-value {
  font-family: "Fira Code", monospace;
  font-size: 12.5px;
  font-weight: 600;
  color: #000b23;
  margin-top: 3px;
}
.ccb-card__stat-value--live {
  color: #22c55e;
  font-variant-numeric: tabular-nums;
}

.ccb-card__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 12px;
}
.ccb-btn-primary {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: #00a8a8;
  color: #fff;
  font-family: "Fira Sans", sans-serif;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s;
}
.ccb-btn-primary:hover {
  background: #00918f;
}
.ccb-btn-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: transparent;
  color: #000b23;
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.ccb-btn-secondary:hover {
  background: rgba(0, 0, 0, 0.03);
}

@media (prefers-reduced-motion: reduce) {
  .ccb-bar-enter-active,
  .ccb-bar-leave-active,
  .ccb-details-wrap,
  .ccb-chevron,
  .ccb-pulse {
    transition: none !important;
    animation: none !important;
  }
}
</style>
