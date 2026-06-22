<template>
  <div class="df-root">

    <!-- ══ HEADER ══════════════════════════════════════════════════════ -->
    <div class="ja-hdr">

      <!-- Fil d'Ariane contextuel -->
      <p class="ja-ctx">
        <span>WORKSPACE</span>
        <span class="ja-ctx__sep">›</span>
        <span>NOUVELLE DEMANDE</span>
        <span class="ja-ctx__sep">›</span>
        <span class="ja-ctx__active">ANOMALIE</span>
      </p>

      <!-- Ligne titre + méta -->
      <div class="ja-title-row">
        <div class="ja-title-left">
          <span class="ja-marker"></span>
          <h2 class="ja-title">JOURNAL D'ANOMALIES</h2>
        </div>
        <div class="ja-title-right">
          <div class="ja-meta-field">
            <span class="ja-meta-lbl">PRIORITÉ</span>
            <select v-model="form.priorite" class="ja-meta-select">
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

      <!-- Intitulé inline (= form.titre) -->
      <div class="ja-titre-row">
        <span class="ja-titre-lbl">INTITULÉ</span>
        <input
          id="an-titre"
          v-model="form.titre"
          class="ja-titre-input"
          placeholder="Ex : Panne réseau bâtiment B — accès bloqué depuis 10h15"
          autocomplete="off"
        />
      </div>
    </div>

    <!-- Bandeau erreur -->
    <div v-if="submitError" class="df-error-bar">
      <v-icon size="13" color="#e74c3c">mdi-alert-circle-outline</v-icon>
      {{ submitError }}
    </div>

    <!-- ══ CORPS ════════════════════════════════════════════════════════ -->
    <div class="ja-body">

      <!-- ─ Section 1 : DÉTAILS DE L'ANOMALIE ──────────────────────── -->
      <section class="ja-sec">
        <header class="ja-sec-hdr">
          <span class="ja-sec-mark ja-sec-mark--red"></span>
          <span class="ja-sec-lbl">DÉTAILS DE L'ANOMALIE</span>
          <span class="ja-sec-rule"></span>
        </header>

        <div class="ja-grid">
          <!-- Ligne 1 : Permanencier + Catégorie -->
          <div class="form-group">
            <label class="form-label">PERMANENCIER AU POSTE</label>
            <div class="ja-perm-display">
              <v-icon size="13" color="#00a8a8">mdi-account-tie-outline</v-icon>
              <span class="ja-perm-name">{{ permanencierLabel }}</span>
              <span class="ja-perm-badge">SESSION ACTIVE</span>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label" for="an-cat">CATÉGORIE D'ANOMALIE</label>
            <select id="an-cat" v-model="form.nature_anomalie" class="form-input">
              <option value="">— Sélectionner —</option>
              <option v-for="opt in natureOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
            <input
              v-if="form.nature_anomalie === 'autre'"
              v-model="form.nature_anomalie_libre"
              class="form-input ja-autre-input"
              placeholder="Précisez le type d'anomalie…"
              autocomplete="off"
            />
          </div>

          <!-- Ligne 2 : Client + Contact -->
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
            <label class="form-label">CONTACT <span class="ja-optional">optionnel</span></label>
            <ContactSelectWithAdd
              v-model="form.contact_id"
              :client-id="form.client_id"
              @contact-selected="onContactSelected"
            />
          </div>

          <!-- Ligne 3 : Agent concerné + Site -->
          <div class="form-group">
            <label class="form-label">AGENT CONCERNÉ <span class="ja-optional">optionnel</span></label>
            <AgentSelect
              @agent-selected="onAgentSelected"
              @agent-cleared="onAgentCleared"
            />
          </div>

          <div class="form-group">
            <label class="form-label">SITE <span class="ja-optional">optionnel</span></label>
            <SiteSelect
              :client-id="form.client_id"
              @site-selected="onSiteSelected"
              @site-cleared="onSiteCleared"
            />
          </div>

          <div class="form-group">
            <label class="form-label" for="an-equip">ÉQUIPEMENT CONCERNÉ</label>
            <input
              id="an-equip"
              v-model="form.equipement_concerne"
              class="form-input"
              placeholder="Ex : Caméra PTZ — Hall d'entrée"
              autocomplete="off"
            />
          </div>

          <!-- Ligne 4 : Description (pleine largeur) -->
          <div class="form-group ja-full">
            <label class="form-label" for="an-desc">DESCRIPTION DÉTAILLÉE</label>
            <textarea
              id="an-desc"
              v-model="form.description"
              class="form-input ja-textarea"
              rows="3"
              placeholder="Décrivez précisément l'anomalie constatée, le contexte et les impacts observés…"
            ></textarea>
          </div>
        </div>
      </section>

      <!-- ─ Section 2 : TRAITEMENT & SUIVI ────────────────────────── -->
      <section class="ja-sec">
        <header class="ja-sec-hdr">
          <span class="ja-sec-mark ja-sec-mark--teal"></span>
          <span class="ja-sec-lbl">TRAITEMENT & SUIVI</span>
          <span class="ja-sec-rule"></span>
        </header>

        <div class="ja-treat-layout">

          <!-- Colonne gauche : PEC + Main courante -->
          <div class="ja-treat-main">
            <div class="form-group">
              <label class="form-label" for="an-pec">
                ACTION DE PRISE EN CHARGE (PEC)
              </label>
              <textarea
                id="an-pec"
                v-model="form.action_corrective"
                class="form-input ja-textarea"
                rows="3"
                placeholder="Actions engagées pour traiter l'anomalie…"
              ></textarea>
            </div>
            <div class="form-group">
              <label class="form-label" for="an-mc">COMMENTAIRES</label>
              <textarea
                id="an-mc"
                v-model="form.commentaire"
                class="form-input ja-textarea"
                rows="3"
                placeholder="Observations, échanges, précisions complémentaires…"
              ></textarea>
            </div>
          </div>

          <!-- Colonne droite : Statut Final -->
          <div class="ja-statut-block">
            <div class="ja-statut-hdr">
              <v-icon size="10" color="#00a8a8">mdi-flag-outline</v-icon>
              STATUT FINAL
            </div>
            <div class="ja-statut-body">

              <div class="form-group">
                <label class="form-label" for="an-statut">STATUT</label>
                <select id="an-statut" v-model="form.statut" class="form-input">
                  <option value="nouvelle">Nouvelle</option>
                  <option value="en_cours">En cours</option>
                  <option value="en_attente">En attente</option>
                  <option value="resolue">Résolue</option>
                  <option value="cloturee">Clôturée</option>
                  <option value="annulee">Annulée</option>
                </select>
              </div>

              <div class="ja-impact-row">
                <input
                  id="an-impact"
                  v-model="form.impact_securite"
                  type="checkbox"
                  class="df-checkbox"
                />
                <label for="an-impact" class="df-checkbox-label">
                  Impact sécurité
                </label>
              </div>

            </div>
          </div>

        </div>
      </section>

    </div>

    <!-- ══ FOOTER ══════════════════════════════════════════════════════ -->
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
import { ref, computed, onMounted } from "vue";
import { createDemande } from "@/services/demandeService";
import { settingsService } from "@/services/settingsService";
import ClientCombobox from "@/components/workspace/ClientCombobox.vue";
import ContactSelectWithAdd from "@/components/workspace/ContactSelectWithAdd.vue";
import AgentSelect from "@/components/workspace/AgentSelect.vue";
import SiteSelect from "@/components/workspace/SiteSelect.vue";
import { useAuthStore } from "@/store/auth";

