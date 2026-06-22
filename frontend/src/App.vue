<template>
  <v-app id="permatel-app">
    <template v-if="authStore.isAuthenticated">
      <SideMenue />
      <v-app-bar elevation="0" color="white" border="b" density="compact">
        <img
          v-if="tenantLogoUrl"
          :src="tenantLogoUrl"
          class="app-bar-logo"
          alt="Logo tenant"
        />

        <!-- Sélecteur de tenant : actif si l'utilisateur a plusieurs espaces -->
        <v-menu v-if="canSwitchTenant" location="bottom start">
          <template #activator="{ props }">
            <button v-bind="props" class="tenant-switch" type="button">
              <span class="app-bar-title">{{ tenantName || "Choisir un espace" }}</span>
              <v-icon size="16" color="#6b7280">mdi-unfold-more-horizontal</v-icon>
            </button>
          </template>
          <v-list density="compact" class="tenant-switch__list">
            <v-list-subheader v-if="authStore.isGlobalAdmin">
              Espaces (admin global)
            </v-list-subheader>
            <v-list-item
              v-for="t in authStore.tenants"
              :key="t.id"
              :active="t.id === authStore.activeTenantId"
              @click="onSwitchTenant(t.id)"
            >
              <template #prepend>
                <v-icon
                  size="16"
                  :color="t.id === authStore.activeTenantId ? '#00a8a8' : '#cbd0d6'"
                >
                  {{ t.id === authStore.activeTenantId ? "mdi-check-circle" : "mdi-circle-outline" }}
                </v-icon>
              </template>
              <v-list-item-title class="tenant-switch__name">{{ t.nom }}</v-list-item-title>
              <v-list-item-subtitle class="tenant-switch__code">{{ t.code }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-menu>
        <v-toolbar-title v-else class="app-bar-title">{{ tenantName }}</v-toolbar-title>

        <v-spacer></v-spacer>
        <v-avatar :src="profileAvatarUrl" size="32" class="mr-2"></v-avatar>
        <v-btn
          color="#000b23"
          @click="handleLogout"
          text="Déconnexion"
          append-icon="mdi-logout"
          variant="text"
        >
        </v-btn>
      </v-app-bar>
    </template>

    <v-main>
      <router-view />
    </v-main>

    <!-- Footer général : copyright + nom & version de l'application -->
    <v-footer app color="white" border="t" class="app-footer">
      <span class="app-footer__brand">{{ APP_NAME }}</span>
      <span class="app-footer__ver">v{{ appVersion }}</span>
      <v-spacer></v-spacer>
      <span class="app-footer__copy">
        © {{ currentYear }} {{ APP_NAME }} — Tous droits réservés.
      </span>
    </v-footer>

    <!-- Avertissement d'inactivité avant déconnexion automatique -->
    <v-dialog v-model="showWarning" max-width="400" persistent>
      <v-card class="idle-card">
        <v-card-title class="idle-card__title">SESSION INACTIVE</v-card-title>
        <v-card-text class="idle-card__text">
          Vous allez être déconnecté dans
          <strong>{{ secondsLeft }}</strong> seconde{{
            secondsLeft > 1 ? "s" : ""
          }}
          pour cause d'inactivité.
        </v-card-text>
        <v-card-actions class="idle-card__actions">
          <v-btn variant="text" @click="handleLogout">Se déconnecter</v-btn>
          <v-btn color="#00a8a8" variant="flat" @click="stayConnected"
            >Rester connecté</v-btn
          >
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-app>
</template>

<script setup>
import { computed, watch } from "vue";
import SideMenue from "@/components/Menu2.vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth";
import { useIdleLogout } from "@/composables/useIdleLogout";

const appVersion = import.meta.env.VITE_APP_VERSION ?? "2.4";
const APP_NAME = import.meta.env.VITE_APP_NAME ?? "PERMATEL";
const currentYear = new Date().getFullYear();
const authStore = useAuthStore();
const router = useRouter();

// Déconnexion automatique sur inactivité (alignée sur le serveur, 30 min)
const { showWarning, secondsLeft, stayConnected } = useIdleLogout();

const profileAvatarUrl = computed(() => {
  const seed = authStore.user?.username ?? "user";
  return `https://api.dicebear.com/8.x/initials/svg?seed=${encodeURIComponent(seed)}&backgroundColor=15223a&textColor=ffffff`;
});

// Logo du tenant actif (affiché avant le titre dans l'app-bar)
const BACKEND_ORIGIN = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api"
).replace(/\/api\/?$/, "");

const tenantLogoUrl = computed(() => {
  const t = authStore.tenants?.find((x) => x.id === authStore.activeTenantId);
  const path = t?.logo_url;
  if (!path) return null;
  return /^https?:\/\//.test(path) ? path : BACKEND_ORIGIN + path;
});

const tenantName = computed(() => {
  const t = authStore.tenants?.find((x) => x.id === authStore.activeTenantId);
  return t?.nom ?? null;
});

