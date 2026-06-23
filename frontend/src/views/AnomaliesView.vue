<template>
  <div class="av-root">

    <!-- ══ HEADER ════════════════════════════════════════════════════════ -->
    <div class="av-hdr">
      <div class="av-hdr-left">
        <div class="av-hdr-title-row">
          <span class="av-hdr-marker"></span>
          <h1 class="av-title">Journal des anomalies</h1>
        </div>
        <p class="av-subtitle">
          Consultez et gérez toutes les anomalies enregistrées par le permanencier.
        </p>
      </div>
      <div class="av-hdr-actions">
        <button class="av-btn av-btn--ghost">
          <v-icon size="13">mdi-download-outline</v-icon>
          Exporter
        </button>
        <button class="av-btn av-btn--primary">
          <v-icon size="13" color="#fff">mdi-plus</v-icon>
          Nouvelle anomalie
        </button>
      </div>
    </div>

    <!-- ══ KPI STRIP ══════════════════════════════════════════════════════ -->
    <div class="av-kpi-strip">
      <div
        v-for="card in kpiCards"
        :key="card.client"
        :class="['av-kpi-card', filterClientId === card.clientId ? 'av-kpi-card--active' : '']"
        @click="toggleClientFilter(card.clientId)"
      >
        <div class="av-kpi-card__head">
          <span v-if="card.hasNew" class="av-kpi-card__badge">NOUVEAU</span>
          <span class="av-kpi-card__dot" :style="{ background: card.color }"></span>
          <span class="av-kpi-card__name">{{ card.client }}</span>
          <button class="av-kpi-card__link" @click.stop="toggleClientFilter(card.clientId)">
            Voir détails
            <v-icon size="10">mdi-arrow-right</v-icon>
          </button>
        </div>
        <div class="av-kpi-card__metrics">
          <div class="av-kpi-card__metric">
            <span class="av-kpi-card__metric-lbl">OUVERTES</span>
            <span class="av-kpi-card__metric-val">
              {{ card.ouvertes }}<span class="av-kpi-card__metric-total">/{{ card.total }}</span>
            </span>
          </div>
          <div class="av-kpi-card__divider"></div>
          <div class="av-kpi-card__metric">
            <span class="av-kpi-card__metric-lbl">URGENTES</span>
            <span
              :class="['av-kpi-card__metric-val', card.urgentes > 0 ? 'av-kpi-card__metric-val--alert' : '']"
            >{{ card.urgentes }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ══ TOOLBAR ════════════════════════════════════════════════════════ -->
    <div class="av-toolbar">
      <div class="av-search">
        <v-icon size="14" color="#bbb">mdi-magnify</v-icon>
        <input
          v-model="search"
          class="av-search__input"
          placeholder="Rechercher une anomalie, un client…"
          autocomplete="off"
        />
        <button v-if="search" class="av-search__clear" @click="search = ''">
          <v-icon size="11">mdi-close</v-icon>
        </button>
      </div>
      <div class="av-toolbar-right">
        <button
          :class="['av-tool-btn', groupEnabled ? 'av-tool-btn--active' : '']"
          @click="groupEnabled = !groupEnabled"
        >
          <v-icon size="13">mdi-format-list-group</v-icon>
          Grouper
        </button>
        <button
          :class="['av-tool-btn', showFilters ? 'av-tool-btn--active' : '']"
          @click="showFilters = !showFilters"
        >
          <v-icon size="13">mdi-filter-outline</v-icon>
          Filtres
          <span v-if="activeFiltersCount > 0" class="av-tool-btn__badge">{{ activeFiltersCount }}</span>
        </button>
      </div>
    </div>

    <!-- ── Barre de filtres rapides ─────────────────────────────────── -->
    <div v-if="showFilters || filterContactId != null || filterAgentId != null" class="av-filter-bar">

      <!-- Filtre contact actif (venant d'un lien ContactsView) -->
      <div v-if="filterContactId != null" class="av-filter-group">
        <span class="av-filter-lbl">DEMANDEUR</span>
        <span class="av-active-filter-chip">
          <v-icon size="11" color="#00a8a8">mdi-account-outline</v-icon>
          {{ filterContactName }}
          <button class="av-active-filter-chip__close" @click="filterContactId = null">
            <v-icon size="10">mdi-close</v-icon>
          </button>
        </span>
      </div>

      <!-- Filtre agent concerné actif -->
      <div v-if="filterAgentId != null" class="av-filter-group">
        <span class="av-filter-lbl">AGENT</span>
        <span class="av-active-filter-chip av-active-filter-chip--amber">
          <v-icon size="11" color="#f39c12">mdi-shield-account-outline</v-icon>
          {{ filterAgentName }}
          <button class="av-active-filter-chip__close" @click="filterAgentId = null">
            <v-icon size="10">mdi-close</v-icon>
          </button>
        </span>
      </div>

      <template v-if="showFilters">
        <div class="av-filter-group">
          <span class="av-filter-lbl">STATUT</span>
          <button
            v-for="s in statutOptions"
            :key="s.value"
            :class="['av-filter-chip', filterStatut === s.value ? 'av-filter-chip--active' : '']"
            @click="filterStatut = filterStatut === s.value ? null : s.value"
          >
            <span class="av-filter-chip__dot" :style="{ background: s.color }"></span>
            {{ s.label }}
          </button>
        </div>
        <div class="av-filter-group">
          <span class="av-filter-lbl">PRIORITÉ</span>
          <button
            v-for="p in prioriteOptions"
            :key="p.value"
            :class="['av-filter-chip', filterPriorite === p.value ? 'av-filter-chip--active' : '']"
            @click="filterPriorite = filterPriorite === p.value ? null : p.value"
          >
            {{ p.label }}
          </button>
        </div>
      </template>

      <button v-if="activeFiltersCount > 0" class="av-filter-reset" @click="resetFilters">
        <v-icon size="11">mdi-close</v-icon>
        Réinitialiser tout
      </button>
    </div>

    <!-- ══ TABLE ══════════════════════════════════════════════════════════ -->
    <div class="av-table-wrap">
      <table class="av-table">
        <thead>
          <tr>
            <th class="av-th" style="width:130px">Client</th>
            <th class="av-th" style="width:130px">Site</th>
            <th class="av-th">Intitulé de l'anomalie</th>
            <th class="av-th" style="width:105px">Catégorie</th>
            <th class="av-th" style="width:78px; text-align:center">Priorité</th>
            <th class="av-th" style="width:118px">Créé le</th>
            <th class="av-th" style="width:110px">Statut</th>
            <th class="av-th" style="width:112px">Permanencier</th>
            <th class="av-th" style="width:112px">Demandeur</th>
            <th class="av-th" style="width:112px">Créé par</th>
            <th class="av-th" style="width:112px">Dernier éditeur</th>
            <th class="av-th" style="width:118px">MàJ le</th>
            <th class="av-th" style="width:38px"></th>
          </tr>
        </thead>
        <tbody>
          <template v-if="groupEnabled">
            <template v-for="group in groupedRows" :key="group.client">

              <!-- Ligne accordéon groupe -->
              <tr class="av-group-row" @click="toggleGroup(group.client)">
                <td colspan="13" class="av-group-row__cell">
                  <div class="av-group-row__inner">
                    <v-icon
                      size="12"
                      :class="['av-group-row__chevron', openGroups.has(group.client) ? 'av-group-row__chevron--open' : '']"
                    >mdi-chevron-right</v-icon>
                    <span class="av-group-row__dot" :style="{ background: group.color }"></span>
                    <span class="av-group-row__name">{{ group.client }}</span>
                    <span class="av-group-row__count">{{ group.items.length }}</span>
                    <span class="av-group-row__spacer"></span>
                    <button class="av-group-row__link" @click.stop>
                      Voir la fiche client
                      <v-icon size="10">mdi-arrow-right</v-icon>
                    </button>
                  </div>
                </td>
              </tr>

              <!-- Lignes du groupe -->
              <template v-if="openGroups.has(group.client)">
                <tr
                  v-for="row in group.items"
                  :key="row.id"
                  class="av-data-row"
                  style="cursor:pointer"
                  @click="selectRow(row)"
                >
                  <td class="av-td">
                    <div class="av-cell-flex">
                      <span class="av-client-dot" :style="{ background: group.color }"></span>
                      <span class="av-client-name">{{ row.client_nom ?? group.client }}</span>
                    </div>
                  </td>
                  <td class="av-td">
                    <span class="av-site-name">
                      <v-icon size="11" color="#9aa0aa">mdi-map-marker-outline</v-icon>
                      {{ row.site_nom ?? '—' }}
                    </span>
                  </td>
                  <td class="av-td av-td--titre">
                    <span class="av-titre">{{ row.titre }}</span>
                  </td>
                  <td class="av-td">
                    <span class="av-nature-badge">{{ natureLabels[row.nature_anomalie] ?? row.nature_anomalie }}</span>
                  </td>
                  <td class="av-td" style="text-align:center">
                    <span :class="['av-prio-chip', `av-prio-chip--${row.priorite}`]">
                      {{ row.priorite }}
                    </span>
                  </td>
                  <td class="av-td av-td--date">{{ formatDate(row.created_at) }}</td>
                  <td class="av-td">
                    <div class="av-cell-flex">
                      <span :class="['av-statut-chip', `av-statut-chip--${row.statut}`]">
                        <span class="av-statut-chip__dot"></span>
                        {{ statutLabels[row.statut] }}
                      </span>
                      <SlaBadge :state="row.sla && row.sla.resolution" />
                      <v-icon size="10" color="#ccc">mdi-chevron-down</v-icon>
                    </div>
                  </td>
                  <td class="av-td">
                    <div class="av-cell-flex">
                      <span class="av-avatar">{{ initials(row.permanencier_nom) }}</span>
                      <span class="av-perm-name">{{ row.permanencier_nom }}</span>
                    </div>
                  </td>
                  <td class="av-td">
                    <div class="av-cell-flex">
                      <span class="av-avatar av-avatar--blue">{{ initials(row.contact_nom) }}</span>
                      <span class="av-perm-name">{{ row.contact_nom ?? '—' }}</span>
                    </div>
                  </td>
                  <td class="av-td">
                    <div class="av-cell-flex">
                      <span class="av-avatar av-avatar--teal">{{ initials(row.created_by_nom) }}</span>
                      <span class="av-perm-name">{{ row.created_by_nom ?? '—' }}</span>
                    </div>
                  </td>
                  <td class="av-td">
                    <div class="av-cell-flex">
                      <span class="av-avatar av-avatar--amber">{{ initials(row.updated_by_nom) }}</span>
                      <span class="av-perm-name">{{ row.updated_by_nom ?? '—' }}</span>
                    </div>
                  </td>
                  <td class="av-td av-td--date">{{ formatDate(row.updated_at) }}</td>
                  <td class="av-td" style="text-align:center">
                    <button class="av-action-btn">
                      <v-icon size="15">mdi-dots-vertical</v-icon>
                    </button>
                  </td>
                </tr>
              </template>

            </template>
          </template>

          <!-- Mode liste plat (sans groupe) -->
          <template v-else>
            <tr
              v-for="row in filteredRows"
              :key="row.id"
              class="av-data-row"
              style="cursor:pointer"
              @click="selectRow(row)"
            >
              <td class="av-td">
                <div class="av-cell-flex">
                  <span class="av-client-dot" :style="{ background: clientColor(row.client_id) }"></span>
                  <span class="av-client-name">{{ row.client_nom ?? `Client #${row.client_id}` }}</span>
                </div>
              </td>
              <td class="av-td">
                <span class="av-site-name">
                  <v-icon size="11" color="#9aa0aa">mdi-map-marker-outline</v-icon>
                  {{ row.site_nom ?? '—' }}
                </span>
              </td>
              <td class="av-td av-td--titre">
                <span class="av-titre">{{ row.titre }}</span>
              </td>
              <td class="av-td">
                <span class="av-nature-badge">{{ natureLabels[row.nature_anomalie] ?? row.nature_anomalie }}</span>
              </td>
              <td class="av-td" style="text-align:center">
                <span :class="['av-prio-chip', `av-prio-chip--${row.priorite}`]">
                  {{ row.priorite }}
                </span>
              </td>
              <td class="av-td av-td--date">{{ formatDate(row.created_at) }}</td>
              <td class="av-td">
                <div class="av-cell-flex">
                  <span :class="['av-statut-chip', `av-statut-chip--${row.statut}`]">
                    <span class="av-statut-chip__dot"></span>
                    {{ statutLabels[row.statut] }}
                  </span>
                  <SlaBadge :state="row.sla && row.sla.resolution" />
                  <v-icon size="10" color="#ccc">mdi-chevron-down</v-icon>
                </div>
              </td>
              <td class="av-td">
                <div class="av-cell-flex">
                  <span class="av-avatar">{{ initials(row.permanencier_nom) }}</span>
                  <span class="av-perm-name">{{ row.permanencier_nom }}</span>
                </div>
              </td>
              <td class="av-td">
                <div class="av-cell-flex">
                  <span class="av-avatar av-avatar--blue">{{ initials(row.created_by_nom) }}</span>
                  <span class="av-perm-name">{{ row.created_by_nom ?? '—' }}</span>
                </div>
              </td>
              <td class="av-td">
                <div class="av-cell-flex">
                  <span class="av-avatar av-avatar--amber">{{ initials(row.updated_by_nom) }}</span>
                  <span class="av-perm-name">{{ row.updated_by_nom ?? '—' }}</span>
                </div>
              </td>
              <td class="av-td av-td--date">{{ formatDate(row.updated_at) }}</td>
              <td class="av-td" style="text-align:center">
                <button class="av-action-btn">
                  <v-icon size="15">mdi-dots-vertical</v-icon>
                </button>
              </td>
            </tr>
          </template>

          <!-- Chargement -->
          <tr v-if="loading">
            <td colspan="13">
              <div class="av-empty">
                <v-icon size="28" color="#e0e0e0" class="av-spin">mdi-loading</v-icon>
                <span>Chargement des anomalies…</span>
              </div>
            </td>
          </tr>

          <!-- Erreur API -->
          <tr v-else-if="loadError">
            <td colspan="13">
              <div class="av-empty" style="color:#e74c3c">
                <v-icon size="28" color="#e74c3c">mdi-alert-circle-outline</v-icon>
                <span>{{ loadError }}</span>
              </div>
            </td>
          </tr>

          <!-- État vide -->
          <tr v-else-if="(groupEnabled ? groupedRows : filteredRows).length === 0">
            <td colspan="13">
              <div class="av-empty">
                <v-icon size="36" color="#e0e0e0">mdi-clipboard-check-outline</v-icon>
                <span>Aucune anomalie ne correspond aux critères</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>

  <!-- ── Drawer d'édition ─────────────────────────────────────────────── -->
  <EditAnomalieDrawer
    v-if="selectedDemande"
    :demande="selectedDemande"
    @close="selectedDemande = null"
    @updated="onUpdated"
  />

</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useRoute } from "vue-router";
import { listDemandes } from "@/services/demandeService";
import SlaBadge from "@/components/sla/SlaBadge.vue";
import EditAnomalieDrawer from "@/components/workspace/EditAnomalieDrawer.vue";

const route = useRoute();

// ─── Palette couleur par client_id ────────────────────────────────────────────
const PALETTE = ["#00a8a8","#3498db","#8e44ad","#e67e22","#27ae60","#e74c3c","#f39c12","#16a085"];
const clientColor = (id) => PALETTE[((id ?? 0) - 1 + PALETTE.length) % PALETTE.length];

// ─── Labels UI (métadonnées statiques) ───────────────────────────────────────
const natureLabels = {
  anj:                          "ANJ",
  absence_justifiee:            "Abs. justifiée",
  retard_prise_service:         "Retard PDS",
  agent_non_sur_site:           "Agent absent",
  doublon_planning:             "Doublon plan.",
  remplacement_permutation:     "Remplacement",
  modification_vacation:        "Modif. vacation",
  probleme_technique:           "Pb. technique",
  site_prestataire_injoignable: "Injoignable",
  blocage_outil_rh:             "Blocage RH",
  demande_de_renfort:           "Renfort",
  anomalie_facturation:         "Fact. anomalie",
  autre:                        "Autre",
};

const statutLabels = { nouvelle: "Nouvelle", en_cours: "En cours", en_attente: "En attente", resolue: "Résolue", cloturee: "Clôturée", annulee: "Annulée" };

const statutOptions = [
  { value: "nouvelle",   label: "Nouvelle",   color: "#3498db" },
  { value: "en_cours",   label: "En cours",   color: "#f39c12" },
  { value: "en_attente", label: "En attente", color: "#8e44ad" },
  { value: "resolue",    label: "Résolue",    color: "#27ae60" },
  { value: "cloturee",   label: "Clôturée",   color: "#95a5a6" },
];

const prioriteOptions = [
  { value: "urgente", label: "Urgente" },
  { value: "haute",   label: "Haute"   },
  { value: "normale", label: "Normale" },
  { value: "basse",   label: "Basse"   },
];

// ─── Données réelles ──────────────────────────────────────────────────────────
const demandes       = ref([]);
const loading        = ref(false);
const loadError      = ref("");
const selectedDemande = ref(null);

async function loadData() {
  loading.value = true;
  loadError.value = "";
  try {
    demandes.value = await listDemandes({ type_demande: "anomalie" });
  } catch {
    loadError.value = "Impossible de charger les anomalies.";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  // Pré-filtrage depuis un lien externe (ContactsView)
  if (route.query.contact_id) filterContactId.value = Number(route.query.contact_id);
  if (route.query.agent_id)   filterAgentId.value   = Number(route.query.agent_id);
  if (filterContactId.value != null || filterAgentId.value != null) showFilters.value = false;
  loadData();
});

// ─── État UI ──────────────────────────────────────────────────────────────────
const search         = ref("");
const showFilters    = ref(false);
const filterStatut   = ref(null);
const filterPriorite = ref(null);
const filterClientId = ref(null);
const filterContactId = ref(null);
const filterAgentId   = ref(null);
const groupEnabled   = ref(true);
const openGroups     = ref(new Set());

// ─── Computed ─────────────────────────────────────────────────────────────────
const activeFiltersCount = computed(() =>
  [filterStatut.value, filterPriorite.value, filterClientId.value,
   filterContactId.value, filterAgentId.value].filter(v => v != null).length
);

// Noms affichés pour les filtres actifs (résolus depuis les données chargées)
const filterContactName = computed(() => {
  if (filterContactId.value == null) return null;
  const found = demandes.value.find(d => d.contact_id === filterContactId.value);
  return found?.contact_nom ?? `Contact #${filterContactId.value}`;
});

const filterAgentName = computed(() => {
  if (filterAgentId.value == null) return null;
  const found = demandes.value.find(d => d.agent_concerne_id === filterAgentId.value);
  return found?.agent_concerne_label ?? `Agent #${filterAgentId.value}`;
});

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase();
  return demandes.value.filter(a => {
    if (q) {
      const hay = `${a.titre} ${a.client_nom ?? ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (filterStatut.value    && a.statut   !== filterStatut.value)     return false;
    if (filterPriorite.value  && a.priorite !== filterPriorite.value)   return false;
    if (filterClientId.value  != null && a.client_id   !== filterClientId.value)  return false;
    if (filterContactId.value != null && a.contact_id  !== filterContactId.value) return false;
    if (filterAgentId.value   != null && a.agent_concerne_id !== filterAgentId.value) return false;
    return true;
  });
});

const groupedRows = computed(() => {
  const map = {};
  for (const a of filteredRows.value) {
    const name = a.client_nom ?? `Client #${a.client_id}`;
    if (!map[name]) map[name] = { client: name, clientId: a.client_id, color: clientColor(a.client_id), items: [] };
    map[name].items.push(a);
  }
  return Object.values(map);
});

// Ouvre automatiquement les groupes au premier chargement
watch(groupedRows, (groups) => {
  const s = new Set(openGroups.value);
  groups.forEach(g => s.add(g.client));
  openGroups.value = s;
}, { immediate: true });

const kpiCards = computed(() => {
  const map = {};
  for (const a of demandes.value) {
    const name = a.client_nom ?? `Client #${a.client_id}`;
    if (!map[name]) map[name] = { client: name, clientId: a.client_id, color: clientColor(a.client_id), ouvertes: 0, urgentes: 0, total: 0, hasNew: false };
    map[name].total++;
    if (["nouvelle", "en_cours", "en_attente"].includes(a.statut)) map[name].ouvertes++;
    if (a.priorite === "urgente") map[name].urgentes++;
    if (a.statut === "nouvelle")  map[name].hasNew = true;
  }
  return Object.values(map);
});

// ─── Méthodes ─────────────────────────────────────────────────────────────────
function toggleGroup(name) {
  const s = new Set(openGroups.value);
  s.has(name) ? s.delete(name) : s.add(name);
  openGroups.value = s;
}

function toggleClientFilter(clientId) {
  filterClientId.value = filterClientId.value === clientId ? null : clientId;
}

function resetFilters() {
  filterStatut.value    = null;
  filterPriorite.value  = null;
  filterClientId.value  = null;
  filterContactId.value = null;
  filterAgentId.value   = null;
}

function selectRow(row) { selectedDemande.value = row; }

function onUpdated(updated) {
  const idx = demandes.value.findIndex(d => d.id === updated.id);
  if (idx !== -1) demandes.value.splice(idx, 1, updated);
  selectedDemande.value = null;
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit" })
    + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

function initials(name) {
  if (!name) return "?";
  return name.split(" ").map(p => p[0]).join("").slice(0, 2).toUpperCase();
}
</script>

<style scoped>
/* ══ ROOT ════════════════════════════════════════════════════════════ */
.av-root {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px;
  background: #f2f2f2;
  min-height: 100%;
  font-family: "Fira Sans", sans-serif;
}

/* ══ HEADER ══════════════════════════════════════════════════════════ */
.av-hdr {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.av-hdr-title-row {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 4px;
}

.av-hdr-marker {
  width: 3px;
  height: 18px;
  background: #e74c3c;
  border-radius: 1px;
  flex-shrink: 0;
}

.av-title {
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #000b23;
  text-transform: uppercase;
  margin: 0;
}

.av-subtitle {
  font-size: 11px;
  color: #999;
  margin: 0;
  padding-left: 12px;
}

.av-hdr-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* ── Boutons header ────────────────────────────────────────────────── */
.av-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 13px;
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
  white-space: nowrap;
}

.av-btn--ghost {
  background: #fff;
  color: #555;
  border: 1px solid rgba(0, 0, 0, 0.12);
}
.av-btn--ghost:hover { border-color: #00a8a8; color: #00a8a8; }

.av-btn--primary {
  background: #000b23;
  color: #fff;
}
.av-btn--primary:hover { background: #00a8a8; }

/* ══ KPI STRIP ═══════════════════════════════════════════════════════ */
.av-kpi-strip {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.av-kpi-strip::-webkit-scrollbar { height: 3px; }
.av-kpi-strip::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 2px; }

.av-kpi-card {
  flex-shrink: 0;
  min-width: 195px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 3px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 9px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.av-kpi-card:hover { border-color: rgba(0,168,168,0.3); box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.av-kpi-card--active { border-color: #00a8a8; background: rgba(0,168,168,0.03); }

.av-kpi-card__head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.av-kpi-card__badge {
  font-family: "Fira Code", monospace;
  font-size: 7px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #27ae60;
  background: rgba(39,174,96,0.1);
  padding: 2px 5px;
  border-radius: 2px;
  text-transform: uppercase;
  flex-shrink: 0;
}

.av-kpi-card__dot {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  flex-shrink: 0;
}

.av-kpi-card__name {
  font-size: 11px;
  font-weight: 700;
  color: #000b23;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.av-kpi-card__link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  font-weight: 600;
  color: #00a8a8;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  white-space: nowrap;
  flex-shrink: 0;
}

.av-kpi-card__metrics {
  display: flex;
  align-items: center;
  gap: 10px;
}

.av-kpi-card__divider {
  width: 1px;
  height: 22px;
  background: rgba(0,0,0,0.07);
}

.av-kpi-card__metric {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.av-kpi-card__metric-lbl {
  font-family: "Fira Code", monospace;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #ccc;
  text-transform: uppercase;
}

.av-kpi-card__metric-val {
  font-family: "Fira Code", monospace;
  font-size: 15px;
  font-weight: 700;
  color: #000b23;
}

.av-kpi-card__metric-val--alert { color: #e74c3c; }

.av-kpi-card__metric-total {
  font-size: 11px;
  color: #bbb;
  font-weight: 500;
}

/* ══ TOOLBAR ════════════════════════════════════════════════════════ */
.av-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 3px;
  padding: 7px 12px;
}

.av-search {
  display: flex;
  align-items: center;
  gap: 7px;
  flex: 1;
}

.av-search__input {
  flex: 1;
  border: none;
  outline: none;
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  color: #000b23;
  background: transparent;
}
.av-search__input::placeholder { color: #ccc; }

.av-search__clear {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: none;
  background: rgba(0,0,0,0.08);
  cursor: pointer;
  color: #888;
}

.av-toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  border-left: 1px solid rgba(0,0,0,0.07);
  padding-left: 10px;
}

.av-tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 10px;
  border: 1px solid rgba(0,0,0,0.1);
  border-radius: 3px;
  background: transparent;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 600;
  color: #666;
  cursor: pointer;
  transition: all 0.12s;
  position: relative;
}
.av-tool-btn:hover { border-color: #00a8a8; color: #00a8a8; }
.av-tool-btn--active { border-color: #00a8a8; color: #00a8a8; background: rgba(0,168,168,0.06); }

.av-tool-btn__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: #e74c3c;
  color: #fff;
  font-size: 8px;
  font-weight: 700;
}

/* ── Filter bar ────────────────────────────────────────────────────── */
.av-filter-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 3px;
  padding: 8px 12px;
  flex-wrap: wrap;
}

.av-filter-group {
  display: flex;
  align-items: center;
  gap: 5px;
}

.av-filter-lbl {
  font-family: "Fira Code", monospace;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #ccc;
  text-transform: uppercase;
  margin-right: 2px;
  white-space: nowrap;
}

.av-filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 9px;
  border: 1px solid rgba(0,0,0,0.1);
  border-radius: 11px;
  background: transparent;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 500;
  color: #555;
  cursor: pointer;
  transition: all 0.12s;
}
.av-filter-chip:hover { border-color: #00a8a8; color: #00a8a8; }
.av-filter-chip--active { background: #000b23; border-color: #000b23; color: #fff; }

.av-filter-chip__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.av-filter-reset {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  height: 22px;
  padding: 0 8px;
  border: none;
  border-radius: 3px;
  background: rgba(231,76,60,0.08);
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 600;
  color: #e74c3c;
  cursor: pointer;
}

/* Chip filtre actif (contact / agent) */
.av-active-filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 24px;
  padding: 0 8px 0 6px;
  border-radius: 12px;
  background: rgba(0,168,168,0.1);
  border: 1px solid rgba(0,168,168,0.3);
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 600;
  color: #00a8a8;
}
.av-active-filter-chip--amber {
  background: rgba(243,156,18,0.1);
  border-color: rgba(243,156,18,0.3);
  color: #f39c12;
}
.av-active-filter-chip__close {
  display: inline-flex;
  align-items: center;
  border: none;
  background: none;
  cursor: pointer;
  color: inherit;
  padding: 0;
  margin-left: 2px;
  opacity: 0.7;
}
.av-active-filter-chip__close:hover { opacity: 1; }

/* ══ TABLE ═══════════════════════════════════════════════════════════ */
.av-table-wrap {
  background: #fff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 3px;
  overflow: hidden;
}

.av-table {
  width: 100%;
  border-collapse: collapse;
}

.av-th {
  padding: 9px 12px;
  text-align: left;
  font-family: "Fira Sans", sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
  background: #fafafa;
  border-bottom: 1px solid rgba(0,0,0,0.07);
  white-space: nowrap;
  user-select: none;
}

/* Ligne de groupe accordéon */
.av-group-row { cursor: pointer; }
.av-group-row:hover .av-group-row__cell { background: rgba(0,168,168,0.04); }

.av-group-row__cell {
  padding: 7px 12px;
  background: rgba(0,11,35,0.02);
  border-bottom: 1px solid rgba(0,0,0,0.06);
  transition: background 0.1s;
}

.av-group-row__inner {
  display: flex;
  align-items: center;
  gap: 7px;
}

.av-group-row__chevron {
  color: #bbb;
  transition: transform 0.18s;
  flex-shrink: 0;
}
.av-group-row__chevron--open { transform: rotate(90deg); }

.av-group-row__dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}

.av-group-row__name {
  font-size: 12px;
  font-weight: 700;
  color: #000b23;
  letter-spacing: 0.01em;
}

.av-group-row__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: rgba(0,0,0,0.07);
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-weight: 700;
  color: #555;
}

.av-group-row__spacer { flex: 1; }

.av-group-row__link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  font-weight: 600;
  color: #00a8a8;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  white-space: nowrap;
}

/* Lignes de données */
.av-data-row {
  border-bottom: 1px solid rgba(0,0,0,0.05);
  transition: background 0.1s;
}
.av-data-row:hover { background: rgba(0,168,168,0.025); }
.av-data-row:last-child { border-bottom: none; }

.av-td {
  padding: 8px 12px;
  font-size: 11.5px;
  color: #333;
  vertical-align: middle;
  max-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.av-td--titre { max-width: 260px; }
.av-td--date {
  font-family: "Fira Code", monospace;
  font-size: 10.5px;
  color: #888;
  white-space: nowrap;
}

.av-cell-flex {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
}

/* Client */
.av-client-dot { width: 7px; height: 7px; border-radius: 1px; flex-shrink: 0; }
.av-client-name { font-size: 11px; color: #777; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.av-site-name { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #777; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Titre */
.av-titre { font-weight: 600; color: #000b23; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }

/* Nature badge */
.av-nature-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 7px;
  border-radius: 2px;
  background: rgba(0,11,35,0.06);
  font-family: "Fira Code", monospace;
  font-size: 9px;
  font-weight: 700;
  color: #555;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

/* Priorité */
.av-prio-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 18px;
  padding: 0 8px;
  border-radius: 2px;
  font-family: "Fira Code", monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
}
.av-prio-chip--urgente { background: rgba(231,76,60,0.1);  color: #e74c3c; }
.av-prio-chip--haute   { background: rgba(243,156,18,0.12); color: #f39c12; }
.av-prio-chip--normale { background: rgba(0,168,168,0.1);  color: #00a8a8; }
.av-prio-chip--basse   { background: rgba(0,0,0,0.05);     color: #aaa;    }

/* Statut */
.av-statut-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}
.av-statut-chip__dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; flex-shrink: 0; }

.av-statut-chip--nouvelle   { background: rgba(52,152,219,0.1); color: #3498db; }
.av-statut-chip--en_cours   { background: rgba(243,156,18,0.1); color: #f39c12; }
.av-statut-chip--en_attente { background: rgba(142,68,173,0.1); color: #8e44ad; }
.av-statut-chip--resolue    { background: rgba(39,174,96,0.1);  color: #27ae60; }
.av-statut-chip--cloturee   { background: rgba(0,0,0,0.06);     color: #95a5a6; }
.av-statut-chip--annulee    { background: rgba(231,76,60,0.1);  color: #e74c3c; }

/* Permanencier */
.av-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(0,11,35,0.08);
  font-family: "Fira Code", monospace;
  font-size: 8px;
  font-weight: 700;
  color: #000b23;
  flex-shrink: 0;
}

.av-perm-name { font-size: 11px; color: #666; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.av-avatar--blue  { background: rgba(52,152,219,0.12);  color: #3498db; }
.av-avatar--teal  { background: rgba(0,168,168,0.12);   color: #00a8a8; }
.av-avatar--amber { background: rgba(243,156,18,0.12);  color: #f39c12; }

/* Bouton actions */
.av-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 3px;
  background: transparent;
  cursor: pointer;
  color: #ccc;
  transition: background 0.1s, color 0.1s;
}
.av-action-btn:hover { background: rgba(0,0,0,0.06); color: #555; }

.av-spin { animation: av-rotate 0.8s linear infinite; }
@keyframes av-rotate { to { transform: rotate(360deg); } }

/* Empty */
.av-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 48px 0;
  color: #ccc;
  font-size: 12px;
}
</style>
