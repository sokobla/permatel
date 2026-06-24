<template>
  <div class="pdf-card">
    <div class="pdf-hdr">
      <span class="pdf-hdr-marker"></span>
      <h2 class="pdf-title">Pointer une vacation</h2>
    </div>

    <div class="pdf-grid">
      <v-autocomplete
        v-model="agentId"
        :items="agents"
        item-title="label"
        item-value="id"
        label="Agent"
        prepend-inner-icon="mdi-shield-account-outline"
        density="compact"
        variant="outlined"
        hide-details
        :loading="loadingRefs"
        clearable
      />
      <v-autocomplete
        v-model="clientId"
        :items="clients"
        item-title="label"
        item-value="id"
        label="Client"
        prepend-inner-icon="mdi-domain"
        density="compact"
        variant="outlined"
        hide-details
        :loading="loadingRefs"
        clearable
        @update:model-value="onClientChange"
      />
      <v-autocomplete
        v-model="siteId"
        :items="filteredSites"
        item-title="label"
        item-value="id"
        label="Site"
        prepend-inner-icon="mdi-map-marker-outline"
        density="compact"
        variant="outlined"
        hide-details
        :disabled="!clientId"
        clearable
      />
    </div>

    <div class="pdf-actions">
      <v-btn
        color="#00a8a8"
        variant="flat"
        class="text-none"
        prepend-icon="mdi-play-circle-outline"
        :loading="loadingStart"
        :disabled="!canStart || loadingEnd"
        @click="onStart"
      >
        Débuter la vacation
      </v-btn>
      <v-btn
        color="#000b23"
        variant="flat"
        class="text-none"
        prepend-icon="mdi-stop-circle-outline"
        :loading="loadingEnd"
        :disabled="!agentId || loadingStart"
        @click="onEnd"
      >
        Terminer la vacation
      </v-btn>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import {
  startPriseDeService,
  endCurrentPriseDeService,
  fetchAgents,
  fetchClients,
  fetchSites,
} from "@/services/priseDeServiceService";

const emit = defineEmits(["changed", "notify"]);

const agents = ref([]);
const clients = ref([]);
const sites = ref([]);
const loadingRefs = ref(false);

const agentId = ref(null);
const clientId = ref(null);
const siteId = ref(null);

const loadingStart = ref(false);
const loadingEnd = ref(false);

const canStart = computed(() => !!(agentId.value && clientId.value && siteId.value));
const filteredSites = computed(() =>
  clientId.value ? sites.value.filter((s) => s.client_id === clientId.value) : sites.value,
);

function onClientChange() {
  // Réinitialise le site si plus cohérent avec le client choisi
  if (siteId.value && !filteredSites.value.some((s) => s.id === siteId.value)) {
    siteId.value = null;
  }
}

function notify(type, text) {
  emit("notify", { type, text });
}
function apiError(err, fallback) {
  return err?.response?.data?.error || fallback;
}

async function onStart() {
  if (!canStart.value) {
    notify("error", "Veuillez sélectionner un agent, un client et un site.");
    return;
  }
  loadingStart.value = true;
  try {
    await startPriseDeService({
      agent_id: agentId.value,
      client_id: clientId.value,
      site_id: siteId.value,
    });
    notify("success", "Vacation démarrée.");
    emit("changed");
  } catch (err) {
    notify("error", apiError(err, "Impossible de démarrer la vacation."));
  } finally {
    loadingStart.value = false;
  }
}

async function onEnd() {
  if (!agentId.value) {
    notify("error", "Sélectionnez l'agent dont la vacation doit être terminée.");
    return;
  }
  loadingEnd.value = true;
  try {
    await endCurrentPriseDeService(agentId.value);
    notify("success", "Vacation terminée.");
    emit("changed");
  } catch (err) {
    notify("error", apiError(err, "Aucune vacation en cours pour cet agent."));
  } finally {
    loadingEnd.value = false;
  }
}

onMounted(async () => {
  loadingRefs.value = true;
  try {
    [agents.value, clients.value, sites.value] = await Promise.all([
      fetchAgents(),
      fetchClients(),
      fetchSites(),
    ]);
  } catch {
    notify("error", "Échec du chargement des référentiels.");
  } finally {
    loadingRefs.value = false;
  }
});
</script>

<style scoped>
.pdf-card {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 3px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.pdf-hdr { display: flex; align-items: center; gap: 9px; }
.pdf-hdr-marker { width: 3px; height: 16px; background: #00a8a8; border-radius: 1px; }
.pdf-title {
  font-size: 0.95rem; font-weight: 800; letter-spacing: 0.08em;
  color: #000b23; text-transform: uppercase; margin: 0;
}
.pdf-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.pdf-actions { display: flex; gap: 10px; flex-wrap: wrap; }
@media (max-width: 720px) {
  .pdf-grid { grid-template-columns: 1fr; }
}
</style>
