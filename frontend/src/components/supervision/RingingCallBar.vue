<template>
  <Transition name="rcb-bar">
    <div v-if="ringingCall" class="rcb-outer">
      <div class="rcb-inner">
        <span class="rcb-pulse"></span>
        <v-icon size="15" color="#b45309">mdi-phone-ring-outline</v-icon>
        <span class="rcb-label">Appel entrant</span>
        <span class="rcb-avatar">{{
          initials(ringingCall.agent_name || ringingCall.agent_login)
        }}</span>
        <span class="rcb-name">{{ ringingCall.caller || "—" }}</span>
        <span class="rcb-num">{{ ringingCall.callee || "" }}</span>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useAuthStore } from "@/store/auth";
import { useTelephonySocket } from "@/composables/useTelephonySocket";
import { telephonyService } from "@/services/telephonyService";

const authStore = useAuthStore();
const telephonySocket = useTelephonySocket();

// "Ça sonne" : avant décroché — distinct de la CallCardBar (appel déjà en
// cours), qui reste l'indicateur pour tout le reste du cycle de l'appel.
const RINGING_STATUSES = new Set(["ringing", "early_media"]);
const STOP_STATUSES = new Set([
  "answered",
  "on_hold",
  "ended",
  "missed",
  "abandoned",
  "technical_failure",
]);

// Uniquement l'appel de l'agent connecté (même motif que CallCardBar.vue) —
// pas un outil de supervision multi-agents, un rappel visuel personnel
// pendant que ça sonne sur son propre poste.
const ringingCall = ref(null);
let lastProcessedIdx = 0;

function myAgentLogin() {
  return authStore.user?.agent_login || null;
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

async function loadInitialRingingCall() {
  const login = myAgentLogin();
  if (!login) return;
  try {
    const { data } = await telephonyService.getActiveCalls();
    const mine = (data.active_calls || []).find(
      (c) => c.agent_login === login && RINGING_STATUSES.has(c.call_status),
    );
    if (mine) ringingCall.value = mine;
  } catch {
    // Best-effort : la bannière restera vide tant qu'aucun événement socket
    // ne confirme une sonnerie — pas d'état d'erreur affiché pour ça.
  }
}

function processIncomingEvents() {
  const login = myAgentLogin();
  const evs = telephonySocket.events.value;
  for (; lastProcessedIdx < evs.length; lastProcessedIdx++) {
    const e = evs[lastProcessedIdx];
    if (!login || e.agent_login !== login) continue;

    if (STOP_STATUSES.has(e.call_status)) {
      if (ringingCall.value?.call_uuid === e.call_uuid)
        ringingCall.value = null;
      continue;
    }
    if (!RINGING_STATUSES.has(e.call_status)) continue;

    ringingCall.value = {
      call_uuid: e.call_uuid,
      caller: e.caller || ringingCall.value?.caller || null,
      callee: e.callee || ringingCall.value?.callee || null,
      agent_login: e.agent_login,
      agent_name: ringingCall.value?.agent_name || null,
    };
  }
}

let eventsWatcherTimer = null;

onMounted(() => {
  telephonySocket.connect();
  loadInitialRingingCall();
  eventsWatcherTimer = setInterval(processIncomingEvents, 1000);
});
onUnmounted(() => {
  if (eventsWatcherTimer) clearInterval(eventsWatcherTimer);
  telephonySocket.disconnect();
});
</script>

<style scoped>
.rcb-outer {
  overflow: hidden;
}
.rcb-inner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 16px;
  background: rgba(180, 83, 9, 0.1);
  border-bottom: 1px solid #e5e7eb;
  font-family: "Fira Sans", sans-serif;
}

.rcb-bar-enter-active,
.rcb-bar-leave-active {
  display: grid;
  grid-template-rows: 1fr;
  transition:
    grid-template-rows 0.32s ease,
    opacity 0.32s ease;
}
.rcb-bar-enter-from,
.rcb-bar-leave-to {
  grid-template-rows: 0fr;
  opacity: 0;
}
.rcb-bar-enter-to,
.rcb-bar-leave-from {
  grid-template-rows: 1fr;
  opacity: 1;
}

.rcb-pulse {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #b45309;
  flex-shrink: 0;
  animation: rcb-pulse 1s infinite;
}
@keyframes rcb-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(180, 83, 9, 0.55);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(180, 83, 9, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(180, 83, 9, 0);
  }
}
.rcb-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #b45309;
  text-transform: uppercase;
  white-space: nowrap;
}
.rcb-avatar {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: #b45309;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-left: 6px;
}
.rcb-name {
  font-size: 14px;
  font-weight: 700;
  color: #000b23;
  white-space: nowrap;
}
.rcb-num {
  font-family: "Fira Code", monospace;
  font-size: 13px;
  color: #9aa0aa;
  white-space: nowrap;
}

@media (prefers-reduced-motion: reduce) {
  .rcb-bar-enter-active,
  .rcb-bar-leave-active,
  .rcb-pulse {
    transition: none !important;
    animation: none !important;
  }
}
</style>