// ─── Catégories d'anomalie (valeurs de référence, avec repli) ─────────────────
// La valeur soumise reste le `code` (clé d'enum backend) ; seul le libellé est
// personnalisable. Repli sur les valeurs par défaut si non configurées.
const DEFAULT_NATURE_OPTIONS = [
  { value: "anj", label: "Absence non justifiée (ANJ)" },
  { value: "absence_justifiee", label: "Absence justifiée" },
  { value: "retard_prise_service", label: "Retard prise de service" },
  { value: "agent_non_sur_site", label: "Agent non sur site" },
  { value: "doublon_planning", label: "Doublon planning" },
  { value: "remplacement_permutation", label: "Remplacement / permutation" },
  { value: "modification_vacation", label: "Modification vacation" },
  { value: "probleme_technique", label: "Problème technique" },
  { value: "site_prestataire_injoignable", label: "Site / prestataire injoignable" },
  { value: "blocage_outil_rh", label: "Blocage outil / RH" },
  { value: "demande_de_renfort", label: "Demande de renfort" },
  { value: "anomalie_facturation", label: "Anomalie facturation" },
  { value: "autre", label: "Autre" },
];
const natureOptions = ref([...DEFAULT_NATURE_OPTIONS]);

async function loadNatureOptions() {
  try {
    const items = await settingsService.getReferenceValues("nature_anomalie");
    // On ne garde que les valeurs actives ET porteuses d'un code (clé d'enum).
    const opts = (items ?? [])
      .filter((i) => i.active && i.code)
      .map((i) => ({ value: i.code, label: i.label }));
    if (opts.length) natureOptions.value = opts;
  } catch {
    /* repli silencieux sur DEFAULT_NATURE_OPTIONS */
  }
}

