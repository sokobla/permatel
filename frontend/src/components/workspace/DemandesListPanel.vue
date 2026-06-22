<template>
  <div class="dlp-root">

    <!-- ══ PANNEAU DÉTAIL LATÉRAL ════════════════════════════════════════════ -->
    <DemandeDetailDrawer
      v-if="detailDemande"
      :demande="detailDemande"
      :prefilled-contact-id="props.contactId"
      :prefilled-contact-nom="props.contactNom"
      @close="detailDemande = null"
    />

    <!-- ══ TOOLBAR ══════════════════════════════════════════════════════════ -->
    <div class="dlp-toolbar">
      <div class="dlp-toolbar-left">
        <span class="dlp-title">DEMANDES</span>
        <span v-if="!loading" class="dlp-count">{{ filtered.length }}</span>
        <span v-else class="dlp-count dlp-count--loading">…</span>
      </div>
      <div class="dlp-toolbar-right">
        <select v-model="filterType" class="dlp-filter-sel">
          <option value="">Tous types</option>
          <option value="anomalie">Anomalie</option>
          <option value="commande">Commande</option>
          <option value="planning">Planning</option>
          <option value="admin">Administratif</option>
        </select>
        <select v-model="filterStatut" class="dlp-filter-sel">
          <option value="">Tous statuts</option>
          <option value="nouvelle">Nouvelle</option>
          <option value="en_cours">En cours</option>
          <option value="en_attente">En attente</option>
          <option value="resolue">Résolue</option>
          <option value="cloturee">Clôturée</option>
          <option value="annulee">Annulée</option>
        </select>
        <button class="dlp-refresh-btn" :disabled="loading" title="Actualiser" @click="load">
          <v-icon size="13" :class="{ 'dlp-spin': loading }">mdi-refresh</v-icon>
        </button>
      </div>
    </div>

    <!-- ══ ERROR ════════════════════════════════════════════════════════════ -->
    <div v-if="loadError" class="dlp-error-bar">
      <v-icon size="12" color="#e74c3c">mdi-alert-circle-outline</v-icon>
      {{ loadError }}
    </div>

    <!-- ══ EMPTY ════════════════════════════════════════════════════════════ -->
    <div v-if="!loading && !loadError && filtered.length === 0" class="dlp-empty">
      <v-icon size="32" color="#ddd">mdi-text-box-check-outline</v-icon>
      <p class="dlp-empty__text">Aucune demande trouvée</p>
      <p class="dlp-empty__sub">Utilisez <strong>NOUVELLE DEMANDE</strong> pour en créer une.</p>
    </div>

    <!-- ══ SKELETON ══════════════════════════════════════════════════════════ -->
    <div v-if="loading" class="dlp-list">
      <div v-for="n in 3" :key="n" class="dlp-row dlp-row--skeleton">
        <div class="dlp-sk dlp-sk--badge"></div>
        <div class="dlp-sk dlp-sk--title"></div>
        <div class="dlp-sk dlp-sk--status"></div>
        <div class="dlp-sk dlp-sk--date"></div>
      </div>
    </div>

    <!-- ══ LISTE ════════════════════════════════════════════════════════════ -->
    <div v-else-if="filtered.length > 0" class="dlp-list">
      <transition-group name="dlp-fade" tag="div">
        <div
          v-for="d in filtered"
          :key="d.id"
          :class="['dlp-row', { 'dlp-row--expanded': expanded === d.id }]"
        >
          <!-- ─ Ligne principale ─ -->
          <div class="dlp-row-main" @click="toggleExpand(d.id)">

            <!-- Type badge -->
            <span :class="['dlp-badge', `dlp-badge--${d.type_demande}`]">
              {{ TYPE_LABELS[d.type_demande] ?? d.type_demande }}
            </span>

            <!-- Ticket + titre -->
            <div class="dlp-row-info">
              <span class="dlp-ticket">{{ d.numero_ticket }}</span>
              <span class="dlp-titre">{{ d.titre }}</span>
            </div>

            <!-- Priorité -->
            <span :class="['dlp-prio', `dlp-prio--${d.priorite}`]">
              {{ PRIO_LABELS[d.priorite] ?? d.priorite }}
            </span>

            <!-- Statut -->
            <span :class="['dlp-statut', `dlp-statut--${d.statut}`]">
              {{ STATUT_LABELS[d.statut] ?? d.statut }}
            </span>

            <!-- Date -->
            <span class="dlp-date">{{ formatDate(d.created_at) }}</span>

            <!-- Chevron -->
            <v-icon size="13" class="dlp-chevron">
              {{ expanded === d.id ? 'mdi-chevron-up' : 'mdi-chevron-down' }}
            </v-icon>
          </div>

          <!-- ─ Panneau détail / actions ─ -->
          <div v-if="expanded === d.id" class="dlp-detail">

            <!-- Méta-infos : demandeur, site, client, prise en charge -->
            <div class="dlp-meta-grid">
              <div class="dlp-meta-item">
                <span class="dlp-detail-lbl">Demandeur</span>
                <span class="dlp-meta-val">
                  <img :src="resolveAvatar(d.contact_avatar_url, d.contact_nom)" class="dlp-avatar-sm" />
                  {{ d.contact_nom || '—' }}
                </span>
              </div>
              <div class="dlp-meta-item">
                <span class="dlp-detail-lbl">Client</span>
                <span class="dlp-meta-val">
                  <img v-if="d.client_logo_url" :src="fileUrl(d.client_logo_url)" class="dlp-logo-sm" />
                  <v-icon v-else size="11" color="#00a8a8">mdi-domain</v-icon>
                  {{ d.client_nom || '—' }}
                </span>
              </div>
              <div class="dlp-meta-item">
                <span class="dlp-detail-lbl">Site</span>
                <span class="dlp-meta-val">
                  <img v-if="d.site_logo_url" :src="fileUrl(d.site_logo_url)" class="dlp-logo-sm" />
                  <v-icon v-else size="11" color="#00a8a8">mdi-map-marker-outline</v-icon>
                  {{ d.site_nom || '—' }}
                </span>
              </div>
              <div class="dlp-meta-item">
                <span class="dlp-detail-lbl">Prise en charge</span>
                <span class="dlp-meta-val">
                  <img :src="resolveAvatar(d.permanencier_avatar_url, d.permanencier_nom)" class="dlp-avatar-sm" />
                  {{ d.permanencier_nom || '—' }}
                </span>
              </div>
              <!-- Agent concerné (anomalie / planning uniquement) -->
              <div
                v-if="d.agent_concerne_label"
                class="dlp-meta-item dlp-meta-item--full"
              >
                <span class="dlp-detail-lbl">Agent concerné</span>
                <span class="dlp-meta-val dlp-meta-val--agent">
                  <img :src="resolveAvatar(d.agent_concerne_avatar_url, d.agent_concerne_label)" class="dlp-avatar-sm dlp-avatar-sm--amber" />
                  {{ d.agent_concerne_label }}
                </span>
              </div>
            </div>

            <div v-if="d.description" class="dlp-detail-desc">
              {{ d.description }}
            </div>

            <div class="dlp-detail-row">
              <div class="dlp-detail-field">
                <span class="dlp-detail-lbl">CHANGER STATUT</span>
                <select
                  :value="d.statut"
                  class="dlp-status-sel"
                  :disabled="patchingId === d.id"
                  @change="onStatusChange(d, $event.target.value)"
                >
                  <option value="nouvelle">Nouvelle</option>
                  <option value="en_cours">En cours</option>
                  <option value="en_attente">En attente</option>
                  <option value="resolue">Résolue</option>
                  <option value="cloturee">Clôturée</option>
                  <option value="annulee">Annulée</option>
                </select>
                <v-icon v-if="patchingId === d.id" size="13" class="dlp-spin" color="#00a8a8">
                  mdi-loading
                </v-icon>
              </div>

              <div class="dlp-detail-actions">
                <!-- Bouton PEC : visible uniquement si statut est nouvelle -->
                <button
                  v-if="d.statut === 'nouvelle'"
                  class="dlp-btn dlp-btn--pec"
                  :disabled="pecingId === d.id"
                  @click.stop="onPEC(d)"
                >
                  <v-icon v-if="pecingId === d.id" size="12" class="dlp-spin">mdi-loading</v-icon>
                  <v-icon v-else size="12">mdi-play-circle-outline</v-icon>
                  PEC
                </button>

                <!-- Bouton DÉTAIL -->
                <button
                  class="dlp-btn dlp-btn--detail"
                  @click.stop="detailDemande = d"
                >
                  <v-icon size="12">mdi-eye-outline</v-icon>
                  DÉTAIL
                </button>

                <button
                  :class="['dlp-btn', suiviOpenId === d.id ? 'dlp-btn--suivi-active' : 'dlp-btn--suivi']"
                  @click.stop="toggleSuivi(d.id)"
                >
                  <v-icon size="12">mdi-pencil-plus-outline</v-icon>
                  SUIVI
                </button>

                <button
                  v-if="canDelete && confirmDeleteId !== d.id"
                  class="dlp-btn dlp-btn--danger"
                  :disabled="deletingId === d.id"
                  @click.stop="confirmDeleteId = d.id"
                >
                  <v-icon size="12">mdi-trash-can-outline</v-icon>
                  SUPPRIMER
                </button>
                <template v-else-if="canDelete">
                  <span class="dlp-confirm-txt">Confirmer ?</span>
                  <button class="dlp-btn dlp-btn--danger-confirm" @click.stop="onDelete(d.id)">
                    OUI
                  </button>
                  <button class="dlp-btn dlp-btn--cancel" @click.stop="confirmDeleteId = null">
                    NON
                  </button>
                </template>
              </div>
            </div>

            <p v-if="actionError === d.id" class="dlp-action-error">
              Une erreur s'est produite. Réessayez.
            </p>

            <!-- ─ Formulaire de suivi ─ -->
            <div v-if="suiviOpenId === d.id" class="dlp-suivi" @click.stop>
              <div class="dlp-suivi-header">
                <v-icon size="12" color="#00a8a8">mdi-pencil-plus-outline</v-icon>
                NOUVELLE INTERACTION
              </div>
              <div class="dlp-suivi-fields">
                <div class="dlp-suivi-field">
                  <!-- Contact verrouillé (contexte workspace) -->
                  <div v-if="props.contactId" class="dlp-suivi-contact">
                    <v-icon size="10" color="#00a8a8">mdi-account-outline</v-icon>
                    {{ props.contactNom ?? `Contact #${props.contactId}` }}
                  </div>
                  <label class="dlp-detail-lbl">TYPE</label>
                  <select v-model="suiviForm.type_interaction" class="dlp-status-sel">
                    <option value="appel">Appel téléphonique</option>
                    <option value="email">Email</option>
                    <option value="whatsapp">WhatsApp</option>
                    <option value="note">Note interne</option>
                  </select>
                </div>
                <textarea
                  v-model="suiviForm.contenu"
                  class="dlp-suivi-textarea"
                  placeholder="Détails de l'interaction…"
                  rows="3"
                  :disabled="suiviSubmitting"
                ></textarea>
                <p v-if="suiviError" class="dlp-action-error">{{ suiviError }}</p>
                <div class="dlp-suivi-actions">
                  <button
                    class="dlp-btn dlp-btn--suivi-submit"
                    :disabled="suiviSubmitting || !suiviForm.contenu.trim()"
                    @click.stop="onSuiviSubmit(d.id)"
                  >
                    <v-icon v-if="suiviSubmitting" size="12" class="dlp-spin">mdi-loading</v-icon>
                    <v-icon v-else size="12">mdi-check</v-icon>
                    {{ suiviSubmitting ? 'ENREGISTREMENT…' : 'ENREGISTRER' }}
                  </button>
                  <button
                    class="dlp-btn dlp-btn--cancel"
                    :disabled="suiviSubmitting"
                    @click.stop="suiviOpenId = null"
                  >
                    ANNULER
                  </button>
                </div>
              </div>
            </div>

          </div>

        </div>
      </transition-group>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from "vue";
