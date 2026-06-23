<template>
  <div class="ws-card wod">
    <div class="card-hdr">
      <h2 class="card-title">Demandes en cours</h2>
      <span class="wod-count">{{ filtered.length }}</span>
    </div>
    <hr class="card-divider" />

    <!-- Filtres -->
    <div class="wod-filters">
      <input v-model="fDate" type="date" class="wod-date" title="À partir du" />
      <select v-model="fType" class="wod-select">
        <option value="">Tous types</option>
        <option v-for="t in TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
      </select>
      <select v-model="fDemandeur" class="wod-select">
        <option value="">Tous demandeurs</option>
        <option v-for="d in demandeurs" :key="d" :value="d">{{ d }}</option>
      </select>
      <button v-if="fDate || fType || fDemandeur" class="wod-reset" title="Réinitialiser" @click="resetFilters">✕</button>
    </div>

    <!-- Liste -->
    <div class="wod-body">
      <div v-if="loading" class="wod-state">Chargement…</div>
      <div v-else-if="!filtered.length" class="wod-state">
        <v-icon size="22" color="#ddd">mdi-clipboard-text-off-outline</v-icon>
        <span>Aucune demande en cours</span>
      </div>
      <ul v-else class="wod-list">
        <li v-for="d in filtered" :key="d.id" class="wod-item" @click="$emit('select', d)">
          <div class="wod-item-top">
            <span class="wod-ticket">{{ d.numero_ticket }}</span>
            <span :class="['wod-type', `wod-type--${d.type_demande}`]">{{ TYPE_LABELS[d.type_demande] || d.type_demande }}</span>
          </div>
          <div class="wod-title">{{ d.titre }}</div>
          <div class="wod-meta">
            <span v-if="d.contact_nom" class="wod-dem"><v-icon size="11">mdi-account-outline</v-icon> {{ d.contact_nom }}</span>
            <span class="wod-date">{{ formatDate(d.created_at) }}</span>
          </div>
          <SlaBadge :state="d.sla && d.sla.resolution" />
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { listDemandes } from "@/services/demandeService";
import SlaBadge from "@/components/sla/SlaBadge.vue";

defineEmits(["select"]);

const TYPES = [
  { value: "anomalie", label: "Anomalie" },
  { value: "commande", label: "Commande" },
  { value: "planning", label: "Planning" },
  { value: "admin", label: "Admin" },
];
const TYPE_LABELS = Object.fromEntries(TYPES.map((t) => [t.value, t.label]));
const CLOSED = new Set(["resolue", "cloturee", "annulee"]);

const rows = ref([]);
const loading = ref(false);
const fDate = ref("");
const fType = ref("");
const fDemandeur = ref("");

async function load() {
  loading.value = true;
  try {
    const res = await listDemandes();
    const list = Array.isArray(res) ? res : res.items ?? [];
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
  if (fDemandeur.value) list = list.filter((d) => d.contact_nom === fDemandeur.value);
  if (fDate.value) {
    const from = new Date(fDate.value + "T00:00:00").getTime();
    list = list.filter((d) => d.created_at && new Date(d.created_at).getTime() >= from);
  }
  return [...list].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
});

function resetFilters() {
  fDate.value = "";
  fType.value = "";
  fDemandeur.value = "";
}
function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

onMounted(load);
</script>

<style scoped>
.wod { display: flex; flex-direction: column; min-height: 0; }
.card-hdr { display: flex; align-items: center; justify-content: space-between; }
.wod-count { font-family: "Fira Code", monospace; font-size: 12px; font-weight: 700; color: #00a8a8; }
.wod-filters { display: flex; gap: 6px; flex-wrap: wrap; padding: 8px 0; }
.wod-date, .wod-select {
  height: 28px; border: 1px solid #e5e7eb; border-radius: 5px; background: #fff;
  font-size: 11.5px; color: #1a1a2e; padding: 0 6px; outline: none; max-width: 120px;
}
.wod-date:focus, .wod-select:focus { border-color: #00a8a8; }
.wod-reset { border: none; background: none; color: #9aa0aa; cursor: pointer; font-size: 13px; }
.wod-body { overflow-y: auto; min-height: 0; flex: 1; }
.wod-state { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 24px; color: #9aa0aa; font-size: 12.5px; }
.wod-list { list-style: none; margin: 0; padding: 0; }
.wod-item { padding: 9px 10px; border: 1px solid #eef0f2; border-radius: 8px; margin-bottom: 7px; cursor: pointer; transition: border-color .15s, background .15s; }
.wod-item:hover { border-color: #00a8a8; background: #f7fdfd; }
.wod-item-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.wod-ticket { font-family: "Fira Code", monospace; font-size: 11px; color: #6b7280; }
.wod-type { font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 999px; background: rgba(0,168,168,.1); color: #00a8a8; text-transform: uppercase; }
.wod-type--anomalie { background: rgba(231,76,60,.1); color: #e74c3c; }
.wod-title { font-size: 13px; font-weight: 600; color: #000b23; margin: 3px 0; line-height: 1.3; }
.wod-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 11px; color: #6b7280; margin-bottom: 5px; }
.wod-dem { display: inline-flex; align-items: center; gap: 3px; }
.wod-date { font-family: "Fira Code", monospace; }
</style>
