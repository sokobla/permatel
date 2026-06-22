<template>
  <!-- ────────────────────────────────────────────────────────────────────
       OPS-SIDEBAR: Navigation Drawer Gauche Redesigné
       ──────────────────────────────────────────────────────────────────── -->
  <aside class="ops-sidebar">
    <!-- ┌─ BLOC PROFIL ─┐ -->
    <div class="sidebar-profile">
      <div class="sidebar-profile__avatar">
        <img :src="profileAvatarUrl" :alt="`${authUser.username} avatar`" />
      </div>
      <div class="sidebar-profile__info">
        <div class="sidebar-profile__handle">{{ authUser.username }}</div>
        <div class="sidebar-profile__name">{{ authUser.fullName || authUser.nom }}</div>
        <div class="sidebar-profile__role">{{ formatRole(authUser.role) }}</div>
      </div>
    </div>

    <div class="sidebar-sep"></div>

    <!-- ┌─ MENU PRINCIPAL ─┐ -->
    <nav class="sidebar-nav">
      <!-- Dashboard -->
      <RouterLink to="/dashboard" class="snav-item">
        <v-icon size="15">mdi-view-dashboard-outline</v-icon>
        <span>DASHBOARD</span>
      </RouterLink>

      <!-- Utilisateurs -->
      <RouterLink to="/users" class="snav-item">
        <v-icon size="15">mdi-account-group-outline</v-icon>
        <span>UTILISATEURS</span>
      </RouterLink>

      <!-- Clients -->
      <RouterLink to="/clients" class="snav-item">
        <v-icon size="15">mdi-office-building-outline</v-icon>
        <span>CLIENTS</span>
      </RouterLink>

      <!-- Sites -->
      <RouterLink to="/sites" class="snav-item">
        <v-icon size="15">mdi-map-marker-outline</v-icon>
        <span>SITES</span>
      </RouterLink>

      <!-- Demandes -->
      <RouterLink to="/demandes" class="snav-item">
        <v-icon size="15">mdi-clipboard-list-outline</v-icon>
        <span>DEMANDES</span>
      </RouterLink>

      <!-- Séparateur -->
      <div class="sidebar-sep sidebar-sep--sm"></div>

      <!-- Paramètres -->
      <a class="snav-item">
        <v-icon size="15">mdi-cog-outline</v-icon>
        <span>PARAMÈTRES</span>
      </a>

      <!-- Déconnexion -->
      <a class="snav-item snav-item--danger" @click="handleLogout">
        <v-icon size="15">mdi-logout</v-icon>
        <span>DÉCONNEXION</span>
      </a>
    </nav>

    <!-- ┌─ FOOTER SIDEBAR ─┐ -->
    <div class="sidebar-footer">
      <div class="sidebar-footer__version">v{{ appVersion }}</div>
      <div class="sidebar-footer__status">
        <span class="status-dot" :class="{ 'status-dot--online': isOnline }"></span>
        {{ isOnline ? 'ONLINE' : 'OFFLINE' }}
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/authStore';

const router = useRouter();
const authStore = useAuthStore();
const isOnline = ref(true);
const appVersion = '1.1.0';

const authUser = computed(() => authStore.user || {
  username: 'Utilisateur',
  fullName: 'Utilisateur',
  role: 'USER'
});

const profileAvatarUrl = computed(() => {
  // Générer un avatar via initiales ou un service
  const initials = (authUser.value.username || 'U').substring(0, 2).toUpperCase();
  return `https://ui-avatars.com/api/?name=${initials}&background=0066ff&color=fff&size=64`;
});

/**
 * Formate le rôle pour l'affichage
 */
const formatRole = (role) => {
  const roleMap = {
    PERMANENCIER: 'Permanencier',
    MANAGER: 'Manager',
    ADMIN: 'Administrateur',
    USER: 'Utilisateur'
  };
  return roleMap[role] || role;
};

/**
 * Gestion de la déconnexion
 */
const handleLogout = async () => {
  try {
    // Appeler logout du store
    await authStore.logout();
    // Rediriger vers login
    await router.push('/login');
  } catch (error) {
    console.error('Erreur déconnexion:', error);
  }
};

/**
 * Détecter l'état en ligne/hors ligne
 */
const handleOnline = () => {
  isOnline.value = true;
};

const handleOffline = () => {
  isOnline.value = false;
};

onMounted(() => {
  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);
});

onBeforeUnmount(() => {
  window.removeEventListener('online', handleOnline);
  window.removeEventListener('offline', handleOffline);
});
</script>

<style scoped>
/* ═════════════════════════════════════════════════════════════════════
   OPS-SIDEBAR: Styles Modernes & Clairs
   ═════════════════════════════════════════════════════════════════════ */