import {
  listDemandes,
  patchDemandeStatus,
  pecDemande,
  deleteDemande,
} from "@/services/demandeService";
import { createInteraction } from "@/services/interactionService";
import DemandeDetailDrawer from "@/components/workspace/DemandeDetailDrawer.vue";
import { useAuthStore } from "@/store/auth";

// RBAC : seuls ADMIN/MANAGER peuvent supprimer
const authStore = useAuthStore();
const canDelete = computed(() => authStore.canDelete);

const props = defineProps({
  contactId:  { type: Number, default: null },
  contactNom: { type: String, default: null },
  clientId:   { type: Number, default: null },
});

const emit = defineEmits(["refresh"]);

const TYPE_LABELS = {
  anomalie: "ANO",
  commande: "CMD",
  planning: "PLN",
  admin:    "ADM",
};

const STATUT_LABELS = {
  nouvelle:   "Nouvelle",
  en_cours:   "En cours",
  en_attente: "En attente",
  resolue:    "Résolue",
  cloturee:   "Clôturée",
  annulee:    "Annulée",
};

const PRIO_LABELS = {
  basse:   "↓",
  normale: "→",
  haute:   "↑",
  urgente: "⚡",
};

const demandes      = ref([]);
const loading       = ref(false);
const loadError     = ref("");
const filterType    = ref("");
const filterStatut  = ref("");
const expanded      = ref(null);
const patchingId    = ref(null);
const deletingId    = ref(null);
const confirmDeleteId = ref(null);
const actionError   = ref(null);