onMounted(loadNatureOptions);

// ─── Props / Emits ───────────────────────────────────────────────────────────
const props = defineProps({ contactId: { type: Number, default: null } });
const emit = defineEmits(["submitted", "cancel"]);

const authStore = useAuthStore();
const permanencierLabel = computed(() => {
  const u = authStore.user;
  if (!u) return "—";
  return [u.prenom, u.nom].filter(Boolean).join(" ");
});

// ─── État ────────────────────────────────────────────────────────────────────
const submitting = ref(false);
const submitError = ref("");

function onClientSelected(client) {
  form.value.client_id = client.id;
  form.value.site_id = null; // reset site quand client change
}
function onClientCleared() {
  form.value.client_id = null;
  form.value.site_id = null;
  form.value.contact_id = null;
}
function onContactSelected(contact) {
  form.value.contact_id = contact?.id ?? null;
}
function onSiteSelected(site) {
  form.value.site_id = site.id;
}
function onSiteCleared() {
  form.value.site_id = null;
}
function onAgentSelected(agent) {
  form.value.agent_concerne_id = agent.id;
}
function onAgentCleared() {
  form.value.agent_concerne_id = null;
}

const form = ref({
  // Champs communs
  titre: "",
  description: "",
  client_id: null,
  site_id: null,
  priorite: "normale",
  statut: "nouvelle",
  contact_id: props.contactId,
  // Champs spécifiques anomalie
  nature_anomalie: "",
  nature_anomalie_libre: "",
  equipement_concerne: "",
  commentaire: "",
  impact_securite: false,
  action_corrective: "",
  agent_concerne_id: null,
});

