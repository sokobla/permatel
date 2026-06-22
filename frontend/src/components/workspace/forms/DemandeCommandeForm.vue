<template>
  <div class="df-root">

    <!-- ══ HEADER ════════════════════════════════════════════════════ -->
    <div class="bc-hdr">

      <!-- Fil d'Ariane -->
      <p class="bc-ctx">
        <span>WORKSPACE</span>
        <span class="bc-ctx__sep">›</span>
        <span>NOUVELLE DEMANDE</span>
        <span class="bc-ctx__sep">›</span>
        <span class="bc-ctx__active">BON DE COMMANDE</span>
      </p>

      <!-- Ligne titre + méta -->
      <div class="bc-title-row">
        <div class="bc-title-left">
          <span class="bc-marker"></span>
          <h2 class="bc-title">BON DE COMMANDE SÉCURITÉ — FORMULAIRE OPÉRATIONNEL</h2>
        </div>
        <div class="bc-title-right">
          <div class="bc-meta-field">
            <span class="bc-meta-lbl">PRIORITÉ</span>
            <select v-model="form.priorite" class="bc-meta-select">
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
      <div class="bc-titre-row">
        <span class="bc-titre-lbl">INTITULÉ</span>
        <input
          id="bc-titre"
          v-model="form.titre"
          class="bc-titre-input"
          placeholder="Ex : Gardiennage site Nord — 24h/24 du 20 au 27 juin"
          autocomplete="off"
        />
      </div>
    </div>

    <!-- Bandeau erreur -->
    <div v-if="submitError" class="df-error-bar">
      <v-icon size="13" color="#e74c3c">mdi-alert-circle-outline</v-icon>
      {{ submitError }}
    </div>

    <!-- ══ CORPS ══════════════════════════════════════════════════════ -->
    <div class="bc-body">

      <!-- ─ Section : INFORMATIONS CLIENT ──────────────────────────── -->
      <section class="bc-sec">
        <header class="bc-sec-hdr">
          <span class="bc-sec-mark bc-sec-mark--green"></span>
          <span class="bc-sec-lbl">INFORMATIONS CLIENT</span>
          <span class="bc-sec-rule"></span>
        </header>
        <div class="bc-client-fields">
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
              :client-id="clientId"
              @contact-selected="onContactSelected"
            />
          </div>
        </div>
      </section>

      <!-- ─ Section : INFORMATIONS SITE ────────────────────────────── -->
      <section class="bc-sec">
        <header class="bc-sec-hdr">
          <span class="bc-sec-mark bc-sec-mark--green"></span>
          <span class="bc-sec-lbl">INFORMATIONS SITE</span>
          <span class="bc-sec-rule"></span>
        </header>
        <div class="bc-grid">

          <div class="form-group bc-full">
            <label class="form-label">SITE D'INTERVENTION</label>
            <SiteSelectWithAdd
              :client-id="clientId"
              @site-resolved="onSiteResolved"
            />
          </div>

          <div class="form-group bc-full">
            <label class="form-label">MOYENS D'ACCÈS</label>
            <div class="bc-chips-row">
              <button
                v-for="opt in MOYENS_ACCES"
                :key="opt"
                type="button"
                class="bc-chip"
                :class="{ 'bc-chip--on': form.moyens_acces.includes(opt) }"
                @click="toggleChip('moyens_acces', opt)"
              >
                {{ opt }}
              </button>
            </div>
          </div>

          <div class="form-group bc-full">
            <label class="form-label">ÉQUIPEMENTS PRÉSENTS SUR SITE</label>
            <div class="bc-checks">
              <label
                v-for="eq in EQUIPEMENTS"
                :key="eq"
                class="bc-check-item"
              >
                <input
                  type="checkbox"
                  :value="eq"
                  v-model="form.equipements_site"
                  class="bc-check-input"
                />
                <span class="bc-check-lbl">{{ eq }}</span>
              </label>
            </div>
          </div>

          <div class="form-group bc-full">
            <label class="form-label">RISQUES SPÉCIFIQUES</label>
            <div class="bc-checks">
              <label
                v-for="r in RISQUES"
                :key="r"
                class="bc-check-item"
              >
                <input
                  type="checkbox"
                  :value="r"
                  v-model="form.risques_specifiques"
                  class="bc-check-input"
                />
                <span class="bc-check-lbl">{{ r }}</span>
              </label>
            </div>
          </div>

        </div>
      </section>

      <!-- ─ Section : NATURE DE LA PRESTATION ─────────────────────── -->
      <section class="bc-sec">
        <header class="bc-sec-hdr">
          <span class="bc-sec-mark bc-sec-mark--green"></span>
          <span class="bc-sec-lbl">NATURE DE LA PRESTATION</span>
          <span class="bc-sec-rule"></span>
        </header>
        <div class="bc-grid">

          <div class="form-group">
            <label class="form-label" for="bc-mission">
              TYPE DE MISSION <span class="df-required">*</span>
            </label>
            <select id="bc-mission" v-model="form.type_commande" class="form-input">
              <option value="">— Sélectionner —</option>
              <option value="gardiennage">Gardiennage statique</option>
              <option value="surveillance_mobile">Surveillance mobile</option>
              <option value="rondes">Rondes de surveillance</option>
              <option value="intervention">Intervention</option>
              <option value="filtrage">Filtrage / Contrôle d'accès</option>
              <option value="protection_rapprochee">Protection rapprochée</option>
              <option value="accueil_securite">Accueil sécurité</option>
              <option value="autre">Autre</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label" for="bc-agents">NOMBRE D'AGENTS</label>
            <input
              id="bc-agents"
              v-model.number="form.nombre_agents"
              type="number"
              class="form-input"
              placeholder="0"
              min="1"
            />
          </div>

          <div class="form-group bc-full">
            <label class="form-label">BESOINS SPÉCIFIQUES AGENT</label>
            <div class="bc-checks">
              <label
                v-for="b in BESOINS_AGENTS"
                :key="b"
                class="bc-check-item"
              >
                <input
                  type="checkbox"
                  :value="b"
                  v-model="form.besoins_agents"
                  class="bc-check-input"
                />
                <span class="bc-check-lbl">{{ b }}</span>
              </label>
            </div>
          </div>

          <div class="form-group bc-full">
            <label class="form-label" for="bc-missions">MISSIONS DÉTAILLÉES</label>
            <textarea
              id="bc-missions"
              v-model="form.missions_detaillees"
              class="form-input bc-textarea"
              rows="3"
              placeholder="Décrivez précisément les missions attendues, les consignes particulières, les procédures de sécurité…"
            ></textarea>
          </div>

        </div>
      </section>

      <!-- ─ Section : HORAIRES ──────────────────────────────────────── -->
      <section class="bc-sec">
        <header class="bc-sec-hdr">
          <span class="bc-sec-mark bc-sec-mark--green"></span>
          <span class="bc-sec-lbl">HORAIRES</span>
          <span class="bc-sec-rule"></span>
        </header>
        <div class="bc-grid">
          <div class="form-group">
            <label class="form-label" for="bc-date-debut">DATE DE DÉBUT</label>
            <input
              id="bc-date-debut"
              v-model="form.date_debut"
              type="date"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="bc-date-fin">DATE DE FIN</label>
            <input
              id="bc-date-fin"
              v-model="form.date_fin"
              type="date"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="bc-heure-debut">HEURE DE DÉBUT</label>
            <input
              id="bc-heure-debut"
              v-model="form.heure_debut"
              type="time"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="bc-heure-fin">HEURE DE FIN</label>
            <input
              id="bc-heure-fin"
              v-model="form.heure_fin"
              type="time"
              class="form-input"
            />
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
        ENREGISTRER LA COMMANDE
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
import SiteSelectWithAdd from "@/components/workspace/SiteSelectWithAdd.vue";

