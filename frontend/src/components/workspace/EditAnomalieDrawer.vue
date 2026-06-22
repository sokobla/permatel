<template>
  <!-- Overlay -->
  <div class="ead-overlay" @click.self="emit('close')">
    <div class="ead-panel" role="dialog" aria-modal="true">

      <!-- ── Header ───────────────────────────────────────────────── -->
      <div class="ead-hdr">
        <p class="ead-ctx">
          <span>JOURNAL DES ANOMALIES</span>
          <span class="ead-ctx__sep">›</span>
          <span class="ead-ctx__ticket">{{ demande.numero_ticket }}</span>
        </p>
        <div class="ead-title-row">
          <span class="ead-marker"></span>
          <h2 class="ead-title">ÉDITION D'ANOMALIE</h2>
          <span class="ead-hdr-spacer"></span>
          <button class="ead-close-btn" @click="emit('close')">
            <v-icon size="15">mdi-close</v-icon>
          </button>
        </div>
        <!-- Intitulé inline -->
        <div class="ead-titre-row">
          <span class="ead-titre-lbl">INTITULÉ</span>
          <input v-model="form.titre" class="ead-titre-input" autocomplete="off" />
        </div>
      </div>

      <!-- Bandeau erreur -->
      <div v-if="error" class="ead-error-bar">
        <v-icon size="12" color="#e74c3c">mdi-alert-circle-outline</v-icon>
        {{ error }}
      </div>

      <!-- ── Corps scrollable ──────────────────────────────────────── -->
      <div class="ead-body">

        <!-- Contexte : client + site -->
        <div class="ead-context">
          <div class="ead-context__item">
            <span class="ead-context__lbl">CLIENT</span>
            <span class="ead-context__val">
              <v-icon size="13" color="#00a8a8">mdi-domain</v-icon>
              {{ demande.client_nom ?? (demande.client_id ? `Client #${demande.client_id}` : '—') }}
            </span>
          </div>
          <div class="ead-context__item">
            <span class="ead-context__lbl">SITE</span>
            <span class="ead-context__val">
              <v-icon size="13" color="#00a8a8">mdi-map-marker-outline</v-icon>
              {{ demande.site_nom ?? '—' }}
            </span>
          </div>
        </div>

        <!-- Section 1 : Qualification -->
        <section class="ead-sec">
          <header class="ead-sec-hdr">
            <span class="ead-sec-mark ead-sec-mark--red"></span>
            <span class="ead-sec-lbl">QUALIFICATION</span>
            <span class="ead-sec-rule"></span>
          </header>
          <div class="ead-grid">
            <div class="form-group">
              <label class="form-label">STATUT</label>
              <select v-model="form.statut" class="form-input">
                <option value="nouvelle">Nouvelle</option>
                <option value="en_cours">En cours</option>
                <option value="en_attente">En attente</option>
                <option value="resolue">Résolue</option>
                <option value="cloturee">Clôturée</option>
                <option value="annulee">Annulée</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">PRIORITÉ</label>
              <select v-model="form.priorite" class="form-input">
                <option value="basse">Basse</option>
                <option value="normale">Normale</option>
                <option value="haute">Haute</option>
                <option value="urgente">Urgente</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">CATÉGORIE D'ANOMALIE</label>
              <select v-model="form.nature_anomalie" class="form-input">
                <option value="">— Sélectionner —</option>
                <option value="anj">Absence non justifiée (ANJ)</option>
                <option value="absence_justifiee">Absence justifiée</option>
                <option value="retard_prise_service">Retard prise de service</option>
                <option value="agent_non_sur_site">Agent non sur site</option>
                <option value="doublon_planning">Doublon planning</option>
                <option value="remplacement_permutation">Remplacement / permutation</option>
                <option value="modification_vacation">Modification vacation</option>
                <option value="probleme_technique">Problème technique</option>
                <option value="site_prestataire_injoignable">Site / prestataire injoignable</option>
                <option value="blocage_outil_rh">Blocage outil / RH</option>
                <option value="demande_de_renfort">Demande de renfort</option>
                <option value="anomalie_facturation">Anomalie facturation</option>
                <option value="autre">Autre…</option>
              </select>
              <input
                v-if="form.nature_anomalie === 'autre'"
                v-model="form.nature_anomalie_libre"
                class="form-input ead-autre-input"
                placeholder="Précisez…"
              />
            </div>
            <div class="form-group">
              <label class="form-label">ÉQUIPEMENT CONCERNÉ</label>
              <input v-model="form.equipement_concerne" class="form-input" autocomplete="off" />
            </div>
          </div>
        </section>

        <!-- Section 2 : Détails -->
        <section class="ead-sec">
          <header class="ead-sec-hdr">
            <span class="ead-sec-mark ead-sec-mark--navy"></span>
            <span class="ead-sec-lbl">DESCRIPTION</span>
            <span class="ead-sec-rule"></span>
          </header>
          <div class="form-group">
            <label class="form-label">DESCRIPTION DÉTAILLÉE</label>
            <textarea v-model="form.description" class="form-input ead-textarea" rows="4"></textarea>
          </div>
        </section>

        <!-- Section 3 : Traitement -->
        <section class="ead-sec">
          <header class="ead-sec-hdr">
            <span class="ead-sec-mark ead-sec-mark--teal"></span>
            <span class="ead-sec-lbl">TRAITEMENT & SUIVI</span>
            <span class="ead-sec-rule"></span>
          </header>
          <div class="form-group">
            <label class="form-label">ACTION DE PRISE EN CHARGE</label>
            <textarea v-model="form.action_corrective" class="form-input ead-textarea" rows="3"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">COMMENTAIRES / LOCALISATION</label>
            <textarea v-model="form.localisation_precise" class="form-input ead-textarea" rows="3"></textarea>
          </div>
          <div class="ead-impact-row">
            <input id="ead-impact" v-model="form.impact_securite" type="checkbox" class="ead-checkbox" />
            <label for="ead-impact" class="ead-checkbox-lbl">Impact sécurité</label>
          </div>
        </section>

        <!-- Section 4 : Agent concerné -->
        <section class="ead-sec">
          <header class="ead-sec-hdr">
            <span class="ead-sec-mark ead-sec-mark--amber"></span>
            <span class="ead-sec-lbl">AGENT CONCERNÉ <span class="ead-optional">optionnel</span></span>
            <span class="ead-sec-rule"></span>
          </header>
          <div v-if="demande.agent_concerne_label && !agentCleared" class="ead-agent-display">
            <v-icon size="13" color="#00a8a8">mdi-account-hard-hat-outline</v-icon>
            <span class="ead-agent-name">{{ demande.agent_concerne_label }}</span>
            <button class="ead-agent-clear" @click="clearAgent">
              <v-icon size="11">mdi-close</v-icon>
              Retirer
            </button>
          </div>
          <AgentSelect
            v-else
            @agent-selected="onAgentSelected"
            @agent-cleared="onAgentCleared"
          />
        </section>

        <!-- Section 5 : Suivi & interactions -->
        <section class="ead-sec">
          <DemandeInteractions :demande-id="demande.id" :client-id="demande.client_id ?? null" />
        </section>

      </div>

      <!-- ── Footer ───────────────────────────────────────────────── -->
      <div class="ead-footer">
        <button class="ead-btn-cancel" :disabled="saving" @click="emit('close')">ANNULER</button>
        <button class="ead-btn-save" :disabled="saving" @click="save">
          <span v-if="saving" class="ead-spinner"></span>
          ENREGISTRER
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from "vue";
import { updateDemande } from "@/services/demandeService";
import AgentSelect from "@/components/workspace/AgentSelect.vue";
import DemandeInteractions from "@/components/workspace/DemandeInteractions.vue";