// ─── Soumission ──────────────────────────────────────────────────────────────
async function submit() {
  submitError.value = "";
  if (!form.value.titre.trim()) {
    submitError.value = "L'intitulé de l'anomalie est requis.";
    return;
  }
  if (!form.value.client_id) {
    submitError.value = "Veuillez sélectionner ou créer un client.";
    return;
  }
  submitting.value = true;
  try {
    const { commentaire, nature_anomalie_libre, ...rest } = form.value;
    // Quand « Autre » est sélectionné, le texte libre préfixe la description
    const descriptionFinale =
      rest.nature_anomalie === "autre" && nature_anomalie_libre.trim()
        ? `[${nature_anomalie_libre.trim()}]\n\n${rest.description}`.trim()
        : rest.description;
    const demande = await createDemande({
      type_demande: "anomalie",
      ...rest,
      description: descriptionFinale,
      localisation_precise: commentaire || null,
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
export default { name: "DemandeAnomalieForm" };
</script>

<style scoped>
/* ══ HEADER ════════════════════════════════════════════════════════ */

.ja-hdr {
  flex-shrink: 0;
  padding: 10px 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

/* Fil d'Ariane */
.ja-ctx {
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

.ja-ctx__sep { color: #e0e0e0; }

.ja-ctx__active {
  color: #e74c3c;
  font-weight: 600;
}

/* Ligne titre */
.ja-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.ja-title-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* Marqueur vertical rouge */
.ja-marker {
  width: 3px;
  height: 18px;
  background: #e74c3c;
  border-radius: 1px;
  flex-shrink: 0;
}

.ja-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.18em;
  color: #000b23;
  text-transform: uppercase;
  margin: 0;
}

.ja-title-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* Sélecteur de priorité inline */
.ja-meta-field {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ja-meta-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
}

.ja-meta-select {
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

.ja-meta-select:focus {
  border-color: rgba(0, 168, 168, 0.4);
}

/* Ligne intitulé (form.titre) */
.ja-titre-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
}

.ja-titre-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}

.ja-titre-input {
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

.ja-titre-input:focus {
  border-bottom-color: #00a8a8;
}

.ja-titre-input::placeholder {
  color: #d0d0d0;
  font-size: 11px;
  font-weight: 400;
}

/* ══ CORPS ════════════════════════════════════════════════════════ */

.ja-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ja-body::-webkit-scrollbar { width: 4px; }
.ja-body::-webkit-scrollbar-track { background: transparent; }
.ja-body::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.12); border-radius: 2px; }

/* ══ SECTIONS ══════════════════════════════════════════════════════ */

.ja-sec {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ja-sec-hdr {
  display: flex;
  align-items: center;
  gap: 7px;
}

/* Marqueur carré coloré */
.ja-sec-mark {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  flex-shrink: 0;
}

.ja-sec-mark--red  { background: #e74c3c; }
.ja-sec-mark--teal { background: #00a8a8; }

.ja-sec-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9.5px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #aaa;
  text-transform: uppercase;
  white-space: nowrap;
}

/* Trait horizontal après le label */
.ja-sec-rule {
  flex: 1;
  height: 1px;
  background: rgba(0, 0, 0, 0.06);
}

/* ══ GRILLE 2 COLONNES ════════════════════════════════════════════ */

.ja-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
}

.ja-full { grid-column: 1 / -1; }

/* ══ TEXTAREA ══════════════════════════════════════════════════════ */

.ja-textarea {
  resize: vertical;
  min-height: 64px;
  line-height: 1.5;
}

/* ══ TRAITEMENT & SUIVI ════════════════════════════════════════════ */

/* Layout : colonne gauche souple + bloc statut fixe */
.ja-treat-layout {
  display: grid;
  grid-template-columns: 1fr 196px;
  gap: 14px;
  align-items: start;
}

.ja-treat-main {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ══ BLOC STATUT FINAL ════════════════════════════════════════════ */

.ja-statut-block {
  border: 1px solid rgba(0, 168, 168, 0.22);
  border-radius: 3px;
  background: rgba(0, 168, 168, 0.025);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.ja-statut-hdr {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  background: rgba(0, 168, 168, 0.07);
  border-bottom: 1px solid rgba(0, 168, 168, 0.12);
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #00a8a8;
  text-transform: uppercase;
}

.ja-statut-body {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ja-impact-row {
  display: flex;
  align-items: center;
  gap: 7px;
}

/* ══ PERMANENCIER ══════════════════════════════════════════════════ */

.ja-perm-display {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 32px;
  padding: 0 10px;
  background: rgba(0, 168, 168, 0.04);
  border: 1px solid rgba(0, 168, 168, 0.18);
  border-radius: 3px;
}

.ja-perm-name {
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 700;
  color: #000b23;
  letter-spacing: 0.02em;
  flex: 1;
}

.ja-perm-badge {
  font-family: "Fira Code", monospace;
  font-size: 8.5px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #00a8a8;
  background: rgba(0, 168, 168, 0.1);
  padding: 2px 6px;
  border-radius: 2px;
  text-transform: uppercase;
}

.ja-optional {
  font-family: "Fira Code", monospace;
  font-size: 8px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: #bbb;
  text-transform: lowercase;
  margin-left: 4px;
}

/* Champ libre "Autre" : se glisse juste sous le select */
.ja-autre-input {
  margin-top: 5px;
  border-left: 2px solid #e74c3c !important;
  padding-left: 8px !important;
}
</style>
