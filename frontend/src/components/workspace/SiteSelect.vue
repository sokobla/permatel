<template>
  <div class="sts-root">
    <div :class="['sts-field', !clientId ? 'sts-field--disabled' : '']">
      <v-icon size="13" color="#aaa" class="sts-icon"
        >mdi-map-marker-outline</v-icon
      >
      <select
        v-model="selectedId"
        class="sts-select"
        :disabled="!clientId || loading"
        @change="onSelect"
      >
        <option value="">{{ placeholder }}</option>
        <option v-for="site in sites" :key="site.id" :value="site.id">
          {{ site.nom }}{{ site.ville ? ` — ${site.ville}` : "" }}
        </option>
      </select>
      <v-icon v-if="loading" size="12" class="sts-spin" color="#aaa"
        >mdi-loading</v-icon
      >
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import apiClient from "@/services/http/axios";

const props = defineProps({
  clientId: { type: Number, default: null },
});

const emit = defineEmits(["site-selected", "site-cleared"]);

const sites = ref([]);
const loading = ref(false);
const selectedId = ref("");

const placeholder = ref("— Sélectionner un site —");

async function loadSites(clientId) {
  if (!clientId) {
    sites.value = [];
    selectedId.value = "";
    return;
  }
  loading.value = true;
  try {
    const { data } = await apiClient.get(`/sites/client/${clientId}`);
    sites.value = data ?? [];
    if (sites.value.length === 0)
      placeholder.value = "Aucun site pour ce client";
    else placeholder.value = "— Sélectionner un site —";
  } catch {
    sites.value = [];
    placeholder.value = "Erreur de chargement";
  } finally {
    loading.value = false;
  }
}

function onSelect() {
  if (!selectedId.value) {
    emit("site-cleared");
    return;
  }
  const site = sites.value.find((s) => s.id === Number(selectedId.value));
  if (site) emit("site-selected", site);
}

watch(
  () => props.clientId,
  (newId) => {
    selectedId.value = "";
    emit("site-cleared");
    loadSites(newId);
  },
  { immediate: true },
);
</script>

<script>
export default { name: "SiteSelect" };
</script>

<style scoped>
.sts-root {
  width: 100%;
}

.sts-field {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 3px;
  background: #fff;
  transition: border-color 0.15s;
}

.sts-field:focus-within {
  border-color: #00a8a8;
}

.sts-field--disabled {
  background: rgba(0, 0, 0, 0.02);
  border-color: rgba(0, 0, 0, 0.07);
}

.sts-icon {
  flex-shrink: 0;
}

.sts-select {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  color: #000b23;
  cursor: pointer;
  min-width: 0;
}

.sts-select:disabled {
  color: #bbb;
  cursor: not-allowed;
}

.sts-spin {
  animation: sts-rotate 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes sts-rotate {
  to {
    transform: rotate(360deg);
  }
}
</style>
