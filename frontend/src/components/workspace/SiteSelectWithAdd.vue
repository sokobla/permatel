<template>
  <div class="ssa-root">

    <!-- ── Sélecteur de mode (existant / nouveau permanent / ponctuel) ── -->
    <template v-if="!addMode">
      <div class="ssa-select-row">
        <select
          v-model="internalValue"
          class="form-input ssa-select"
          :disabled="!clientId || loading"
          @change="onSelectChange"
        >
          <option value="">
            {{ loading ? "Chargement…" : clientId ? "— Sélectionner un site —" : "— Sélectionner d'abord un client —" }}
          </option>
          <option v-for="s in sites" :key="s.id" :value="String(s.id)">
            {{ s.nom }}{{ s.ville ? ` — ${s.ville}` : "" }}
          </option>
          <option value="__new__">＋ Nouveau site permanent</option>
          <option value="__ponctuel__">✎ Site ponctuel (saisie libre)</option>
        </select>
      </div>

      <!-- Affichage auto-fill site existant -->
      <div v-if="selectedSite" class="ssa-autofill">
        <div class="form-group bc-full">
          <label class="form-label">ADRESSE DU SITE</label>
          <input
            :value="[selectedSite.adresse, selectedSite.code_postal, selectedSite.ville].filter(Boolean).join(', ')"
            class="form-input ssa-readonly"
            readonly
          />
        </div>
        <div class="form-group">
          <label class="form-label">TYPE DE SITE</label>
          <input
            :value="TYPE_SITE_LABELS[selectedSite.type_site] ?? selectedSite.type_site ?? '—'"
            class="form-input ssa-readonly"
            readonly
          />
        </div>
      </div>

      <!-- Saisie libre site ponctuel -->
      <div v-if="poncuel" class="ssa-ponctuel">
        <div class="ssa-badge ssa-badge--info">
          <v-icon size="10" color="#888">mdi-information-outline</v-icon>
          Site ponctuel — aucune fiche créée en base
        </div>
        <div class="form-group bc-full">
          <label class="form-label" for="ssa-addr-p">
            ADRESSE DU SITE <span class="df-required">*</span>
          </label>
          <input
            id="ssa-addr-p"
            v-model="poncuelAddr"
            class="form-input"
            placeholder="Adresse complète du site d'intervention"
            autocomplete="off"
            @input="emitResolved"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="ssa-type-p">TYPE DE SITE</label>
          <select id="ssa-type-p" v-model="poncuelType" class="form-input" @change="emitResolved">
            <option value="">— Sélectionner —</option>
            <option v-for="(lbl, val) in TYPE_SITE_LABELS" :key="val" :value="val">{{ lbl }}</option>
          </select>
        </div>
      </div>
    </template>

    <!-- ── Formulaire nouveau site permanent ── -->
    <template v-else>
      <div class="ssa-add-header">
        <v-icon size="11" color="#3498db">mdi-map-marker-plus-outline</v-icon>
        <span>NOUVEAU SITE PERMANENT</span>
        <button type="button" class="ssa-back-btn" @click="closeAddMode">
          <v-icon size="11">mdi-arrow-left</v-icon>
          Retour
        </button>
      </div>
      <div class="bc-grid">
        <div class="form-group">
          <label class="form-label" for="ssa-nom">
            NOM DU SITE <span class="df-required">*</span>
          </label>
          <input
            id="ssa-nom"
            v-model="newSite.nom"
            class="form-input"
            placeholder="Ex: Entrepôt Nord"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="ssa-code">
            CODE SITE <span class="df-required">*</span>
          </label>
          <input
            id="ssa-code"
            v-model="newSite.code_site"
            class="form-input"
            placeholder="Ex: SIT-001"
            autocomplete="off"
          />
        </div>
        <div class="form-group bc-full">
          <label class="form-label" for="ssa-adresse">
            ADRESSE <span class="df-required">*</span>
          </label>
          <input
            id="ssa-adresse"
            v-model="newSite.adresse"
            class="form-input"
            placeholder="N° rue, code postal, ville"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="ssa-ville">VILLE</label>
          <input
            id="ssa-ville"
            v-model="newSite.ville"
            class="form-input"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="ssa-cp">CODE POSTAL</label>
          <input
            id="ssa-cp"
            v-model="newSite.code_postal"
            class="form-input"
            autocomplete="off"
          />
        </div>
        <div class="form-group bc-full">
          <label class="form-label" for="ssa-type-n">TYPE DE SITE</label>
          <select id="ssa-type-n" v-model="newSite.type_site" class="form-input">
            <option value="">— Sélectionner —</option>
            <option v-for="(lbl, val) in TYPE_SITE_LABELS" :key="val" :value="val">{{ lbl }}</option>
          </select>
        </div>
        <div v-if="addError" class="ssa-error bc-full">{{ addError }}</div>
        <div class="bc-full ssa-add-actions">
          <button
            type="button"
            class="ssa-save-btn"
            :disabled="saving"
            @click="saveSite"
          >
            <span v-if="saving" class="btn-submit__spinner"></span>
            CRÉER LE SITE
          </button>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { getSitesForClient, createSite } from "@/services/siteService";

