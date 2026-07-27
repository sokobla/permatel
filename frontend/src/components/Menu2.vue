<template>
  <v-navigation-drawer
    v-model="drawer"
    :rail="rail"
    :rail-width="wider ? 80 : undefined"
    permanent
    color="#000b23"
    theme="dark"
    @click="rail = false"
  >
    <v-list>
      <v-list-item
        :title="authUser.fullName"
        :subtitle="authUser.role"
      >
        <template v-slot:prepend>
          <v-avatar
            :class="{ 'mx-1': wider }"
            :size="wider && rail ? 40 : undefined"
            color="#00a8a8"
          >
            <v-img v-if="userAvatarUrl" :src="userAvatarUrl" alt="Avatar utilisateur" />
            <span v-else class="menu-avatar-initials">{{ userInitials }}</span>
          </v-avatar>
        </template>
        <template v-slot:append>
          <v-btn
            :inert="rail"
            icon="mdi-chevron-left"
            variant="text"
            @click.stop="rail = !rail"
          ></v-btn>
        </template>
      </v-list-item>
    </v-list>

    <v-divider></v-divider>

    <v-list density="compact" nav>
      <v-list-item
        v-for="item in visibleTopItems"
        :key="item.value"
        :class="{ 'pl-5': wider }"
        :prepend-icon="item.icon"
        :title="item.label"
        :to="item.value"
      ></v-list-item>

      <!-- Groupes (filtrés par rôle) -->
      <v-list-group
        v-for="group in visibleGroups"
        :key="group.value"
        :value="group.value"
      >
        <template v-slot:activator="{ props }">
          <v-list-item
            v-bind="props"
            :class="{ 'pl-5': wider }"
            :prepend-icon="group.icon"
            :title="group.label"
          ></v-list-item>
        </template>

        <v-list-item
          v-for="sub in group.children"
          :key="sub.value"
          :class="{ 'pl-5': wider }"
          :prepend-icon="sub.icon"
          :title="sub.label"
          :to="sub.value"
        ></v-list-item>
      </v-list-group>

      <v-list-item
        v-for="item in visibleBottomItems"
        :key="item.value"
        :class="{ 'pl-5': wider }"
        :prepend-icon="item.icon"
        :title="item.label"
        :to="item.value"
      ></v-list-item>
    </v-list>

    <!-- Footer : nom application + version -->
    <template v-slot:append>
      <div :class="['tn-menu-foot', { 'tn-menu-foot--rail': rail }]">
        <span class="tn-menu-foot__name">{{ rail ? "P" : APP_NAME }}</span>
        <span v-if="!rail" class="tn-menu-foot__ver">v{{ APP_VERSION }}</span>
      </div>
    </template>
  </v-navigation-drawer>
</template>

<script setup>
import { ref, computed } from "vue";

const drawer = ref(true);
const rail = ref(true);
const wider = ref(false);
import { useAuthStore } from "@/store/auth";

const authStore = useAuthStore();

// Identité applicative (footer du menu)
const APP_NAME = import.meta.env.VITE_APP_NAME ?? "PERMATEL";
const APP_VERSION = import.meta.env.VITE_APP_VERSION ?? "1.0.0";

// Avatar réel du tenant/utilisateur connecté (sinon initiales)
const BACKEND_ORIGIN = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api"
).replace(/\/api\/?$/, "");

const userAvatarUrl = computed(() => {
  const path = authStore.user?.avatar_url;
  if (!path) return null;
  return /^https?:\/\//.test(path) ? path : BACKEND_ORIGIN + path;
});

const userInitials = computed(() => {
  const u = authStore.user;
  const ini = `${u?.prenom?.[0] ?? ""}${u?.nom?.[0] ?? ""}`.trim();
  return (ini || u?.username?.slice(0, 2) || "?").toUpperCase();
});

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

// ─── RBAC : rôles autorisés par entrée ─────────────────────────────────────────
// roles absent ⇒ accessible à tous les rôles connectés.
const ALL = ["ADMIN", "MANAGER", "PERMANENCIER"];
const STAFF = ["ADMIN", "MANAGER"];
const ADMIN = ["ADMIN"];

