import { ref } from "vue";
import { io } from "socket.io-client";
import { useAuthStore } from "@/store/auth";

const MAX_EVENTS = 200;

// Origine backend (hors /api) — même motif que ContactSelectWithAdd.vue /
// TenantsView.vue pour dériver l'URL des ressources servies par le backend.
const BACKEND_ORIGIN = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api"
).replace(/\/api\/?$/, "");

/**
 * Connexion partagée au namespace Socket.IO /telephony (Phase 11bis/12) —
 * un seul socket par page, les événements portent `pbx_connector_id` pour
 * être filtrés côté composant par connecteur (cf. SettingsTelephony.vue).
 */
export function useTelephonySocket() {
  const connected = ref(false);
  const events = ref([]);
  let socket = null;

  function connect() {
    if (socket) return;
    const authStore = useAuthStore();
    const token = authStore.accessToken;
    if (!token) return;

    socket = io(`${BACKEND_ORIGIN}/telephony`, {
      query: { token },
      transports: ["websocket"],
    });

    socket.on("connect", () => {
      connected.value = true;
    });
    socket.on("disconnect", () => {
      connected.value = false;
    });
    socket.on("telephony_event", (payload) => {
      events.value.push({ ...payload, _receivedAt: Date.now() });
      if (events.value.length > MAX_EVENTS) events.value.shift();
    });
  }

  function disconnect() {
    socket?.disconnect();
    socket = null;
    connected.value = false;
  }

  function clear() {
    events.value = [];
  }

  return { connected, events, connect, disconnect, clear };
}
