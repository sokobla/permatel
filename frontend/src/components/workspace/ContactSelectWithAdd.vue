<template>
  <div class="csa-root">

    <template v-if="!addMode">
      <div class="csa-select-row">
        <select
          v-model="internalValue"
          class="form-input csa-select"
          :disabled="!clientId || loading"
          @change="onSelectChange"
        >
          <option value="">
            {{ loading ? "Chargement…" : clientId ? "— Sélectionner un contact —" : "— Sélectionner d'abord un client —" }}
          </option>
          <option v-for="c in contacts" :key="c.id" :value="c.id">
            {{ c.prenom }} {{ c.nom }}{{ c.fonction ? ` — ${c.fonction}` : "" }}
          </option>
        </select>
        <button
          type="button"
          class="csa-add-btn"
          :disabled="!clientId"
          title="Ajouter un contact"
          @click="openAddMode"
        >
          <v-icon size="13">mdi-plus</v-icon>
        </button>
      </div>

      <!-- Info contact sélectionné -->
      <div v-if="selectedContact" class="csa-info">
        <span v-if="selectedContact.telephone" class="csa-info__item">
          <v-icon size="10" color="#bbb">mdi-phone</v-icon>
          {{ selectedContact.telephone }}
        </span>
        <span v-if="selectedContact.email" class="csa-info__item">
          <v-icon size="10" color="#bbb">mdi-email-outline</v-icon>
          {{ selectedContact.email }}
        </span>
      </div>
    </template>

    <!-- Mini-formulaire ajout contact -->
    <template v-else>
      <div class="csa-add-header">
        <v-icon size="11" color="#00a8a8">mdi-account-plus-outline</v-icon>
        <span>NOUVEAU CONTACT</span>
        <button type="button" class="csa-back-btn" @click="closeAddMode">
          <v-icon size="11">mdi-arrow-left</v-icon>
          Retour
        </button>
      </div>
      <div class="bc-grid">
        <div class="form-group">
          <label class="form-label" for="csa-prenom">PRÉNOM</label>
          <input
            id="csa-prenom"
            v-model="newContact.prenom"
            class="form-input"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="csa-nom">
            NOM <span class="df-required">*</span>
          </label>
          <input
            id="csa-nom"
            v-model="newContact.nom"
            class="form-input"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="csa-fonction">FONCTION</label>
          <input
            id="csa-fonction"
            v-model="newContact.fonction"
            class="form-input"
            placeholder="Directeur sécurité…"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="csa-tel2">TÉLÉPHONE</label>
          <input
            id="csa-tel2"
            v-model="newContact.telephone"
            type="tel"
            class="form-input"
            autocomplete="off"
          />
        </div>
        <div class="form-group bc-full">
          <label class="form-label" for="csa-email2">EMAIL</label>
          <input
            id="csa-email2"
            v-model="newContact.email"
            type="email"
            class="form-input"
            autocomplete="off"
          />
        </div>
        <div v-if="addError" class="csa-error bc-full">{{ addError }}</div>
        <div class="bc-full csa-add-actions">
          <button
            type="button"
            class="csa-save-btn"
            :disabled="saving"
            @click="saveContact"
          >
            <span v-if="saving" class="btn-submit__spinner"></span>
            CRÉER LE CONTACT
          </button>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { getContactsForClient, createContact } from "@/services/contactService";

const props = defineProps({
  modelValue: { type: Number, default: null },
  clientId: { type: Number, default: null },
});
const emit = defineEmits(["update:modelValue", "contact-selected"]);

const contacts = ref([]);
const loading = ref(false);
const internalValue = ref(props.modelValue ?? "");
const selectedContact = ref(null);

const addMode = ref(false);
const saving = ref(false);
const addError = ref("");
const newContact = ref({ prenom: "", nom: "", fonction: "", telephone: "", email: "" });

// Charger les contacts quand le client change
watch(
  () => props.clientId,
  async (id) => {
    contacts.value = [];
    internalValue.value = "";
    selectedContact.value = null;
    emit("update:modelValue", null);
    if (!id) return;
    loading.value = true;
    try {
      const { contacts: list } = await getContactsForClient(id);
      contacts.value = list;
      if (list.length) {
        internalValue.value = list[0].id;
        selectedContact.value = list[0];
        emit("update:modelValue", list[0].id);
        emit("contact-selected", list[0]);
      }
    } catch {
      contacts.value = [];
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

function onSelectChange() {
  const found = contacts.value.find((c) => c.id === internalValue.value);
  selectedContact.value = found ?? null;
  emit("update:modelValue", internalValue.value || null);
  if (found) emit("contact-selected", found);
}

function openAddMode() {
  newContact.value = { prenom: "", nom: "", fonction: "", telephone: "", email: "" };
  addError.value = "";
  addMode.value = true;
}

function closeAddMode() {
  addMode.value = false;
}

async function saveContact() {
  addError.value = "";
  if (!newContact.value.nom.trim()) {
    addError.value = "Le nom est requis.";
    return;
  }
  saving.value = true;
  try {
    const created = await createContact({
      ...newContact.value,
      client_id: props.clientId,
      type: "Client",
    });
    contacts.value.push(created);
    internalValue.value = created.id;
    selectedContact.value = created;
    emit("update:modelValue", created.id);
    emit("contact-selected", created);
    addMode.value = false;
  } catch (err) {
    addError.value = err?.response?.data?.error ?? "Erreur lors de la création.";
  } finally {
    saving.value = false;
  }
}
</script>

<script>
export default { name: "ContactSelectWithAdd" };
</script>

<style scoped>
.csa-root { display: flex; flex-direction: column; gap: 5px; }

.csa-select-row { display: flex; gap: 6px; align-items: center; }

.csa-select { flex: 1; }

.csa-add-btn {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 3px;
  background: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #555;
  transition: background 0.12s, border-color 0.12s;
}
.csa-add-btn:hover:not(:disabled) {
  background: rgba(0, 168, 168, 0.06);
  border-color: rgba(0, 168, 168, 0.4);
  color: #00a8a8;
}
.csa-add-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.csa-info {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 2px 0;
}
.csa-info__item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  color: #888;
}

/* ── Ajout contact ── */
.csa-add-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 0 8px;
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #00a8a8;
  text-transform: uppercase;
}

.csa-back-btn {
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
.csa-back-btn:hover { color: #555; }

.csa-error {
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  color: #e74c3c;
}

.csa-add-actions { display: flex; justify-content: flex-end; }

.csa-save-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 14px;
  border: none;
  border-radius: 3px;
  background: #00a8a8;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.csa-save-btn:hover:not(:disabled) { background: #008f8f; }
.csa-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
