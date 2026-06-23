<template>
  <v-card variant="flat" class="sla-card" rounded="lg" border>
    <div class="sla-head">
      <div>
        <h2 class="sla-title">Délais SLA</h2>
        <p class="sla-sub">
          Cibles de <strong>prise en charge</strong> et de <strong>résolution</strong> par
          priorité — affinables par type de demande et par client (le plus spécifique l'emporte).
        </p>
      </div>
      <v-btn color="#00a8a8" variant="flat" size="small" class="text-none" prepend-icon="mdi-plus" @click="openCreate">
        Ajouter une règle
      </v-btn>
    </div>

    <v-divider />

    <v-alert v-if="feedback.text" :type="feedback.type" variant="tonal" density="compact" class="ma-3" closable @click:close="feedback.text = ''">
      {{ feedback.text }}
    </v-alert>

    <v-data-table
      :headers="headers"
      :items="rows"
      :loading="loading"
      density="comfortable"
      items-per-page="25"
      class="sla-table"
    >
      <template #[`item.type_demande`]="{ item }">{{ item.type_demande || "Tous" }}</template>
      <template #[`item.client`]="{ item }">{{ clientName(item.client_id) }}</template>
      <template #[`item.response_minutes`]="{ item }">{{ fmt(item.response_minutes) }}</template>
      <template #[`item.resolution_minutes`]="{ item }">{{ fmt(item.resolution_minutes) }}</template>
      <template #[`item.warning_pct`]="{ item }">{{ item.warning_pct }} %</template>
      <template #[`item.pause_on_waiting`]="{ item }">
        <v-icon size="16" :color="item.pause_on_waiting ? '#16a34a' : '#cbd0d6'">
          {{ item.pause_on_waiting ? "mdi-check-circle" : "mdi-minus-circle-outline" }}
        </v-icon>
      </template>
      <template #[`item.actions`]="{ item }">
        <v-btn icon="mdi-pencil-outline" variant="text" size="x-small" @click="openEdit(item)" />
        <v-btn icon="mdi-trash-can-outline" variant="text" size="x-small" color="#e74c3c" @click="remove(item)" />
      </template>
    </v-data-table>

    <!-- Dialog création / édition -->
    <v-dialog v-model="dialog" max-width="480">
      <v-card rounded="lg">
        <v-card-title class="sla-dlg-title">{{ editing ? "Modifier la règle SLA" : "Nouvelle règle SLA" }}</v-card-title>
        <v-divider />
        <v-card-text>
          <v-alert v-if="formError" type="error" variant="tonal" density="compact" class="mb-3">{{ formError }}</v-alert>
          <v-select v-model="form.priorite" :items="prioriteItems" label="Priorité" variant="outlined" density="comfortable" :disabled="editing" />
          <v-select v-model="form.type_demande" :items="typeItems" label="Type de demande" variant="outlined" density="comfortable" :disabled="editing" clearable />
          <v-select v-model="form.client_id" :items="clientItems" item-title="nom" item-value="id" label="Client" variant="outlined" density="comfortable" :disabled="editing" clearable />
          <div class="sla-row">
            <v-text-field v-model.number="form.response_minutes" type="number" min="1" label="Prise en charge (min)" variant="outlined" density="comfortable" :hint="hint(form.response_minutes)" persistent-hint />
            <v-text-field v-model.number="form.resolution_minutes" type="number" min="1" label="Résolution (min)" variant="outlined" density="comfortable" :hint="hint(form.resolution_minutes)" persistent-hint />
          </div>
          <div class="sla-row">
            <v-text-field v-model.number="form.warning_pct" type="number" min="1" max="100" label="Seuil d'alerte (%)" variant="outlined" density="comfortable" />
            <v-switch v-model="form.pause_on_waiting" color="#00a8a8" label="Pause si « en attente »" hide-details />
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-btn variant="text" class="text-none" @click="dialog = false">Annuler</v-btn>
          <v-spacer />
          <v-btn :loading="saving" color="#00a8a8" class="text-none" @click="save">Enregistrer</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import apiClient from "@/services/http/axios";
import { settingsService } from "@/services/settingsService";

const headers = [
  { title: "Priorité", key: "priorite" },
  { title: "Type", key: "type_demande" },
  { title: "Client", key: "client" },
  { title: "Prise en charge", key: "response_minutes", align: "end" },
  { title: "Résolution", key: "resolution_minutes", align: "end" },
  { title: "Alerte", key: "warning_pct", align: "end" },
  { title: "Pause", key: "pause_on_waiting", align: "center" },
  { title: "", key: "actions", sortable: false, align: "end" },
];
const prioriteItems = [
  { title: "Urgente", value: "urgente" },
  { title: "Haute", value: "haute" },
  { title: "Normale", value: "normale" },
  { title: "Basse", value: "basse" },
];
const typeItems = [
  { title: "Anomalie", value: "anomalie" },
  { title: "Commande", value: "commande" },
  { title: "Planning", value: "planning" },
  { title: "Admin", value: "admin" },
];

const rows = ref([]);
const clients = ref([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref(false);
const editing = ref(false);
const formError = ref("");
const feedback = reactive({ text: "", type: "success" });
const form = reactive({
  priorite: "normale", type_demande: null, client_id: null,
  response_minutes: 240, resolution_minutes: 1440, warning_pct: 80, pause_on_waiting: true,
});

const clientItems = computed(() => [...clients.value]);

function fmt(min) {
  if (min == null) return "—";
  const h = Math.floor(min / 60), m = min % 60;
  if (h >= 24) return `${Math.floor(h / 24)} j ${h % 24} h`;
  if (h > 0) return m ? `${h} h ${m}` : `${h} h`;
  return `${m} min`;
}
const hint = (min) => (min ? `≈ ${fmt(min)}` : "");
function clientName(id) {
  if (!id) return "Tous";
  return clients.value.find((c) => c.id === id)?.nom || `#${id}`;
}
function notify(text, type = "success") { feedback.text = text; feedback.type = type; }

async function load() {
  loading.value = true;
  try {
    rows.value = await settingsService.getSlaPolicies();
  } catch {
    notify("Échec du chargement des règles SLA.", "error");
  } finally {
    loading.value = false;
  }
}
async function loadClients() {
  try {
    const { data } = await apiClient.get("/clients");
    const list = data.clients ?? data.items ?? (Array.isArray(data) ? data : []);
    clients.value = list.map((c) => ({ id: c.id, nom: c.nom }));
  } catch {
    clients.value = [];
  }
}

function openCreate() {
  editing.value = false;
  formError.value = "";
  Object.assign(form, {
    priorite: "normale", type_demande: null, client_id: null,
    response_minutes: 240, resolution_minutes: 1440, warning_pct: 80, pause_on_waiting: true,
  });
  dialog.value = true;
}
function openEdit(item) {
  editing.value = true;          // périmètre (priorité/type/client) verrouillé en édition
  formError.value = "";
  Object.assign(form, {
    priorite: item.priorite, type_demande: item.type_demande, client_id: item.client_id,
    response_minutes: item.response_minutes, resolution_minutes: item.resolution_minutes,
    warning_pct: item.warning_pct, pause_on_waiting: item.pause_on_waiting,
  });
  dialog.value = true;
}

async function save() {
  formError.value = "";
  if (!form.response_minutes || !form.resolution_minutes || form.response_minutes <= 0 || form.resolution_minutes <= 0) {
    formError.value = "Les délais doivent être des entiers positifs."; return;
  }
  saving.value = true;
  try {
    await settingsService.upsertSlaPolicy({ ...form });
    dialog.value = false;
    notify("Règle SLA enregistrée.");
    load();
  } catch (e) {
    formError.value = e?.response?.data?.error || "Échec de l'enregistrement.";
  } finally {
    saving.value = false;
  }
}
async function remove(item) {
  try {
    await settingsService.deleteSlaPolicy(item.id);
    notify("Règle SLA supprimée.");
    load();
  } catch (e) {
    notify(e?.response?.data?.error || "Échec de la suppression.", "error");
  }
}

onMounted(() => { load(); loadClients(); });
</script>

<style scoped>
.sla-card { font-family: "Fira Sans", sans-serif; }
.sla-head { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; gap: 16px; }
.sla-title { font-size: 15px; font-weight: 700; color: #000b23; margin: 0; }
.sla-sub { font-size: 12.5px; color: #6b7280; margin: 2px 0 0; max-width: 640px; }
.sla-table { font-size: 13px; }
.sla-dlg-title { font-size: 15px; font-weight: 700; color: #000b23; }
.sla-row { display: flex; gap: 12px; }
.sla-row > * { flex: 1; }
</style>
