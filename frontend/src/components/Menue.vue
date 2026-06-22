<template>
  <v-navigation-drawer
    :rail="isCollapsed"
    permanent
    class="permatel-navigation-drawer"
    @update:rail="onRailUpdate"
  >
    <!-- ══════════════════ ZONE HAUTE : PROFIL & BRANDING ══════════════════ -->
    <div
      v-if="authStore.user"
      class="user-profile-block"
      :class="{ 'user-profile-block--collapsed': isCollapsed }"
      @click="isCollapsed = !isCollapsed"
    >
      <v-icon class="branding-logo" size="32">mdi-shield-check</v-icon>
      <div class="user-profile-info" v-show="!isCollapsed">
        <div class="user-profile-name">{{ authUser.fullName }}</div>
        <div class="user-profile-role">{{ authUser.role }}</div>
      </div>
      <v-spacer v-if="!isCollapsed"></v-spacer>
      <v-icon v-show="!isCollapsed" class="collapse-icon"
        >mdi-chevron-left</v-icon
      >
    </div>

    <v-divider class="main-divider"></v-divider>

    <!-- ══════════════════ NAVIGATION PRINCIPALE ══════════════════ -->
    <v-list density="compact" nav>
      <v-list-item
        prepend-icon="mdi-view-dashboard-variant-outline"
        title="Dashboard"
        to="/dashboard"
        :class="navItemClasses('/dashboard')"
      ></v-list-item>

      <v-list-item
        prepend-icon="mdi-headset"
        title="Workspace"
        to="/workspace"
        :class="navItemClasses('/workspace')"
      ></v-list-item>

      <!-- Groupe Opérations personnalisé -->
      <v-list-item
        prepend-icon="mdi-cogs"
        title="Opérations"
        @click="toggleGroup('Operations')"
        :class="navGroupActivatorClass('Operations')"
      >
        <template v-slot:append v-if="!isCollapsed">
          <v-icon
            :class="[
              'group-chevron',
              { 'group-chevron--open': openGroup === 'Operations' },
            ]"
            >mdi-chevron-down</v-icon
          >
        </template>
      </v-list-item>
      <v-expand-transition>
        <div v-show="openGroup === 'Operations'">
          <v-list-item
            prepend-icon="mdi-handshake-outline"
            title="Prestataires"
            to="/partners"
            :class="navItemClasses('/partners', ['nav-item--sub'])"
          ></v-list-item>
          <v-list-item
            prepend-icon="mdi-account-supervisor-circle-outline"
            title="Clients"
            to="/clients"
            :class="navItemClasses('/clients', ['nav-item--sub'])"
          ></v-list-item>
          <v-list-item
            prepend-icon="mdi-office-building-marker-outline"
            title="Sites"
            to="/sites"
            :class="navItemClasses('/sites', ['nav-item--sub'])"
          ></v-list-item>
          <v-list-item
            prepend-icon="mdi-card-account-details-outline"
            title="Agents"
            to="/agents"
            :class="navItemClasses('/agents', ['nav-item--sub'])"
          ></v-list-item>
          <v-list-item
            prepend-icon="mdi-card-account-phone-outline"
            title="Contacts"
            to="/contacts"
            :class="navItemClasses('/contacts', ['nav-item--sub'])"
          ></v-list-item>
        </div>
      </v-expand-transition>

      <!-- Groupe Configuration personnalisé -->
      <v-list-item
        prepend-icon="mdi-tune"
        title="Configuration"
        @click="toggleGroup('Configuration')"
        :class="navGroupActivatorClass('Configuration')"
      >
        <template v-slot:append v-if="!isCollapsed">
          <v-icon
            :class="[
              'group-chevron',
              { 'group-chevron--open': openGroup === 'Configuration' },
            ]"
            >mdi-chevron-down</v-icon
          >
        </template>
      </v-list-item>
      <v-expand-transition>
        <div v-show="openGroup === 'Configuration'">
          <v-list-item
            prepend-icon="mdi-account-group-outline"
            title="Utilisateurs"
            to="/users"
            :class="navItemClasses('/users', ['nav-item--sub'])"
          ></v-list-item>
        </div>
      </v-expand-transition>
    </v-list>

    <v-spacer></v-spacer>

    <!-- ══════════════════ ZONE BASSE ══════════════════ -->
    <v-divider class="main-divider"></v-divider>
    <v-list density="compact" nav>
      <v-list-item
        prepend-icon="mdi-logout"
        title="Déconnexion"
        @click="handleLogout"
        class="nav-item"
      >
      </v-list-item>
    </v-list>
  </v-navigation-drawer>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/store/auth";

