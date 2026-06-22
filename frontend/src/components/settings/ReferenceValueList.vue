<template>
  <div class="rvl">
    <header class="rvl-head">
      <div>
        <h3 class="rvl-title">{{ title }}</h3>
        <span class="rvl-count">{{ items.length }} valeur(s)</span>
      </div>
      <v-btn color="#00a8a8" variant="flat" size="small" class="text-none" prepend-icon="mdi-plus" @click="openCreate">
        Ajouter
      </v-btn>
    </header>

    <!-- Loader -->
    <div v-if="loading" class="rvl-state">
      <v-progress-circular indeterminate size="22" color="#00a8a8" />
      <span>Chargement…</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="items.length === 0" class="rvl-state rvl-state--empty">
      <v-icon size="30" color="#d0d4da">mdi-tag-off-outline</v-icon>
      <span>Aucune valeur. Ajoutez-en une pour démarrer.</span>
    </div>

    <!-- Liste -->
    <v-table v-else density="comfortable" class="rvl-table">
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td class="rvl-td-label">
            <span :class="{ 'rvl-inactive': !item.active }">{{ item.label }}</span>
          </td>
          <td class="rvl-td-status">
            <v-chip size="x-small" :color="item.active ? '#22c55e' : '#9aa0aa'" variant="tonal">
              {{ item.active ? "Actif" : "Inactif" }}
            </v-chip>
          </td>
          <td class="rvl-td-actions">
            <v-btn
              v-if="showDiscriminant"
              :icon="item.is_discriminant ? 'mdi-alert' : 'mdi-alert-outline'"
              :color="item.is_discriminant ? '#e74c3c' : '#9aa0aa'"
              variant="text" size="x-small"
              :title="item.is_discriminant ? 'Discriminante — impacte Incidents agent & score' : 'Non discriminante — cliquer pour marquer discriminante'"
              @click="emit('discriminant', item)"
            />
            <v-btn icon="mdi-pencil-outline" variant="text" size="x-small" title="Modifier" @click="openEdit(item)" />
            <v-btn
              :icon="item.active ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
              variant="text" size="x-small"
              :title="item.active ? 'Désactiver' : 'Activer'"
              @click="emit('toggle', item)"
            />
            <v-btn icon="mdi-trash-can-outline" variant="text" size="x-small" color="#e74c3c" title="Supprimer" @click="askDelete(item)" />
          </td>
        </tr>
      </tbody>
    </v-table>

    <!-- Dialog création / édition -->
    <v-dialog v-model="editOpen" max-width="420">
      <v-card rounded="lg">
        <v-card-title class="rvl-dlg-title">
          {{ editing ? "Modifier la valeur" : "Nouvelle valeur" }}
        </v-card-title>
        <v-divider />
        <v-card-text>
          <v-form ref="formRef" @submit.prevent="confirm">
            <label class="rvl-label">Libellé <span class="rvl-req">*</span></label>
            <v-text-field
              v-model="draft"
              variant="outlined"
              density="comfortable"
              autofocus
              :rules="[rules.required]"
              hide-details="auto"
              @keyup.enter="confirm"
            />
          </v-form>
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-btn variant="text" class="text-none" :disabled="saving" @click="editOpen = false">Annuler</v-btn>
          <v-spacer />
          <v-btn color="#00a8a8" variant="flat" class="text-none" :loading="saving" @click="confirm">
            Enregistrer
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Confirmation suppression -->
    <v-dialog v-model="deleteOpen" max-width="400">
      <v-card rounded="lg">
        <v-card-title class="rvl-dlg-title">Supprimer la valeur</v-card-title>
        <v-divider />
        <v-card-text class="rvl-dlg-text">
          Confirmer la suppression de
          <strong>« {{ target?.label }} »</strong> ? Cette action est définitive.
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-btn variant="text" class="text-none" :disabled="saving" @click="deleteOpen = false">Annuler</v-btn>
          <v-spacer />
          <v-btn color="#e74c3c" variant="flat" class="text-none" :loading="saving" @click="confirmDelete">
            Supprimer
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
  title: { type: String, required: true },
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  // Affiche le bouton « discriminante » (famille nature_anomalie uniquement)
  showDiscriminant: { type: Boolean, default: false },
});
const emit = defineEmits(["create", "update", "delete", "toggle", "discriminant"]);

const editOpen = ref(false);
const editing = ref(null); // item en cours d'édition ou null (création)
const draft = ref("");
const formRef = ref(null);

const deleteOpen = ref(false);
const target = ref(null);

const rules = { required: (v) => (!!v && v.trim().length > 0) || "Champ requis." };

function openCreate() {
  editing.value = null;
  draft.value = "";
  editOpen.value = true;
}
function openEdit(item) {
  editing.value = item;
  draft.value = item.label;
  editOpen.value = true;
}
async function confirm() {
  const { valid } = await formRef.value.validate();
  if (!valid) return;
  if (editing.value) {
    emit("update", { item: editing.value, label: draft.value.trim() });
  } else {
    emit("create", draft.value.trim());
  }
  editOpen.value = false;
}
function askDelete(item) {
  target.value = item;
  deleteOpen.value = true;
}
function confirmDelete() {
  emit("delete", target.value);
  deleteOpen.value = false;
}
</script>

<style scoped>
.rvl { font-family: "Fira Sans", sans-serif; }
.rvl-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.rvl-title { font-size: 14px; font-weight: 700; color: #000b23; margin: 0; }
.rvl-count { font-size: 11px; color: #6b7280; }

.rvl-state {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 32px 16px; color: #9aa0aa; font-size: 13px;
}
.rvl-state--empty { color: #9aa0aa; }

.rvl-table { border: 1px solid #e5e7eb; border-radius: 8px; }
.rvl-td-label { font-size: 13px; }
.rvl-inactive { color: #9aa0aa; text-decoration: line-through; }
.rvl-td-status { width: 90px; }
.rvl-td-actions { width: 180px; text-align: right; white-space: nowrap; }

.rvl-dlg-title { font-size: 15px; font-weight: 700; color: #000b23; }
.rvl-dlg-text { font-size: 13px; color: #374151; }
.rvl-label { display: block; font-size: 12px; font-weight: 600; color: #15223a; margin-bottom: 4px; }
.rvl-req { color: #e74c3c; }
</style>
