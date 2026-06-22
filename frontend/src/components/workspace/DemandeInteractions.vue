<template>
  <section class="di-sec">
    <!-- Section header -->
    <header class="di-hdr">
      <span class="di-mark"></span>
      <span class="di-lbl">SUIVI &amp; INTERACTIONS</span>
      <span v-if="interactions.length" class="di-count">{{
        interactions.length
      }}</span>
      <span class="di-rule"></span>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="di-state">
      <v-icon size="14" color="#ccc" class="di-spin">mdi-loading</v-icon>
      <span>Chargement…</span>
    </div>

    <!-- Error -->
    <div v-else-if="loadError" class="di-state di-state--err">
      <v-icon size="12" color="#e74c3c">mdi-alert-circle-outline</v-icon>
      {{ loadError }}
    </div>

    <!-- Empty -->
    <div v-else-if="interactions.length === 0" class="di-state di-state--empty">
      <v-icon size="22" color="#e0e0e0">mdi-comment-text-outline</v-icon>
      <span>Aucune interaction enregistrée</span>
    </div>

    <!-- Timeline -->
    <div v-else class="di-timeline">
      <div v-for="item in interactions" :key="item.id" class="di-item">
        <span :class="['di-dot', `di-dot--${item.type_interaction}`]"></span>
        <div class="di-item-body">
          <div class="di-item-meta">
            <span :class="['di-type', `di-type--${item.type_interaction}`]">
              {{ TYPE_LABELS[item.type_interaction] ?? item.type_interaction }}
            </span>
            <span v-if="item.contact_nom" class="di-contact-tag">
              <v-icon size="9">mdi-account-outline</v-icon>
              {{ item.contact_nom }}
            </span>
            <span class="di-author">{{ item.user_nom ?? "—" }}</span>
            <span class="di-date">{{ formatDate(item.created_at) }}</span>
          </div>
          <p class="di-text">{{ item.contenu }}</p>
          <!-- Changement de statut -->
          <div
            v-if="
              item.type_interaction === 'changement_statut' &&
              item.nouveau_statut
            "
            class="di-statut-change"
          >
            <span
              v-if="item.ancien_statut"
              :class="[
                'di-statut-chip',
                `di-statut-chip--${item.ancien_statut}`,
              ]"
            >
              {{ STATUT_LABELS[item.ancien_statut] ?? item.ancien_statut }}
            </span>
            <v-icon v-if="item.ancien_statut" size="10" color="#ccc"
              >mdi-arrow-right</v-icon
            >
            <span
              :class="[
                'di-statut-chip',
                `di-statut-chip--${item.nouveau_statut}`,
              ]"
            >
              {{ STATUT_LABELS[item.nouveau_statut] ?? item.nouveau_statut }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Formulaire ajout -->
    <div class="di-form" ref="formRef">
      <!-- Contact -->
      <div class="di-form-contact">
        <!-- chip verrouillé (contexte workspace) -->
        <div v-if="prefilledContactId" class="di-contact-chip">
          <v-icon size="10" color="#00a8a8">mdi-account-outline</v-icon>
          {{ prefilledContactNom ?? `Contact #${prefilledContactId}` }}
        </div>

        <!-- sélecteur avec ajout (contexte édition) -->
        <ContactSelectWithAdd
          v-else
          v-model="selectedContactId"
          :client-id="clientId"
          @contact-selected="onContactSelected"
        />
      </div>

      <div class="di-form-row">
        <!-- Type -->
        <select
          v-model="form.type_interaction"
          class="di-select di-select--type"
        >
          <option value="note">Note</option>
          <option value="appel">Appel</option>
          <option value="email">Email</option>
          <option value="whatsapp">WhatsApp</option>
        </select>
      </div>

      <textarea
        ref="textareaRef"
        v-model="form.contenu"
        class="di-textarea"
        :placeholder="PLACEHOLDERS[form.type_interaction]"
        rows="3"
        :disabled="submitting"
      ></textarea>

      <div v-if="submitError" class="di-submit-err">
        <v-icon size="10" color="#e74c3c">mdi-alert-circle-outline</v-icon>
        {{ submitError }}
      </div>

      <div class="di-form-actions">
        <button
          class="di-btn-submit"
          :disabled="submitting || !form.contenu.trim()"
          @click="submit"
        >
          <v-icon v-if="submitting" size="11" class="di-spin"
            >mdi-loading</v-icon
          >
          <v-icon v-else size="11">mdi-plus</v-icon>
          {{ submitting ? "ENREGISTREMENT…" : "AJOUTER" }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { getInteractions } from "@/services/demandeService";
import { createInteraction } from "@/services/interactionService";
import ContactSelectWithAdd from "@/components/workspace/ContactSelectWithAdd.vue";

const props = defineProps({
  demandeId: { type: Number, required: true },
  clientId: { type: Number, default: null },
  prefilledContactId: { type: Number, default: null },
  prefilledContactNom: { type: String, default: null },
});

const TYPE_LABELS = {
  appel: "Appel",
  email: "Email",
  whatsapp: "WhatsApp",
  note: "Note",
  changement_statut: "Statut",
};

const STATUT_LABELS = {
  nouvelle: "Nouvelle",
  en_cours: "En cours",
  en_attente: "En attente",
  resolue: "Résolue",
  cloturee: "Clôturée",
  annulee: "Annulée",
};

const PLACEHOLDERS = {
  note: "Note interne…",
  appel: "Résumé de l'appel téléphonique…",
  email: "Contenu ou résumé de l'email…",
  whatsapp: "Contenu du message WhatsApp…",
};

const interactions = ref([]);
const loading = ref(false);
const loadError = ref("");
const selectedContactId = ref(null);
const resolvedContact = ref(null);
const form = reactive({ type_interaction: "note", contenu: "" });
const submitting = ref(false);
const submitError = ref("");
const textareaRef = ref(null);
const formRef = ref(null);

async function fetchInteractions() {
  loading.value = true;
  loadError.value = "";
  try {
    interactions.value = await getInteractions(props.demandeId);
  } catch {
    loadError.value = "Impossible de charger les interactions.";
  } finally {
    loading.value = false;
  }
}

function onContactSelected(contact) {
  resolvedContact.value = contact ?? null;
}

async function submit() {
  if (!form.contenu.trim()) return;
  submitting.value = true;
  submitError.value = "";
  const contactId = props.prefilledContactId ?? selectedContactId.value ?? null;
  try {
    const created = await createInteraction(props.demandeId, {
      type_interaction: form.type_interaction,
      contenu: form.contenu.trim(),
      contact_id: contactId,
    });
    const fallbackNom =
      props.prefilledContactNom ??
      (resolvedContact.value
        ? `${resolvedContact.value.prenom ?? ""} ${resolvedContact.value.nom ?? ""}`.trim()
        : null);
    interactions.value.unshift({
      ...created,
      user_nom: null,
      contact_nom: created.contact_nom ?? fallbackNom ?? null,
    });
    form.contenu = "";
  } catch {
    submitError.value = "Erreur lors de l'enregistrement.";
  } finally {
    submitting.value = false;
  }
}

function focusForm() {
  formRef.value?.scrollIntoView({ behavior: "smooth", block: "start" });
  setTimeout(() => textareaRef.value?.focus(), 180);
}

defineExpose({ focusForm });

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return (
    d.toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
    }) +
    " " +
    d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
  );
}

