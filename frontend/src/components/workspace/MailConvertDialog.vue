<template>
  <v-dialog :model-value="modelValue" max-width="560" @update:model-value="emit('update:modelValue', $event)">
    <v-card rounded="lg" class="mcv-card">
      <v-card-title class="mcv-title">
        Traiter l'email
        <button class="mcv-close" @click="emit('update:modelValue', false)"><v-icon size="18">mdi-close</v-icon></button>
      </v-card-title>
      <v-divider />

      <v-card-text class="mcv-body">
        <v-alert
          v-if="error" type="error" variant="tonal" density="compact" border="start"
          class="mb-4" closable @click:close="error = ''"
        >{{ error }}</v-alert>

        <p class="mcv-source">
          <v-icon size="14" color="#9aa0aa">mdi-email-outline</v-icon>
          {{ email?.subject || "(sans objet)" }} — <span class="mcv-from">{{ email?.from_address }}</span>
        </p>

        <!-- Choix du mode -->
        <div class="mcv-modes">
          <button :class="['mcv-mode', { 'mcv-mode--on': mode === 'existing' }]" @click="mode = 'existing'">
            <v-icon size="16">mdi-link-variant</v-icon> Demande existante
          </button>
          <button :class="['mcv-mode', { 'mcv-mode--on': mode === 'new' }]" @click="mode = 'new'">
            <v-icon size="16">mdi-plus-circle-outline</v-icon> Nouvelle demande
          </button>
        </div>

        <!-- ── Mode : demande existante ─────────────────────────────────── -->
        <div v-if="mode === 'existing'" class="mcv-section">
          <label class="mcv-label">Sélectionner la demande</label>
          <v-autocomplete
            v-model="targetDemande"
            :items="demandeItems"
            :loading="loadingDemandes"
            item-title="label"
            return-object
            variant="outlined"
            density="comfortable"
            placeholder="Rechercher (n° ticket, intitulé)…"
            hide-details="auto"
          />
        </div>

        <!-- ── Mode : nouvelle demande ──────────────────────────────────── -->
        <div v-else class="mcv-section">
          <v-row dense>
            <v-col cols="12" sm="6">
              <label class="mcv-label">Type <span class="mcv-req">*</span></label>
              <v-select
                v-model="form.type_demande" :items="TYPES" item-title="label" item-value="value"
                variant="outlined" density="comfortable" hide-details="auto"
              />
            </v-col>
            <v-col cols="12" sm="6">
              <label class="mcv-label">Client <span class="mcv-req">*</span></label>
              <ClientCombobox @client-selected="onClient" @client-cleared="form.client_id = null" />
            </v-col>
            <v-col cols="12">
              <label class="mcv-label">Intitulé <span class="mcv-req">*</span></label>
              <v-text-field v-model="form.titre" variant="outlined" density="comfortable" hide-details="auto" />
            </v-col>
            <v-col cols="12">
              <label class="mcv-label">Description</label>
              <v-textarea v-model="form.description" variant="outlined" density="comfortable" rows="4" auto-grow hide-details="auto" />
            </v-col>
          </v-row>
        </div>
      </v-card-text>

      <v-divider />
      <v-card-actions class="mcv-actions">
        <v-btn variant="text" class="text-none" :disabled="saving" @click="emit('update:modelValue', false)">Annuler</v-btn>
        <v-spacer />
        <v-btn color="#00a8a8" variant="flat" class="text-none" :loading="saving" @click="confirm">
          {{ mode === "new" ? "Créer et rattacher" : "Rattacher" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, reactive, watch } from "vue";
import { listDemandes, createDemande } from "@/services/demandeService";
import { emailService } from "@/services/emailService";
import ClientCombobox from "@/components/workspace/ClientCombobox.vue";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  email: { type: Object, default: null },
});
const emit = defineEmits(["update:modelValue", "converted"]);

const TYPES = [
  { value: "anomalie", label: "Anomalie" },
  { value: "commande", label: "Commande" },
  { value: "planning", label: "Planning" },
  { value: "admin", label: "Administratif" },
];

const mode = ref("existing");
const saving = ref(false);
const error = ref("");

const demandeItems = ref([]);
const loadingDemandes = ref(false);
const targetDemande = ref(null);

const form = reactive({ type_demande: "anomalie", client_id: null, titre: "", description: "" });

function onClient(c) { form.client_id = c?.id ?? null; }

async function loadDemandes() {
  loadingDemandes.value = true;
  try {
    const data = await listDemandes({});
    const list = Array.isArray(data) ? data : data.items ?? [];
    demandeItems.value = list.map((d) => ({
      id: d.id,
      label: `${d.numero_ticket ?? "#" + d.id} — ${d.titre ?? ""}`,
    }));
  } catch {
    demandeItems.value = [];
  } finally {
    loadingDemandes.value = false;
  }
}

// Pré-remplissage à l'ouverture
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    error.value = "";
    mode.value = "existing";
    targetDemande.value = null;
    form.type_demande = "anomalie";
    form.client_id = null;
    form.titre = props.email?.subject || "";
    form.description = props.email?.body_text || "";
    loadDemandes();
  },
);

async function confirm() {
  error.value = "";
  saving.value = true;
  try {
    let demandeId;
    if (mode.value === "existing") {
      if (!targetDemande.value) { error.value = "Sélectionnez une demande."; return; }
      demandeId = targetDemande.value.id;
    } else {
      if (!form.client_id) { error.value = "Sélectionnez un client."; return; }
      if (!form.titre.trim()) { error.value = "L'intitulé est requis."; return; }
      const created = await createDemande({
        type_demande: form.type_demande,
        client_id: form.client_id,
        titre: form.titre.trim(),
        description: form.description || null,
        contact_id: props.email?.contact_id || null,
      });
      demandeId = created.id;
    }
    const updated = await emailService.linkDemande(props.email.id, demandeId);
    emit("converted", updated);
    emit("update:modelValue", false);
  } catch (err) {
    error.value = err?.response?.data?.error || err?.response?.data?.message || "Échec de la conversion.";
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.mcv-card { font-family: "Fira Sans", sans-serif; }
.mcv-title {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 15px; font-weight: 700; color: #000b23;
}
.mcv-close { border: none; background: none; cursor: pointer; color: #9aa0aa; display: flex; }
.mcv-body { padding: 18px 20px; }
.mcv-source { font-size: 12.5px; color: #374151; margin: 0 0 14px; display: flex; align-items: center; gap: 6px; }
.mcv-from { color: #6b7280; }
.mcv-modes { display: flex; gap: 8px; margin-bottom: 16px; }
.mcv-mode {
  flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  height: 38px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff;
  font-size: 12.5px; font-weight: 600; color: #6b7280; cursor: pointer; transition: all 0.15s;
}
.mcv-mode--on { border-color: #00a8a8; color: #007a7a; background: rgba(0, 168, 168, 0.06); }
.mcv-section { margin-top: 4px; }
.mcv-label { display: block; font-size: 12px; font-weight: 600; color: #15223a; margin: 8px 0 4px; }
.mcv-req { color: #e74c3c; }
.mcv-actions { padding: 12px 16px; }
</style>