const detailDemande  = ref(null);
const pecingId       = ref(null);

const suiviOpenId    = ref(null);
const suiviForm      = reactive({ type_interaction: "note", contenu: "" });
const suiviSubmitting = ref(false);
const suiviError     = ref("");

const filtered = computed(() => {
  let list = demandes.value;
  if (filterType.value)   list = list.filter((d) => d.type_demande === filterType.value);
  if (filterStatut.value) list = list.filter((d) => d.statut === filterStatut.value);
  return list;
});

async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    const params = {};
    if (props.contactId) params.contact_id = props.contactId;
    if (props.clientId)  params.client_id  = props.clientId;
    demandes.value = await listDemandes(params);
  } catch {
    loadError.value = "Impossible de charger les demandes.";
  } finally {
    loading.value = false;
  }
}

function toggleExpand(id) {
  expanded.value = expanded.value === id ? null : id;
  confirmDeleteId.value = null;
  actionError.value = null;
  if (suiviOpenId.value !== id) suiviOpenId.value = null;
}

function toggleSuivi(id) {
  if (suiviOpenId.value === id) {
    suiviOpenId.value = null;
  } else {
    suiviOpenId.value = id;
    suiviForm.type_interaction = "note";
    suiviForm.contenu = "";
    suiviError.value = "";
    if (expanded.value !== id) expanded.value = id;
  }
}

