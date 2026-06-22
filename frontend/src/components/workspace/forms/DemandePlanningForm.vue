<template>
  <div class="df-root">

    <!-- ══ HEADER ════════════════════════════════════════════════════ -->
    <div class="pl-hdr">

      <p class="pl-ctx">
        <span>WORKSPACE</span>
        <span class="pl-ctx__sep">›</span>
        <span>NOUVELLE DEMANDE</span>
        <span class="pl-ctx__sep">›</span>
        <span class="pl-ctx__active">PLANNING</span>
      </p>

      <div class="pl-title-row">
        <div class="pl-title-left">
          <span class="pl-marker"></span>
          <h2 class="pl-title">GESTION PLANNING — MODIFICATION OPÉRATIONNELLE</h2>
        </div>
        <div class="pl-title-right">
          <div class="pl-meta-field">
            <span class="pl-meta-lbl">PRIORITÉ</span>
            <select v-model="form.priorite" class="pl-meta-select">
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

      <div class="pl-titre-row">
        <span class="pl-titre-lbl">INTITULÉ</span>
        <input
          id="pl-titre"
          v-model="form.titre"
          class="pl-titre-input"
          placeholder="Ex : Absence agent — site Nord"
          autocomplete="off"
        />
      </div>
    </div>

    <div v-if="submitError" class="df-error-bar">
      <v-icon size="13" color="#e74c3c">mdi-alert-circle-outline</v-icon>
      {{ submitError }}
    </div>

    <!-- ══ CORPS ════════════════════════════════════════════════════ -->
    <div class="pl-body">

      <!-- ─ Section : INFORMATIONS GÉNÉRALES ── -->
      <section class="pl-sec">
        <header class="pl-sec-hdr">
          <span class="pl-sec-mark pl-sec-mark--blue"></span>
          <span class="pl-sec-lbl">INFORMATIONS GÉNÉRALES</span>
          <span class="pl-sec-rule"></span>
        </header>
        <div class="pl-grid">
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
            <label class="form-label" for="pl-type">TYPE DE MODIFICATION</label>
            <select id="pl-type" v-model="form.type_modification" class="form-input">
              <option value="">— Sélectionner —</option>
              <option value="absence">Absence</option>
              <option value="conge">Congé</option>
              <option value="formation">Formation</option>
              <option value="reunion">Réunion</option>
              <option value="remplacement">Remplacement</option>
              <option value="autre">Autre</option>
            </select>
          </div>
          <div class="form-group pl-full">
            <label class="form-label" for="pl-desc">DESCRIPTION</label>
            <textarea
              id="pl-desc"
              v-model="form.description"
              class="form-input pl-textarea"
              rows="2"
              placeholder="Contexte de la modification planning..."
            ></textarea>
          </div>
        </div>
      </section>

      <!-- ─ Section : AGENTS & DATES ── -->
      <section class="pl-sec">
        <header class="pl-sec-hdr">
          <span class="pl-sec-mark pl-sec-mark--blue"></span>
          <span class="pl-sec-lbl">AGENTS & DATES</span>
          <span class="pl-sec-rule"></span>
        </header>
        <div class="pl-grid">
          <div class="form-group">
            <label class="form-label" for="pl-agent">ID AGENT CONCERNÉ</label>
            <input
              id="pl-agent"
              v-model.number="form.agent_concerne_id"
              type="number"
              class="form-input"
              placeholder="ID agent"
              min="1"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="pl-remplacant">ID AGENT REMPLAÇANT</label>
            <input
              id="pl-remplacant"
              v-model.number="form.agent_remplacant_id"
              type="number"
              class="form-input"
              placeholder="ID agent"
              min="1"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="pl-debut">DATE DÉBUT</label>
            <input
              id="pl-debut"
              v-model="form.date_debut"
              type="datetime-local"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="pl-fin">DATE FIN</label>
            <input
              id="pl-fin"
              v-model="form.date_fin"
              type="datetime-local"
              class="form-input"
            />
          </div>
          <div class="form-group pl-full">
            <label class="form-label" for="pl-motif">MOTIF</label>
            <textarea
              id="pl-motif"
              v-model="form.motif"
              class="form-input pl-textarea"
              rows="2"
              placeholder="Raison de la modification..."
            ></textarea>
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
  type_modification: "",
  agent_concerne_id: null,
  agent_remplacant_id: null,
  date_debut: "",
  date_fin: "",
  motif: "",
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
      type_demande: "planning",
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
export default { name: "DemandePlanningForm" };
</script>

<style scoped>
/* ══ HEADER ════════════════════════════════════════════════════════ */

.pl-hdr {
  flex-shrink: 0;
  padding: 10px 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.pl-ctx {
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

.pl-ctx__sep { color: #e0e0e0; }

.pl-ctx__active {
  color: #3498db;
  font-weight: 600;
}

.pl-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.pl-title-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.pl-marker {
  width: 3px;
  height: 18px;
  background: #3498db;
  border-radius: 1px;
  flex-shrink: 0;
}

.pl-title {
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

.pl-title-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.pl-meta-field {
  display: flex;
  align-items: center;
  gap: 6px;
}

.pl-meta-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
}

.pl-meta-select {
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
.pl-meta-select:focus { border-color: rgba(52, 152, 219, 0.4); }

.pl-titre-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
}

.pl-titre-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}

.pl-titre-input {
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
.pl-titre-input:focus { border-bottom-color: #3498db; }
.pl-titre-input::placeholder { color: #d0d0d0; font-size: 11px; font-weight: 400; }

/* ══ CORPS ════════════════════════════════════════════════════════ */

.pl-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pl-body::-webkit-scrollbar { width: 4px; }
.pl-body::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.12); border-radius: 2px; }

/* ══ SECTIONS ══════════════════════════════════════════════════════ */

.pl-sec {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pl-sec-hdr {
  display: flex;
  align-items: center;
  gap: 7px;
}

.pl-sec-mark {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  flex-shrink: 0;
}

.pl-sec-mark--blue { background: #3498db; }

.pl-sec-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9.5px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #aaa;
  text-transform: uppercase;
  white-space: nowrap;
}

.pl-sec-rule {
  flex: 1;
  height: 1px;
  background: rgba(0, 0, 0, 0.06);
}

/* ══ GRILLE ═══════════════════════════════════════════════════════ */

.pl-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
}

.pl-full { grid-column: 1 / -1; }

.pl-textarea {
  resize: vertical;
  min-height: 56px;
  line-height: 1.5;
}
</style>