onMounted(() => {
  fetchInteractions();
});
</script>

<script>
export default { name: "DemandeInteractions" };
</script>

<style scoped>
/* ── Section ─────────────────────────────────────────────────────────── */
.di-sec {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── Header ──────────────────────────────────────────────────────────── */
.di-hdr {
  display: flex;
  align-items: center;
  gap: 7px;
}

.di-mark {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  background: #3498db;
  flex-shrink: 0;
}

.di-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #aaa;
  text-transform: uppercase;
  white-space: nowrap;
}

.di-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  border-radius: 9px;
  background: rgba(52, 152, 219, 0.12);
  font-family: "Fira Code", monospace;
  font-size: 9px;
  font-weight: 700;
  color: #3498db;
}

.di-rule {
  flex: 1;
  height: 1px;
  background: rgba(0, 0, 0, 0.06);
}

/* ── States ──────────────────────────────────────────────────────────── */
.di-state {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 0;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #bbb;
}
.di-state--err {
  color: #e74c3c;
}
.di-state--empty {
  flex-direction: column;
  gap: 5px;
  padding: 14px 0;
  font-size: 10.5px;
}

/* ── Timeline ────────────────────────────────────────────────────────── */
.di-timeline {
  display: flex;
  flex-direction: column;
  border-left: 2px solid rgba(0, 0, 0, 0.06);
  margin-left: 5px;
  padding-left: 12px;
}

