<template>
  <v-card elevation="0" class="dud-card">
    <div class="dud-header">
      <span class="card-title">DEMANDES CRITIQUES — URGENCES &amp; SLA DÉPASSÉS</span>
      <span v-if="!loading && demandes.length > 0" class="dud-count">{{ demandes.length }}</span>
    </div>
    <v-divider />

    <!-- Skeleton -->
    <div v-if="loading" class="dud-skeleton">
      <div v-for="n in 3" :key="n" class="dud-sk-row">
        <div class="dud-sk dud-sk--ticket"></div>
        <div class="dud-sk dud-sk--badge"></div>
        <div class="dud-sk dud-sk--title"></div>
        <div class="dud-sk dud-sk--chip"></div>
        <div class="dud-sk dud-sk--status"></div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="demandes.length === 0" class="dud-empty">
      <v-icon size="28" color="#ddd">mdi-check-circle-outline</v-icon>
      <span class="dud-empty__text">Aucune demande critique en cours</span>
    </div>

    <!-- Table -->
    <v-data-table
      v-else
      :headers="headers"
      :items="demandes"
      density="compact"
      hide-default-footer
      :items-per-page="-1"
      class="dud-table"
    >
      <template #[`item.numero_ticket`]="{ item }">
        <span class="code-font text-caption">{{ item.numero_ticket }}</span>
      </template>

      <template #[`item.type_demande`]="{ item }">
        <span :class="['dud-type-badge', `dud-type-badge--${item.type_demande}`]">
          {{ TYPE_LABELS[item.type_demande] ?? item.type_demande }}
        </span>
      </template>

      <template #[`item.titre`]="{ item }">
        <span class="dud-titre">{{ item.titre }}</span>
      </template>

      <template #[`item.priorite`]="{ item }">
        <v-chip
          :color="prioriteColor(item.priorite)"
          label
          size="small"
          class="priority-chip"
        >
          {{ item.priorite?.toUpperCase() }}
        </v-chip>
      </template>

      <template #[`item.sla_deadline`]="{ item }">
        <span v-if="item.sla_deadline" :class="['code-font text-caption', isSlaBreached(item.sla_deadline) ? 'dud-sla--alert' : '']">
          {{ formatDate(item.sla_deadline) }}
          <v-icon v-if="isSlaBreached(item.sla_deadline)" size="11" color="#e74c3c">mdi-alert</v-icon>
        </span>
        <span v-else class="dud-na">—</span>
      </template>

      <template #[`item.statut`]="{ item }">
        <span :class="['dud-statut', `dud-statut--${item.statut}`]">
          {{ STATUT_LABELS[item.statut] ?? item.statut }}
        </span>
      </template>
    </v-data-table>
  </v-card>
</template>

<script setup>
defineProps({
  demandes: { type: Array, default: () => [] },
  loading:  { type: Boolean, default: false },
});

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

const headers = [
  { title: "TICKET",    key: "numero_ticket", sortable: false, width: "120px" },
  { title: "TYPE",      key: "type_demande",  sortable: false, width: "72px" },
  { title: "TITRE",     key: "titre",         sortable: false },
  { title: "PRIORITÉ",  key: "priorite",      sortable: false, width: "110px" },
  { title: "SLA",       key: "sla_deadline",  sortable: false, width: "110px" },
  { title: "STATUT",    key: "statut",        sortable: false, width: "110px" },
];

function prioriteColor(p) {
  return { urgente: "#e74c3c", haute: "orange-darken-2", normale: "grey-darken-1", basse: "grey" }[p] ?? "grey";
}

function isSlaBreached(deadline) {
  return deadline && new Date(deadline) < new Date();
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}
</script>

<script>
export default { name: "DashboardUrgentDemandes" };
</script>

<style scoped>
.dud-card {
  border: 1px solid rgba(197, 198, 206, 0.15) !important;
}

.dud-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px 8px;
}

.dud-count {
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: #e74c3c;
  border-radius: 3px;
  padding: 1px 7px;
  min-width: 20px;
  text-align: center;
}

/* ── Table ─────────────────────────────────────────────────── */

.dud-table {
  font-family: "Fira Sans", sans-serif;
  background-color: #ffffff;
}

.dud-titre {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.75rem;
  font-weight: 600;
  color: #000b23;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260px;
  display: block;
}

/* ── Type badge ────────────────────────────────────────────── */

.dud-type-badge {
  font-family: "Fira Code", monospace;
  font-size: 8.5px;
  font-weight: 700;
  letter-spacing: 0.1em;
  padding: 2px 6px;
  border-radius: 2px;
}

.dud-type-badge--anomalie { background: rgba(231, 76, 60, 0.1);  color: #c0392b; }
.dud-type-badge--commande { background: rgba(0, 168, 168, 0.1);  color: #007a7a; }
.dud-type-badge--planning { background: rgba(52, 152, 219, 0.1); color: #1a73c1; }
.dud-type-badge--admin    { background: rgba(142, 68, 173, 0.1); color: #7d3c98; }

/* ── SLA ───────────────────────────────────────────────────── */

.dud-sla--alert {
  color: #e74c3c;
  font-weight: 700;
}

.dud-na {
  color: #bbb;
  font-family: "Fira Code", monospace;
  font-size: 0.75rem;
}

/* ── Statut ────────────────────────────────────────────────── */

.dud-statut {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 2px 7px;
  border-radius: 10px;
  white-space: nowrap;
}

.dud-statut--nouvelle   { background: #eaf4fb; color: #1a73c1; }
.dud-statut--en_cours   { background: rgba(0,168,168,0.1); color: #007a7a; }
.dud-statut--en_attente { background: #fef9e7; color: #b7770d; }
.dud-statut--resolue    { background: #eafaf1; color: #1e8449; }
.dud-statut--cloturee   { background: #f4f6f7; color: #707b7c; }
.dud-statut--annulee    { background: rgba(231,76,60,0.07); color: #c0392b; }

/* ── Empty ─────────────────────────────────────────────────── */

.dud-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px;
}

.dud-empty__text {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.8rem;
  font-weight: 600;
  color: #bbb;
  letter-spacing: 0.06em;
}

/* ── Skeleton ──────────────────────────────────────────────── */

.dud-skeleton {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 6px 16px;
  animation: dud-pulse 1.4s ease-in-out infinite;
}

@keyframes dud-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.35; }
}

.dud-sk-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(0,0,0,0.04);
}

.dud-sk { background: #e8e8e8; border-radius: 3px; }

.dud-sk--ticket { width: 90px;  height: 10px; flex-shrink: 0; }
.dud-sk--badge  { width: 36px;  height: 16px; flex-shrink: 0; }
.dud-sk--title  { flex: 1;      height: 10px; }
.dud-sk--chip   { width: 70px;  height: 18px; flex-shrink: 0; border-radius: 9px; }
.dud-sk--status { width: 80px;  height: 10px; flex-shrink: 0; }
</style>
