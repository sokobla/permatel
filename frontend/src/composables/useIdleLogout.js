/**
 * useIdleLogout — déconnexion automatique après inactivité (UX).
 *
 * Aligné sur le timeout serveur (SESSION_INACTIVITY_TIMEOUT = 30 min).
 * Affiche un avertissement ~1 min avant la déconnexion.
 * Synchronisé entre onglets via localStorage (l'activité dans un onglet
 * réarme tous les autres).
 *
 * Le serveur reste la source de vérité : ce mécanisme est purement confort.
 */
import { ref, watch, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth";

const ACTIVITY_EVENTS = ["mousedown", "keydown", "scroll", "touchstart", "click", "mousemove"];
const PING_KEY = "permatel_idle_ping";

export function useIdleLogout(options = {}) {
  const minutes = Number(import.meta.env.VITE_INACTIVITY_TIMEOUT_MINUTES ?? 30);
  const TIMEOUT_MS = options.timeoutMs ?? minutes * 60_000;
  const WARN_MS = options.warnMs ?? 60_000; // avertissement 1 min avant

  const router = useRouter();
  const authStore = useAuthStore();

  const showWarning = ref(false);
  const secondsLeft = ref(Math.floor(WARN_MS / 1000));

  let warnTimer = null;
  let hardTimer = null;
  let countdown = null;
  let lastPing = 0;
  let active = false;

  function clearTimers() {
    clearTimeout(warnTimer);
    clearTimeout(hardTimer);
    clearInterval(countdown);
    warnTimer = hardTimer = countdown = null;
  }

  async function doLogout() {
    clearTimers();
    showWarning.value = false;
    stop();
    await authStore.logout();
    router.push({ name: "Login", query: { reason: "inactivity" } });
  }

  function startWarning() {
    showWarning.value = true;
    secondsLeft.value = Math.floor(WARN_MS / 1000);
    countdown = setInterval(() => {
      secondsLeft.value -= 1;
      if (secondsLeft.value <= 0) doLogout();
    }, 1000);
  }

  function resetTimer(broadcast = true) {
    clearTimers();
    showWarning.value = false;
    if (!authStore.isAuthenticated) return;
    warnTimer = setTimeout(startWarning, Math.max(0, TIMEOUT_MS - WARN_MS));
    hardTimer = setTimeout(doLogout, TIMEOUT_MS); // filet de sécurité
    if (broadcast) {
      const now = Date.now();
      if (now - lastPing > 3000) {
        lastPing = now;
        try { localStorage.setItem(PING_KEY, String(now)); } catch { /* quota */ }
      }
    }
  }

  function onActivity() {
    // Pendant l'avertissement, seule une action explicite réarme (évite le flicker)
    if (!showWarning.value) resetTimer();
  }

  function onStorage(e) {
    if (e.key === PING_KEY) resetTimer(false); // un autre onglet est actif
  }

  function stayConnected() {
    resetTimer();
  }

  function start() {
    if (active) return;
    active = true;
    ACTIVITY_EVENTS.forEach((ev) =>
      window.addEventListener(ev, onActivity, { passive: true }),
    );
    window.addEventListener("storage", onStorage);
    resetTimer(false);
  }

  function stop() {
    if (!active) return;
    active = false;
    clearTimers();
    ACTIVITY_EVENTS.forEach((ev) => window.removeEventListener(ev, onActivity));
    window.removeEventListener("storage", onStorage);
  }

  // Démarre/arrête selon l'état d'authentification
  watch(
    () => authStore.isAuthenticated,
    (isAuth) => (isAuth ? start() : stop()),
  );

  onMounted(() => {
    if (authStore.isAuthenticated) start();
  });
  onBeforeUnmount(stop);

  return { showWarning, secondsLeft, stayConnected };
}
