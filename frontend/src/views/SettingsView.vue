<template>
  <div class="set-page">
    <!-- En-tête -->
    <header class="set-head">
      <div>
        <h1 class="set-title">PARAMÈTRES</h1>
        <p class="set-sub">Configuration système et valeurs de référence.</p>
      </div>
    </header>

    <!-- Navigation des sections -->
    <v-tabs v-model="tab" color="#00a8a8" density="comfortable" class="set-tabs">
      <v-tab value="general" class="text-none"><v-icon start size="16">mdi-tune</v-icon>Général</v-tab>
      <v-tab value="smtp" class="text-none"><v-icon start size="16">mdi-email-arrow-right-outline</v-icon>SMTP</v-tab>
      <v-tab v-if="sections.imap" value="imap" class="text-none"><v-icon start size="16">mdi-email-arrow-left-outline</v-icon>IMAP</v-tab>
      <v-tab value="reference" class="text-none"><v-icon start size="16">mdi-format-list-bulleted</v-icon>Valeurs de référence</v-tab>
      <v-tab value="sla" class="text-none"><v-icon start size="16">mdi-timer-alert-outline</v-icon>SLA</v-tab>
      <v-tab v-if="sections.integrations" value="integrations" class="text-none"><v-icon start size="16">mdi-puzzle-outline</v-icon>Intégrations</v-tab>
    </v-tabs>

    <!-- Contenu (transition douce) -->
    <v-window v-model="tab" class="set-window">
      <v-window-item value="general" transition="fade-transition">
        <SettingsGeneral />
      </v-window-item>
      <v-window-item value="smtp" transition="fade-transition">
        <SettingsSmtp />
      </v-window-item>
      <v-window-item v-if="sections.imap" value="imap" transition="fade-transition">
        <SettingsImap />
      </v-window-item>
      <v-window-item value="reference" transition="fade-transition">
        <SettingsReferenceValues />
      </v-window-item>
      <v-window-item value="sla" transition="fade-transition">
        <SettingsSla />
      </v-window-item>
      <v-window-item v-if="sections.integrations" value="integrations" transition="fade-transition">
        <SettingsIntegrations />
      </v-window-item>
    </v-window>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth";
import SettingsGeneral from "@/components/settings/SettingsGeneral.vue";
import SettingsSmtp from "@/components/settings/SettingsSmtp.vue";
import SettingsImap from "@/components/settings/SettingsImap.vue";
import SettingsReferenceValues from "@/components/settings/SettingsReferenceValues.vue";
import SettingsSla from "@/components/settings/SettingsSla.vue";
import SettingsIntegrations from "@/components/settings/SettingsIntegrations.vue";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

// Sections disponibles (pilotées par les canaux du tenant). SMTP/Général/Référence toujours là.
const sections = computed(() => authStore.featureMap.settings_sections || {});
const availableTabs = computed(() => [
  "general", "smtp",
  ...(sections.value.imap ? ["imap"] : []),
  "reference", "sla",
  ...(sections.value.integrations ? ["integrations"] : []),
]);

// Onglet initial depuis ?tab= (deep-link), borné aux onglets disponibles.
const requested = route.query.tab;
const tab = ref(availableTabs.value.includes(requested) ? requested : "general");

// Garde l'URL synchronisée (partageable / rafraîchissable)
watch(tab, (t) => {
  if (route.query.tab !== t) router.replace({ query: { ...route.query, tab: t } });
});

// Si l'onglet courant devient indisponible (canal désactivé), retomber sur Général.
watch(availableTabs, (tabs) => {
  if (!tabs.includes(tab.value)) tab.value = "general";
});

onMounted(() => {
  if (!authStore.features) authStore.fetchFeatures();
});
</script>

<style scoped>
.set-page {
  font-family: "Fira Sans", sans-serif;
  background: #f2f2f2;
  min-height: 100%;
  padding: 24px;
  box-sizing: border-box;
}
.set-head { margin-bottom: 16px; }
.set-title { font-size: 18px; font-weight: 700; letter-spacing: 0.08em; color: #000b23; margin: 0; }
.set-sub { font-size: 12.5px; color: #6b7280; margin: 2px 0 0; }
.set-tabs { margin-bottom: 18px; border-bottom: 1px solid #e5e7eb; }
.set-window { max-width: 980px; }
</style>