const authStore = useAuthStore();
const router = useRouter();

const isCollapsed = ref(
  localStorage.getItem("permatel_drawer_collapsed") === "true",
);
const openGroup = ref(null);
const route = useRoute();

const navigationGroups = {
  Operations: ["/partners", "/clients", "/sites", "/agents", "/contacts"],
  Configuration: ["/users"],
};

const isRouteActive = (path) => {
  const currentPath = route.path || "";
  return currentPath === path || currentPath.startsWith(`${path}/`);
};

const isGroupOpen = (groupName) => openGroup.value === groupName;

const navItemClasses = (path, extra = []) => [
  "nav-item",
  ...extra,
  { "permatel-nav-item--active": isRouteActive(path) },
];

const navGroupActivatorClass = (groupName) => [
  "nav-item",
  "nav-group-activator",
  { "nav-group-activator--open": isGroupOpen(groupName) },
];

const toggleGroup = (groupName) => {
  if (openGroup.value === groupName) {
    openGroup.value = null;
  } else {
    openGroup.value = groupName;
  }
};

const onRailUpdate = (val) => {
  isCollapsed.value = val;
  localStorage.setItem("permatel_drawer_collapsed", String(val));
};

const authUser = computed(() => ({
  username: authStore.user?.username ? `@${authStore.user.username}` : "@—",
  fullName: authStore.user
    ? `${authStore.user.prenom ?? ""} ${authStore.user.nom ?? ""}`.trim() || "—"
    : "—",
  role: authStore.user?.role ?? "—",
  avatar: `https://api.dicebear.com/8.x/initials/svg?seed=${encodeURIComponent(
    authStore.user?.username ?? "P",
  )}&backgroundColor=00A8A8&textColor=ffffff&fontFamily=Fira%20Sans`,
}));

watch(isCollapsed, (newVal) => {
  if (newVal) {
    openGroup.value = null;
  }
});

watch(
  () => route.path,
  (newPath) => {
    const parentGroup = Object.keys(navigationGroups).find((group) =>
      navigationGroups[group].some((path) => newPath.startsWith(path)),
    );
    openGroup.value = parentGroup || null;
  },
  { immediate: true },
);

const handleLogout = async () => {
  await authStore.logout();
  router.push("/login");
};
</script>

<script>
export default {
  name: "SideMenue",
};
</script>

<style scoped>
/* ══════════════════ VARIABLES DE THÈME ══════════════════ */
:root {
  --drawer-bg: #15223a; /* Bleu nuit sombre */
  --drawer-text-primary: #eaf0f6; /* Blanc cassé */
  --drawer-text-secondary: #9fb0c9; /* Gris-bleu clair */
  --drawer-icon-secondary: #9fb0c9;
  --drawer-active-highlight: #00a8a8; /* Teal/Cyan pour icône et liseré */
  --drawer-active-item-bg: rgba(0, 168, 168, 0.1);
  --drawer-hover-bg: #ffffff0d;
  --drawer-divider-color: #9fb0c91a;
}

/* ══════════════════ STYLE DU DRAWER ══════════════════ */
.permatel-navigation-drawer {
  background-color: var(--drawer-bg) !important;
  border-right: none !important;
  color: var(--drawer-text-primary);
  transition: width 0.2s ease-in-out;
  --v-navigation-drawer-rail-width: 72px;
}

/* ══════════════════ ITEMS DE NAVIGATION ══════════════════ */
.nav-item {
  height: 44px;
  margin: 4px 12px;
  border-radius: 10px !important;
  padding-inline-start: 18px !important; /* Espace pour l'icône et le texte */
  transition:
    background-color 0.18s ease-out,
    color 0.18s ease-out;
  background-color: transparent !important;
}

.nav-item .v-list-item-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--drawer-text-secondary); /* Texte inactif est secondaire */
}

.nav-item .v-list-item__prepend > .v-icon {
  color: var(--drawer-icon-secondary);
  margin-inline-end: 18px !important;
  transition: color 0.18s ease-out;
}