const TYPE_SITE_LABELS = {
  bureau: "Bureau / Siège social",
  entrepot: "Entrepôt / Logistique",
  commerce: "Commerce / Grande surface",
  chantier: "Chantier",
  evenement: "Site événementiel",
  residentiel: "Résidentiel",
  industriel: "Industriel",
  autre: "Autre",
};

const props = defineProps({
  modelValue: { type: Number, default: null },
  clientId: { type: Number, default: null },
});
const emit = defineEmits(["update:modelValue", "site-resolved"]);

const sites = ref([]);
const loading = ref(false);
const internalValue = ref("");
const selectedSite = ref(null);
const poncuel = ref(false);
const poncuelAddr = ref("");
const poncuelType = ref("");

const addMode = ref(false);
const saving = ref(false);
const addError = ref("");
const newSite = ref({ nom: "", code_site: "", adresse: "", ville: "", code_postal: "", type_site: "" });

// Charger les sites quand le client change
watch(
  () => props.clientId,
  async (id) => {
    reset();
    if (!id) return;
    loading.value = true;
    try {
      const { sites: list } = await getSitesForClient(id);
      sites.value = list;
    } catch {
      sites.value = [];
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

function reset() {
  sites.value = [];
  internalValue.value = "";
  selectedSite.value = null;
  poncuel.value = false;
  poncuelAddr.value = "";
  poncuelType.value = "";
  emit("update:modelValue", null);
  emit("site-resolved", { site_id: null, adresse_intervention: null, mode: null });
}

function onSelectChange() {
  selectedSite.value = null;
  poncuel.value = false;
  addMode.value = false;

  if (internalValue.value === "__new__") {
    newSite.value = { nom: "", code_site: "", adresse: "", ville: "", code_postal: "", type_site: "" };
    addError.value = "";
    addMode.value = true;
    internalValue.value = "";
    return;
  }

  if (internalValue.value === "__ponctuel__") {
    poncuel.value = true;
    poncuelAddr.value = "";
    poncuelType.value = "";
    emit("update:modelValue", null);
    emit("site-resolved", { site_id: null, adresse_intervention: "", mode: "ponctuel" });
    return;
  }

  const id = parseInt(internalValue.value, 10);
  const found = sites.value.find((s) => s.id === id);
  if (found) {
    selectedSite.value = found;
    emit("update:modelValue", found.id);
    emit("site-resolved", {
      site_id: found.id,
      adresse_intervention: null,
      mode: "existant",
      siteData: found,
    });
  }
}

function emitResolved() {
  emit("site-resolved", {
    site_id: null,
    adresse_intervention: poncuelAddr.value,
    mode: "ponctuel",
    type_site: poncuelType.value,
  });
}

function closeAddMode() {
  addMode.value = false;
  internalValue.value = "";
}

async function saveSite() {
  addError.value = "";
  if (!newSite.value.nom.trim()) { addError.value = "Le nom du site est requis."; return; }
  if (!newSite.value.code_site.trim()) { addError.value = "Le code site est requis."; return; }
  if (!newSite.value.adresse.trim()) { addError.value = "L'adresse est requise."; return; }
  saving.value = true;
  try {
    const created = await createSite({ ...newSite.value, client_id: props.clientId });
    sites.value.push(created);
    internalValue.value = String(created.id);
    selectedSite.value = created;
    addMode.value = false;
    emit("update:modelValue", created.id);
    emit("site-resolved", {
      site_id: created.id,
      adresse_intervention: null,
      mode: "nouveau",
      siteData: created,
    });
  } catch (err) {
    addError.value = err?.response?.data?.error ?? "Erreur lors de la création.";
  } finally {
    saving.value = false;
  }
}
</script>

<script>
export default { name: "SiteSelectWithAdd" };
</script>

<style scoped>
.ssa-root { display: flex; flex-direction: column; gap: 8px; }

.ssa-select-row { display: flex; gap: 6px; }
.ssa-select { flex: 1; }

/* Site existant readonly */
.ssa-autofill { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; }

.ssa-readonly {
  background: rgba(0, 0, 0, 0.02) !important;
  color: #666 !important;
  cursor: default;
}

/* Ponctuel */
.ssa-ponctuel { display: flex; flex-direction: column; gap: 8px; }

.ssa-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 9px;
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  align-self: flex-start;
}
.ssa-badge--info {
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.08);
  color: #777;
}

/* Formulaire nouveau site */
.ssa-add-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 0 8px;
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #3498db;
  text-transform: uppercase;
}

.ssa-back-btn {
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
.ssa-back-btn:hover { color: #555; }

.ssa-error {
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  color: #e74c3c;
}

.ssa-add-actions { display: flex; justify-content: flex-end; }

.ssa-save-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 14px;
  border: none;
  border-radius: 3px;
  background: #3498db;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.ssa-save-btn:hover:not(:disabled) { background: #2a82c4; }
.ssa-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