// ─── Valeurs de référence (chargées depuis les paramètres, avec repli) ────────
// Les valeurs par défaut servent de repli si la famille n'est pas configurée.
const MOYENS_ACCES = ref([
  "Clé", "Digicode", "Badge magnétique", "Interphone", "Accès libre", "Autre",
]);
const RISQUES = ref([
  "Vol", "Intrusion", "Incendie", "Vandalisme", "Conflit social", "Risque terroriste",
]);
const BESOINS_AGENTS = ref([
  "Tenue fournie", "Formation SSIAP", "Habilitation électrique",
  "Maîtrise anglais", "Permis B", "Agent APS qualifié", "Autre",
]);

// Équipements : pas de famille de référence dédiée → reste statique.
const EQUIPEMENTS = [
  "Vidéosurveillance",
  "Système d'alarme",
  "Contrôle d'accès",
  "Éclairage sécurisé",
  "Portiques de détection",
  "Autre",
];

async function loadReferenceValues() {
  const map = [
    ["moyens_acces", MOYENS_ACCES],
    ["risques_specifiques", RISQUES],
    ["besoins_agents", BESOINS_AGENTS],
  ];
  await Promise.all(
    map.map(async ([family, target]) => {
      try {
        const items = await settingsService.getReferenceValues(family);
        const labels = (items ?? []).filter((i) => i.active).map((i) => i.label);
        if (labels.length) target.value = labels; // sinon on conserve le repli
      } catch {
        /* repli silencieux sur les valeurs par défaut */
      }
    }),
  );
}

