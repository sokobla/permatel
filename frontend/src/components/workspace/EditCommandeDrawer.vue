<template>
  <div class="ecd-overlay" @click.self="emit('close')">
    <div class="ecd-panel" role="dialog" aria-modal="true">

      <!-- ── Header ───────────────────────────────────────────────── -->
      <div class="ecd-hdr">
        <p class="ecd-ctx">
          <span>COMMANDES DE SÉCURITÉ</span>
          <span class="ecd-ctx__sep">›</span>
          <span class="ecd-ctx__ticket">{{ demande.numero_ticket }}</span>
        </p>
        <div class="ecd-title-row">
          <span class="ecd-marker"></span>
          <h2 class="ecd-title">ÉDITION DE COMMANDE</h2>
          <span class="ecd-hdr-spacer"></span>
          <button class="ecd-close-btn" @click="emit('close')">
            <v-icon size="15">mdi-close</v-icon>
          </button>
        </div>
        <div class="ecd-titre-row">
          <span class="ecd-titre-lbl">INTITULÉ</span>
          <input v-model="form.titre" class="ecd-titre-input" autocomplete="off" />
        </div>
      </div>

      <div v-if="error" class="ecd-error-bar">
        <v-icon size="12" color="#e74c3c">mdi-alert-circle-outline</v-icon>
        {{ error }}
      </div>

      <!-- ── Corps ──────────────────────────────────────────────────── -->
      <div class="ecd-body">

        <!-- Contexte : client + site -->
        <div class="ecd-context">
          <div class="ecd-context__item">
            <span class="ecd-context__lbl">CLIENT</span>
            <span class="ecd-context__val">
              <v-icon size="13" color="#00a8a8">mdi-domain</v-icon>
              {{ demande.client_nom ?? (demande.client_id ? `Client #${demande.client_id}` : '—') }}
            </span>
          </div>
          <div class="ecd-context__item">
            <span class="ecd-context__lbl">SITE</span>
            <span class="ecd-context__val">
              <v-icon size="13" color="#00a8a8">mdi-map-marker-outline</v-icon>
              {{ demande.site_nom ?? '—' }}
            </span>
          </div>
        </div>

        <!-- Section 1 : Qualification -->
        <section class="ecd-sec">
          <header class="ecd-sec-hdr">
            <span class="ecd-sec-mark ecd-sec-mark--teal"></span>
            <span class="ecd-sec-lbl">QUALIFICATION</span>
            <span class="ecd-sec-rule"></span>
          </header>
          <div class="ecd-grid">
            <div class="form-group">
              <label class="form-label">STATUT</label>
              <select v-model="form.statut" class="form-input">
                <option value="nouvelle">Nouvelle</option>
                <option value="en_cours">En cours</option>
                <option value="en_attente">En attente</option>
                <option value="resolue">Validée</option>
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
            <div class="form-group ecd-full">
              <label class="form-label">TYPE DE PRESTATION</label>
              <select v-model="form.type_commande" class="form-input">
                <option value="">— Sélectionner —</option>
                <option value="gardiennage">Gardiennage</option>
                <option value="surveillance_mobile">Surveillance mobile</option>
                <option value="rondes">Rondes</option>
                <option value="intervention">Intervention</option>
                <option value="filtrage">Filtrage</option>
                <option value="protection_rapprochee">Protection rapprochée</option>
                <option value="accueil_securite">Accueil sécurité</option>
                <option value="autre">Autre</option>
              </select>
            </div>
          </div>
        </section>

        <!-- Section 2 : Description -->
        <section class="ecd-sec">
          <header class="ecd-sec-hdr">
            <span class="ecd-sec-mark ecd-sec-mark--navy"></span>
            <span class="ecd-sec-lbl">DESCRIPTION DE LA PRESTATION</span>
            <span class="ecd-sec-rule"></span>
          </header>
          <div class="form-group">
            <label class="form-label">DESCRIPTION</label>
            <textarea v-model="form.description" class="form-input ecd-textarea" rows="4"></textarea>
          </div>
        </section>

        <!-- Section 3 : Logistique -->
        <section class="ecd-sec">
          <header class="ecd-sec-hdr">
            <span class="ecd-sec-mark ecd-sec-mark--amber"></span>
            <span class="ecd-sec-lbl">LOGISTIQUE & BUDGET</span>
            <span class="ecd-sec-rule"></span>
          </header>
          <div class="ecd-grid">
            <div class="form-group">
              <label class="form-label">QUANTITÉ / EFFECTIF</label>
              <input v-model.number="form.quantite" type="number" min="1" class="form-input" />
            </div>
            <div class="form-group">
              <label class="form-label">BUDGET ESTIMÉ (€)</label>
              <input v-model.number="form.budget_estime" type="number" min="0" step="10" class="form-input" />
            </div>
            <div class="form-group">
              <label class="form-label">DATE LIVRAISON SOUHAITÉE</label>
              <input v-model="form.date_livraison_souhaitee" type="date" class="form-input" />
            </div>
            <div class="form-group">
              <label class="form-label">FOURNISSEUR SUGGÉRÉ</label>
              <input v-model="form.fournisseur_suggere" class="form-input" autocomplete="off" />
            </div>
            <div class="form-group ecd-full">
              <label class="form-label">BON DE COMMANDE / RÉFÉRENCE</label>
              <input v-model="form.bon_commande" class="form-input" autocomplete="off" />
            </div>
          </div>
        </section>

        <!-- Section 4 : Suivi & interactions -->
        <section class="ecd-sec">
          <DemandeInteractions :demande-id="demande.id" :client-id="demande.client_id ?? null" />
        </section>

      </div>

      <!-- ── Footer ───────────────────────────────────────────────── -->
      <div class="ecd-footer">
        <button class="ecd-btn-cancel" :disabled="saving" @click="emit('close')">ANNULER</button>
        <button class="ecd-btn-save" :disabled="saving" @click="save">
          <span v-if="saving" class="ecd-spinner"></span>
          ENREGISTRER
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from "vue";
import { updateDemande } from "@/services/demandeService";
import DemandeInteractions from "@/components/workspace/DemandeInteractions.vue";

