<template>
  <v-menu v-model="open" location="bottom end" :close-on-content-click="false" width="380">
    <template #activator="{ props }">
      <v-btn v-bind="props" icon variant="text" class="mr-1" title="Notifications">
        <v-badge :model-value="unread > 0" :content="unread > 99 ? '99+' : unread" color="#e74c3c">
          <v-icon color="#000b23">mdi-bell-outline</v-icon>
        </v-badge>
      </v-btn>
    </template>

    <v-card class="nb-card">
      <div class="nb-head">
        <span class="nb-title">Notifications</span>
        <button v-if="unread > 0" class="nb-readall" @click="markAll">Tout marquer lu</button>
      </div>
      <v-divider />

      <div v-if="loading" class="nb-state">
        <v-progress-circular indeterminate size="20" color="#00a8a8" />
      </div>
      <div v-else-if="!items.length" class="nb-state">Aucune notification.</div>

      <ul v-else class="nb-list">
        <li
          v-for="n in items"
          :key="n.id"
          :class="['nb-item', { 'nb-item--unread': !n.is_read }]"
          @click="onClick(n)"
        >
          <span class="nb-dot" :style="{ background: sevColor(n.severity) }"></span>
          <div class="nb-body">
            <div class="nb-item-title">{{ n.title }}</div>
            <div v-if="n.body" class="nb-item-text">{{ n.body }}</div>
            <div class="nb-time">{{ ago(n.created_at) }}</div>
          </div>
        </li>
      </ul>
    </v-card>
  </v-menu>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth";
import { notificationService } from "@/services/notificationService";

const POLL_MS = 45000;
const authStore = useAuthStore();
const router = useRouter();

const open = ref(false);
const unread = ref(0);
const items = ref([]);
const loading = ref(false);
let timer = null;

const SEV = { high: "#e74c3c", normal: "#00a8a8", low: "#9aa0aa" };
const sevColor = (s) => SEV[s] || SEV.normal;

const ROUTE_BY_ENTITY = { demande: "/issues", email: "/workspace" };

async function refreshCount() {
  if (!authStore.isAuthenticated || !authStore.activeTenantId) return;
  try {
    const { data } = await notificationService.unreadCount();
    unread.value = data.unread_count ?? 0;
  } catch { /* silencieux */ }
}

async function loadList() {
  loading.value = true;
  try {
    const { data } = await notificationService.list({ limit: 20 });
    items.value = data.notifications ?? [];
    unread.value = data.unread_count ?? unread.value;
  } catch { /* silencieux */ } finally {
    loading.value = false;
  }
}

async function onClick(n) {
  if (!n.is_read) {
    try { await notificationService.markRead(n.id); } catch { /* */ }
    n.is_read = true;
    unread.value = Math.max(0, unread.value - 1);
  }
  const to = ROUTE_BY_ENTITY[n.entity_type];
  if (to) {
    open.value = false;
    router.push(to);
  }
}

async function markAll() {
  try {
    await notificationService.markAllRead();
    items.value.forEach((n) => (n.is_read = true));
    unread.value = 0;
  } catch { /* */ }
}

function ago(iso) {
  if (!iso) return "";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "à l'instant";
  if (s < 3600) return `il y a ${Math.floor(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
  return `il y a ${Math.floor(s / 86400)} j`;
}

watch(open, (v) => { if (v) loadList(); });

onMounted(() => {
  refreshCount();
  timer = setInterval(refreshCount, POLL_MS);
});
onUnmounted(() => { if (timer) clearInterval(timer); });
</script>

<style scoped>
.nb-card { font-family: "Fira Sans", sans-serif; }
.nb-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; }
.nb-title { font-size: 13px; font-weight: 700; color: #000b23; }
.nb-readall { background: none; border: none; color: #00a8a8; font-size: 11.5px; cursor: pointer; }
.nb-state { padding: 24px; text-align: center; color: #9aa0aa; font-size: 12.5px; }
.nb-list { list-style: none; margin: 0; padding: 0; max-height: 60vh; overflow-y: auto; }
.nb-item { display: flex; gap: 10px; padding: 10px 14px; border-bottom: 1px solid #f0f1f3; cursor: pointer; }
.nb-item:hover { background: #f7fdfd; }
.nb-item--unread { background: #f0fafa; }
.nb-dot { width: 7px; height: 7px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
.nb-body { min-width: 0; }
.nb-item-title { font-size: 13px; font-weight: 600; color: #000b23; }
.nb-item-text { font-size: 12px; color: #4b5563; margin-top: 1px; }
.nb-time { font-size: 10.5px; color: #9aa0aa; margin-top: 2px; }
</style>