onMounted(loadReferenceValues);


// ─── Props / Emits ───────────────────────────────────────────────────────────
const props = defineProps({ contactId: { type: Number, default: null } });
const emit = defineEmits(["submitted", "cancel"]);

// ─── État ────────────────────────────────────────────────────────────────────
const submitting = ref(false);
const submitError = ref("");

// Entités résolues par les composants enfants
const resolvedClient = ref(null);   // objet client complet
const resolvedContact = ref(null);  // objet contact complet
const resolvedSite = ref(null);     // { site_id, adresse_intervention, mode, siteData? }

const clientId = computed(() => resolvedClient.value?.id ?? null);

const form = ref({
  // Champs communs API
  titre: "",
  priorite: "normale",
  statut: "nouvelle",
  contact_id: props.contactId,
  // Champs spécifiques commande
  type_commande: "",
  nombre_agents: null,
  besoins_agents: [],
  missions_detaillees: "",
  // Horaires
  date_debut: "",
  date_fin: "",
  heure_debut: "",
  heure_fin: "",
  // Sécurité / contexte site
  moyens_acces: [],
  equipements_site: [],
  risques_specifiques: [],
});

// Handlers composants enfants
function onClientSelected(client) {
  resolvedClient.value = client;
}
function onClientCleared() {
  resolvedClient.value = null;
  resolvedContact.value = null;
  resolvedSite.value = null;
}
function onContactSelected(contact) {
  resolvedContact.value = contact;
}
function onSiteResolved(sitePayload) {
  resolvedSite.value = sitePayload;
}

// ─── Chips multi-sélect ──────────────────────────────────────────────────────
function toggleChip(field, value) {
  const arr = form.value[field];
  const idx = arr.indexOf(value);
  if (idx === -1) arr.push(value);
  else arr.splice(idx, 1);
}

// ─── Construction du payload API ─────────────────────────────────────────────
function buildPayload() {
  const f = form.value;
  const client = resolvedClient.value;
  const contact = resolvedContact.value;
  const site = resolvedSite.value;

  const dateDebut = f.date_debut
    ? `${f.date_debut}${f.heure_debut ? "T" + f.heure_debut : ""}`
    : null;

  return {
    titre: f.titre.trim(),
    description: f.missions_detaillees || null,
    client_id: client?.id ?? null,
    priorite: f.priorite,
    statut: f.statut,
    contact_id: contact?.id ?? f.contact_id ?? null,
    site_id: site?.site_id ?? null,
    adresse_intervention: site?.adresse_intervention ?? null,
    type_commande: f.type_commande || "autre",
    quantite: f.nombre_agents,
    fournisseur_suggere: client?.nom ?? null,
    date_livraison_souhaitee: dateDebut,
    moyens_acces: f.moyens_acces,
    equipements_site: f.equipements_site,
    risques_specifiques: f.risques_specifiques,
    besoins_agents: f.besoins_agents,
  };
}

