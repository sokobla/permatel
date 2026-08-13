<template>
  <div class="ws-card wod">
    <div class="card-hdr">
      <h2 class="card-title">Demandes en cours</h2>
      <span class="wod-count">{{ filtered.length }}</span>
    </div>
    <hr class="card-divider" />

    <!-- Filtres -->
    <div class="wod-filters">
      <label
        class="wod-date-btn"
        :class="{ 'wod-date-btn--active': fDate }"
        :title="fDate ? `À partir du ${fDate}` : 'Filtrer à partir d\'une date'"
      >
        <v-icon size="14" :color="fDate ? '#00a8a8' : '#9aa0aa'"
          >mdi-calendar-outline</v-icon
        >
        <input v-model="fDate" type="date" />
      </label>
      <div class="wod-filter-pill">
        <select v-model="fType" title="Type de demande">
          <option value="">Tous types</option>
          <option v-for="t in TYPES" :key="t.value" :value="t.value">
            {{ t.label }}
          </option>
        </select>
      </div>
      <div class="wod-filter-pill">
        <select v-model="fDemandeur" title="Demandeur">
          <option value="">Tous demandeurs</option>
          <option v-for="d in demandeurs" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>
      <button
        v-if="fDate || fType || fDemandeur"
        class="wod-reset"
        title="Réinitialiser"
        @click="resetFilters"
      >
        <v-icon size="12">mdi-close</v-icon>
      </button>
    </div>

    <!-- Liste -->
    <div class="wod-body">
      <div v-if="loading" class="wod-state">Chargement…</div>
      <div v-else-if="!filtered.length" class="wod-state">
        <v-icon size="22" color="#ddd">mdi-clipboard-text-off-outline</v-icon>
        <span>Aucune demande en cours</span>
      </div>
      <ul v-else class="wod-list">
        <li
          v-for="d in filtered"
          :key="d.id"
          class="wod-item"
          @click="$emit('select', d)"
        >
          <div class="wod-item__top">
            <span
              class="wod-type-icon"
              :style="{ background: typeMeta(d.type_demande).color }"
            >
              <v-icon size="13" color="#fff">{{
                typeMeta(d.type_demande).icon
              }}</v-icon>
            </span>
            <div class="wod-item__text">
              <span
                class="wod-type-chip"
                :style="{
                  background: typeMeta(d.type_demande).tint,
                  color: typeMeta(d.type_demande).color,
                }"
                >{{ typeMeta(d.type_demande).label }}</span
              >
              <div class="wod-title">{{ d.titre }}</div>
            </div>
            <span
              v-if="d.contact_nom"
              class="wod-avatar"
              :title="d.contact_nom"
              >{{ initials(d.contact_nom) }}</span
            >
          </div>

          <div class="wod-meta">
            <span class="wod-ticket">{{ d.numero_ticket }}</span>
            <span class="sep">·</span>
            <span>{{ relativeTime(d.created_at) }}</span>
          </div>

          <div v-if="slaProgress(d)" class="wod-sla-row">
            <div class="wod-sla-track">
              <div
                class="wod-sla-fill"
                :style="{
                  width: slaProgress(d).pct + '%',
                  background: slaProgress(d).color,
                }"
              ></div>
            </div>
            <span
              class="wod-sla-label"
              :style="{ color: slaProgress(d).color }"
              >{{ slaProgress(d).label }}</span
            >
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { listDemandes } from "@/services/demandeService";

defineEmits(["select"]);

const TYPES = [
  { value: "anomalie", label: "Anomalie" },
  { value: "commande", label: "Commande" },
  { value: "planning", label: "Planning" },
  { value: "admin", label: "Admin" },
];
const CLOSED = new Set(["resolue", "cloturee", "annulee"]);

// Couleurs/icônes par type — reprend la palette déjà utilisée ailleurs dans
// l'app (dashboard, AnomaliesView) pour rester cohérent.
const TYPE_META = {
  anomalie: {
    label: "Anomalie",
    color: "#e74c3c",
    tint: "rgba(231,76,60,0.1)",
    icon: "mdi-alert-octagon-outline",
  },
  commande: {
    label: "Commande",
    color: "#00a8a8",
    tint: "rgba(0,168,168,0.1)",
    icon: "mdi-package-variant-closed",
  },
  planning: {
    label: "Planning",
    color: "#3498db",
    tint: "rgba(52,152,219,0.1)",
    icon: "mdi-calendar-outline",
  },
  admin: {
    label: "Admin",
    color: "#8e44ad",
    tint: "rgba(142,68,173,0.1)",
    icon: "mdi-folder-cog-outline",
  },
};
function typeMeta(type) {
  return (
    TYPE_META[type] || {
      label: type || "?",
      color: "#9aa0aa",
      tint: "rgba(0,0,0,0.05)",
      icon: "mdi-file-outline",
    }
  );
}

