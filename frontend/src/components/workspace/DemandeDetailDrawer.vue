<template>
  <div class="ddd-overlay" @click.self="emit('close')">
    <div class="ddd-panel" role="dialog" aria-modal="true">

      <!-- ── Header ──────────────────────────────────────────────────────── -->
      <div class="ddd-hdr">
        <p class="ddd-ctx">
          <span>DEMANDES</span>
          <span class="ddd-ctx__sep">›</span>
          <span :class="['ddd-ctx__type', `ddd-ctx__type--${demande.type_demande}`]">
            {{ TYPE_LABELS[demande.type_demande] ?? demande.type_demande }}
          </span>
          <span class="ddd-ctx__sep">›</span>
          <span class="ddd-ctx__ticket">{{ demande.numero_ticket }}</span>
        </p>
        <div class="ddd-title-row">
          <span :class="['ddd-marker', `ddd-marker--${demande.type_demande}`]"></span>
          <h2 class="ddd-title">{{ demande.titre }}</h2>
          <span class="ddd-hdr-spacer"></span>
          <button class="ddd-close-btn" @click="emit('close')">
            <v-icon size="15">mdi-close</v-icon>
          </button>
        </div>
        <div class="ddd-status-row">
          <span :class="['ddd-statut', `ddd-statut--${demande.statut}`]">
            {{ STATUT_LABELS[demande.statut] ?? demande.statut }}
          </span>
          <span :class="['ddd-prio', `ddd-prio--${demande.priorite}`]">
            {{ PRIO_LABELS[demande.priorite] ?? demande.priorite }}
          </span>
          <span class="ddd-date">{{ formatDate(demande.created_at) }}</span>
        </div>
      </div>

      <!-- ── Corps scrollable ────────────────────────────────────────────── -->
      <div class="ddd-body">

        <!-- CONTEXTE ─────────────────────────────────────────────────────── -->
        <section class="ddd-sec">
          <header class="ddd-sec-hdr">
            <span class="ddd-sec-mark ddd-sec-mark--navy"></span>
            <span class="ddd-sec-lbl">CONTEXTE</span>
            <span class="ddd-sec-rule"></span>
          </header>
          <div class="ddd-meta-grid">
            <div class="ddd-field">
              <span class="ddd-lbl">Client</span>
              <span class="ddd-val">
                <img v-if="demande.client_logo_url" :src="fileUrl(demande.client_logo_url)" class="ddd-logo-sm" />
                <v-icon v-else size="11" color="#00a8a8">mdi-domain</v-icon>
                {{ demande.client_nom || '—' }}
              </span>
            </div>
            <div class="ddd-field">
              <span class="ddd-lbl">Site</span>
              <span class="ddd-val">
                <img v-if="demande.site_logo_url" :src="fileUrl(demande.site_logo_url)" class="ddd-logo-sm" />
                <v-icon v-else size="11" color="#00a8a8">mdi-map-marker-outline</v-icon>
                {{ demande.site_nom || '—' }}
              </span>
            </div>
            <div class="ddd-field">
              <span class="ddd-lbl">Demandeur</span>
              <span class="ddd-val">
                <img :src="resolveAvatar(demande.contact_avatar_url, demande.contact_nom)" class="ddd-avatar-sm" />
                {{ demande.contact_nom || '—' }}
              </span>
            </div>
            <div class="ddd-field">
              <span class="ddd-lbl">Prise en charge</span>
              <span class="ddd-val">
                <img :src="resolveAvatar(demande.permanencier_avatar_url, demande.permanencier_nom)" class="ddd-avatar-sm" />
                {{ demande.permanencier_nom || '—' }}
              </span>
            </div>
          </div>
        </section>

        <!-- DESCRIPTION ──────────────────────────────────────────────────── -->
        <section v-if="demande.description" class="ddd-sec">
          <header class="ddd-sec-hdr">
            <span class="ddd-sec-mark ddd-sec-mark--teal"></span>
            <span class="ddd-sec-lbl">DESCRIPTION</span>
            <span class="ddd-sec-rule"></span>
          </header>
          <div class="ddd-desc">{{ demande.description }}</div>
        </section>

        <!-- ANOMALIE ─────────────────────────────────────────────────────── -->
        <section v-if="demande.type_demande === 'anomalie'" class="ddd-sec">
          <header class="ddd-sec-hdr">
            <span class="ddd-sec-mark ddd-sec-mark--red"></span>
            <span class="ddd-sec-lbl">QUALIFICATION DE L'ANOMALIE</span>
            <span class="ddd-sec-rule"></span>
          </header>
          <div class="ddd-chips-row">
            <span v-if="demande.nature_anomalie" class="ddd-chip">
              {{ NATURE_LABELS[demande.nature_anomalie] ?? demande.nature_anomalie }}
            </span>
            <span v-if="demande.impact_securite" class="ddd-chip ddd-chip--danger">
              <v-icon size="10">mdi-alert</v-icon> Impact sécurité
            </span>
          </div>
          <div v-if="demande.equipement_concerne" class="ddd-kv">
            <span class="ddd-lbl">Équipement concerné</span>
            <span class="ddd-kv-val">{{ demande.equipement_concerne }}</span>
          </div>
          <!-- Agent concerné -->
          <div v-if="demande.agent_concerne_label" class="ddd-agent-row">
            <img :src="resolveAvatar(demande.agent_concerne_avatar_url, demande.agent_concerne_label)" class="ddd-avatar-lg" />
            <div class="ddd-agent-content">
              <span class="ddd-lbl">Agent concerné</span>
              <span class="ddd-agent-name">{{ demande.agent_concerne_label }}</span>
            </div>
          </div>
          <!-- Action PEC -->
          <div v-if="demande.action_corrective" class="ddd-pec-block">
            <div class="ddd-pec-header">
              <v-icon size="12" color="#00a8a8">mdi-clipboard-check-outline</v-icon>
              ACTION DE PRISE EN CHARGE (PEC)
            </div>
            <p class="ddd-pec-text">{{ demande.action_corrective }}</p>
          </div>
        </section>

        <!-- COMMANDE ─────────────────────────────────────────────────────── -->
        <section v-if="demande.type_demande === 'commande'" class="ddd-sec">
          <header class="ddd-sec-hdr">
            <span class="ddd-sec-mark ddd-sec-mark--teal"></span>
            <span class="ddd-sec-lbl">DÉTAILS COMMANDE</span>
            <span class="ddd-sec-rule"></span>
          </header>
          <div class="ddd-meta-grid">
            <div v-if="demande.type_commande" class="ddd-field">
              <span class="ddd-lbl">Type de prestation</span>
              <span class="ddd-kv-val">{{ COMMANDE_LABELS[demande.type_commande] ?? demande.type_commande }}</span>
            </div>
            <div v-if="demande.quantite" class="ddd-field">
              <span class="ddd-lbl">Quantité</span>
              <span class="ddd-kv-val">{{ demande.quantite }}</span>
            </div>
            <div v-if="demande.budget_estime" class="ddd-field">
              <span class="ddd-lbl">Budget estimé</span>
              <span class="ddd-kv-val">{{ demande.budget_estime }}</span>
            </div>
            <div v-if="demande.date_livraison_souhaitee" class="ddd-field">
              <span class="ddd-lbl">Livraison souhaitée</span>
              <span class="ddd-kv-val">{{ formatDate(demande.date_livraison_souhaitee) }}</span>
            </div>
            <div v-if="demande.bon_commande" class="ddd-field">
              <span class="ddd-lbl">Bon de commande</span>
              <span class="ddd-kv-val">{{ demande.bon_commande }}</span>
            </div>
            <div v-if="demande.fournisseur_suggere" class="ddd-field">
              <span class="ddd-lbl">Fournisseur suggéré</span>
              <span class="ddd-kv-val">{{ demande.fournisseur_suggere }}</span>
            </div>
          </div>
        </section>

        <!-- PLANNING ─────────────────────────────────────────────────────── -->
        <section v-if="demande.type_demande === 'planning'" class="ddd-sec">
          <header class="ddd-sec-hdr">
            <span class="ddd-sec-mark ddd-sec-mark--blue"></span>
            <span class="ddd-sec-lbl">MODIFICATION PLANNING</span>
            <span class="ddd-sec-rule"></span>
          </header>
          <div v-if="demande.type_modification" class="ddd-chips-row">
            <span class="ddd-chip ddd-chip--blue">
              {{ PLANNING_LABELS[demande.type_modification] ?? demande.type_modification }}
            </span>
          </div>
          <div class="ddd-meta-grid">
            <div v-if="demande.agent_concerne_label" class="ddd-field">
              <span class="ddd-lbl">Agent concerné</span>
              <span class="ddd-val">
                <img :src="resolveAvatar(demande.agent_concerne_avatar_url, demande.agent_concerne_label)" class="ddd-avatar-sm ddd-avatar-sm--amber" />
                {{ demande.agent_concerne_label }}
              </span>
            </div>
            <div v-if="demande.agent_remplacant_label" class="ddd-field">
              <span class="ddd-lbl">Agent remplaçant</span>
              <span class="ddd-val">
                <img :src="resolveAvatar(demande.agent_remplacant_avatar_url, demande.agent_remplacant_label)" class="ddd-avatar-sm ddd-avatar-sm--blue" />
                {{ demande.agent_remplacant_label }}
              </span>
            </div>
            <div v-if="demande.date_debut" class="ddd-field">
              <span class="ddd-lbl">Début</span>
              <span class="ddd-kv-val">{{ formatDate(demande.date_debut) }}</span>
            </div>
            <div v-if="demande.date_fin" class="ddd-field">
              <span class="ddd-lbl">Fin</span>
              <span class="ddd-kv-val">{{ formatDate(demande.date_fin) }}</span>
            </div>
          </div>
          <div v-if="demande.motif" class="ddd-kv">
            <span class="ddd-lbl">Motif</span>
            <p class="ddd-pec-text">{{ demande.motif }}</p>
          </div>
        </section>

        <!-- ADMIN ────────────────────────────────────────────────────────── -->
        <section v-if="demande.type_demande === 'admin'" class="ddd-sec">
          <header class="ddd-sec-hdr">
            <span class="ddd-sec-mark ddd-sec-mark--purple"></span>
            <span class="ddd-sec-lbl">DOSSIER ADMINISTRATIF</span>
            <span class="ddd-sec-rule"></span>
          </header>
          <div class="ddd-meta-grid">
            <div v-if="demande.categorie" class="ddd-field">
              <span class="ddd-lbl">Catégorie</span>
              <span class="ddd-kv-val">{{ ADMIN_CAT_LABELS[demande.categorie] ?? demande.categorie }}</span>
            </div>
            <div v-if="demande.document_type" class="ddd-field">
              <span class="ddd-lbl">Type de document</span>
              <span class="ddd-kv-val">{{ ADMIN_DOC_LABELS[demande.document_type] ?? demande.document_type }}</span>
            </div>
            <div v-if="demande.date_echeance" class="ddd-field">
              <span class="ddd-lbl">Échéance</span>
              <span class="ddd-kv-val">{{ formatDate(demande.date_echeance) }}</span>
            </div>
            <div class="ddd-field">
              <span class="ddd-lbl">Validation requise</span>
              <span :class="['ddd-kv-val', demande.validation_requise ? 'ddd-kv-val--yes' : '']">
                {{ demande.validation_requise ? 'Oui' : 'Non' }}
              </span>
            </div>
          </div>
        </section>

        <!-- INTERACTIONS ─────────────────────────────────────────────────── -->
        <DemandeInteractions
          ref="interactionsRef"
          :demande-id="demande.id"
          :prefilled-contact-id="props.prefilledContactId"
          :prefilled-contact-nom="props.prefilledContactNom"
        />

      </div>

      <!-- ── Footer ──────────────────────────────────────────────────────── -->
      <div class="ddd-footer">
        <button class="ddd-btn-close" @click="emit('close')">FERMER</button>
        <button class="ddd-btn-suivi" @click="interactionsRef?.focusForm()">
          <v-icon size="11">mdi-pencil-plus-outline</v-icon>
          SUIVI
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import DemandeInteractions from "@/components/workspace/DemandeInteractions.vue";

