<template>
  <div class="cg-root">
    <div class="cg-card">
      <div class="cg-icon"><v-icon size="30" :color="iconColor">{{ icon }}</v-icon></div>
      <h3 class="cg-title">{{ title }}</h3>
      <p class="cg-text">{{ message }}</p>

      <v-btn
        v-if="canConfigure"
        :color="ctaColor"
        variant="flat"
        class="text-none cg-cta"
        :append-icon="'mdi-arrow-right'"
        @click="goConfigure"
      >
        {{ ctaLabel }}
      </v-btn>
      <p v-else class="cg-note">
        Contactez un administrateur pour activer cette fonctionnalité.
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth";

const props = defineProps({
  // 'locked' : dépendance indisponible (ex. Slack inactif)
  // 'config' : dépendance à configurer (ex. SMTP non renseigné)
  variant: { type: String, default: "config" },
  title: { type: String, required: true },
  message: { type: String, required: true },
  icon: { type: String, default: "mdi-cog-outline" },
  ctaLabel: { type: String, default: "Ouvrir les paramètres" },
  settingsTab: { type: String, default: null }, // 'smtp' | 'integrations'
});

const router = useRouter();
const authStore = useAuthStore();

// Seul un ADMIN peut atteindre la page Paramètres (route /parameters).
const canConfigure = computed(() => authStore.isAdmin);
const iconColor = computed(() => (props.variant === "locked" ? "#9aa0aa" : "#f39c12"));
const ctaColor = computed(() => (props.variant === "locked" ? "#15223a" : "#00a8a8"));

function goConfigure() {
  router.push({ path: "/parameters", query: props.settingsTab ? { tab: props.settingsTab } : {} });
}
</script>

<style scoped>
.cg-root {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 320px;
  padding: 32px;
  font-family: "Fira Sans", sans-serif;
}
.cg-card {
  max-width: 420px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.cg-icon {
  width: 64px; height: 64px; border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
  background: #f2f4f6; margin-bottom: 4px;
}
.cg-title { font-size: 16px; font-weight: 700; color: #000b23; margin: 0; }
.cg-text { font-size: 13px; color: #6b7280; line-height: 1.55; margin: 0 0 8px; }
.cg-cta { min-width: 200px; }
.cg-note { font-size: 12px; color: #9aa0aa; font-style: italic; margin: 0; }
</style>