async function onSuiviSubmit(demandeId) {
  if (!suiviForm.contenu.trim()) {
    suiviError.value = "Le contenu est requis.";
    return;
  }
  suiviSubmitting.value = true;
  suiviError.value = "";
  try {
    await createInteraction(demandeId, {
      type_interaction: suiviForm.type_interaction,
      contenu: suiviForm.contenu.trim(),
      contact_id: props.contactId ?? null,
    });
    suiviOpenId.value = null;
  } catch {
    suiviError.value = "Erreur lors de l'enregistrement. Réessayez.";
  } finally {
    suiviSubmitting.value = false;
  }
}

async function onPEC(demande) {
  pecingId.value = demande.id;
  actionError.value = null;
  try {
    const updated = await pecDemande(demande.id);
    const idx = demandes.value.findIndex((d) => d.id === demande.id);
    if (idx !== -1) demandes.value[idx] = updated;
    if (detailDemande.value?.id === demande.id) detailDemande.value = updated;
  } catch {
    actionError.value = demande.id;
  } finally {
    pecingId.value = null;
  }
}

async function onStatusChange(demande, newStatut) {
  if (newStatut === demande.statut) return;
  patchingId.value = demande.id;
  actionError.value = null;
  try {
    const updated = await patchDemandeStatus(demande.id, newStatut);
    const idx = demandes.value.findIndex((d) => d.id === demande.id);
    if (idx !== -1) demandes.value[idx] = updated;
  } catch {
    actionError.value = demande.id;
  } finally {
    patchingId.value = null;
  }
}