.ops-sidebar {
  display: flex;
  flex-direction: column;
  width: 260px;
  height: 100vh;
  background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 100%);
  border-right: 1px solid #e9ecef;
  color: #495057;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', sans-serif;
  flex-shrink: 0;
  overflow-y: auto;
  overflow-x: hidden;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
}

/* Scrollbar personnalisée */
.ops-sidebar::-webkit-scrollbar {
  width: 6px;
}

.ops-sidebar::-webkit-scrollbar-track {
  background: transparent;
}

.ops-sidebar::-webkit-scrollbar-thumb {
  background: #dee2e6;
  border-radius: 3px;
}

.ops-sidebar::-webkit-scrollbar-thumb:hover {
  background: #adb5bd;
}

/* ┌─ PROFIL UTILISATEUR ─┐ */
.sidebar-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 12px;
  margin: 8px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 8px;
  border: 1px solid #e9ecef;
  transition: all 0.3s ease;
}

.sidebar-profile:hover {
  background: rgba(255, 255, 255, 1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.sidebar-profile__avatar {
  flex-shrink: 0;
}

.sidebar-profile__avatar img {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid #0066ff;
  object-fit: cover;
}

.sidebar-profile__info {
  flex: 1;
  min-width: 0;
}

.sidebar-profile__handle {
  font-size: 13px;
  font-weight: 600;
  color: #212529;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-profile__name {
  font-size: 12px;
  color: #6c757d;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-profile__role {
  font-size: 10px;
  color: #adb5bd;
  text-transform: uppercase;
  font-weight: 500;
  letter-spacing: 0.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ┌─ SÉPARATEURS ─┐ */
.sidebar-sep {
  height: 1px;
  background: linear-gradient(
    to right,
    transparent,
    #dee2e6 20%,
    #dee2e6 80%,
    transparent
  );
  margin: 12px 0;
}

.sidebar-sep--sm {
  margin: 8px 0;
}

/* ┌─ MENU NAVIGATION ─┐ */
.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-nav::-webkit-scrollbar {
  width: 6px;
}

.sidebar-nav::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-nav::-webkit-scrollbar-thumb {
  background: #dee2e6;
  border-radius: 3px;
}

/* Item navigation */
.snav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  color: #495057;
  text-decoration: none;
  border-radius: 6px;
  transition: all 0.2s ease;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.3px;
}

.snav-item:hover {
  background-color: #e9ecef;
  color: #212529;
}

/* Active link (router-link-exact-active) */
.snav-item.router-link-exact-active {
  background: linear-gradient(135deg, #0066ff 0%, #0052cc 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 102, 255, 0.2);
}

.snav-item.router-link-exact-active :deep(.v-icon) {
  color: white !important;
}

/* Danger state (logout) */
.snav-item--danger {
  color: #dc3545;
}

.snav-item--danger:hover {
  background-color: rgba(220, 53, 69, 0.1);
  color: #a02830;
}

.snav-item--danger:active {
  background-color: rgba(220, 53, 69, 0.2);
}

/* Icon styling */
.snav-item :deep(.v-icon) {
  color: inherit;
  flex-shrink: 0;
}

/* Text overflow handling */
.snav-item span {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ┌─ FOOTER SIDEBAR ─┐ */
.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  margin: 8px;
  border-top: 1px solid #e9ecef;
  font-size: 11px;
  color: #adb5bd;
  flex-shrink: 0;
  text-transform: uppercase;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.sidebar-footer__version {
  opacity: 0.7;
}

.sidebar-footer__status {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

/* Status indicator dot */
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #ffc107;
  animation: pulse 2s infinite;
  flex-shrink: 0;
}

.status-dot--online {
  background-color: #28a745;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .ops-sidebar {
    width: 240px;
  }

  .sidebar-profile__name,
  .sidebar-profile__role {
    display: none;
  }

  .snav-item span {
    font-size: 12px;
  }
}

/* Dark mode support (optionnel) */
@media (prefers-color-scheme: dark) {
  .ops-sidebar {
    background: linear-gradient(180deg, #1e1e1e 0%, #2a2a2a 100%);
    border-right-color: #3a3a3a;
    color: #b0b8c1;
  }

  .sidebar-profile {
    background: rgba(255, 255, 255, 0.05);
    border-color: #3a3a3a;
  }

  .sidebar-profile__handle {
    color: #e1e8ed;
  }

  .sidebar-profile__name,
  .sidebar-profile__role {
    color: #8a9aad;
  }

  .snav-item {
    color: #b0b8c1;
  }

  .snav-item:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: #e1e8ed;
  }

  .sidebar-sep {
    background: linear-gradient(
      to right,
      transparent,
      #3a3a3a 20%,
      #3a3a3a 80%,
      transparent
    );
  }

  .sidebar-footer {
    border-top-color: #3a3a3a;
    color: #8a9aad;
  }
}
</style>
