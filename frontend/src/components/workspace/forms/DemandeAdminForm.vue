<template>
  <div class="df-root">

    <!-- ══ HEADER ════════════════════════════════════════════════════ -->
    <div class="ad-hdr">

      <p class="ad-ctx">
        <span>WORKSPACE</span>
        <span class="ad-ctx__sep">›</span>
        <span>NOUVELLE DEMANDE</span>
        <span class="ad-ctx__sep">›</span>
        <span class="ad-ctx__active">ADMINISTRATIF</span>
      </p>

      <div class="ad-title-row">
        <div class="ad-title-left">
          <span class="ad-marker"></span>
          <h2 class="ad-title">DEMANDE ADMINISTRATIVE — TRAITEMENT INTERNE</h2>
        </div>
        <div class="ad-title-right">
          <div class="ad-meta-field">
            <span class="ad-meta-lbl">PRIORITÉ</span>
            <select v-model="form.priorite" class="ad-meta-select">
              <option value="basse">Basse</option>
              <option value="normale">Normale</option>
              <option value="haute">Haute</option>
              <option value="urgente">Urgente</option>
            </select>
          </div>
          <button class="df-close-btn" title="Fermer" @click="emit('cancel')">
            <v-icon size="15">mdi-close</v-icon>
          </button>
        </div>
      </div>

      <div class="ad-titre-row">
        <span class="ad-titre-lbl">INTITULÉ</span>
        <input
          id="ad-titre"
          v-model="form.titre"
          class="ad-titre-input"
          placeholder="Ex : Validation contrat prestataire"
          autocomplete="off"
        />
      </div>
    </div>

    <div v-if="submitError" class="df-error-bar">
      <v-icon size="13" color="#e74c3c">mdi-alert-circle-outline</v-icon>
      {{ submitError }}
    </div>

    <!-- ══ CORPS ════════════════════════════════════════════════════ -->
    <div class="ad-body">

      <!-- ─ Section : INFORMATIONS GÉNÉRALES ── -->
      <section class="ad-sec">
        <header class="ad-sec-hdr">
          <span class="ad-sec-mark ad-sec-mark--purple"></span>
          <span class="ad-sec-lbl">INFORMATIONS GÉNÉRALES</span>
          <span class="ad-sec-rule"></span>
        </header>
        <div class="ad-grid">
          <div class="form-group">
            <label class="form-label">
              CLIENT <span class="df-required">*</span>
            </label>
            <ClientCombobox
              @client-selected="onClientSelected"
              @client-cleared="onClientCleared"
            />
          </div>
          <div class="form-group">
            <label class="form-label">CONTACT</label>
            <ContactSelectWithAdd
              v-model="form.contact_id"
              :client-id="form.client_id"
              @contact-selected="onContactSelected"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="ad-categorie">CATÉGORIE</label>
            <select id="ad-categorie" v-model="form.categorie" class="form-input">
              <option value="">— Sélectionner —</option>
              <option value="ressources_humaines">Ressources humaines</option>
              <option value="comptabilite">Comptabilité</option>
              <option value="contrat">Contrat</option>
              <option value="politique">Politique</option>
              <option value="autre">Autre</option>
            </select>
          </div>
          <div class="form-group ad-full">
            <label class="form-label" for="ad-desc">DESCRIPTION</label>
            <textarea
              id="ad-desc"
              v-model="form.description"
              class="form-input ad-textarea"
              rows="2"
              placeholder="Contexte et objectif de la demande..."
            ></textarea>
          </div>
        </div>
      </section>

      <!-- ─ Section : DÉTAILS ADMINISTRATIFS ── -->
      <section class="ad-sec">
        <header class="ad-sec-hdr">
          <span class="ad-sec-mark ad-sec-mark--purple"></span>
          <span class="ad-sec-lbl">DÉTAILS ADMINISTRATIFS</span>
          <span class="ad-sec-rule"></span>
        </header>
        <div class="ad-grid">
          <div class="form-group">
            <label class="form-label" for="ad-doctype">TYPE DE DOCUMENT</label>
            <select id="ad-doctype" v-model="form.document_type" class="form-input">
              <option value="">— Sélectionner —</option>
              <option value="contrat">Contrat</option>
              <option value="facture">Facture</option>
              <option value="rapport">Rapport</option>
              <option value="demande_officielle">Demande officielle</option>
              <option value="approbation">Approbation</option>
              <option value="autre">Autre</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="ad-echeance">DATE ÉCHÉANCE</label>
            <input
              id="ad-echeance"
              v-model="form.date_echeance"
              type="date"
              class="form-input"
            />
          </div>
          <div class="ad-full">
            <div class="ad-checkbox-row">
              <input
                id="ad-validation"
                v-model="form.validation_requise"
                type="checkbox"
                class="df-checkbox"
              />
              <label for="ad-validation" class="df-checkbox-label">
                Validation hiérarchique requise
              </label>
            </div>
          </div>
        </div>
      </section>

    </div>

    <!-- ══ FOOTER ════════════════════════════════════════════════════ -->
    <div class="df-footer">
      <button class="df-btn-cancel" :disabled="submitting" @click="emit('cancel')">
        ANNULER
      </button>
      <button class="btn-submit" :disabled="submitting" @click="submit">
        <span v-if="submitting" class="btn-submit__spinner"></span>
        ENREGISTRER
      </button>
    </div>

  </div>
