<template>
  <div class="ccb-root" ref="rootEl">

    <!-- Mode sélection (client existant ou recherche) -->
    <template v-if="!newMode">
      <div class="ccb-search-row">
        <div class="ccb-input-wrap">
          <v-icon size="12" class="ccb-search-icon">mdi-magnify</v-icon>
          <input
            ref="inputEl"
            v-model="query"
            class="ccb-input"
            :placeholder="selectedClient ? selectedClient.nom : 'Rechercher un client…'"
            :class="{ 'ccb-input--filled': selectedClient }"
            autocomplete="off"
            @focus="onFocus"
            @input="onInput"
            @keydown.escape="close"
            @keydown.enter.prevent="selectHighlighted"
            @keydown.down.prevent="moveDown"
            @keydown.up.prevent="moveUp"
          />
          <button
            v-if="selectedClient"
            type="button"
            class="ccb-clear-btn"
            title="Effacer la sélection"
            @click="clearSelection"
          >
            <v-icon size="11">mdi-close</v-icon>
          </button>
        </div>

        <!-- Dropdown résultats -->
        <div v-if="open && (results.length || loading || query.length >= 2)" class="ccb-dropdown">
          <div v-if="loading" class="ccb-dropdown__loader">
            <span class="ccb-spinner"></span> Recherche…
          </div>
          <template v-else>
            <button
              v-for="(client, i) in results"
              :key="client.id"
              type="button"
              class="ccb-item"
              :class="{ 'ccb-item--hi': i === highlighted }"
              @mouseenter="highlighted = i"
              @click="selectClient(client)"
            >
              <span class="ccb-item__name">{{ client.nom }}</span>
              <span class="ccb-item__code">{{ client.code_client }}</span>
            </button>
            <div v-if="!results.length && query.length >= 2" class="ccb-dropdown__empty">
              <span>Aucun résultat pour « {{ query }} »</span>
              <button type="button" class="ccb-new-btn" @click="enterNewMode">
                <v-icon size="11">mdi-plus</v-icon>
                Créer ce client
              </button>
            </div>
          </template>
        </div>
      </div>

      <!-- Client sélectionné : affichage condensé -->
      <div v-if="selectedClient" class="ccb-selected-badge">
        <v-icon size="10" color="#27ae60">mdi-check-circle-outline</v-icon>
        <span>{{ selectedClient.nom }}</span>
        <span class="ccb-selected-badge__code">{{ selectedClient.code_client }}</span>
      </div>
    </template>

    <!-- Mode nouveau client -->
    <template v-else>
      <div class="ccb-new-header">
        <v-icon size="11" color="#27ae60">mdi-domain-plus</v-icon>
        <span>NOUVEAU CLIENT</span>
        <button type="button" class="ccb-back-btn" @click="exitNewMode">
          <v-icon size="11">mdi-arrow-left</v-icon>
          Rechercher
        </button>
      </div>
      <div class="bc-grid">
        <div class="form-group">
          <label class="form-label" for="ccb-nom">
            RAISON SOCIALE <span class="df-required">*</span>
          </label>
          <input
            id="ccb-nom"
            v-model="newClient.nom"
            class="form-input"
            placeholder="Nom de l'entreprise"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="ccb-code">
            CODE CLIENT <span class="df-required">*</span>
          </label>
          <input
            id="ccb-code"
            v-model="newClient.code_client"
            class="form-input"
            placeholder="Ex: CLI-001"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="ccb-siret">SIRET</label>
          <input
            id="ccb-siret"
            v-model="newClient.siret"
            class="form-input"
            placeholder="000 000 000 00000"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="ccb-tel">TÉLÉPHONE</label>
          <input
            id="ccb-tel"
            v-model="newClient.telephone"
            type="tel"
            class="form-input"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="ccb-email">EMAIL</label>
          <input
            id="ccb-email"
            v-model="newClient.email"
            type="email"
            class="form-input"
            autocomplete="off"
          />
        </div>
        <div class="form-group bc-full">
          <label class="form-label" for="ccb-adresse">ADRESSE</label>
          <input
            id="ccb-adresse"
            v-model="newClient.adresse"
            class="form-input"
            placeholder="N° rue, code postal, ville"
            autocomplete="off"
          />
        </div>
        <div v-if="newError" class="ccb-new-error bc-full">{{ newError }}</div>
        <div class="bc-full ccb-new-actions">
          <button
            type="button"
            class="ccb-new-save-btn"
            :disabled="saving"
            @click="saveNewClient"
          >
            <span v-if="saving" class="btn-submit__spinner"></span>
            ENREGISTRER LE CLIENT
          </button>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from "vue";