.di-item {
  position: relative;
  display: flex;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}
.di-item:last-child {
  border-bottom: none;
}

.di-dot {
  position: absolute;
  left: -17px;
  top: 12px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 2px solid #fff;
  flex-shrink: 0;
  background: #ccc;
}
.di-dot--appel {
  background: #3498db;
}
.di-dot--email {
  background: #00a8a8;
}
.di-dot--whatsapp {
  background: #27ae60;
}
.di-dot--note {
  background: #8e44ad;
}
.di-dot--changement_statut {
  background: #f39c12;
}

.di-item-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.di-item-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.di-type {
  font-family: "Fira Code", monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 2px 6px;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.05);
  color: #555;
}
.di-type--appel {
  background: rgba(52, 152, 219, 0.1);
  color: #1a73c1;
}
.di-type--email {
  background: rgba(0, 168, 168, 0.1);
  color: #007a7a;
}
.di-type--whatsapp {
  background: rgba(39, 174, 96, 0.1);
  color: #1e8449;
}
.di-type--note {
  background: rgba(142, 68, 173, 0.1);
  color: #7d3c98;
}
.di-type--changement_statut {
  background: rgba(243, 156, 18, 0.1);
  color: #b7770d;
}

.di-contact-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 600;
  color: #00a8a8;
  background: rgba(0, 168, 168, 0.07);
  padding: 1px 6px;
  border-radius: 10px;
}

.di-author {
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 600;
  color: #888;
}

.di-date {
  font-family: "Fira Code", monospace;
  font-size: 9px;
  color: #bbb;
  margin-left: auto;
  white-space: nowrap;
}

.di-text {
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  color: #444;
  line-height: 1.5;
  margin: 0;
  word-break: break-word;
}

/* Changement statut */
.di-statut-change {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 2px;
}

.di-statut-chip {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 2px 7px;
  border-radius: 10px;
}
.di-statut-chip--nouvelle {
  background: #eaf4fb;
  color: #1a73c1;
}
.di-statut-chip--en_cours {
  background: rgba(0, 168, 168, 0.1);
  color: #007a7a;
}
.di-statut-chip--en_attente {
  background: #fef9e7;
  color: #b7770d;
}
.di-statut-chip--resolue {
  background: #eafaf1;
  color: #1e8449;
}
.di-statut-chip--cloturee {
  background: #f4f6f7;
  color: #707b7c;
}
.di-statut-chip--annulee {
  background: rgba(231, 76, 60, 0.07);
  color: #c0392b;
}

/* ── Formulaire ──────────────────────────────────────────────────────── */
.di-form {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.02);
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 4px;
}

.di-form-contact {
  width: 100%;
}

.di-form-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

/* Contact verrouillé */
.di-contact-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 10px;
  border-radius: 13px;
  background: rgba(0, 168, 168, 0.08);
  border: 1px solid rgba(0, 168, 168, 0.2);
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 600;
  color: #00a8a8;
  white-space: nowrap;
  flex-shrink: 0;
}

.di-select {
  height: 26px;
  padding: 0 7px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 3px;
  background: #fff;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #444;
  cursor: pointer;
  outline: none;
}
.di-select:focus {
  border-color: #00a8a8;
}
.di-select--type {
  width: 100%;
}

.di-textarea {
  width: 100%;
  padding: 7px 9px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  color: #333;
  resize: vertical;
  outline: none;
  box-sizing: border-box;
  min-height: 68px;
  background: #fff;
  transition: border-color 0.12s;
}
.di-textarea:focus {
  border-color: #00a8a8;
}
.di-textarea::placeholder {
  color: #ccc;
}
.di-textarea:disabled {
  background: rgba(0, 0, 0, 0.02);
  color: #aaa;
}

.di-submit-err {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  color: #e74c3c;
}

.di-form-actions {
  display: flex;
  justify-content: flex-end;
}

.di-btn-submit {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 14px;
  border: none;
  border-radius: 3px;
  background: #000b23;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.di-btn-submit:hover:not(:disabled) {
  background: #00a8a8;
}
.di-btn-submit:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

@keyframes di-rotate {
  to {
    transform: rotate(360deg);
  }
}
.di-spin {
  animation: di-rotate 0.7s linear infinite;
}
</style>
