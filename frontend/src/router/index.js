import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/store/auth";

// ─── Rôles ────────────────────────────────────────────────────────────────────
const ALL   = ["ADMIN", "MANAGER", "PERMANENCIER"];
const STAFF = ["ADMIN", "MANAGER"];
const ADMIN = ["ADMIN"];

// ─── Routes ───────────────────────────────────────────────────────────────────
const routes = [
  // Redirection racine : homeRoute si connecté, sinon /login
  {
    path: "/",
    redirect: () => {
      const authStore = useAuthStore();
      return authStore.isAuthenticated ? authStore.homeRoute : "/login";
    },
  },

  // Page publique
  {
    path: "/login",
    name: "Login",
    component: () => import("../views/LoginView.vue"),
    meta: { guestOnly: true },
  },

  // Sélection du tenant actif (authentifié, mais hors garde de tenant)
  {
    path: "/select-tenant",
    name: "SelectTenant",
    component: () => import("../views/SelectTenantView.vue"),
    meta: { requiresAuth: true, roles: ALL, skipTenantGuard: true },
  },

  // Acceptation d'invitation — page publique (accessible connecté ou non)
  {
    path: "/accept-invite",
    name: "AcceptInvite",
    component: () => import("../views/AcceptInviteView.vue"),
    meta: { skipTenantGuard: true },
  },

  // Gestion des membres du tenant (admin de tenant ou super-admin)
  {
    path: "/members",
    name: "Members",
    component: () => import("../views/TenantMembersView.vue"),
    meta: { requiresAuth: true, roles: ALL, requiresMemberAdmin: true },
  },

  // ── Accès tous rôles ────────────────────────────────────────────────────────
  {
    path: "/dashboard",
    name: "Dashboard",
    component: () => import("../views/DashboardView.vue"),
    meta: { requiresAuth: true, roles: ALL },
  },
  {
    path: "/workspace",
    name: "Workspace",
    component: () => import("../views/WorkspaceView.vue"),
    meta: { requiresAuth: true, roles: ALL },
  },
  {
    path: "/issues",
    name: "Anomalies",
    component: () => import("../views/AnomaliesView.vue"),
    meta: { requiresAuth: true, roles: ALL },
  },
  {
    path: "/orders",
    name: "Orders",
    component: () => import("../views/OrdersView.vue"),
    meta: { requiresAuth: true, roles: ALL },
  },
  {
    path: "/contacts",
    name: "Contacts",
    component: () => import("../views/ContactsView.vue"),
    meta: { requiresAuth: true, roles: ALL },
  },

  // ── Accès admin + manager ───────────────────────────────────────────────────
  {
    path: "/supervision",
    name: "Supervision",
    component: () => import("../views/SupervisionView.vue"),
    meta: { requiresAuth: true, roles: STAFF },
  },
  {
    path: "/clients",
    name: "Clients",
    component: () => import("../views/ClientsView.vue"),
    meta: { requiresAuth: true, roles: STAFF },
  },
  {
    path: "/sites",
    name: "Sites",
    component: () => import("../views/SitesView.vue"),
    meta: { requiresAuth: true, roles: STAFF },
  },
  {
    path: "/partners",
    name: "Partners",
    component: () => import("../views/PartnerView.vue"),
    meta: { requiresAuth: true, roles: STAFF },
  },
  {
    path: "/agents",
    name: "Agents",
    component: () => import("../views/AgentView.vue"),
    meta: { requiresAuth: true, roles: STAFF },
  },
  {
    path: "/reports",
    name: "Reports",
    component: () => import("../views/ReportView.vue"),
    meta: { requiresAuth: true, roles: STAFF },
  },

  // ── Accès admin uniquement ──────────────────────────────────────────────────
  {
    path: "/users",
    name: "Users",
    component: () => import("../views/UsersView.vue"),
    meta: { requiresAuth: true, roles: ADMIN },
  },
  {
    path: "/tenants",
    name: "Tenants",
    component: () => import("../views/TenantsView.vue"),
    meta: { requiresAuth: true, roles: ADMIN },
  },
  {
    // Configuration du tenant : déléguée à l'admin de tenant (et super-admin)
    path: "/parameters",
    name: "Settings",
    component: () => import("../views/SettingsView.vue"),
    meta: { requiresAuth: true, roles: ALL, requiresMemberAdmin: true },
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

// ─── Garde de navigation ──────────────────────────────────────────────────────
router.beforeEach((to, _from, next) => {
  const authStore      = useAuthStore();
  const authenticated  = authStore.isAuthenticated;
  const role           = authStore.user?.role ?? null;

  // 1. Route réservée aux guests : rediriger les utilisateurs déjà connectés
  if (to.meta.guestOnly) {
    return authenticated ? next(authStore.homeRoute) : next();
  }

  // 2. Route protégée — non authentifié
  if (to.meta.requiresAuth && !authenticated) {
    authStore.returnUrl = to.fullPath;
    return next({ name: "Login", query: { redirect: to.fullPath } });
  }

  // 3. Sélection de tenant requise → forcer l'écran dédié avant toute route métier
  if (authenticated && authStore.needsTenantSelection && !to.meta.skipTenantGuard) {
    return next({ name: "SelectTenant" });
  }
  // …et empêcher d'y accéder quand ce n'est pas (ou plus) nécessaire
  if (to.name === "SelectTenant" && authenticated && !authStore.needsTenantSelection) {
    return next(authStore.homeRoute);
  }

  // 4. RBAC — rôle insuffisant → renvoyer sur homeRoute
  if (to.meta.roles && role && !to.meta.roles.includes(role)) {
    return next(authStore.homeRoute);
  }

  // 5. Capacité d'administration du tenant (gestion des membres)
  if (to.meta.requiresMemberAdmin && !authStore.canManageMembers) {
    return next(authStore.homeRoute);
  }

  next();
});

export default router;