const props = defineProps({
  demande:             { type: Object, required: true },
  prefilledContactId:  { type: Number, default: null },
  prefilledContactNom: { type: String, default: null },
});
const emit = defineEmits(["close"]);

const interactionsRef = ref(null);

const TYPE_LABELS   = { anomalie: "ANO", commande: "CMD", planning: "PLN", admin: "ADM" };
const STATUT_LABELS = {
  nouvelle: "Nouvelle", en_cours: "En cours", en_attente: "En attente",
  resolue: "Résolue", cloturee: "Clôturée", annulee: "Annulée",
};
const PRIO_LABELS = { basse: "↓ Basse", normale: "→ Normale", haute: "↑ Haute", urgente: "⚡ Urgente" };

const NATURE_LABELS = {
  anj:                         "Absence non justifiée (ANJ)",
  absence_justifiee:           "Absence justifiée",
  retard_prise_service:        "Retard prise de service",
  agent_non_sur_site:          "Agent non sur site",
  doublon_planning:            "Doublon planning",
  remplacement_permutation:    "Remplacement / permutation",
  modification_vacation:       "Modification vacation",
  probleme_technique:          "Problème technique",
  site_prestataire_injoignable:"Site / prestataire injoignable",
  blocage_outil_rh:            "Blocage outil / RH",
  demande_de_renfort:          "Demande de renfort",
  anomalie_facturation:        "Anomalie facturation",
  autre:                       "Autre",
};