const props = defineProps({ demande: { type: Object, required: true } });
const emit  = defineEmits(["close", "updated"]);

const saving     = ref(false);
const error      = ref("");
const agentCleared = ref(false);

// Formulaire initialisé depuis la prop
const form = reactive({
  titre:                props.demande.titre              ?? "",
  statut:               props.demande.statut             ?? "nouvelle",
  priorite:             props.demande.priorite           ?? "normale",
  nature_anomalie:      props.demande.nature_anomalie    ?? "",
  nature_anomalie_libre:"",
  equipement_concerne:  props.demande.equipement_concerne ?? "",
  description:          props.demande.description        ?? "",
  action_corrective:    props.demande.action_corrective  ?? "",
  localisation_precise: props.demande.localisation_precise ?? "",
  impact_securite:      props.demande.impact_securite    ?? false,
  agent_concerne_id:    props.demande.agent_concerne_id  ?? null,
});

function clearAgent() {
  agentCleared.value = true;
  form.agent_concerne_id = null;
}
function onAgentSelected(agent) { form.agent_concerne_id = agent.id; agentCleared.value = false; }
function onAgentCleared()       { form.agent_concerne_id = null; }

async function save() {
  error.value = "";
  saving.value = true;
  try {
    const payload = { ...form };
    delete payload.nature_anomalie_libre;
    // Intègre le texte libre dans la description si "autre"
    if (form.nature_anomalie === "autre" && form.nature_anomalie_libre.trim()) {
      payload.description = `[${form.nature_anomalie_libre.trim()}]\n\n${form.description}`.trim();
    }
    const updated = await updateDemande(props.demande.id, payload);
    emit("updated", updated);
  } catch (e) {
    error.value = e?.response?.data?.error ?? "Erreur lors de la sauvegarde.";
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
/* ── Overlay ─────────────────────────────────────────────────────── */
.ead-overlay {
  position: fixed;
  top: var(--v-layout-top, 48px);
  right: 0;
  bottom: 0;
  left: 0;
  background: rgba(0, 11, 35, 0.45);
  z-index: 300;
  display: flex;
  justify-content: flex-end;
}

/* ── Panneau ─────────────────────────────────────────────────────── */
.ead-panel {
  width: 480px;
  max-width: 100vw;
  height: 100%;
  background: #fff;
  display: flex;
  flex-direction: column;
  animation: ead-slide 0.22s ease;
  box-shadow: -4px 0 24px rgba(0, 11, 35, 0.12);
}

@keyframes ead-slide {
  from { transform: translateX(100%); }
  to   { transform: translateX(0); }
}

/* ── Header ──────────────────────────────────────────────────────── */
.ead-hdr {
  flex-shrink: 0;
  padding: 12px 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.ead-ctx {
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
.ead-ctx__sep { color: #e0e0e0; }
.ead-ctx__ticket { color: #00a8a8; font-weight: 600; }

.ead-title-row {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 10px;
}

.ead-marker {
  width: 3px;
  height: 16px;
  background: #e74c3c;
  border-radius: 1px;
  flex-shrink: 0;
}

.ead-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  color: #000b23;
  text-transform: uppercase;
  margin: 0;
}

.ead-hdr-spacer { flex: 1; }

.ead-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 3px;
  background: transparent;
  cursor: pointer;
  color: #aaa;
  flex-shrink: 0;
}
.ead-close-btn:hover { color: #e74c3c; border-color: #e74c3c; }

.ead-titre-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 10px;
}

.ead-titre-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #ccc;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}

.ead-titre-input {
  flex: 1;
  height: 26px;
  padding: 0 4px;
  border: none;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: #000b23;
  background: transparent;
  outline: none;
  transition: border-color 0.15s;
}
.ead-titre-input:focus { border-color: #00a8a8; }

/* ── Erreur ──────────────────────────────────────────────────────── */
.ead-error-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  background: rgba(231, 76, 60, 0.07);
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #e74c3c;
  flex-shrink: 0;
}

/* ── Corps ───────────────────────────────────────────────────────── */
.ead-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.ead-body::-webkit-scrollbar { width: 4px; }
.ead-body::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.1); border-radius: 2px; }

/* ── Contexte client / site ──────────────────────────────────────── */
.ead-context {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
  padding: 10px 12px;
  background: rgba(0, 168, 168, 0.04);
  border: 1px solid rgba(0, 168, 168, 0.18);
  border-radius: 6px;
}
.ead-context__item { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.ead-context__lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #9aa0aa;
  text-transform: uppercase;
}
.ead-context__val {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: #15223a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Sections ────────────────────────────────────────────────────── */
.ead-sec { display: flex; flex-direction: column; gap: 10px; }

.ead-sec-hdr {
  display: flex;
  align-items: center;
  gap: 7px;
}

.ead-sec-mark {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  flex-shrink: 0;
}
.ead-sec-mark--red   { background: #e74c3c; }
.ead-sec-mark--teal  { background: #00a8a8; }
.ead-sec-mark--navy  { background: #000b23; }
.ead-sec-mark--amber { background: #f39c12; }

.ead-sec-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #aaa;
  text-transform: uppercase;
  white-space: nowrap;
}

.ead-sec-rule { flex: 1; height: 1px; background: rgba(0, 0, 0, 0.06); }

.ead-optional {
  font-family: "Fira Code", monospace;
  font-size: 8px;
  font-weight: 500;
  color: #ccc;
  text-transform: lowercase;
  margin-left: 4px;
}

/* ── Grille 2 colonnes ───────────────────────────────────────────── */
.ead-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 14px;
}

/* ── Form primitives (dupliqués depuis le design system) ─────────── */
.form-group { display: flex; flex-direction: column; gap: 4px; }

.form-label {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #bbb;
  text-transform: uppercase;
}

.form-input {
  height: 32px;
  padding: 0 8px;
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  color: #000b23;
  background: #fff;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
  box-sizing: border-box;
}
.form-input:focus { border-color: #00a8a8; }

/* ── Textarea ────────────────────────────────────────────────────── */
.ead-textarea {
  height: auto;
  padding: 7px 8px;
  resize: vertical;
  line-height: 1.5;
  min-height: 70px;
}

/* ── Champ "Autre" ───────────────────────────────────────────────── */
.ead-autre-input {
  margin-top: 5px;
  border-left: 2px solid #e74c3c !important;
  padding-left: 8px !important;
}

/* ── Impact sécurité ─────────────────────────────────────────────── */
.ead-impact-row {
  display: flex;
  align-items: center;
  gap: 7px;
}

.ead-checkbox { width: 14px; height: 14px; accent-color: #00a8a8; cursor: pointer; }
.ead-checkbox-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 600;
  color: #555;
  cursor: pointer;
}

/* ── Agent display ───────────────────────────────────────────────── */
.ead-agent-display {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 32px;
  padding: 0 10px;
  background: rgba(0, 168, 168, 0.04);
  border: 1px solid rgba(0, 168, 168, 0.18);
  border-radius: 3px;
}

.ead-agent-name {
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 700;
  color: #000b23;
  flex: 1;
}

.ead-agent-clear {
  display: flex;
  align-items: center;
  gap: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 600;
  color: #e74c3c;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}

/* ── Footer ──────────────────────────────────────────────────────── */
.ead-footer {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.ead-btn-cancel {
  height: 30px;
  padding: 0 14px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 3px;
  background: #fff;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #555;
  cursor: pointer;
}
.ead-btn-cancel:hover { border-color: #aaa; }

.ead-btn-save {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 16px;
  border: none;
  border-radius: 3px;
  background: #000b23;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.ead-btn-save:hover:not(:disabled) { background: #00a8a8; }
.ead-btn-save:disabled { opacity: 0.6; cursor: not-allowed; }

.ead-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: ead-spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes ead-spin { to { transform: rotate(360deg); } }
</style>
