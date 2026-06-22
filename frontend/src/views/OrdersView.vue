<template>
  <div class="ov-root">

    <!-- ══ HEADER ════════════════════════════════════════════════════════ -->
    <div class="ov-hdr">
      <div class="ov-hdr-left">
        <div class="ov-hdr-title-row">
          <span class="ov-hdr-marker"></span>
          <h1 class="ov-title">Commandes de sécurité</h1>
        </div>
        <p class="ov-subtitle">
          Suivez l'ensemble des commandes de prestations de sécurité en cours et à venir.
        </p>
      </div>
      <div class="ov-hdr-actions">
        <button class="ov-btn ov-btn--ghost">
          <v-icon size="13">mdi-download-outline</v-icon>
          Exporter
        </button>
        <button class="ov-btn ov-btn--primary">
          <v-icon size="13" color="#fff">mdi-plus</v-icon>
          Nouvelle commande
        </button>
      </div>
    </div>

    <!-- ══ KPI STRIP ══════════════════════════════════════════════════════ -->
    <div class="ov-kpi-strip">
      <div
        v-for="card in kpiCards"
        :key="card.client"
        :class="['ov-kpi-card', filterClientId === card.clientId ? 'ov-kpi-card--active' : '']"
        @click="toggleClientFilter(card.clientId)"
      >
        <div class="ov-kpi-card__head">
          <span v-if="card.hasNew" class="ov-kpi-card__badge">NOUVEAU</span>
          <span class="ov-kpi-card__dot" :style="{ background: card.color }"></span>
          <span class="ov-kpi-card__name">{{ card.client }}</span>
          <button class="ov-kpi-card__link" @click.stop="toggleClientFilter(card.clientId)">
            Voir détails
            <v-icon size="10">mdi-arrow-right</v-icon>
          </button>
        </div>
        <div class="ov-kpi-card__metrics">
          <div class="ov-kpi-card__metric">
            <span class="ov-kpi-card__metric-lbl">EN COURS</span>
            <span class="ov-kpi-card__metric-val">
              {{ card.enCours }}<span class="ov-kpi-card__metric-total">/{{ card.total }}</span>
            </span>
          </div>
          <div class="ov-kpi-card__divider"></div>
          <div class="ov-kpi-card__metric">
            <span class="ov-kpi-card__metric-lbl">MONTANT</span>
            <span class="ov-kpi-card__metric-val ov-kpi-card__metric-val--teal">
              {{ formatMontant(card.montantTotal) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- ══ TOOLBAR ════════════════════════════════════════════════════════ -->
    <div class="ov-toolbar">
      <div class="ov-search">
        <v-icon size="14" color="#bbb">mdi-magnify</v-icon>
        <input
          v-model="search"
          class="ov-search__input"
          placeholder="Rechercher une commande, un client, un type…"
          autocomplete="off"
        />
        <button v-if="search" class="ov-search__clear" @click="search = ''">
          <v-icon size="11">mdi-close</v-icon>
        </button>
      </div>
      <div class="ov-toolbar-right">
        <button
          :class="['ov-tool-btn', groupEnabled ? 'ov-tool-btn--active' : '']"
          @click="groupEnabled = !groupEnabled"
        >
          <v-icon size="13">mdi-format-list-group</v-icon>
          Grouper
        </button>
        <button
          :class="['ov-tool-btn', showFilters ? 'ov-tool-btn--active' : '']"
          @click="showFilters = !showFilters"
        >
          <v-icon size="13">mdi-filter-outline</v-icon>
          Filtres
          <span v-if="activeFiltersCount > 0" class="ov-tool-btn__badge">{{ activeFiltersCount }}</span>
        </button>
      </div>
    </div>

    <!-- ── Barre de filtres rapides ─────────────────────────────────── -->
    <div v-if="showFilters || filterContactId != null" class="ov-filter-bar">

      <!-- Filtre contact actif (venant d'un lien ContactsView) -->
      <div v-if="filterContactId != null" class="ov-filter-group">
        <span class="ov-filter-lbl">DEMANDEUR</span>
        <span class="ov-active-filter-chip">
          <v-icon size="11" color="#00a8a8">mdi-account-outline</v-icon>
          {{ filterContactName }}
          <button class="ov-active-filter-chip__close" @click="filterContactId = null">
            <v-icon size="10">mdi-close</v-icon>
          </button>
        </span>
      </div>

      <template v-if="showFilters">
        <div class="ov-filter-group">
          <span class="ov-filter-lbl">STATUT</span>
          <button
            v-for="s in statutOptions"
            :key="s.value"
            :class="['ov-filter-chip', filterStatut === s.value ? 'ov-filter-chip--active' : '']"
            @click="filterStatut = filterStatut === s.value ? null : s.value"
          >
            <span class="ov-filter-chip__dot" :style="{ background: s.color }"></span>
            {{ s.label }}
          </button>
        </div>
        <div class="ov-filter-group">
          <span class="ov-filter-lbl">TYPE</span>
          <button
            v-for="t in typeOptions"
            :key="t.value"
            :class="['ov-filter-chip', filterType === t.value ? 'ov-filter-chip--active' : '']"
            @click="filterType = filterType === t.value ? null : t.value"
          >
            {{ t.label }}
          </button>
        </div>
      </template>

      <button v-if="activeFiltersCount > 0" class="ov-filter-reset" @click="resetFilters">
        <v-icon size="11">mdi-close</v-icon>
        Réinitialiser tout
      </button>
    </div>

    <!-- ══ TABLE ══════════════════════════════════════════════════════════ -->
    <div class="ov-table-wrap">
      <table class="ov-table">
        <thead>
          <tr>
            <th class="ov-th" style="width:120px">Client</th>
            <th class="ov-th" style="width:120px">Site</th>
            <th class="ov-th">Intitulé de la commande</th>
            <th class="ov-th" style="width:115px">Type</th>
            <th class="ov-th" style="width:90px">Commande</th>
            <th class="ov-th" style="width:110px">Début prestation</th>
            <th class="ov-th" style="width:80px; text-align:right">Montant</th>
            <th class="ov-th" style="width:108px">Statut</th>
            <th class="ov-th" style="width:108px">Responsable</th>
            <th class="ov-th" style="width:108px">Demandeur</th>
            <th class="ov-th" style="width:108px">Créé par</th>
            <th class="ov-th" style="width:108px">Dernier éditeur</th>
            <th class="ov-th" style="width:110px">MàJ le</th>
            <th class="ov-th" style="width:38px"></th>
          </tr>
        </thead>
        <tbody>
          <template v-if="groupEnabled">
            <template v-for="group in groupedRows" :key="group.client">

              <!-- Ligne accordéon groupe -->
              <tr class="ov-group-row" @click="toggleGroup(group.client)">
                <td colspan="14" class="ov-group-row__cell">
                  <div class="ov-group-row__inner">
                    <v-icon
                      size="12"
                      :class="['ov-group-row__chevron', openGroups.has(group.client) ? 'ov-group-row__chevron--open' : '']"
                    >mdi-chevron-right</v-icon>
                    <span class="ov-group-row__dot" :style="{ background: group.color }"></span>
                    <span class="ov-group-row__name">{{ group.client }}</span>
                    <span class="ov-group-row__count">{{ group.items.length }}</span>
                    <span class="ov-group-row__total">
                      {{ formatMontant(group.items.reduce((s, o) => s + (o.budget_estime ?? 0), 0)) }}
                    </span>
                    <span class="ov-group-row__spacer"></span>
                    <button class="ov-group-row__link" @click.stop>
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
                  class="ov-data-row"
                  style="cursor:pointer"
                  @click="selectRow(row)"
                >
                  <td class="ov-td">
                    <div class="ov-cell-flex">
                      <span class="ov-client-dot" :style="{ background: group.color }"></span>
                      <span class="ov-client-name">{{ row.client_nom ?? `Client #${row.client_id}` }}</span>
                    </div>
                  </td>
                  <td class="ov-td">
                    <span class="ov-site-name">
                      <v-icon size="11" color="#9aa0aa">mdi-map-marker-outline</v-icon>
                      {{ row.site_nom ?? '—' }}
                    </span>
                  </td>
                  <td class="ov-td ov-td--titre">
                    <span class="ov-titre">{{ row.titre }}</span>
                  </td>
                  <td class="ov-td">
                    <span class="ov-type-badge" :style="typeStyle(row.type_commande)">
                      {{ typeLabels[row.type_commande] ?? row.type_commande }}
                    </span>
                  </td>
                  <td class="ov-td ov-td--date">{{ formatShortDate(row.created_at) }}</td>
                  <td class="ov-td">
                    <button
                      v-if="row.statut === 'planifiee'"
                      class="ov-schedule-btn"
                    >Planifié {{ formatShortDate(row.date_livraison_souhaitee) }}</button>
                    <span v-else class="ov-td--date">{{ formatShortDate(row.date_livraison_souhaitee) }}</span>
                  </td>
                  <td class="ov-td" style="text-align:right">
                    <span class="ov-montant">{{ formatMontant(row.budget_estime) }}</span>
                  </td>
                  <td class="ov-td">
                    <div class="ov-cell-flex">
                      <span :class="['ov-statut-chip', `ov-statut-chip--${row.statut}`]">
                        <span class="ov-statut-chip__dot"></span>
                        {{ statutLabels[row.statut] }}
                      </span>
                      <v-icon size="10" color="#ccc">mdi-chevron-down</v-icon>
                    </div>
                  </td>
                  <td class="ov-td">
                    <div class="ov-cell-flex">
                      <span class="ov-avatar">{{ initials(row.permanencier_nom) }}</span>
                      <span class="ov-resp-name">{{ row.permanencier_nom }}</span>
                    </div>
                  </td>
                  <td class="ov-td">
                    <div class="ov-cell-flex">
                      <span class="ov-avatar ov-avatar--blue">{{ initials(row.contact_nom) }}</span>
                      <span class="ov-resp-name">{{ row.contact_nom ?? '—' }}</span>
                    </div>
                  </td>
                  <td class="ov-td">
                    <div class="ov-cell-flex">
                      <span class="ov-avatar ov-avatar--teal">{{ initials(row.created_by_nom) }}</span>
                      <span class="ov-resp-name">{{ row.created_by_nom ?? '—' }}</span>
                    </div>
                  </td>
                  <td class="ov-td">
                    <div class="ov-cell-flex">
                      <span class="ov-avatar ov-avatar--amber">{{ initials(row.updated_by_nom) }}</span>
                      <span class="ov-resp-name">{{ row.updated_by_nom ?? '—' }}</span>
                    </div>
                  </td>
                  <td class="ov-td ov-td--date">{{ formatShortDate(row.updated_at) }}</td>
                  <td class="ov-td" style="text-align:center">
                    <button class="ov-action-btn" @click.stop="selectRow(row)">
                      <v-icon size="15">mdi-dots-vertical</v-icon>
                    </button>
                  </td>
                </tr>
              </template>

            </template>
          </template>

          <!-- Mode liste plat -->
          <template v-else>
            <tr
              v-for="row in filteredRows"
              :key="row.id"
              class="ov-data-row"
              style="cursor:pointer"
              @click="selectRow(row)"
            >
              <td class="ov-td">
                <div class="ov-cell-flex">
                  <span class="ov-client-dot" :style="{ background: clientColor(row.client_id) }"></span>
                  <span class="ov-client-name">{{ row.client_nom ?? `Client #${row.client_id}` }}</span>
                </div>
              </td>
              <td class="ov-td">
                <span class="ov-site-name">
                  <v-icon size="11" color="#9aa0aa">mdi-map-marker-outline</v-icon>
                  {{ row.site_nom ?? '—' }}
                </span>
              </td>
              <td class="ov-td ov-td--titre">
                <span class="ov-titre">{{ row.titre }}</span>
              </td>
              <td class="ov-td">
                <span class="ov-type-badge" :style="typeStyle(row.type_commande)">
                  {{ typeLabels[row.type_commande] ?? row.type_commande }}
                </span>
              </td>
              <td class="ov-td ov-td--date">{{ formatShortDate(row.created_at) }}</td>
              <td class="ov-td">
                <button v-if="row.statut === 'planifiee'" class="ov-schedule-btn">
                  Planifié {{ formatShortDate(row.date_livraison_souhaitee) }}
                </button>
                <span v-else class="ov-td--date">{{ formatShortDate(row.date_livraison_souhaitee) }}</span>
              </td>
              <td class="ov-td" style="text-align:right">
                <span class="ov-montant">{{ formatMontant(row.budget_estime) }}</span>
              </td>
              <td class="ov-td">
                <div class="ov-cell-flex">
                  <span :class="['ov-statut-chip', `ov-statut-chip--${row.statut}`]">
                    <span class="ov-statut-chip__dot"></span>
                    {{ statutLabels[row.statut] }}
                  </span>
                  <v-icon size="10" color="#ccc">mdi-chevron-down</v-icon>
                </div>
              </td>
              <td class="ov-td">
                <div class="ov-cell-flex">
                  <span class="ov-avatar">{{ initials(row.permanencier_nom) }}</span>
                  <span class="ov-resp-name">{{ row.permanencier_nom }}</span>
                </div>
              </td>
              <td class="ov-td">
                <div class="ov-cell-flex">
                  <span class="ov-avatar ov-avatar--blue">{{ initials(row.created_by_nom) }}</span>
                  <span class="ov-resp-name">{{ row.created_by_nom ?? '—' }}</span>
                </div>
              </td>
              <td class="ov-td">
                <div class="ov-cell-flex">
                  <span class="ov-avatar ov-avatar--amber">{{ initials(row.updated_by_nom) }}</span>
                  <span class="ov-resp-name">{{ row.updated_by_nom ?? '—' }}</span>
                </div>
              </td>
              <td class="ov-td ov-td--date">{{ formatShortDate(row.updated_at) }}</td>
              <td class="ov-td" style="text-align:center">
                <button class="ov-action-btn" @click.stop="selectRow(row)">
                  <v-icon size="15">mdi-dots-vertical</v-icon>
                </button>
              </td>
            </tr>
          </template>

          <!-- Chargement -->
          <tr v-if="loading">
            <td colspan="14">
              <div class="ov-empty">
                <v-icon size="28" color="#e0e0e0" class="ov-spin">mdi-loading</v-icon>
                <span>Chargement des commandes…</span>
              </div>
            </td>
          </tr>

          <!-- Erreur API -->
          <tr v-else-if="loadError">
            <td colspan="14">
              <div class="ov-empty" style="color:#e74c3c">
                <v-icon size="28" color="#e74c3c">mdi-alert-circle-outline</v-icon>
                <span>{{ loadError }}</span>
              </div>
            </td>
          </tr>

          <!-- État vide -->
          <tr v-else-if="(groupEnabled ? groupedRows : filteredRows).length === 0">
            <td colspan="14">
              <div class="ov-empty">
                <v-icon size="36" color="#e0e0e0">mdi-package-variant-closed-check</v-icon>
                <span>Aucune commande ne correspond aux critères</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>

  <!-- ── Drawer d'édition ─────────────────────────────────────────────── -->
  <EditCommandeDrawer
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
import EditCommandeDrawer from "@/components/workspace/EditCommandeDrawer.vue";

const route = useRoute();

// ─── Palette couleur ──────────────────────────────────────────────────────────
const PALETTE = ["#00a8a8","#3498db","#8e44ad","#e67e22","#27ae60","#e74c3c","#f39c12","#16a085"];
const clientColor = (id) => PALETTE[((id ?? 0) - 1 + PALETTE.length) % PALETTE.length];

const typeLabels = {
  gardiennage:          "Gardiennage",
  surveillance_mobile:  "Surv. mobile",
  rondes:               "Rondes",
  intervention:         "Intervention",
  filtrage:             "Filtrage",
  protection_rapprochee:"Protection",
  accueil_securite:     "Accueil sécu.",
  autre:                "Autre",
};

const typeColors = {
  gardiennage:          { bg: "rgba(0,168,168,0.1)",  fg: "#00a8a8" },
  surveillance_mobile:  { bg: "rgba(52,152,219,0.1)", fg: "#3498db" },
  rondes:               { bg: "rgba(0,11,35,0.06)",   fg: "#555"    },
  intervention:         { bg: "rgba(231,76,60,0.1)",  fg: "#e74c3c" },
  filtrage:             { bg: "rgba(243,156,18,0.1)", fg: "#f39c12" },
  protection_rapprochee:{ bg: "rgba(142,68,173,0.1)", fg: "#8e44ad" },
  accueil_securite:     { bg: "rgba(39,174,96,0.1)",  fg: "#27ae60" },
  autre:                { bg: "rgba(0,0,0,0.05)",     fg: "#aaa"    },
};

const statutLabels = {
  planifiee: "Planifiée",
  en_cours:  "En cours",
  validee:   "Validée",
  termine:   "Terminée",
  suspendue: "Suspendue",
  annulee:   "Annulée",
};

const statutOptions = [
  { value: "planifiee", label: "Planifiée",  color: "#3498db" },
  { value: "en_cours",  label: "En cours",   color: "#f39c12" },
  { value: "validee",   label: "Validée",    color: "#27ae60" },
  { value: "termine",   label: "Terminée",   color: "#95a5a6" },
  { value: "annulee",   label: "Annulée",    color: "#e74c3c" },
];

const typeOptions = [
  { value: "gardiennage",          label: "Gardiennage"   },
  { value: "surveillance_mobile",  label: "Surveillance"  },
  { value: "rondes",               label: "Rondes"        },
  { value: "intervention",         label: "Intervention"  },
  { value: "filtrage",             label: "Filtrage"      },
  { value: "protection_rapprochee",label: "Protection"    },
  { value: "accueil_securite",     label: "Accueil"       },
];

// ─── Données réelles ──────────────────────────────────────────────────────────
const demandes        = ref([]);
const loading         = ref(false);
const loadError       = ref("");
const selectedDemande = ref(null);

async function loadData() {
  loading.value = true;
  loadError.value = "";
  try {
    demandes.value = await listDemandes({ type_demande: "commande" });
  } catch {
    loadError.value = "Impossible de charger les commandes.";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  if (route.query.contact_id) {
    filterContactId.value = Number(route.query.contact_id);
    showFilters.value = false;
  }
  loadData();
});

// ─── État UI ──────────────────────────────────────────────────────────────────
const search          = ref("");
const showFilters     = ref(false);
const filterStatut    = ref(null);
const filterType      = ref(null);
const filterClientId  = ref(null);
const filterContactId = ref(null);
const groupEnabled   = ref(true);
const openGroups     = ref(new Set());

// ─── Computed ─────────────────────────────────────────────────────────────────
const activeFiltersCount = computed(() =>
  [filterStatut.value, filterType.value, filterClientId.value,
   filterContactId.value].filter(v => v != null).length
);

const filterContactName = computed(() => {
  if (filterContactId.value == null) return null;
  const found = demandes.value.find(d => d.contact_id === filterContactId.value);
  return found?.contact_nom ?? `Contact #${filterContactId.value}`;
});

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase();
  return demandes.value.filter(o => {
    if (q) {
      const hay = `${o.titre} ${o.client_nom ?? ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (filterStatut.value    && o.statut        !== filterStatut.value)    return false;
    if (filterType.value      && o.type_commande !== filterType.value)      return false;
    if (filterClientId.value  != null && o.client_id  !== filterClientId.value)  return false;
    if (filterContactId.value != null && o.contact_id !== filterContactId.value) return false;
    return true;
  });
});

const groupedRows = computed(() => {
  const map = {};
  for (const o of filteredRows.value) {
    const name = o.client_nom ?? `Client #${o.client_id}`;
    if (!map[name]) map[name] = { client: name, clientId: o.client_id, color: clientColor(o.client_id), items: [] };
    map[name].items.push(o);
  }
  return Object.values(map);
});

watch(groupedRows, (groups) => {
  const s = new Set(openGroups.value);
  groups.forEach(g => s.add(g.client));
  openGroups.value = s;
}, { immediate: true });

const kpiCards = computed(() => {
  const map = {};
  for (const o of demandes.value) {
    const name = o.client_nom ?? `Client #${o.client_id}`;
    if (!map[name]) map[name] = { client: name, clientId: o.client_id, color: clientColor(o.client_id), enCours: 0, total: 0, montantTotal: 0, hasNew: false };
    map[name].total++;
    map[name].montantTotal += o.budget_estime ?? 0;
    if (["planifiee", "en_cours"].includes(o.statut)) map[name].enCours++;
    if (o.statut === "planifiee") map[name].hasNew = true;
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
  filterType.value      = null;
  filterClientId.value  = null;
  filterContactId.value = null;
}

function selectRow(row) { selectedDemande.value = row; }

function onUpdated(updated) {
  const idx = demandes.value.findIndex(d => d.id === updated.id);
  if (idx !== -1) demandes.value.splice(idx, 1, updated);
  selectedDemande.value = null;
}

function typeStyle(type) {
  const c = typeColors[type] ?? typeColors.autre;
  return { background: c.bg, color: c.fg };
}

function formatMontant(val) {
  if (val == null) return "—";
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(val);
}

function formatShortDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

function initials(name) {
  if (!name) return "?";
  return name.split(" ").map(p => p[0]).join("").slice(0, 2).toUpperCase();
}
</script>

<style scoped>
/* ══ ROOT ════════════════════════════════════════════════════════════ */
.ov-root {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px;
  background: #f2f2f2;
  min-height: 100%;
  font-family: "Fira Sans", sans-serif;
}

/* ══ HEADER ══════════════════════════════════════════════════════════ */
.ov-hdr {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.ov-hdr-title-row {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 4px;
}

.ov-hdr-marker {
  width: 3px;
  height: 18px;
  background: #00a8a8;
  border-radius: 1px;
  flex-shrink: 0;
}

.ov-title {
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #000b23;
  text-transform: uppercase;
  margin: 0;
}

.ov-subtitle {
  font-size: 11px;
  color: #999;
  margin: 0;
  padding-left: 12px;
}

.ov-hdr-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.ov-btn {
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

.ov-btn--ghost {
  background: #fff;
  color: #555;
  border: 1px solid rgba(0, 0, 0, 0.12);
}
.ov-btn--ghost:hover { border-color: #00a8a8; color: #00a8a8; }

.ov-btn--primary {
  background: #000b23;
  color: #fff;
}
.ov-btn--primary:hover { background: #00a8a8; }

/* ══ KPI STRIP ═══════════════════════════════════════════════════════ */
.ov-kpi-strip {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.ov-kpi-strip::-webkit-scrollbar { height: 3px; }
.ov-kpi-strip::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 2px; }

.ov-kpi-card {
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
.ov-kpi-card:hover { border-color: rgba(0,168,168,0.3); box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.ov-kpi-card--active { border-color: #00a8a8; background: rgba(0,168,168,0.03); }

.ov-kpi-card__head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ov-kpi-card__badge {
  font-family: "Fira Code", monospace;
  font-size: 7px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #3498db;
  background: rgba(52,152,219,0.1);
  padding: 2px 5px;
  border-radius: 2px;
  text-transform: uppercase;
  flex-shrink: 0;
}

.ov-kpi-card__dot {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  flex-shrink: 0;
}

.ov-kpi-card__name {
  font-size: 11px;
  font-weight: 700;
  color: #000b23;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ov-kpi-card__link {
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

.ov-kpi-card__metrics {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ov-kpi-card__divider {
  width: 1px;
  height: 22px;
  background: rgba(0,0,0,0.07);
}

.ov-kpi-card__metric {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.ov-kpi-card__metric-lbl {
  font-family: "Fira Code", monospace;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #ccc;
  text-transform: uppercase;
}

.ov-kpi-card__metric-val {
  font-family: "Fira Code", monospace;
  font-size: 14px;
  font-weight: 700;
  color: #000b23;
}
.ov-kpi-card__metric-val--teal { color: #00a8a8; font-size: 12px; }
.ov-kpi-card__metric-total { font-size: 11px; color: #bbb; font-weight: 500; }

/* ══ TOOLBAR ════════════════════════════════════════════════════════ */
.ov-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 3px;
  padding: 7px 12px;
}

.ov-search {
  display: flex;
  align-items: center;
  gap: 7px;
  flex: 1;
}

.ov-search__input {
  flex: 1;
  border: none;
  outline: none;
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  color: #000b23;
  background: transparent;
}
.ov-search__input::placeholder { color: #ccc; }

.ov-search__clear {
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

.ov-toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  border-left: 1px solid rgba(0,0,0,0.07);
  padding-left: 10px;
}

.ov-tool-btn {
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
.ov-tool-btn:hover { border-color: #00a8a8; color: #00a8a8; }
.ov-tool-btn--active { border-color: #00a8a8; color: #00a8a8; background: rgba(0,168,168,0.06); }

.ov-tool-btn__badge {
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
.ov-filter-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 3px;
  padding: 8px 12px;
  flex-wrap: wrap;
}

.ov-filter-group {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
}

.ov-filter-lbl {
  font-family: "Fira Code", monospace;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #ccc;
  text-transform: uppercase;
  margin-right: 2px;
  white-space: nowrap;
}

.ov-filter-chip {
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
.ov-filter-chip:hover { border-color: #00a8a8; color: #00a8a8; }
.ov-filter-chip--active { background: #000b23; border-color: #000b23; color: #fff; }

.ov-filter-chip__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ov-filter-reset {
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

/* ══ TABLE ═══════════════════════════════════════════════════════════ */
.ov-table-wrap {
  background: #fff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 3px;
  overflow: hidden;
}

.ov-table {
  width: 100%;
  border-collapse: collapse;
}

.ov-th {
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

/* Groupe accordéon */
.ov-group-row { cursor: pointer; }
.ov-group-row:hover .ov-group-row__cell { background: rgba(0,168,168,0.04); }

.ov-group-row__cell {
  padding: 7px 12px;
  background: rgba(0,11,35,0.02);
  border-bottom: 1px solid rgba(0,0,0,0.06);
  transition: background 0.1s;
}

.ov-group-row__inner {
  display: flex;
  align-items: center;
  gap: 7px;
}

.ov-group-row__chevron {
  color: #bbb;
  transition: transform 0.18s;
  flex-shrink: 0;
}
.ov-group-row__chevron--open { transform: rotate(90deg); }

.ov-group-row__dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}

.ov-group-row__name {
  font-size: 12px;
  font-weight: 700;
  color: #000b23;
}

.ov-group-row__count {
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

.ov-group-row__total {
  font-family: "Fira Code", monospace;
  font-size: 11px;
  font-weight: 700;
  color: #00a8a8;
}

.ov-group-row__spacer { flex: 1; }

.ov-group-row__link {
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
.ov-data-row {
  border-bottom: 1px solid rgba(0,0,0,0.05);
  transition: background 0.1s;
}
.ov-data-row:hover { background: rgba(0,168,168,0.025); }
.ov-data-row:last-child { border-bottom: none; }

.ov-td {
  padding: 8px 12px;
  font-size: 11.5px;
  color: #333;
  vertical-align: middle;
  max-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ov-td--titre { max-width: 250px; }
.ov-td--date {
  font-family: "Fira Code", monospace;
  font-size: 10.5px;
  color: #888;
  white-space: nowrap;
  display: inline;
}

.ov-cell-flex {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
}

/* Client */
.ov-client-dot { width: 7px; height: 7px; border-radius: 1px; flex-shrink: 0; }
.ov-client-name { font-size: 11px; color: #777; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ov-site-name { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #777; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Titre */
.ov-titre { font-weight: 600; color: #000b23; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }

/* Type badge — couleur dynamique via :style */
.ov-type-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 7px;
  border-radius: 2px;
  font-family: "Fira Code", monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

/* Bouton "Planifié xx/xx" */
.ov-schedule-btn {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border: none;
  border-radius: 2px;
  background: rgba(52,152,219,0.08);
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  font-weight: 700;
  color: #3498db;
  cursor: pointer;
  white-space: nowrap;
  letter-spacing: 0.02em;
}
.ov-schedule-btn:hover { background: rgba(52,152,219,0.15); }

/* Montant */
.ov-montant {
  font-family: "Fira Code", monospace;
  font-size: 11px;
  font-weight: 700;
  color: #000b23;
}

/* Statut */
.ov-statut-chip {
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
.ov-statut-chip__dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; flex-shrink: 0; }

.ov-statut-chip--planifiee { background: rgba(52,152,219,0.1); color: #3498db; }
.ov-statut-chip--en_cours  { background: rgba(243,156,18,0.1); color: #f39c12; }
.ov-statut-chip--validee   { background: rgba(39,174,96,0.1);  color: #27ae60; }
.ov-statut-chip--termine   { background: rgba(0,0,0,0.06);     color: #95a5a6; }
.ov-statut-chip--suspendue { background: rgba(231,76,60,0.1);  color: #e67e22; }
.ov-statut-chip--annulee   { background: rgba(231,76,60,0.1);  color: #e74c3c; }

/* Responsable */
.ov-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(0,168,168,0.12);
  font-family: "Fira Code", monospace;
  font-size: 8px;
  font-weight: 700;
  color: #00a8a8;
  flex-shrink: 0;
}

.ov-resp-name { font-size: 11px; color: #666; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ov-avatar--blue  { background: rgba(52,152,219,0.12);  color: #3498db; }
.ov-avatar--teal  { background: rgba(0,168,168,0.12);   color: #00a8a8; }
.ov-avatar--amber { background: rgba(243,156,18,0.12);  color: #f39c12; }

/* Chip filtre actif demandeur */
.ov-active-filter-chip {
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
.ov-active-filter-chip__close {
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
.ov-active-filter-chip__close:hover { opacity: 1; }

/* Actions */
.ov-action-btn {
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
.ov-action-btn:hover { background: rgba(0,0,0,0.06); color: #555; }

.ov-spin { animation: ov-rotate 0.8s linear infinite; }
@keyframes ov-rotate { to { transform: rotate(360deg); } }

/* Empty */
.ov-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 48px 0;
  color: #ccc;
  font-size: 12px;
}
</style>