// État SLA -> couleur/libellé pour la barre de progression (mêmes états que
// SlaBadge, dupliqué ici en local — ce composant n'exporte pas sa palette).
const SLA_META = {
  on_time: { label: "Dans les délais", color: "#22c55e" },
  at_risk: { label: "À risque", color: "#f39c12" },
  breached: { label: "Hors délai", color: "#e74c3c" },
  met: { label: "Respecté", color: "#22c55e" },
  missed: { label: "Non respecté", color: "#e74c3c" },
  paused: { label: "En pause", color: "#9aa0aa" },
};
function slaProgress(d) {
  const sla = d.sla && d.sla.resolution;
  if (!sla || !sla.status) return null;
  const meta = SLA_META[sla.status];
  if (!meta) return null;
  let pct = 100;
  if (sla.deadline && d.created_at) {
    const start = new Date(d.created_at).getTime();
    const end = new Date(sla.deadline).getTime();
    const now = Date.now();
    pct =
      end > start
        ? Math.min(100, Math.max(0, ((now - start) / (end - start)) * 100))
        : 100;
  }
  return { pct, color: meta.color, label: meta.label };
}

const rows = ref([]);
const loading = ref(false);
const fDate = ref("");
const fType = ref("");
const fDemandeur = ref("");

async function load() {
  loading.value = true;
  try {
    const res = await listDemandes();
    const list = Array.isArray(res) ? res : (res.items ?? []);
    rows.value = list.filter((d) => !CLOSED.has(d.statut));
  } catch {
    rows.value = [];
  } finally {
    loading.value = false;
  }
}
defineExpose({ reload: load });

const demandeurs = computed(() =>
  [...new Set(rows.value.map((d) => d.contact_nom).filter(Boolean))].sort(),
);

const filtered = computed(() => {
  let list = rows.value;
  if (fType.value) list = list.filter((d) => d.type_demande === fType.value);
  if (fDemandeur.value)
    list = list.filter((d) => d.contact_nom === fDemandeur.value);
  if (fDate.value) {
    const from = new Date(fDate.value + "T00:00:00").getTime();
    list = list.filter(
      (d) => d.created_at && new Date(d.created_at).getTime() >= from,
    );
  }
  return [...list].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at),
  );
});

function resetFilters() {
  fDate.value = "";
  fType.value = "";
  fDemandeur.value = "";
}
function initials(name) {
  if (!name) return "?";
  return name
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
function relativeTime(iso) {
  if (!iso) return "—";
  const diffSec = Math.max(
    0,
    Math.floor((Date.now() - new Date(iso).getTime()) / 1000),
  );
  if (diffSec < 60) return `il y a ${diffSec}s`;
  const min = Math.floor(diffSec / 60);
  if (min < 60) return `il y a ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `il y a ${h} h`;
  const j = Math.floor(h / 24);
  return `il y a ${j} j`;
}

onMounted(load);
</script>

<style scoped>
.wod {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.card-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.wod-count {
  font-family: "Fira Code", monospace;
  font-size: 13px;
  font-weight: 700;
  color: #00a8a8;
  background: rgba(0, 168, 168, 0.1);
  border-radius: 10px;
  padding: 1px 7px;
}

/* Filtres */
.wod-filters {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px 0;
}

.wod-date-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #fff;
  cursor: pointer;
  flex-shrink: 0;
  position: relative;
}
.wod-date-btn--active {
  border-color: #00a8a8;
  background: rgba(0, 168, 168, 0.08);
}
.wod-date-btn input[type="date"] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
  width: 100%;
  height: 100%;
  border: none;
}

.wod-filter-pill {
  display: flex;
  align-items: center;
  height: 28px;
  padding: 0 8px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #fff;
  flex: 1;
  min-width: 0;
}
.wod-filter-pill:focus-within {
  border-color: #00a8a8;
}
.wod-filter-pill select {
  border: none;
  outline: none;
  background: transparent;
  font-size: 10.5px;
  color: #1a1a2e;
  width: 100%;
  text-overflow: ellipsis;
}

.wod-reset {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 50%;
  background: rgba(231, 76, 60, 0.08);
  color: #e74c3c;
  cursor: pointer;
  flex-shrink: 0;
}

.wod-body {
  overflow-y: auto;
  min-height: 0;
  flex: 1;
  padding: 10px 14px 14px;
}
.wod-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px;
  color: #9aa0aa;
  font-size: 12.5px;
}

.wod-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wod-item {
  padding: 10px 10px 9px;
  border: 1px solid #eef0f2;
  border-radius: 10px;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s;
}
.wod-item:hover {
  border-color: #00a8a8;
  background: #f7fdfd;
}

.wod-item__top {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.wod-type-icon {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.wod-item__text {
  min-width: 0;
  flex: 1;
}
.wod-type-chip {
  display: inline-block;
  font-size: 8.5px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 1px 6px;
  border-radius: 999px;
  margin-bottom: 3px;
}
.wod-title {
  font-size: 12.5px;
  font-weight: 600;
  color: #000b23;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.wod-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(0, 168, 168, 0.12);
  color: #00a8a8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9.5px;
  font-weight: 700;
  font-family: "Fira Code", monospace;
  flex-shrink: 0;
  margin-top: 1px;
}

.wod-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
  color: #9aa0aa;
  margin-top: 7px;
}
.wod-ticket {
  font-family: "Fira Code", monospace;
}
.wod-meta .sep {
  opacity: 0.5;
}

.wod-sla-row {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 7px;
}
.wod-sla-track {
  flex: 1;
  height: 4px;
  border-radius: 3px;
  background: #f2f2f2;
  overflow: hidden;
  border: 1px solid #eef0f2;
}
.wod-sla-fill {
  height: 100%;
  border-radius: 3px;
}
.wod-sla-label {
  font-size: 9.5px;
  font-weight: 700;
  white-space: nowrap;
}
</style>