const props = defineProps({ demande: { type: Object, required: true } });
const emit  = defineEmits(["close", "updated"]);

const saving = ref(false);
const error  = ref("");

const form = reactive({
  titre:                    props.demande.titre                     ?? "",
  statut:                   props.demande.statut                    ?? "nouvelle",
  priorite:                 props.demande.priorite                  ?? "normale",
  type_commande:            props.demande.type_commande             ?? "",
  description:              props.demande.description               ?? "",
  quantite:                 props.demande.quantite                  ?? null,
  budget_estime:            props.demande.budget_estime             ?? null,
  fournisseur_suggere:      props.demande.fournisseur_suggere       ?? "",
  date_livraison_souhaitee: props.demande.date_livraison_souhaitee
    ? props.demande.date_livraison_souhaitee.slice(0, 10)
    : "",
  bon_commande:             props.demande.bon_commande              ?? "",
});

async function save() {
  error.value = "";
  saving.value = true;
  try {
    const updated = await updateDemande(props.demande.id, { ...form });
    emit("updated", updated);
  } catch (e) {
    error.value = e?.response?.data?.error ?? "Erreur lors de la sauvegarde.";
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.ecd-overlay {
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

.ecd-panel {
  width: 480px;
  max-width: 100vw;
  height: 100%;
  background: #fff;
  display: flex;
  flex-direction: column;
  animation: ecd-slide 0.22s ease;
  box-shadow: -4px 0 24px rgba(0, 11, 35, 0.12);
}

@keyframes ecd-slide {
  from { transform: translateX(100%); }
  to   { transform: translateX(0); }
}

.ecd-hdr {
  flex-shrink: 0;
  padding: 12px 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.ecd-ctx {
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
.ecd-ctx__sep { color: #e0e0e0; }
.ecd-ctx__ticket { color: #00a8a8; font-weight: 600; }

.ecd-title-row {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 10px;
}

.ecd-marker {
  width: 3px;
  height: 16px;
  background: #00a8a8;
  border-radius: 1px;
  flex-shrink: 0;
}

.ecd-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  color: #000b23;
  text-transform: uppercase;
  margin: 0;
}

.ecd-hdr-spacer { flex: 1; }

.ecd-close-btn {
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
}
.ecd-close-btn:hover { color: #e74c3c; border-color: #e74c3c; }

.ecd-titre-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 10px;
}

.ecd-titre-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #ccc;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}

.ecd-titre-input {
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
.ecd-titre-input:focus { border-color: #00a8a8; }

.ecd-error-bar {
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

.ecd-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.ecd-body::-webkit-scrollbar { width: 4px; }
.ecd-body::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.1); border-radius: 2px; }

/* ── Contexte client / site ──────────────────────────────────────── */
.ecd-context {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
  padding: 10px 12px;
  background: rgba(0, 168, 168, 0.04);
  border: 1px solid rgba(0, 168, 168, 0.18);
  border-radius: 6px;
}
.ecd-context__item { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.ecd-context__lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #9aa0aa;
  text-transform: uppercase;
}
.ecd-context__val {
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

.ecd-sec { display: flex; flex-direction: column; gap: 10px; }

.ecd-sec-hdr {
  display: flex;
  align-items: center;
  gap: 7px;
}

.ecd-sec-mark {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  flex-shrink: 0;
}
.ecd-sec-mark--teal  { background: #00a8a8; }
.ecd-sec-mark--navy  { background: #000b23; }
.ecd-sec-mark--amber { background: #f39c12; }

.ecd-sec-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #aaa;
  text-transform: uppercase;
  white-space: nowrap;
}

.ecd-sec-rule { flex: 1; height: 1px; background: rgba(0, 0, 0, 0.06); }

.ecd-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 14px;
}

.ecd-full { grid-column: 1 / -1; }

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

.ecd-textarea {
  height: auto;
  padding: 7px 8px;
  resize: vertical;
  line-height: 1.5;
  min-height: 80px;
}

.ecd-footer {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.ecd-btn-cancel {
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
.ecd-btn-cancel:hover { border-color: #aaa; }

.ecd-btn-save {
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
.ecd-btn-save:hover:not(:disabled) { background: #00a8a8; }
.ecd-btn-save:disabled { opacity: 0.6; cursor: not-allowed; }

.ecd-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: ecd-spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes ecd-spin { to { transform: rotate(360deg); } }
</style>
