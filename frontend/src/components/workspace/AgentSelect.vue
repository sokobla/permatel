<template>
  <div class="ags-root" ref="rootRef">
    <!-- Champ de recherche -->
    <div :class="['ags-field', open ? 'ags-field--open' : '']">
      <v-icon size="13" color="#aaa" class="ags-icon">mdi-account-hard-hat-outline</v-icon>
      <input
        ref="inputRef"
        v-model="query"
        class="ags-input"
        :placeholder="selectedLabel || 'Rechercher un agent…'"
        :class="{ 'ags-input--has-value': !!selectedLabel && !open }"
        autocomplete="off"
        @focus="onFocus"
        @input="onInput"
        @keydown.escape="close"
        @keydown.tab="close"
      />
      <button v-if="selectedId" class="ags-clear" tabindex="-1" @click.prevent="clear">
        <v-icon size="12">mdi-close</v-icon>
      </button>
    </div>

    <!-- Dropdown -->
    <div v-if="open" class="ags-dropdown">
      <div v-if="loading" class="ags-loading">
        <v-icon size="12" class="ags-spin" color="#aaa">mdi-loading</v-icon>
        Chargement…
      </div>
      <div v-else-if="results.length === 0" class="ags-empty">
        Aucun agent trouvé
      </div>
      <button
        v-for="agent in results"
        :key="agent.id"
        class="ags-item"
        tabindex="-1"
        @mousedown.prevent="select(agent)"
      >
        <span class="ags-item__name">{{ agent.prenom }} {{ agent.nom }}</span>
        <span class="ags-item__mat">{{ agent.matricule }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from "vue";
import apiClient from "@/services/http/axios";

const emit = defineEmits(["agent-selected", "agent-cleared"]);

const query      = ref("");
const results    = ref([]);
const loading    = ref(false);
const open       = ref(false);
const selectedId = ref(null);
const selectedLabel = ref("");

const rootRef  = ref(null);
const inputRef = ref(null);

let debounceTimer = null;

async function search(term = "") {
  loading.value = true;
  try {
    const params = { per_page: 20 };
    if (term) params.search = term;
    const { data } = await apiClient.get("/agents", { params });
    results.value = data.agents ?? [];
  } catch {
    results.value = [];
  } finally {
    loading.value = false;
  }
}

function onFocus() {
  open.value = true;
  if (results.value.length === 0) search(query.value);
}

function onInput() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => search(query.value), 250);
  open.value = true;
}

function select(agent) {
  selectedId.value = agent.id;
  selectedLabel.value = `${agent.prenom ?? ""} ${agent.nom ?? ""}`.trim();
  query.value = "";
  open.value = false;
  emit("agent-selected", agent);
}

function clear() {
  selectedId.value = null;
  selectedLabel.value = "";
  query.value = "";
  results.value = [];
  emit("agent-cleared");
}

function close() {
  open.value = false;
  query.value = "";
}

function onOutsideClick(e) {
  if (rootRef.value && !rootRef.value.contains(e.target)) close();
}

onMounted(() => document.addEventListener("mousedown", onOutsideClick));
onBeforeUnmount(() => document.removeEventListener("mousedown", onOutsideClick));
</script>

<script>
export default { name: "AgentSelect" };
</script>

<style scoped>
.ags-root {
  position: relative;
  width: 100%;
}

.ags-field {
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

.ags-field--open,
.ags-field:focus-within {
  border-color: #00a8a8;
}

.ags-icon { flex-shrink: 0; }

.ags-input {
  flex: 1;
  border: none;
  outline: none;
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  color: #000b23;
  background: transparent;
  min-width: 0;
}

.ags-input::placeholder {
  color: #bbb;
  font-size: 11px;
}

.ags-input--has-value::placeholder {
  color: #000b23;
  font-weight: 600;
}

.ags-clear {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.08);
  cursor: pointer;
  color: #666;
  flex-shrink: 0;
}
.ags-clear:hover { background: rgba(0, 0, 0, 0.15); }

/* ── Dropdown ──────────────────────────────────────────────── */

.ags-dropdown {
  position: absolute;
  top: calc(100% + 3px);
  left: 0;
  right: 0;
  z-index: 100;
  background: #fff;
  border: 1px solid rgba(0, 168, 168, 0.3);
  border-radius: 3px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  max-height: 200px;
  overflow-y: auto;
}

.ags-dropdown::-webkit-scrollbar { width: 3px; }
.ags-dropdown::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.12); border-radius: 2px; }

.ags-loading,
.ags-empty {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #aaa;
}

.ags-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 7px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  transition: background 0.1s;
}
.ags-item:last-child { border-bottom: none; }
.ags-item:hover { background: rgba(0, 168, 168, 0.05); }

.ags-item__name {
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  font-weight: 600;
  color: #000b23;
}

.ags-item__mat {
  font-family: "Fira Code", monospace;
  font-size: 10px;
  color: #aaa;
  flex-shrink: 0;
}

.ags-spin {
  animation: ags-rotate 0.8s linear infinite;
}

@keyframes ags-rotate {
  to { transform: rotate(360deg); }
}
</style>