async function onDelete(id) {
  deletingId.value = id;
  actionError.value = null;
  try {
    await deleteDemande(id);
    demandes.value = demandes.value.filter((d) => d.id !== id);
    expanded.value = null;
    confirmDeleteId.value = null;
    emit("refresh");
  } catch {
    actionError.value = id;
    confirmDeleteId.value = null;
  } finally {
    deletingId.value = null;
  }
}

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

watch(() => props.contactId, load);
watch(() => props.clientId, load);
onMounted(load);
</script>

<script>
export default { name: "DemandesListPanel" };
</script>

<style scoped>
/* ══ RACINE ════════════════════════════════════════════════════════════════ */

.dlp-root {
  display: flex;
  flex-direction: column;
  gap: 0;
  height: 100%;
  overflow: hidden;
}

/* ══ TOOLBAR ════════════════════════════════════════════════════════════════ */

.dlp-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px 8px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  flex-shrink: 0;
}

.dlp-toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dlp-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #000b23;
  text-transform: uppercase;
}

.dlp-count {
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: #00a8a8;
  border-radius: 3px;
  padding: 1px 6px;
  min-width: 18px;
  text-align: center;
}

.dlp-count--loading {
  background: #ccc;
}

.dlp-toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dlp-filter-sel {
  height: 24px;
  padding: 0 6px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  color: #444;
  background: #fafafa;
  cursor: pointer;
  outline: none;
}
.dlp-filter-sel:focus { border-color: rgba(0, 168, 168, 0.4); }

.dlp-refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 3px;
  background: #fafafa;
  cursor: pointer;
  color: #666;
  transition: background 0.15s;
}
.dlp-refresh-btn:hover:not(:disabled) { background: rgba(0, 168, 168, 0.08); }
.dlp-refresh-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ══ ERROR / EMPTY ══════════════════════════════════════════════════════════ */

.dlp-error-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  background: rgba(231, 76, 60, 0.06);
  border-bottom: 1px solid rgba(231, 76, 60, 0.15);
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #c0392b;
  flex-shrink: 0;
}

.dlp-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 6px;
  padding: 40px 20px;
}

.dlp-empty__text {
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 700;
  color: #bbb;
  margin: 0;
  letter-spacing: 0.06em;
}

.dlp-empty__sub {
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #ccc;
  margin: 0;
  text-align: center;
}

/* ══ LISTE ══════════════════════════════════════════════════════════════════ */

.dlp-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dlp-list::-webkit-scrollbar { width: 4px; }
.dlp-list::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.1); border-radius: 2px; }

/* ══ LIGNE ══════════════════════════════════════════════════════════════════ */

.dlp-row {
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 4px;
  background: #fff;
  transition: border-color 0.15s;
  overflow: hidden;
}

.dlp-row:hover { border-color: rgba(0, 168, 168, 0.25); }
.dlp-row--expanded { border-color: rgba(0, 168, 168, 0.4); }

.dlp-row-main {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  cursor: pointer;
  user-select: none;
}

.dlp-chevron {
  margin-left: auto;
  color: #bbb;
  flex-shrink: 0;
}

/* ══ TYPE BADGE ═════════════════════════════════════════════════════════════ */

.dlp-badge {
  font-family: "Fira Code", monospace;
  font-size: 8.5px;
  font-weight: 700;
  letter-spacing: 0.1em;
  padding: 2px 6px;
  border-radius: 2px;
  white-space: nowrap;
  flex-shrink: 0;
}