const COMMANDE_LABELS = {
  gardiennage:           "Gardiennage",
  surveillance_mobile:   "Surveillance mobile",
  rondes:                "Rondes",
  intervention:          "Intervention",
  filtrage:              "Filtrage",
  protection_rapprochee: "Protection rapprochée",
  accueil_securite:      "Accueil sécurité",
  autre:                 "Autre",
};

const PLANNING_LABELS = {
  absence:     "Absence",
  conge:       "Congé",
  formation:   "Formation",
  reunion:     "Réunion",
  remplacement:"Remplacement",
  autre:       "Autre",
};

const ADMIN_CAT_LABELS = {
  ressources_humaines: "Ressources humaines",
  comptabilite:        "Comptabilité",
  contrat:             "Contrat",
  politique:           "Politique",
  autre:               "Autre",
};

const ADMIN_DOC_LABELS = {
  contrat:            "Contrat",
  facture:            "Facture",
  rapport:            "Rapport",
  demande_officielle: "Demande officielle",
  approbation:        "Approbation",
  autre:              "Autre",
};

const BACKEND_ORIGIN = (import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api").replace(/\/api\/?$/, "");

function fileUrl(path) {
  if (!path) return null;
  if (/^https?:\/\//.test(path)) return path;
  return BACKEND_ORIGIN + path;
}

function resolveAvatar(url, name) {
  const full = fileUrl(url);
  if (full) return full;
  const seed = encodeURIComponent(name ?? "user");
  return `https://api.dicebear.com/8.x/initials/svg?seed=${seed}&backgroundColor=15223a&textColor=ffffff`;
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}
</script>

<script>
export default { name: "DemandeDetailDrawer" };
</script>

<style scoped>
/* ── Overlay ─────────────────────────────────────────────────────────────── */
.ddd-overlay {
  position: fixed;
  top: var(--v-layout-top, 48px);
  right: 0;
  bottom: 0;
  left: 0;
  background: rgba(0, 11, 35, 0.4);
  z-index: 300;
  display: flex;
  justify-content: flex-end;
}

/* ── Panneau ─────────────────────────────────────────────────────────────── */
.ddd-panel {
  width: 500px;
  max-width: 100vw;
  height: 100%;
  background: #fff;
  display: flex;
  flex-direction: column;
  animation: ddd-slide 0.22s ease;
  box-shadow: -4px 0 28px rgba(0, 11, 35, 0.14);
}

@keyframes ddd-slide {
  from { transform: translateX(100%); }
  to   { transform: translateX(0); }
}

/* ── Header ──────────────────────────────────────────────────────────────── */
.ddd-hdr {
  flex-shrink: 0;
  padding: 14px 18px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.ddd-ctx {
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
.ddd-ctx__sep    { color: #e0e0e0; }
.ddd-ctx__ticket { color: #00a8a8; font-weight: 600; }

.ddd-ctx__type--anomalie { color: #e74c3c; font-weight: 700; }
.ddd-ctx__type--commande { color: #007a7a; font-weight: 700; }
.ddd-ctx__type--planning { color: #1a73c1; font-weight: 700; }
.ddd-ctx__type--admin    { color: #7d3c98; font-weight: 700; }

.ddd-title-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}

.ddd-marker {
  width: 3px;
  height: 16px;
  border-radius: 1px;
  flex-shrink: 0;
  margin-top: 2px;
}
.ddd-marker--anomalie { background: #e74c3c; }
.ddd-marker--commande { background: #00a8a8; }
.ddd-marker--planning { background: #3498db; }
.ddd-marker--admin    { background: #8e44ad; }

.ddd-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  font-weight: 800;
  color: #000b23;
  margin: 0;
  line-height: 1.3;
  flex: 1;
  word-break: break-word;
}

.ddd-hdr-spacer { flex-shrink: 0; width: 4px; }

.ddd-close-btn {
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
.ddd-close-btn:hover { color: #e74c3c; border-color: rgba(231, 76, 60, 0.4); }

.ddd-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 12px;
}

.ddd-statut {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  padding: 2px 8px;
  border-radius: 10px;
}
.ddd-statut--nouvelle   { background: #eaf4fb; color: #1a73c1; }
.ddd-statut--en_cours   { background: rgba(0, 168, 168, 0.1); color: #007a7a; }
.ddd-statut--en_attente { background: #fef9e7; color: #b7770d; }
.ddd-statut--resolue    { background: #eafaf1; color: #1e8449; }
.ddd-statut--cloturee   { background: #f4f6f7; color: #707b7c; }
.ddd-statut--annulee    { background: rgba(231, 76, 60, 0.07); color: #c0392b; }

.ddd-prio {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #777;
}
.ddd-prio--haute   { color: #e67e22; }
.ddd-prio--urgente { color: #e74c3c; }
.ddd-prio--normale { color: #3498db; }
.ddd-prio--basse   { color: #aaa; }

.ddd-date {
  font-family: "Fira Code", monospace;
  font-size: 9px;
  color: #bbb;
  margin-left: auto;
}

/* ── Corps ───────────────────────────────────────────────────────────────── */
.ddd-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.ddd-body::-webkit-scrollbar { width: 4px; }
.ddd-body::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.1); border-radius: 2px; }

/* ── Sections ────────────────────────────────────────────────────────────── */
.ddd-sec { display: flex; flex-direction: column; gap: 10px; }

.ddd-sec-hdr {
  display: flex;
  align-items: center;
  gap: 7px;
}

.ddd-sec-mark {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  flex-shrink: 0;
}
.ddd-sec-mark--navy   { background: #000b23; }
.ddd-sec-mark--teal   { background: #00a8a8; }
.ddd-sec-mark--red    { background: #e74c3c; }
.ddd-sec-mark--blue   { background: #3498db; }
.ddd-sec-mark--purple { background: #8e44ad; }

.ddd-sec-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #aaa;
  text-transform: uppercase;
  white-space: nowrap;
}

.ddd-sec-rule { flex: 1; height: 1px; background: rgba(0, 0, 0, 0.06); }

/* ── Grille méta 2 colonnes ──────────────────────────────────────────────── */
.ddd-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
}

.ddd-field {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.ddd-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
  white-space: nowrap;
}

.ddd-val {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: #222;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ddd-kv-val {
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: #222;
}
.ddd-kv-val--yes { color: #1e8449; }

.ddd-kv {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

/* ── Description ─────────────────────────────────────────────────────────── */
.ddd-desc {
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  color: #444;
  line-height: 1.6;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 3px;
  border-left: 2px solid rgba(0, 168, 168, 0.3);
}

/* ── Chips ───────────────────────────────────────────────────────────────── */
.ddd-chips-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ddd-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: "Fira Sans", sans-serif;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 3px 9px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.05);
  color: #555;
}
.ddd-chip--danger { background: rgba(231, 76, 60, 0.1); color: #c0392b; }
.ddd-chip--blue   { background: rgba(52, 152, 219, 0.1); color: #1a73c1; }

/* ── Logos ───────────────────────────────────────────────────────────────── */
.ddd-logo-sm {
  height: 20px;
  width: auto;
  max-width: 48px;
  flex-shrink: 0;
  object-fit: contain;
  border-radius: 2px;
}

/* ── Avatars ─────────────────────────────────────────────────────────────── */
.ddd-avatar-sm {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  flex-shrink: 0;
  object-fit: cover;
  border: 1.5px solid rgba(0, 11, 35, 0.1);
}
.ddd-avatar-sm--amber { border-color: rgba(243, 156, 18, 0.35); }
.ddd-avatar-sm--blue  { border-color: rgba(52, 152, 219, 0.35); }

.ddd-avatar-lg {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  flex-shrink: 0;
  object-fit: cover;
  border: 2px solid rgba(243, 156, 18, 0.3);
}

/* ── Agent concerné ──────────────────────────────────────────────────────── */
.ddd-agent-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: rgba(243, 156, 18, 0.05);
  border: 1px solid rgba(243, 156, 18, 0.2);
  border-radius: 4px;
}

.ddd-agent-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.ddd-agent-name {
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 700;
  color: #000b23;
}

/* ── Action PEC ──────────────────────────────────────────────────────────── */
.ddd-pec-block {
  border-left: 2px solid #00a8a8;
  padding: 8px 12px;
  background: rgba(0, 168, 168, 0.03);
  border-radius: 0 3px 3px 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.ddd-pec-header {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #00a8a8;
  text-transform: uppercase;
}

.ddd-pec-text {
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  color: #444;
  line-height: 1.5;
  margin: 0;
}

/* ── Footer ──────────────────────────────────────────────────────────────── */
.ddd-footer {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 18px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
}

.ddd-btn-close {
  height: 30px;
  padding: 0 18px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 3px;
  background: #fff;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #555;
  cursor: pointer;
  transition: border-color 0.15s;
}
.ddd-btn-close:hover { border-color: #aaa; }

.ddd-btn-suivi {
  display: inline-flex;
  align-items: center;
  gap: 5px;
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
.ddd-btn-suivi:hover { background: #3498db; }
</style>