const topItems = [
  {
    label: "Dashboard",
    icon: "mdi-view-dashboard",
    value: "/dashboard",
    roles: ALL,
  },
  {
    label: "Supervision",
    icon: "mdi-monitor-dashboard",
    value: "/supervision",
    roles: STAFF,
  },
  { label: "Workspace", icon: "mdi-headset", value: "/workspace", roles: ALL },
  {
    label: "Utilisateurs",
    icon: "mdi-account-supervisor-circle-outline",
    value: "/users",
    roles: ADMIN,
  },
];

const groups = [
  {
    label: "Opérations",
    icon: "mdi-cogs",
    value: "Operations",
    children: [
      {
        label: "Prestataires",
        icon: "mdi-handshake-outline",
        value: "/partners",
        roles: STAFF,
      },
      {
        label: "Clients",
        icon: "mdi-account-supervisor-circle-outline",
        value: "/clients",
        roles: STAFF,
      },
      {
        label: "Sites",
        icon: "mdi-office-building-marker-outline",
        value: "/sites",
        roles: STAFF,
      },
    ],
  },
  {
    label: "Ressources",
    icon: "mdi-account-group",
    value: "Resources",
    children: [
      {
        label: "Agents",
        icon: "mdi-handshake-outline",
        value: "/agents",
        roles: STAFF,
      },
      {
        label: "Contacts",
        icon: "mdi-account-supervisor-circle-outline",
        value: "/contacts",
        roles: ALL,
      },
    ],
  },
  {
    label: "Production",
    icon: "mdi-factory",
    value: "Production",
    children: [
      { label: "Anomalies", icon: "mdi-alert", value: "/issues", roles: ALL },
      {
        label: "Commandes",
        icon: "mdi-point-of-sale",
        value: "/orders",
        roles: ALL,
      },
      {
        label: "Prises de services",
        icon: "mdi-clock-start",
        value: "/shifts",
        roles: ALL,
      },
    ],
  },
  {
    label: "Configuration",
    icon: "mdi-cog",
    value: "Configuration",
    children: [
      {
        label: "Membres",
        icon: "mdi-account-multiple-outline",
        value: "/members",
        roles: ALL,
        requiresMemberAdmin: true,
      },
      {
        label: "Tenants",
        icon: "mdi-shield-account-outline",
        value: "/tenants",
        roles: ADMIN,
      },
      {
        label: "Paramètres",
        icon: "mdi-tune",
        value: "/parameters",
        roles: ALL,
        requiresMemberAdmin: true,
      },
    ],
  },
];

const bottomItems = [
  { label: "Rapports", icon: "mdi-chart-bar", value: "/reports", roles: STAFF },
];

// ─── Filtrage par rôle ─────────────────────────────────────────────────────────
const allowed = (item) => {
  if (item.requiresMemberAdmin && !authStore.canManageMembers) return false;
  return authStore.hasAnyRole(item.roles);
};

const visibleTopItems = computed(() => topItems.filter(allowed));
const visibleBottomItems = computed(() => bottomItems.filter(allowed));
const visibleGroups = computed(() =>
  groups
    .map((g) => ({ ...g, children: g.children.filter(allowed) }))
    .filter((g) => g.children.length > 0),
);
</script>

<style>
@import url("https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap");
@import url("https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200");

:root {
  --font-sans: "Fira Sans", sans-serif;
  --font-mono: "Fira Code", monospace;
}

aside {
  font-family: var(--font-sans);
}

.font-mono {
  font-family: var(--font-mono);
}

/* Initiales dans l'avatar du menu (fallback sans photo) */
.menu-avatar-initials {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.02em;
}

/* Footer du menu : nom application + version */
.tn-menu-foot {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 12px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.tn-menu-foot--rail {
  justify-content: center;
  padding: 12px 0;
}
.tn-menu-foot__name {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: rgba(255, 255, 255, 0.85);
  text-transform: uppercase;
}
.tn-menu-foot__ver {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-teal, #00a8a8);
}
</style>
