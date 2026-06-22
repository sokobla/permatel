<template>
  <div class="st-page">
    <div class="st-card">
      <div class="st-head">
        <span class="st-brand__mark"></span>
        <div>
          <h1 class="st-title">Choisir un espace de travail</h1>
          <p class="st-subtitle">
            <template v-if="authStore.isGlobalAdmin">
              Vous êtes administrateur global : sélectionnez le tenant à superviser.
            </template>
            <template v-else>
              Votre compte est rattaché à plusieurs entités. Sélectionnez celle à ouvrir.
            </template>
          </p>
        </div>
      </div>

      <v-alert
        v-if="errorMessage"
        type="error"
        variant="tonal"
        density="compact"
        class="mb-4"
        border="start"
        closable
        @click:close="errorMessage = null"
      >
        {{ errorMessage }}
      </v-alert>

      <div v-if="loadingList" class="st-loading">
        <v-progress-circular indeterminate color="#00a8a8" size="28" />
        <span>Chargement des espaces…</span>
      </div>

      <div v-else-if="!authStore.tenants.length" class="st-empty">
        Aucun espace de travail disponible. Contactez un administrateur.
      </div>

      <ul v-else class="st-list">
        <li
          v-for="t in authStore.tenants"
          :key="t.id"
          class="st-item"
          :class="{ 'st-item--busy': selectingId === t.id }"
          role="button"
          tabindex="0"
          @click="choose(t)"
          @keydown.enter="choose(t)"
        >
          <div class="st-item__logo">
            <img v-if="logoOf(t)" :src="logoOf(t)" :alt="t.nom" />
            <span v-else>{{ initials(t.nom) }}</span>
          </div>
          <div class="st-item__body">
            <span class="st-item__name">{{ t.nom }}</span>
            <span class="st-item__code">{{ t.code }}</span>
          </div>
          <v-progress-circular
            v-if="selectingId === t.id"
            indeterminate
            color="#00a8a8"
            size="18"
            width="2"
          />
          <v-icon v-else size="18" color="#9aa0aa">mdi-chevron-right</v-icon>
        </li>
      </ul>

      <div class="st-foot">
        <button class="st-logout" @click="onLogout">
          <v-icon size="14">mdi-logout</v-icon> Se déconnecter
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth";

const authStore = useAuthStore();
const router = useRouter();

const selectingId = ref(null);
const errorMessage = ref(null);
const loadingList = ref(false);

const BACKEND_ORIGIN = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api"
).replace(/\/api\/?$/, "");

function logoOf(t) {
  if (!t?.logo_url) return null;
  return /^https?:\/\//.test(t.logo_url) ? t.logo_url : BACKEND_ORIGIN + t.logo_url;
}

function initials(name) {
  return (name || "?")
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

async function choose(t) {
  if (selectingId.value) return;
  selectingId.value = t.id;
  errorMessage.value = null;
  const res = await authStore.selectTenant(t.id);
  if (res.success) {
    const dest = authStore.returnUrl || authStore.homeRoute;
    authStore.returnUrl = null;
    router.push(dest);
  } else {
    errorMessage.value = res.error;
    selectingId.value = null;
  }
}

async function onLogout() {
  await authStore.logout();
  router.push("/login");
}

onMounted(async () => {
  // Rafraîchit la liste (surtout pour l'admin global : tous les tenants actifs).
  if (!authStore.tenants.length || authStore.isGlobalAdmin) {
    loadingList.value = true;
    await authStore.fetchTenants();
    loadingList.value = false;
  }
});
</script>

<style scoped>
.st-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f2f2f2;
  padding: 24px;
  font-family: "Fira Sans", sans-serif;
}
.st-card {
  width: 100%;
  max-width: 440px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 28px;
}
.st-head {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.st-brand__mark {
  width: 4px;
  height: 38px;
  background: #00a8a8;
  border-radius: 2px;
  flex-shrink: 0;
}
.st-title {
  font-size: 18px;
  font-weight: 800;
  color: #000b23;
  margin: 0;
}
.st-subtitle {
  font-size: 12.5px;
  color: #6b7280;
  margin: 4px 0 0;
  line-height: 1.5;
}
.st-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.st-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.st-item:hover {
  border-color: #00a8a8;
  background: #f7fdfd;
}
.st-item--busy {
  opacity: 0.7;
  pointer-events: none;
}
.st-item__logo {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
  font-family: "Fira Code", monospace;
  font-size: 13px;
  font-weight: 700;
  color: #000b23;
}
.st-item__logo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.st-item__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.st-item__name {
  font-size: 14px;
  font-weight: 600;
  color: #000b23;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.st-item__code {
  font-family: "Fira Code", monospace;
  font-size: 11px;
  color: #9aa0aa;
}
.st-loading,
.st-empty {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  color: #6b7280;
  font-size: 13px;
  padding: 24px 0;
}
.st-foot {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #e5e7eb;
  text-align: center;
}
.st-logout {
  background: none;
  border: none;
  color: #6b7280;
  font-size: 12.5px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.st-logout:hover {
  color: #c0392b;
}
</style>
