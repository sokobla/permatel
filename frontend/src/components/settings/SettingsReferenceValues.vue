<template>
  <v-card variant="flat" class="srv-card" rounded="lg" border>
    <div class="srv-head">
      <div>
        <h2 class="srv-title">Valeurs de référence</h2>
        <p class="srv-sub">Gérez les listes de valeurs utilisées dans les formulaires métier.</p>
      </div>
    </div>

    <v-divider />

    <div class="srv-body">
      <!-- Sélecteur de famille -->
      <v-tabs
        v-model="activeFamily"
        color="#00a8a8"
        density="comfortable"
        show-arrows
        class="srv-tabs"
      >
        <v-tab v-for="f in FAMILIES" :key="f.key" :value="f.key" class="text-none">
          <v-icon size="15" start>{{ f.icon }}</v-icon>
          {{ f.label }}
        </v-tab>
      </v-tabs>

      <v-window v-model="activeFamily" class="srv-window">
        <v-window-item v-for="f in FAMILIES" :key="f.key" :value="f.key">
          <ReferenceValueList
            :title="f.label"
            :items="state[f.key].items"
            :loading="state[f.key].loading"
            :saving="state[f.key].saving"
            :show-discriminant="f.key === 'nature_anomalie'"
            @create="(label) => onCreate(f.key, label)"
            @update="({ item, label }) => onUpdate(f.key, item, { label })"
            @toggle="(item) => onUpdate(f.key, item, { active: !item.active })"
            @discriminant="(item) => onUpdate(f.key, item, { is_discriminant: !item.is_discriminant })"
            @delete="(item) => onDelete(f.key, item)"
          />
        </v-window-item>
      </v-window>
    </div>

    <v-snackbar v-model="snack.show" :color="snack.color" timeout="2500" location="bottom right">
      {{ snack.text }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { reactive, ref, watch, onMounted } from "vue";
import ReferenceValueList from "@/components/settings/ReferenceValueList.vue";
import { settingsService } from "@/services/settingsService";

const FAMILIES = [
  { key: "nature_anomalie",     label: "Catégories d'anomalie", icon: "mdi-alert-outline" },
  { key: "statut_demande",      label: "Statuts de demande",    icon: "mdi-flag-outline" },
  { key: "moyens_acces",        label: "Moyens d'accès",        icon: "mdi-key-outline" },
  { key: "risques_specifiques", label: "Risques spécifiques",   icon: "mdi-shield-alert-outline" },
  { key: "besoins_agents",      label: "Besoins agent",         icon: "mdi-account-check-outline" },
  { key: "type_mission",        label: "Types de mission",      icon: "mdi-briefcase-outline" },
  { key: "qualification_agent", label: "Qualifications Agent",  icon: "mdi-shield-star-outline" },
];

const activeFamily = ref(FAMILIES[0].key);
const state = reactive(
  Object.fromEntries(FAMILIES.map((f) => [f.key, { items: [], loading: false, saving: false, loaded: false }])),
);
const snack = reactive({ show: false, text: "", color: "#00a8a8" });

function notify(text, color = "#00a8a8") {
  snack.text = text; snack.color = color; snack.show = true;
}

async function loadFamily(key) {
  const s = state[key];
  if (s.loaded) return;
  s.loading = true;
  try {
    s.items = await settingsService.getReferenceValues(key);
    s.loaded = true;
  } catch {
    notify("Échec du chargement.", "#e74c3c");
  } finally {
    s.loading = false;
  }
}

async function onCreate(key, label) {
  const s = state[key];
  s.saving = true;
  try {
    const created = await settingsService.createReferenceValue(key, label);
    s.items = [...s.items, created];
    notify("Valeur ajoutée.");
  } catch {
    notify("Échec de l'ajout.", "#e74c3c");
  } finally {
    s.saving = false;
  }
}

async function onUpdate(key, item, patch) {
  const s = state[key];
  s.saving = true;
  try {
    const updated = await settingsService.updateReferenceValue(key, item.id, patch);
    s.items = s.items.map((v) => (v.id === item.id ? updated : v));
    notify("Valeur mise à jour.");
  } catch {
    notify("Échec de la mise à jour.", "#e74c3c");
  } finally {
    s.saving = false;
  }
}

async function onDelete(key, item) {
  const s = state[key];
  s.saving = true;
  try {
    await settingsService.deleteReferenceValue(key, item.id);
    s.items = s.items.filter((v) => v.id !== item.id);
    notify("Valeur supprimée.");
  } catch {
    notify("Échec de la suppression.", "#e74c3c");
  } finally {
    s.saving = false;
  }
}

watch(activeFamily, (k) => loadFamily(k));
onMounted(() => loadFamily(activeFamily.value));
</script>

<style scoped>
.srv-card { font-family: "Fira Sans", sans-serif; }
.srv-head { padding: 16px 20px; }
.srv-title { font-size: 15px; font-weight: 700; color: #000b23; margin: 0; }
.srv-sub { font-size: 12.5px; color: #6b7280; margin: 2px 0 0; }
.srv-body { padding: 8px 20px 20px; }
.srv-tabs { margin-bottom: 16px; border-bottom: 1px solid #e5e7eb; }
.srv-window { padding-top: 4px; }
</style>