.dlp-badge--anomalie { background: rgba(231, 76, 60, 0.1);  color: #c0392b; }
.dlp-badge--commande { background: rgba(0, 168, 168, 0.1); color: #007a7a; }
.dlp-badge--planning { background: rgba(52, 152, 219, 0.1); color: #1a73c1; }
.dlp-badge--admin    { background: rgba(142, 68, 173, 0.1); color: #7d3c98; }

/* ══ INFO ═══════════════════════════════════════════════════════════════════ */

.dlp-row-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.dlp-ticket {
  font-family: "Fira Code", monospace;
  font-size: 9px;
  color: #aaa;
  letter-spacing: 0.06em;
}

.dlp-titre {
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 700;
  color: #000b23;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ══ PRIORITÉ ═══════════════════════════════════════════════════════════════ */

.dlp-prio {
  font-family: "Fira Code", monospace;
  font-size: 12px;
  flex-shrink: 0;
}

.dlp-prio--basse   { color: #aaa; }
.dlp-prio--normale { color: #3498db; }
.dlp-prio--haute   { color: #e67e22; }
.dlp-prio--urgente { color: #e74c3c; }

/* ══ STATUT ══════════════════════════════════════════════════════════════════ */

.dlp-statut {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  padding: 2px 7px;
  border-radius: 10px;
  white-space: nowrap;
  flex-shrink: 0;
}

.dlp-statut--nouvelle   { background: #eaf4fb; color: #1a73c1; }
.dlp-statut--en_cours   { background: rgba(0, 168, 168, 0.1); color: #007a7a; }
.dlp-statut--en_attente { background: #fef9e7; color: #b7770d; }
.dlp-statut--resolue    { background: #eafaf1; color: #1e8449; }
.dlp-statut--cloturee   { background: #f4f6f7; color: #707b7c; }
.dlp-statut--annulee    { background: rgba(231, 76, 60, 0.07); color: #c0392b; }

/* ══ DATE ════════════════════════════════════════════════════════════════════ */

.dlp-date {
  font-family: "Fira Code", monospace;
  font-size: 9.5px;
  color: #bbb;
  flex-shrink: 0;
}

/* ══ DÉTAIL ══════════════════════════════════════════════════════════════════ */

.dlp-detail {
  padding: 10px 12px 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(0, 168, 168, 0.02);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ══ MÉTA-INFOS GRILLE ═══════════════════════════════════════════════════════ */

.dlp-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px 16px;
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.dlp-meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.dlp-meta-item--full {
  grid-column: 1 / -1;
}

.dlp-avatar-sm {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  flex-shrink: 0;
  object-fit: cover;
  border: 1.5px solid rgba(0, 11, 35, 0.12);
}
.dlp-avatar-sm--amber { border-color: rgba(243, 156, 18, 0.4); }

.dlp-logo-sm {
  height: 16px;
  width: auto;
  max-width: 32px;
  flex-shrink: 0;
  object-fit: contain;
  border-radius: 2px;
}

.dlp-meta-val {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 600;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dlp-meta-val--agent {
  color: #b7770d;
}

/* ══ DESCRIPTION ════════════════════════════════════════════════════════════ */

.dlp-detail-desc {
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #555;
  line-height: 1.5;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 3px;
  padding: 7px 10px;
  border-left: 2px solid rgba(0, 168, 168, 0.3);
}

.dlp-detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.dlp-detail-field {
  display: flex;
  align-items: center;
  gap: 7px;
}

.dlp-detail-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #aaa;
  text-transform: uppercase;
  white-space: nowrap;
}

.dlp-status-sel {
  height: 26px;
  padding: 0 8px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 600;
  color: #333;
  background: #fff;
  cursor: pointer;
  outline: none;
}
.dlp-status-sel:focus { border-color: rgba(0, 168, 168, 0.4); }
.dlp-status-sel:disabled { opacity: 0.5; cursor: not-allowed; }

.dlp-detail-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dlp-confirm-txt {
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 700;
  color: #c0392b;
}

/* ══ BOUTONS ACTION ══════════════════════════════════════════════════════════ */

.dlp-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
}

.dlp-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.dlp-btn--danger {
  background: rgba(231, 76, 60, 0.07);
  border-color: rgba(231, 76, 60, 0.2);
  color: #c0392b;
}
.dlp-btn--danger:hover:not(:disabled) { background: rgba(231, 76, 60, 0.14); }

.dlp-btn--danger-confirm {
  background: #e74c3c;
  color: #fff;
}
.dlp-btn--danger-confirm:hover { background: #c0392b; }

.dlp-btn--cancel {
  background: #f5f5f5;
  border-color: rgba(0, 0, 0, 0.1);
  color: #555;
}
.dlp-btn--cancel:hover { background: #ebebeb; }

.dlp-btn--pec {
  background: rgba(0, 168, 168, 0.12);
  border-color: #00a8a8;
  color: #005f5f;
  font-weight: 800;
}
.dlp-btn--pec:hover:not(:disabled) { background: rgba(0, 168, 168, 0.22); }

.dlp-btn--detail {
  background: rgba(0, 11, 35, 0.05);
  border-color: rgba(0, 11, 35, 0.15);
  color: #000b23;
}
.dlp-btn--detail:hover { background: rgba(0, 11, 35, 0.1); }

.dlp-btn--suivi {
  background: rgba(0, 168, 168, 0.07);
  border-color: rgba(0, 168, 168, 0.25);
  color: #007a7a;
}
.dlp-btn--suivi:hover:not(:disabled) {
  background: rgba(0, 168, 168, 0.14);
  border-color: rgba(0, 168, 168, 0.4);
}

.dlp-btn--suivi-active {
  background: rgba(0, 168, 168, 0.18);
  border-color: #00a8a8;
  color: #005f5f;
}

.dlp-btn--suivi-submit {
  background: #00a8a8;
  border-color: transparent;
  color: #fff;
}
.dlp-btn--suivi-submit:hover:not(:disabled) { background: #008585; }
.dlp-btn--suivi-submit:disabled { opacity: 0.5; cursor: not-allowed; }

.dlp-action-error {
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  color: #c0392b;
  margin: 0;
}

/* ══ FORMULAIRE SUIVI ════════════════════════════════════════════════════════ */

.dlp-suivi {
  border-top: 1px dashed rgba(0, 168, 168, 0.25);
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dlp-suivi-header {
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

.dlp-suivi-fields {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.dlp-suivi-field {
  display: flex;
  align-items: center;
  gap: 7px;
}

.dlp-suivi-textarea {
  width: 100%;
  min-height: 64px;
  padding: 7px 10px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #333;
  background: #fff;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}
.dlp-suivi-textarea:focus { border-color: rgba(0, 168, 168, 0.45); }
.dlp-suivi-textarea:disabled { opacity: 0.5; }
.dlp-suivi-textarea::placeholder { color: #bbb; }

.dlp-suivi-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dlp-suivi-contact {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  border-radius: 12px;
  background: rgba(0, 168, 168, 0.08);
  border: 1px solid rgba(0, 168, 168, 0.2);
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  font-weight: 600;
  color: #00a8a8;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ══ SKELETON ════════════════════════════════════════════════════════════════ */

.dlp-row--skeleton {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 10px;
  animation: dlp-pulse 1.4s ease-in-out infinite;
}

@keyframes dlp-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}

.dlp-sk {
  border-radius: 3px;
  background: #e8e8e8;
}

.dlp-sk--badge  { width: 36px; height: 18px; flex-shrink: 0; }
.dlp-sk--title  { flex: 1; height: 12px; }
.dlp-sk--status { width: 60px; height: 18px; flex-shrink: 0; }
.dlp-sk--date   { width: 45px; height: 10px; flex-shrink: 0; }

/* ══ TRANSITIONS ═════════════════════════════════════════════════════════════ */

.dlp-fade-enter-active,
.dlp-fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.dlp-fade-enter-from { opacity: 0; transform: translateY(-4px); }
.dlp-fade-leave-to   { opacity: 0; transform: translateY(4px); }

/* ══ SPIN ════════════════════════════════════════════════════════════════════ */

.dlp-spin {
  animation: dlp-rotate 0.8s linear infinite;
}

@keyframes dlp-rotate {
  to { transform: rotate(360deg); }
}
</style>