// Sélecteur visible si l'utilisateur a plusieurs espaces (ou est admin global)
const canSwitchTenant = computed(
  () => authStore.isGlobalAdmin || (authStore.tenants?.length ?? 0) > 1,
);

const onSwitchTenant = async (tenantId) => {
  await authStore.switchTenant(tenantId);
};

// Garde la liste des tenants à jour pour l'admin global (nouveaux tenants créés)
watch(
  () => authStore.isAuthenticated,
  (authed) => {
    if (authed && authStore.isGlobalAdmin) authStore.fetchTenants();
  },
  { immediate: true },
);

const handleLogout = async () => {
  await authStore.logout();
  router.push("/login");
};
</script>

<style scoped>
.app-bar-logo {
  height: 26px;
  width: auto;
  max-width: 90px;
  object-fit: contain;
  margin-left: 16px;
  margin-right: 12px;
  border-radius: 4px;
}

.app-bar-title {
  font-family: "Fira Code", monospace;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: #000b23;
  text-transform: uppercase;
}

/* Sélecteur de tenant (app-bar) */
.tenant-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
  transition: background 0.15s;
}
.tenant-switch:hover {
  background: #f0f2f5;
}
.tenant-switch__list {
  min-width: 240px;
  max-height: 60vh;
}
.tenant-switch__name {
  font-size: 13px;
  font-weight: 600;
  color: #000b23;
}
.tenant-switch__code {
  font-family: "Fira Code", monospace;
  font-size: 11px;
  color: #9aa0aa;
}

.idle-card__title {
  font-family: "Fira Sans", sans-serif;
  font-size: 14px !important;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #000b23;
}
.idle-card__text {
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  color: #1a1a2e;
}
.idle-card__actions {
  justify-content: flex-end;
  gap: 8px;
  padding: 8px 16px 16px;
}

/* ── Footer général ──────────────────────────────────────────────── */
.app-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 16px;
  font-size: 11px;
}
.app-footer__brand {
  font-family: "Fira Code", monospace;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: #000b23;
}
.app-footer__ver {
  font-family: "Fira Code", monospace;
  font-size: 10px;
  color: #00a8a8;
}
.app-footer__copy {
  font-family: "Fira Sans", sans-serif;
  color: #6b7280;
}

:root {
  --permatel-drawer-bg: #f5f5f5;
  --permatel-text-primary: #333333;
  --permatel-text-secondary: #666666;
  --permatel-accent-active: #00bcd4; /* Cyan / Turquoise */
}

.permatel-profile-block {
  padding: 16px;
  text-align: left;
  /* Aligner à gauche */
  border-bottom: 1px solid #e0e0e0;
  /* Séparateur fin */
  margin-bottom: 8px;
  /* Espace après le bloc profil */
}

.permatel-profile-username {
  font-size: 0.85em;
  color: var(--permatel-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 2px;
}

.permatel-profile-fullname {
  font-size: 1.1em;
  font-weight: 600;
  color: var(--permatel-text-primary);
  margin-bottom: 2px;
}

.permatel-profile-role {
  font-size: 0.75em;
  color: var(--permatel-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.permatel-divider {
  border-color: #e0e0e0 !important;
  /* Couleur du diviseur */
  margin: 8px 0;
  /* Espacement du diviseur */
}

.permatel-navigation-list {
  padding-top: 0;
  /* Supprimer le padding supérieur de la liste */
}

.permatel-navigation-list .v-list-item {
  min-height: 40px;
  /* Hauteur des items pour densité compacte */
  padding: 0 16px;
  /* Padding horizontal */
  color: var(--permatel-text-primary) !important;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-radius: 0 !important;
  /* Supprimer les arrondis */
}

.permatel-navigation-list .v-list-item .v-list-item__prepend > .v-icon {
  color: var(--permatel-text-secondary) !important;
  /* Couleur des icônes */
  margin-right: 12px;
  /* Espacement icône-texte */
  opacity: 0.8;
  /* Légèrement atténué */
}

.permatel-navigation-list .v-list-item--active {
  background-color: rgba(var(--permatel-accent-active), 0.1) !important;
  /* Fond légèrement teinté */
  border-left: 3px solid var(--permatel-accent-active) !important;
  /* Indicateur vertical */
  color: var(--permatel-accent-active) !important;
  /* Texte actif */
}

.permatel-navigation-list .v-list-item--active .v-list-item__prepend > .v-icon {
  color: var(--permatel-accent-active) !important;
  /* Icône active */
}

.permatel-navigation-list .v-list-item:hover {
  background-color: rgba(var(--permatel-accent-active), 0.05) !important;
  /* Effet hover discret */
}

/* Surcharge des styles Vuetify pour neutraliser les effets Material */
.v-navigation-drawer {
  /* Réduire les paddings internes par défaut du drawer */
  padding: 0 !important;
}

.v-list-item {
  /* Neutraliser box-shadow et border-radius */
  box-shadow: none !important;
  border-radius: 0 !important;
}

.v-list-item:before {
  /* masquer l'overlay de ripple Vuetify par défaut */
  background-color: transparent !important;
}
</style>
