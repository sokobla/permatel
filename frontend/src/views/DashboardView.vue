<template>
  <v-container fluid class="dashboard-container">

    <!-- ── Barre de filtres ─────────────────────────────────────────────── -->
    <v-row>
      <v-col>
        <v-sheet
          color="#FFFFFF"
          class="pa-2 d-flex align-center gap-4"
          style="border: 1px solid rgba(197, 198, 206, 0.15)"
        >
          <span class="filter-label">PÉRIODE</span>
          <v-chip-group
            v-model="filters.period"
            mandatory
            selected-class="text-teal-accent-3"
          >
            <v-chip v-for="p in periods" :key="p.value" :value="p.value" size="small">
              {{ p.label }}
            </v-chip>
          </v-chip-group>

          <v-divider vertical class="mx-3" />

          <span class="filter-label">TYPE</span>
          <v-chip-group
            v-model="filters.type"
            selected-class="text-teal-accent-3"
          >
            <v-chip v-for="t in typeOptions" :key="t.value" :value="t.value" size="small">
              {{ t.label }}
            </v-chip>
          </v-chip-group>

          <v-spacer />

          <div class="filter-status">
            <span :class="['filter-status__dot', (demandeLoading || demandeRefreshing) ? 'filter-status__dot--loading' : 'filter-status__dot--ok']"></span>
            <span class="filter-status__label">
              {{ demandeLoading ? 'CHARGEMENT…' : demandeRefreshing ? 'ACTUALISATION…' : 'OPÉRATIONNEL' }}
            </span>
          </div>
        </v-sheet>
      </v-col>
    </v-row>

    <!-- ── 1. KPI Demandes ────────────────────────────────────────────── -->
    <v-row>
      <v-col
        v-for="(kpi, key) in filteredKpis"
        :key="key"
        cols="12"
        sm="6"
        md="4"
        lg="2"
      >
        <DashboardDemandesKpiCard :kpi="kpi" />
      </v-col>
    </v-row>

    <!-- ── 2. Tendance 30j + Répartition ──────────────────────────────── -->
    <v-row>
      <v-col cols="12" lg="7">
        <DashboardDemandeTrend
          :trend-data="demandeTrendData"
          :loading="demandeLoading"
        />
      </v-col>
      <v-col cols="12" lg="5">
        <DashboardDemandesBreakdown
          :by-type="demandeByType"
          :by-statut="demandeByStatut"
          :loading="demandeLoading"
        />
      </v-col>
    </v-row>

    <!-- ── 3. Demandes critiques ───────────────────────────────────────── -->
    <v-row class="mb-4">
      <v-col>
        <DashboardUrgentDemandes
          :demandes="demandeCritiques"
          :loading="demandeLoading"
        />
      </v-col>
    </v-row>

  </v-container>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useDashboardDemandesData } from "@/composables/useDashboardDemandesData";
import DashboardDemandesKpiCard  from "@/components/dashboard/DashboardDemandesKpiCard.vue";
import DashboardDemandeTrend     from "@/components/dashboard/DashboardDemandeTrend.vue";
import DashboardDemandesBreakdown from "@/components/dashboard/DashboardDemandesBreakdown.vue";
import DashboardUrgentDemandes   from "@/components/dashboard/DashboardUrgentDemandes.vue";

const {
  loading: demandeLoading,
  refreshing: demandeRefreshing,
  kpis: demandeKpis,
  byType: demandeByType,
  byStatut: demandeByStatut,
  trendData: demandeTrendData,
  critiques: demandeCritiques,
  startAutoRefresh: startDemandeRefresh,
} = useDashboardDemandesData();

const periods = [
  { value: "today",  label: "Aujourd'hui" },
  { value: "7j",     label: "7 Jours" },
  { value: "30j",    label: "30 Jours" },
  { value: "all",    label: "Tout" },
];

const typeOptions = [
  { value: "anomalie", label: "Anomalie" },
  { value: "commande", label: "Commande" },
  { value: "planning", label: "Planning" },
  { value: "admin",    label: "Administratif" },
];

const filters = reactive({
  period: "30j",
  type: null as string | null,
});

// Tous les KPIs sont toujours affichés (le filtre type oriente la lecture)
const filteredKpis = computed(() => demandeKpis.value);

onMounted(() => {
  startDemandeRefresh(30000);
});
</script>

<style scoped>
.dashboard-container {
  background-color: #f2f2f2;
  font-family: "Fira Sans", sans-serif;
}

/* ── Filtre bar ────────────────────────────────────────────────────── */

.filter-label {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #555;
  white-space: nowrap;
}

.filter-status {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-status__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.filter-status__dot--ok {
  background: #27ae60;
  box-shadow: 0 0 0 2px rgba(39, 174, 96, 0.2);
}

.filter-status__dot--loading {
  background: #f39c12;
  animation: dot-pulse 1s ease-in-out infinite;
}

@keyframes dot-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.3; }
}

.filter-status__label {
  font-family: "Fira Code", monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #888;
  text-transform: uppercase;
}

/* ── Utilitaires ───────────────────────────────────────────────────── */

.card-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 1rem;
  font-weight: 700;
  color: #000b23;
}

.code-font {
  font-family: "Fira Code", monospace;
}
</style>