import { searchClients, createClient } from "@/services/clientService";

const props = defineProps({
  modelValue: { type: Number, default: null },
});
const emit = defineEmits(["update:modelValue", "client-selected", "client-cleared"]);

// ─── État ────────────────────────────────────────────────────────────────────
const rootEl = ref(null);
const inputEl = ref(null);
const query = ref("");
const results = ref([]);
const loading = ref(false);
const open = ref(false);
const highlighted = ref(-1);
const selectedClient = ref(null);

const newMode = ref(false);
const saving = ref(false);
const newError = ref("");
const newClient = ref({ nom: "", code_client: "", siret: "", telephone: "", email: "", adresse: "" });

// ─── Debounce search ─────────────────────────────────────────────────────────
let searchTimer = null;

function onInput() {
  selectedClient.value = null;
  emit("update:modelValue", null);
  emit("client-cleared");
  highlighted.value = -1;
  open.value = true;
  clearTimeout(searchTimer);
  if (query.value.length < 2) {
    results.value = [];
    return;
  }
  loading.value = true;
  searchTimer = setTimeout(async () => {
    try {
      const { clients } = await searchClients({ search: query.value, perPage: 8 });
      results.value = clients;
    } catch {
      results.value = [];
    } finally {
      loading.value = false;
    }
  }, 280);
}

function onFocus() {
  if (query.value.length >= 2) open.value = true;
}

function close() {
  open.value = false;
  highlighted.value = -1;
}

function moveDown() {
  if (!open.value) return;
  highlighted.value = Math.min(highlighted.value + 1, results.value.length - 1);
}

function moveUp() {
  highlighted.value = Math.max(highlighted.value - 1, 0);
}

function selectHighlighted() {
  if (highlighted.value >= 0 && results.value[highlighted.value]) {
    selectClient(results.value[highlighted.value]);
  }
}

function selectClient(client) {
  selectedClient.value = client;
  query.value = "";
  open.value = false;
  emit("update:modelValue", client.id);
  emit("client-selected", client);
}

function clearSelection() {
  selectedClient.value = null;
  query.value = "";
  results.value = [];
  emit("update:modelValue", null);
  emit("client-cleared");
  inputEl.value?.focus();
}

// ─── Nouveau client ───────────────────────────────────────────────────────────
function enterNewMode() {
  newClient.value = {
    nom: query.value.trim(),
    code_client: "",
    siret: "",
    telephone: "",
    email: "",
    adresse: "",
  };
  newError.value = "";
  close();
  newMode.value = true;
}

function exitNewMode() {
  newMode.value = false;
  query.value = "";
}

async function saveNewClient() {
  newError.value = "";
  if (!newClient.value.nom.trim()) {
    newError.value = "La raison sociale est requise.";
    return;
  }
  if (!newClient.value.code_client.trim()) {
    newError.value = "Le code client est requis.";
    return;
  }
  saving.value = true;
  try {
    const created = await createClient(newClient.value);
    selectClient(created);
    newMode.value = false;
  } catch (err) {
    newError.value = err?.response?.data?.error ?? "Erreur lors de la création.";
  } finally {
    saving.value = false;
  }
}