.nav-item:hover {
  background-color: rgba(255, 255, 255, 0.05);
}
.nav-item:hover .v-list-item-title,
.nav-item:hover .v-list-item__prepend > .v-icon {
  color: var(--drawer-text-primary);
}

.nav-group-activator {
  padding-left: 16px !important;
}

.nav-group-activator .v-list-item-title {
  color: var(--drawer-text-primary);
}

.nav-group-activator .v-list-item__prepend > .v-icon {
  color: var(--drawer-text-secondary);
}

/* Style pour un groupe OUVERT (subtil) */
.nav-group-activator--open {
  color: var(--drawer-text-primary);
}
.nav-group-activator--open .v-list-item-title,
.nav-group-activator--open .v-list-item__prepend > .v-icon,
.nav-group-activator--open:hover .v-list-item-title {
  color: var(--drawer-text-primary) !important;
}

.nav-item--sub {
  margin: 2px 12px;
  padding-inline-start: 28px !important;
  background-color: transparent !important;
}

.nav-item--sub .v-list-item__prepend > .v-icon {
  margin-inline-end: 14px !important;
  font-size: 18px;
  color: #64768a;
}

.nav-item--sub .v-list-item-title {
  font-size: 0.82rem;
  color: var(--drawer-text-secondary);
}

/* Style pour l'item de navigation ACTIF (lien final, pas un groupe)
   On utilise la classe .v-list-item--active de Vuetify */
.nav-item.v-list-item--active:not(.nav-group-activator), .nav-item--sub.v-list-item--active {
  background-color: var(--drawer-active-item-bg) !important;
  position: relative;
}

/* Liseré gauche pour l'item actif */
.nav-item.v-list-item--active:not(.nav-group-activator)::before {
  content: "";
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  background-color: var(--drawer-active-highlight);
  border-radius: 0 3px 3px 0;
}

.nav-item.v-list-item--active:not(.nav-group-activator) .v-list-item-title,
.nav-item.v-list-item--active:not(.nav-group-activator) .v-list-item__prepend > .v-icon,
.nav-item--sub.v-list-item--active .v-list-item-title,
.nav-item--sub.v-list-item--active .v-list-item__prepend > .v-icon {
  color: var(--drawer-active-highlight) !important;
}

/* ══════════════════ GROUPES DE NAVIGATION ══════════════════ */
.nav-group-activator {
  margin: 4px 0;
}
.group-chevron {
  transition: transform 0.2s ease-in-out !important;
}
.group-chevron--open {
  transform: rotate(180deg);
}

.nav-item--sub {
  margin: 2px 12px;
  padding-inline-start: 28px !important; /* Indentation des sous-items */
  background-color: transparent !important;
}
.nav-item--sub .v-list-item__prepend > .v-icon {
  margin-inline-end: 16px !important;
  font-size: 18px;
}
.nav-item--sub .v-list-item-title {
  font-size: 0.8rem;
}

/* ══════════════════ ZONE BASSE ══════════════════ */
.main-divider {
  border-color: var(--drawer-divider-color) !important;
  margin: 8px 16px;
}

.user-profile-block {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  min-height: 64px;
  cursor: pointer;
  transition: background-color 0.15s ease-out;
}
.user-profile-block:hover {
  background-color: var(--drawer-hover-bg);
}
.user-profile-block--collapsed {
  justify-content: center;
  padding: 16px 0;
}
.user-profile-info {
  overflow: hidden;
  white-space: nowrap;
}
.user-profile-name {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--drawer-text-primary);
}
.user-profile-role {
  font-family: "Fira Code", monospace;
  font-size: 0.7rem;
  text-transform: uppercase;
  color: var(--drawer-text-secondary);
}

.collapse-icon {
  color: var(--drawer-text-secondary);
  transition: opacity 0.2s ease;
}

/* ══════════════════ SURCHARGE VUETIFY ══════════════════ */

/* Centrage parfait en mode réduit (rail) */
.v-navigation-drawer--rail .nav-item {
  width: 48px;
  padding: 0 !important;
  margin: 4px auto !important;
  justify-content: center;
}

.v-navigation-drawer--rail :deep(.v-list-item__prepend) {
  margin-inline-end: 0 !important;
}

.v-navigation-drawer--rail :deep(.v-list-item__prepend .v-icon) {
  margin-inline-end: 0 !important;
}

</style>
