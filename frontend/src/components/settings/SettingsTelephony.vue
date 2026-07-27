<template>
  <v-card variant="flat" class="tel-card" rounded="lg" border>
    <div class="tel-head">
      <div>
        <h2 class="tel-title">Téléphonie</h2>
        <p class="tel-sub">
          Domaines PBX rattachés à votre organisation et files d'attente
          supervisées dans le Workspace. Le rattachement d'un domaine PBX
          (nouveau connecteur) est géré par l'administrateur global PERMATEL.
        </p>
      </div>
    </div>

    <v-divider />

    <v-alert
      v-if="feedback.text"
      :type="feedback.type"
      variant="tonal"
      density="compact"
      class="ma-3"
      closable
      @click:close="feedback.text = ''"
    >
      {{ feedback.text }}
    </v-alert>

    <div v-if="!loading && bindings.length === 0" class="tel-empty">
      <v-icon size="28" color="#cbd0d6">mdi-phone-off-outline</v-icon>
      <p class="tel-empty__text">
        Aucun domaine PBX n'est encore rattaché à votre organisation. Contactez
        votre administrateur PERMATEL pour configurer la téléphonie.
      </p>
    </div>

    <v-data-table
      v-else
      :headers="headers"
      :items="bindings"
      :loading="loading"
      density="comfortable"
      items-per-page="25"
      class="tel-table"
    >
      <template #[`item.connector_name`]="{ item }">
        {{ item.connector_name || "—" }}
        <v-chip
          v-if="item.connector_type"
          size="x-small"
          variant="tonal"
          class="ml-1"
        >
          {{ item.connector_type }}
        </v-chip>
      </template>
      <template #[`item.queue_ids`]="{ item }">
        <v-chip
          v-for="q in item.queue_ids"
          :key="q"
          size="small"
          variant="tonal"
          class="mr-1 mb-1"
        >
          {{ q }}
        </v-chip>
        <span v-if="!item.queue_ids?.length" class="tel-muted">Aucune</span>
      </template>
      <template #[`item.actions`]="{ item }">
        <v-btn
          icon="mdi-pencil-outline"
          variant="text"
          size="x-small"
          @click="openEdit(item)"
        />
      </template>
    </v-data-table>

    <!-- Dialog édition des queues supervisées -->
    <v-dialog v-model="dialog" max-width="480">
      <v-card rounded="lg">
        <v-card-title class="tel-dlg-title">
          Files d'attente supervisées — {{ editing?.pbx_domain }}
        </v-card-title>
        <v-divider />
        <v-card-text>
          <v-alert
            v-if="formError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
            >{{ formError }}</v-alert
          >
          <v-combobox
            v-model="form.queue_ids"
            label="Identifiants de queue (Entrée pour ajouter)"
            variant="outlined"
            density="comfortable"
            multiple
            chips
            closable-chips
            hint="Identifiant tel que défini côté PBX (ex. queue-support)."
            persistent-hint
          />
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-btn variant="text" class="text-none" @click="dialog = false"
            >Annuler</v-btn
          >
          <v-spacer />
          <v-btn
            :loading="saving"
            color="#00a8a8"
            class="text-none"
            @click="save"
            >Enregistrer</v-btn
          >
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import apiClient from "@/services/http/axios";

const bindings = ref([]);
const loading = ref(false);
const feedback = reactive({ text: "", type: "success" });

const headers = [
  { title: "Domaine PBX", key: "pbx_domain" },
  { title: "Connecteur", key: "connector_name" },
  { title: "Files d'attente supervisées", key: "queue_ids", sortable: false },
  { title: "", key: "actions", sortable: false, align: "end" },
];

const dialog = ref(false);
const editing = ref(null);
const saving = ref(false);
const formError = ref("");
const form = reactive({ queue_ids: [] });

async function fetchBindings() {
  loading.value = true;
  try {
    const { data } = await apiClient.get("/telephony/settings");
    bindings.value = Array.isArray(data) ? data : [];
  } catch (err) {
    feedback.type = "error";
    feedback.text =
      err?.response?.data?.error ||
      "Impossible de charger la configuration téléphonie.";
  } finally {
    loading.value = false;
  }
}

function openEdit(binding) {
  editing.value = binding;
  form.queue_ids = [...(binding.queue_ids || [])];
  formError.value = "";
  dialog.value = true;
}

async function save() {
  if (!editing.value) return;
  saving.value = true;
  formError.value = "";
  try {
    const { data } = await apiClient.put(
      `/telephony/settings/${editing.value.id}/queues`,
      {
        queue_ids: form.queue_ids,
      },
    );
    const idx = bindings.value.findIndex((b) => b.id === editing.value.id);
    if (idx !== -1) bindings.value[idx] = { ...bindings.value[idx], ...data };
    dialog.value = false;
    feedback.type = "success";
    feedback.text = "Files d'attente mises à jour.";
  } catch (err) {
    formError.value = err?.response?.data?.error || "Une erreur est survenue.";
  } finally {
    saving.value = false;
  }
}

onMounted(fetchBindings);
</script>

<style scoped>
.tel-card {
  font-family: "Fira Sans", sans-serif;
}
.tel-head {
  padding: 16px 20px;
}
.tel-title {
  font-size: 15px;
  font-weight: 700;
  color: #000b23;
  margin: 0;
}
.tel-sub {
  font-size: 12.5px;
  color: #6b7280;
  margin: 2px 0 0;
  max-width: 640px;
  line-height: 1.5;
}
.tel-muted {
  font-size: 12px;
  color: #9aa0aa;
}
.tel-dlg-title {
  font-size: 15px;
  font-weight: 700;
  color: #000b23;
}

.tel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 20px;
  text-align: center;
}
.tel-empty__text {
  font-size: 12.5px;
  color: #6b7280;
  max-width: 420px;
  margin: 0;
}
</style>