// ─── Clic en dehors ──────────────────────────────────────────────────────────
function onClickOutside(e) {
  if (rootEl.value && !rootEl.value.contains(e.target)) close();
}
onMounted(() => document.addEventListener("mousedown", onClickOutside));
onBeforeUnmount(() => document.removeEventListener("mousedown", onClickOutside));
</script>

<script>
export default { name: "ClientCombobox" };
</script>

<style scoped>
.ccb-root { position: relative; }

/* ── Ligne de recherche ── */
.ccb-search-row { position: relative; }

.ccb-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.ccb-search-icon {
  position: absolute;
  left: 8px;
  color: #bbb;
  pointer-events: none;
}

.ccb-input {
  width: 100%;
  height: 28px;
  padding: 0 28px 0 26px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #000b23;
  background: #fff;
  outline: none;
  transition: border-color 0.15s;
}

.ccb-input:focus { border-color: rgba(0, 168, 168, 0.45); }

.ccb-input--filled {
  border-color: rgba(39, 174, 96, 0.35);
  background: rgba(39, 174, 96, 0.02);
}

.ccb-clear-btn {
  position: absolute;
  right: 6px;
  background: none;
  border: none;
  cursor: pointer;
  color: #bbb;
  line-height: 1;
  padding: 0;
}
.ccb-clear-btn:hover { color: #555; }

/* ── Dropdown ── */
.ccb-dropdown {
  position: absolute;
  top: calc(100% + 3px);
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 3px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  z-index: 200;
  max-height: 220px;
  overflow-y: auto;
}

.ccb-dropdown__loader {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 12px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  color: #aaa;
}

.ccb-spinner {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid rgba(0, 168, 168, 0.2);
  border-top-color: #00a8a8;
  border-radius: 50%;
  animation: ccb-spin 0.7s linear infinite;
}
@keyframes ccb-spin { to { transform: rotate(360deg); } }

.ccb-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 7px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}
.ccb-item:hover,
.ccb-item--hi { background: rgba(0, 168, 168, 0.06); }

.ccb-item__name {
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 600;
  color: #000b23;
}
.ccb-item__code {
  font-family: "Fira Code", monospace;
  font-size: 9.5px;
  color: #aaa;
}

.ccb-dropdown__empty {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  color: #aaa;
}

.ccb-new-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 24px;
  padding: 0 10px;
  border: 1px solid #27ae60;
  border-radius: 3px;
  background: rgba(39, 174, 96, 0.05);
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 700;
  color: #27ae60;
  cursor: pointer;
  align-self: flex-start;
}
.ccb-new-btn:hover { background: rgba(39, 174, 96, 0.1); }

/* ── Badge client sélectionné ── */
.ccb-selected-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: 5px;
  padding: 3px 7px;
  background: rgba(39, 174, 96, 0.06);
  border: 1px solid rgba(39, 174, 96, 0.2);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 600;
  color: #1a7a3c;
}
.ccb-selected-badge__code {
  font-family: "Fira Code", monospace;
  font-size: 9px;
  color: #27ae60;
  opacity: 0.7;
}

/* ── Nouveau client ── */
.ccb-new-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 0 10px;
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #27ae60;
  text-transform: uppercase;
}

.ccb-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  background: none;
  border: none;
  font-family: "Fira Sans", sans-serif;
  font-size: 9.5px;
  color: #aaa;
  cursor: pointer;
}
.ccb-back-btn:hover { color: #555; }

.ccb-new-error {
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  color: #e74c3c;
  padding: 4px 0;
}

.ccb-new-actions {
  display: flex;
  justify-content: flex-end;
}

.ccb-new-save-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 14px;
  border: none;
  border-radius: 3px;
  background: #27ae60;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.ccb-new-save-btn:hover:not(:disabled) { background: #219a52; }
.ccb-new-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