// ─── Soumission ──────────────────────────────────────────────────────────────
async function submit() {
  submitError.value = "";
  if (!form.value.titre.trim()) {
    submitError.value = "L'intitulé de la commande est requis.";
    return;
  }
  if (!resolvedClient.value) {
    submitError.value = "Veuillez sélectionner ou créer un client.";
    return;
  }
  if (!form.value.type_commande) {
    submitError.value = "Le type de mission est requis.";
    return;
  }
  submitting.value = true;
  try {
    const demande = await createDemande({
      type_demande: "commande",
      ...buildPayload(),
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
export default { name: "DemandeCommandeForm" };
</script>

<style scoped>
/* ══ HEADER ════════════════════════════════════════════════════════ */

.bc-hdr {
  flex-shrink: 0;
  padding: 10px 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

/* Fil d'Ariane */
.bc-ctx {
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

.bc-ctx__sep { color: #e0e0e0; }

.bc-ctx__active {
  color: #27ae60;
  font-weight: 600;
}

/* Ligne titre */
.bc-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.bc-title-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

/* Marqueur vertical vert */
.bc-marker {
  width: 3px;
  height: 18px;
  background: #27ae60;
  border-radius: 1px;
  flex-shrink: 0;
}

.bc-title {
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

.bc-title-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.bc-meta-field {
  display: flex;
  align-items: center;
  gap: 6px;
}

.bc-meta-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
}

.bc-meta-select {
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

.bc-meta-select:focus {
  border-color: rgba(0, 168, 168, 0.4);
}

/* Ligne intitulé (form.titre) */
.bc-titre-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
}

.bc-titre-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}

.bc-titre-input {
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

.bc-titre-input:focus {
  border-bottom-color: #00a8a8;
}

.bc-titre-input::placeholder {
  color: #d0d0d0;
  font-size: 11px;
  font-weight: 400;
}

/* ══ CORPS ════════════════════════════════════════════════════════ */

.bc-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.bc-body::-webkit-scrollbar { width: 4px; }
.bc-body::-webkit-scrollbar-track { background: transparent; }
.bc-body::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.12); border-radius: 2px; }

/* ══ SECTIONS ══════════════════════════════════════════════════════ */

.bc-sec {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bc-sec-hdr {
  display: flex;
  align-items: center;
  gap: 7px;
}

.bc-sec-mark {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  flex-shrink: 0;
}

.bc-sec-mark--green { background: #27ae60; }

.bc-sec-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9.5px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #aaa;
  text-transform: uppercase;
  white-space: nowrap;
}

.bc-sec-rule {
  flex: 1;
  height: 1px;
  background: rgba(0, 0, 0, 0.06);
}

/* ══ GRILLE 2 COLONNES ════════════════════════════════════════════ */

.bc-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
}

.bc-full { grid-column: 1 / -1; }

/* ── Section client (2 colonnes: combobox + contact) ── */
.bc-client-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
}

/* ══ TEXTAREA ══════════════════════════════════════════════════════ */

.bc-textarea {
  resize: vertical;
  min-height: 64px;
  line-height: 1.5;
}

/* ══ CHIPS (MOYENS D'ACCÈS) ═══════════════════════════════════════ */

.bc-chips-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 4px 0;
}

.bc-chip {
  height: 24px;
  padding: 0 10px;
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 3px;
  background: #fff;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #555;
  cursor: pointer;
  transition:
    background 0.12s,
    border-color 0.12s,
    color 0.12s;
  white-space: nowrap;
}

.bc-chip:hover:not(.bc-chip--on) {
  background: rgba(0, 0, 0, 0.04);
  border-color: rgba(0, 0, 0, 0.22);
}

.bc-chip--on {
  background: #000b23;
  border-color: #000b23;
  color: #fff;
}

/* ══ CHECKBOXES ═══════════════════════════════════════════════════ */

.bc-checks {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 6px 10px;
  padding: 4px 0;
}

.bc-check-item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
}

.bc-check-input {
  width: 13px;
  height: 13px;
  accent-color: #00a8a8;
  flex-shrink: 0;
  cursor: pointer;
  margin: 0;
}

.bc-check-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  color: #333;
}
</style>