</template>

<script setup>
import { ref } from "vue";
import { createDemande } from "@/services/demandeService";
import ClientCombobox from "@/components/workspace/ClientCombobox.vue";
import ContactSelectWithAdd from "@/components/workspace/ContactSelectWithAdd.vue";

const props = defineProps({ contactId: { type: Number, default: null } });
const emit = defineEmits(["submitted", "cancel"]);

const submitting = ref(false);
const submitError = ref("");

function onClientSelected(client) {
  form.value.client_id = client.id;
}
function onClientCleared() {
  form.value.client_id = null;
  form.value.contact_id = null;
}
function onContactSelected(contact) {
  form.value.contact_id = contact?.id ?? null;
}

const form = ref({
  titre: "",
  description: "",
  client_id: null,
  priorite: "normale",
  contact_id: props.contactId,
  categorie: "",
  document_type: "",
  date_echeance: "",
  validation_requise: false,
});

async function submit() {
  submitError.value = "";
  if (!form.value.titre.trim()) {
    submitError.value = "L'intitulé est requis.";
    return;
  }
  if (!form.value.client_id) {
    submitError.value = "Veuillez sélectionner ou créer un client.";
    return;
  }
  submitting.value = true;
  try {
    const demande = await createDemande({
      type_demande: "admin",
      ...form.value,
    });
    emit("submitted", demande);
  } catch (err) {
    submitError.value =
      err?.response?.data?.error ?? "Erreur lors de la création.";
  } finally {
    submitting.value = false;
  }
}
</script>

<script>
export default { name: "DemandeAdminForm" };
</script>

<style scoped>
/* ══ HEADER ════════════════════════════════════════════════════════ */

.ad-hdr {
  flex-shrink: 0;
  padding: 10px 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.ad-ctx {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: "Fira Code", monospace;
  font-size: 9px;
  letter-spacing: 0.1em;
  color: #ccc;
  text-transform: uppercase;
  margin: 0 0 8px;
}

.ad-ctx__sep { color: #e0e0e0; }

.ad-ctx__active {
  color: #8e44ad;
  font-weight: 600;
}

.ad-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.ad-title-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.ad-marker {
  width: 3px;
  height: 18px;
  background: #8e44ad;
  border-radius: 1px;
  flex-shrink: 0;
}

.ad-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #000b23;
  text-transform: uppercase;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ad-title-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.ad-meta-field {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ad-meta-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
}

.ad-meta-select {
  height: 24px;
  padding: 0 6px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.07em;
  color: #333;
  background: #fff;
  cursor: pointer;
  outline: none;
}
.ad-meta-select:focus { border-color: rgba(142, 68, 173, 0.4); }

.ad-titre-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
}

.ad-titre-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}

.ad-titre-input {
  flex: 1;
  height: 26px;
  padding: 0 4px;
  border: none;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 0;
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 500;
  color: #000b23;
  background: transparent;
  outline: none;
  transition: border-bottom-color 0.15s;
}
.ad-titre-input:focus { border-bottom-color: #8e44ad; }
.ad-titre-input::placeholder { color: #d0d0d0; font-size: 11px; font-weight: 400; }

/* ══ CORPS ════════════════════════════════════════════════════════ */

.ad-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ad-body::-webkit-scrollbar { width: 4px; }
.ad-body::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.12); border-radius: 2px; }

/* ══ SECTIONS ══════════════════════════════════════════════════════ */

.ad-sec {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ad-sec-hdr {
  display: flex;
  align-items: center;
  gap: 7px;
}

.ad-sec-mark {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  flex-shrink: 0;
}

.ad-sec-mark--purple { background: #8e44ad; }

.ad-sec-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9.5px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #aaa;
  text-transform: uppercase;
  white-space: nowrap;
}

.ad-sec-rule {
  flex: 1;
  height: 1px;
  background: rgba(0, 0, 0, 0.06);
}

/* ══ GRILLE ═══════════════════════════════════════════════════════ */

.ad-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
}

.ad-full { grid-column: 1 / -1; }

.ad-textarea {
  resize: vertical;
  min-height: 56px;
  line-height: 1.5;
}

.ad-checkbox-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 4px 0;
}
</style>
