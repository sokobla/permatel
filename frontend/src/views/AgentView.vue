<template>
  <div class="agents-view-container">
    <div class="ops-body">
      <main class="ops-main">
        <!-- En-tête section -->
        <div class="section-hdr">
          <div class="section-hdr__left">
            <h1 class="section-title">GESTION DES AGENTS</h1>
            <div class="section-subtitle">
              SECURITY_STAFF_MODULE&nbsp;/&nbsp;AGENT_POOL
            </div>
          </div>
          <div class="section-hdr__right">
            <button class="btn-add" @click="openCreatePanel">
              <v-icon size="13" color="white" style="margin-right: 6px"
                >mdi-plus</v-icon
              >
              AJOUTER UN AGENT
            </button>
          </div>
        </div>

        <!-- Barre de contrôle -->
        <div class="controls-bar">
          <div class="cb-search">
            <v-icon size="13" color="#999">mdi-magnify</v-icon>
            <input
              v-model="searchQuery"
              class="cb-search__input"
              placeholder="RECHERCHER NOM, PRÉNOM..."
              @input="onSearchInput"
            />
          </div>
          <div class="cb-filter">
            <label class="cb-filter__label">TYPE</label>
            <select
              v-model="typeFilter"
              class="cb-filter__select"
              @change="loadAgents"
            >
              <option value="">TOUS</option>
              <option v-for="t in agentTypes" :key="t" :value="t">
                {{ t.toUpperCase() }}
              </option>
            </select>
          </div>
          <div class="cb-filter">
            <label class="cb-filter__label">STATUT</label>
            <select
              v-model="statusFilter"
              class="cb-filter__select"
              @change="loadAgents"
            >
              <option value="">TOUS</option>
              <option value="true">ACTIF</option>
              <option value="false">INACTIF</option>
            </select>
          </div>
          <div class="cb-spacer"></div>
          <div class="cb-meta">
            <span class="cb-meta__count">{{
              loading ? "—" : totalAgents
            }}</span>
            <span class="cb-meta__label">AGENTS</span>
          </div>
          <button
            class="cb-refresh"
            :class="{ 'cb-refresh--spinning': loading }"
            @click="loadAgents"
          >
            <v-icon size="14" color="#555">mdi-refresh</v-icon>
          </button>
        </div>

        <!-- Tableau -->
        <div class="table-wrapper">
          <div v-if="loading" class="table-loader">
            <div class="table-loader__bar"></div>
          </div>
          <v-data-table-server
            :headers="headers"
            :items="agents"
            :items-length="totalAgents"
            :loading="loading"
            :items-per-page="itemsPerPage"
            density="compact"
            class="users-table"
            item-value="id"
            hide-default-footer
            @update:options="onTableOptions"
          >
            <template #[`item.nom`]="{ item }">
              <div class="user-cell">
                <div class="user-cell__avatar">
                  <img
                    v-if="item.avatar_url"
                    :src="getAvatarFullUrl(item.avatar_url)"
                    alt="avatar"
                    class="user-cell__avatar-img"
                  />
                  <div
                    v-else
                    class="user-cell__avatar-initials"
                    :style="{ background: avatarColor(item.nom) }"
                  >
                    {{ getInitials(item.nom) }}
                  </div>
                </div>
                <div class="user-cell__info">
                  <span
                    class="user-cell__handle"
                    style="font-family: &quot;Fira Sans, sans-serif&quot;"
                    >{{ item.nom }} {{ item.prenom }}</span
                  >
                </div>
              </div>
            </template>

            <template #[`item.contact`]="{ item }">
              <div v-if="item.telephone" class="d-flex align-center">
                <v-icon start size="x-small">mdi-phone-outline</v-icon>
                <span class="mono-text">{{ item.telephone }}</span>
              </div>
              <div v-if="item.email" class="d-flex align-center mt-1">
                <v-icon start size="x-small">mdi-email-outline</v-icon>
                <span class="mono-text cell-email">{{ item.email }}</span>
              </div>
            </template>

            <template #[`item.type_agent`]="{ item }">
              <span class="role-badge">{{
                item.type_agent || item.qualification || "—"
              }}</span>
            </template>

            <template #[`item.motorise`]="{ item }">
              <span
                v-if="
                  item.motorise === true ||
                  item.motorise === 'true' ||
                  item.motorise === 1
                "
                ><v-icon icon="mdi-car-side" color="green"></v-icon
              ></span>
              <span v-else class="tenant-badge"></span>
            </template>
            <template #[`item.prestataire`]="{ item }">
              <span v-if="item.prestataire_id !== ''" class="role-badge">{{
                item.prestataire_nom
              }}</span>
              <span v-else class="tenant-badge">INTERNE</span>
            </template>

            <template #[`item.is_active`]="{ item }">
              <span
                :class="[
                  'status-badge',
                  item.is_active
                    ? 'status-badge--active'
                    : 'status-badge--inactive',
                ]"
              >
                <span class="status-badge__dot"></span>
                {{ item.is_active ? "ACTIF" : "INACTIF" }}
              </span>
            </template>

            <template #[`item.actions`]="{ item }">
              <div class="actions-cell">
                <button
                  class="act-btn act-btn--edit"
                  title="Modifier"
                  @click="openEditPanel(item)"
                >
                  <v-icon size="13">mdi-pencil-outline</v-icon>
                </button>
                <button
                  class="act-btn act-btn--delete"
                  title="Supprimer"
                  @click="confirmDelete(item)"
                >
                  <v-icon size="13">mdi-delete-outline</v-icon>
                </button>
              </div>
            </template>

            <template v-slot:no-data>
              <div class="table-empty">
                <p class="table-empty__text">AUCUN AGENT TROUVÉ</p>
              </div>
            </template>
          </v-data-table-server>
        </div>
      </main>

      <!-- Panneau latéral -->
      <aside :class="['ops-panel', { 'ops-panel--open': panelOpen }]">
        <div class="panel-hdr">
          <div class="panel-hdr__content">
            <div class="panel-title">{{ panelTitle }}</div>
          </div>
          <button class="panel-close" @click="closePanel" title="Fermer">
            <v-icon size="16" color="rgba(255,255,255,0.5)">mdi-close</v-icon>
          </button>
        </div>
        <div class="panel-body">
          <!-- KPI de l'agent (édition uniquement) -->
          <div v-if="panelMode === 'edit'" class="agent-kpi-block">
            <AgentKpiCards :kpis="agentKpis" :loading="kpisLoading" />
          </div>

          <div
            class="avatar-upload"
            :class="{ 'avatar-upload--drag': dragging }"
            @click="triggerAvatarInput"
            @dragover.prevent="dragging = true"
            @dragleave.prevent="dragging = false"
            @drop.prevent="onAvatarDrop"
          >
            <input
              ref="avatarInputRef"
              type="file"
              accept="image/*"
              hidden
              @change="onAvatarFileChange"
            />
            <template v-if="!avatarPreview">
              <v-icon size="28" color="#bbb">mdi-camera-plus-outline</v-icon>
              <span class="avatar-upload__label">UPLOAD AVATAR</span>
              <span class="avatar-upload__hint">PNG/JPG - 2MB MAX</span>
            </template>
            <template v-else>
              <img
                :src="avatarPreview"
                alt="avatar preview"
                class="avatar-upload__img"
              />
              <button
                class="avatar-upload__remove"
                @click.stop="removeAvatar"
                title="Supprimer"
              >
                <v-icon size="12" color="white">mdi-close</v-icon>
              </button>
            </template>
          </div>
          <span
            v-if="formErrors.avatar"
            class="form-errmsg"
            style="
              display: block;
              text-align: center;
              margin-top: -10px;
              margin-bottom: 10px;
            "
          >
            {{ formErrors.avatar }}
          </span>

          <form class="create-form" @submit.prevent="saveAgent" novalidate>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label"
                  >NOM <span class="form-req">*</span></label
                >
                <input
                  v-model="form.nom"
                  class="form-input"
                  :class="{ 'form-input--err': formErrors.nom }"
                  placeholder="DUPONT"
                />
                <span v-if="formErrors.nom" class="form-errmsg">{{
                  formErrors.nom
                }}</span>
              </div>
              <div class="form-group">
                <label class="form-label">PRÉNOM</label>
                <input
                  v-model="form.prenom"
                  class="form-input"
                  placeholder="JEAN"
                />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label"
                >MATRICULE <span class="form-req">*</span></label
              >
              <input
                v-model="form.matricule"
                class="form-input"
                :class="{ 'form-input--err': formErrors.matricule }"
                placeholder="AGENT007"
              />
              <span v-if="formErrors.matricule" class="form-errmsg">{{
                formErrors.matricule
              }}</span>
            </div>

            <div class="form-group">
              <label class="form-label"
                >ADRESSE <span class="form-req">*</span></label
              >
              <input
                v-model="form.adresse"
                class="form-input"
                :class="{ 'form-input--err': formErrors.adresse }"
                placeholder="123 Rue Exemple"
              />
              <span v-if="formErrors.adresse" class="form-errmsg">{{
                formErrors.adresse
              }}</span>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label"
                  >VILLE <span class="form-req">*</span></label
                >
                <input
                  v-model="form.ville"
                  class="form-input"
                  :class="{ 'form-input--err': formErrors.ville }"
                  placeholder="Casablanca"
                />
                <span v-if="formErrors.ville" class="form-errmsg">{{
                  formErrors.ville
                }}</span>
              </div>
              <div class="form-group">
                <label class="form-label"
                  >TÉLÉPHONE <span class="form-req">*</span></label
                >
                <input
                  v-model="form.telephone"
                  class="form-input"
                  :class="{ 'form-input--err': formErrors.telephone }"
                  placeholder="0600000000"
                />
                <span v-if="formErrors.telephone" class="form-errmsg">{{
                  formErrors.telephone
                }}</span>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">EMAIL</label>
              <input
                v-model="form.email"
                type="email"
                class="form-input"
                :class="{ 'form-input--err': formErrors.email }"
                placeholder="agent@email.com"
              />
              <span v-if="formErrors.email" class="form-errmsg">{{
                formErrors.email
              }}</span>
            </div>

            <div class="form-sep"><span>DÉTAILS OPÉRATIONNELS</span></div>

            <div class="form-group">
              <label class="form-label"
                >TYPE <span class="form-req">*</span></label
              >
              <div class="select-wrapper">
                <select
                  v-model="form.type_agent"
                  class="form-input form-select"
                  :class="{ 'form-input--err': formErrors.type_agent }"
                  :disabled="agentTypesLoading"
                >
                  <option value="">— SÉLECTIONNER —</option>
                  <option v-if="isOrphanType" :value="form.type_agent" disabled>
                    {{ form.type_agent }} (inactif / hors référentiel)
                  </option>
                  <option v-for="t in agentTypes" :key="t" :value="t">
                    {{ t }}
                  </option>
                </select>
                <v-icon size="13" color="#888" class="select-caret"
                  >mdi-chevron-down</v-icon
                >
              </div>
              <span v-if="formErrors.type_agent" class="form-errmsg">{{
                formErrors.type_agent
              }}</span>
            </div>

            <div class="form-group">
              <label class="form-label">ORIGINE (PRESTATAIRE)</label>
              <div class="select-wrapper">
                <select
                  v-model="form.prestataire_id"
                  class="form-input form-select"
                  :disabled="prestatairesLoading"
                >
                  <option :value="null">
                    {{
                      prestatairesLoading ? "CHARGEMENT..." : "Agent Interne"
                    }}
                  </option>
                  <option v-for="p in prestataires" :key="p.id" :value="p.id">
                    {{ p.nom }}
                  </option>
                </select>
                <v-icon size="13" color="#888" class="select-caret"
                  >mdi-chevron-down</v-icon
                >
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">MOTORISÉ</label>
                <div class="select-wrapper">
                  <select
                    v-model="form.motorise"
                    class="form-input form-select"
                  >
                    <option :value="true">OUI</option>
                    <option :value="false">NON</option>
                  </select>
                  <v-icon size="13" color="#888" class="select-caret"
                    >mdi-chevron-down</v-icon
                  >
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">STATUT</label>
                <div class="select-wrapper">
                  <select
                    v-model="form.is_active"
                    class="form-input form-select"
                  >
                    <option :value="true">ACTIF</option>
                    <option :value="false">INACTIF</option>
                  </select>
                  <v-icon size="13" color="#888" class="select-caret"
                    >mdi-chevron-down</v-icon
                  >
                </div>
              </div>
            </div>

            <div
              v-if="submissionError"
              class="form-feedback form-feedback--error"
            >
              {{ submissionError }}
            </div>
            <div
              v-if="submissionSuccess"
              class="form-feedback form-feedback--success"
            >
              {{ successMessage }}
            </div>

            <button
              type="submit"
              class="btn-submit"
              :disabled="submissionLoading"
            >
              <template v-if="submissionLoading">VALIDATION...</template>
              <template v-else>{{ submitButtonText }}</template>
            </button>
          </form>
        </div>
      </aside>
    </div>

    <!-- Dialog Confirmation Suppression -->
    <div v-if="deleteTarget" class="confirm-overlay">
      <div class="confirm-dialog">
        <div class="confirm-dialog__title">SUPPRIMER L'AGENT</div>
        <div class="confirm-dialog__msg">
          Confirmer la suppression de&nbsp;<span
            class="mono-text"
            style="font-weight: bold"
            >{{ deleteTarget.nom }} {{ deleteTarget.prenom }}</span
          >&nbsp;?
          <br />
          <span class="confirm-dialog__warn"
            >Cette action est irréversible.</span
          >
        </div>
        <div class="confirm-dialog__actions">
          <button
            class="confirm-btn confirm-btn--cancel"
            @click="deleteTarget = null"
          >
            ANNULER
          </button>
          <button
            class="confirm-btn confirm-btn--confirm"
            :disabled="deleteInProgress"
            @click="executeDelete"
          >
            <template v-if="deleteInProgress">SUPPRESSION...</template>
            <template v-else>CONFIRMER</template>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from "vue";
import { useAgents } from "@/composables/useAgents";
import apiClient from "@/services/http/axios";
import AgentKpiCards from "@/components/agents/AgentKpiCards.vue";
import { agentKpiService } from "@/services/agentKpiService";
import { settingsService } from "@/services/settingsService";
import "@/assets/styles/crud-view.css";

const {
  agents,
  totalAgents,
  loading,
  prestataires,
  prestatairesLoading,
  submissionLoading,
  submissionError,
  submissionSuccess,
  searchQuery,
  statusFilter,
  typeFilter,
  itemsPerPage,
  init,
  loadAgents,
  onSearchInput,
  onTableOptions,
  createAgent,
  updateAgent,
  deleteAgent,
  resetSubmissionState,
} = useAgents();

const panelOpen = ref(false);
const panelMode = ref("create");
const form = reactive({
  id: null,
  nom: "",
  prenom: "",
  matricule: "",
  adresse: "",
  ville: "",
  telephone: "",
  email: "",
  type_agent: "",
  prestataire_id: null,
  motorise: false,
  is_active: true,
});
const formErrors = reactive({ avatar: "" });
const avatarFile = ref(null);
const avatarPreview = ref(null);
const avatarInputRef = ref(null);
const avatarRemoved = ref(false);
const deleteTarget = ref(null);
const deleteInProgress = ref(false);
const dragging = ref(false);

// KPI de l'agent en cours d'édition
const agentKpis = ref(null);
const kpisLoading = ref(false);
async function loadAgentKpis(agentId) {
  agentKpis.value = null;
  kpisLoading.value = true;
  try {
    const { data } = await agentKpiService.getAgentKpis(agentId);
    agentKpis.value = data;
  } catch {
    agentKpis.value = null;
  } finally {
    kpisLoading.value = false;
  }
}

const headers = [
  { title: "AGENT", key: "nom", sortable: true, width: "30%" },
  { title: "CONTACT", key: "contact", sortable: false },
  { title: "TYPE", key: "type_agent", sortable: true },
  { title: "MOTORISÉ", key: "motorise", align: "center" },
  { title: "ORIGINE", key: "prestataire", sortable: true, align: "center" },
  { title: "STATUT", key: "is_active", sortable: true, align: "center" },
  { title: "ACTIONS", key: "actions", sortable: false, align: "center" },
];

const agentTypes = ref([]);
const agentTypesLoading = ref(false);

async function loadAgentTypes() {
  agentTypesLoading.value = true;
  try {
    const data = await settingsService.getReferenceValues("qualification_agent");
    agentTypes.value = data.filter(v => v.active).sort((a, b) => a.position - b.position).map(v => v.label);
  } catch (err) {
    console.error("Erreur chargement qualifications agent", err);
  } finally {
    agentTypesLoading.value = false;
  }
}

const isOrphanType = computed(() => {
  return form.type_agent && !agentTypes.value.includes(form.type_agent);
});

const panelTitle = computed(() =>
  panelMode.value === "edit" ? "MODIFIER L'AGENT" : "NOUVEL AGENT",
);
const submitButtonText = computed(() =>
  panelMode.value === "edit" ? "ENREGISTRER" : "VALIDER",
);
const successMessage = computed(() =>
  panelMode.value === "create"
    ? "Agent créé avec succès."
    : "Agent mis à jour avec succès.",
);

function resetForm() {
  Object.assign(form, {
    id: null,
    nom: "",
    prenom: "",
    matricule: "",
    adresse: "",
    ville: "",
    telephone: "",
    email: "",
    type_agent: "",
    prestataire_id: null,
    motorise: false,
    is_active: true,
  });
  Object.keys(formErrors).forEach((k) => (formErrors[k] = ""));
  avatarFile.value = null;
  avatarPreview.value = null;
  avatarRemoved.value = false;
  resetSubmissionState();
}

const openCreatePanel = () => {
  resetForm();
  panelMode.value = "create";
  panelOpen.value = true;
};

const openEditPanel = (agent) => {
  resetForm();
  panelMode.value = "edit";
  Object.assign(form, {
    ...agent,
    type_agent: agent.type_agent || "",
    motorise:
      agent.motorise === true ||
      agent.motorise === "true" ||
      agent.motorise === 1,
    prestataire_id: agent.prestataire?.id ?? null,
  });
  if (agent.avatar_url) {
    avatarPreview.value = getAvatarFullUrl(agent.avatar_url);
  }
  panelOpen.value = true;
  loadAgentKpis(agent.id);
};

const closePanel = () => {
  panelOpen.value = false;
};

function validateForm() {
  Object.keys(formErrors).forEach((k) => (formErrors[k] = ""));
  let isValid = true;
  if (!form.nom) {
    formErrors.nom = "Le nom est requis.";
    isValid = false;
  }
  if (!form.matricule) {
    formErrors.matricule = "Le matricule est requis.";
    isValid = false;
  }
  if (!form.adresse) {
    formErrors.adresse = "L'adresse est requise.";
    isValid = false;
  }
  if (!form.ville) {
    formErrors.ville = "La ville est requise.";
    isValid = false;
  }
  if (!form.telephone) {
    formErrors.telephone = "Le téléphone est requis.";
    isValid = false;
  }
  if (!form.type_agent) {
    formErrors.type_agent = "Le type est requis.";
    isValid = false;
  }
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    formErrors.email = "Format d'email invalide.";
    isValid = false;
  }
  return isValid;
}

async function saveAgent() {
  if (!validateForm()) return;

  let payload = { ...form };
  if (panelMode.value === "edit" && avatarRemoved.value) {
    payload.avatar_url = null;
  }

  let success = false;
  if (form.id) {
    success = await updateAgent(form.id, payload, avatarFile.value);
  } else {
    success = await createAgent(payload, avatarFile.value);
  }

  if (success) {
    setTimeout(() => closePanel(), 1800);
  }
}

function confirmDelete(agent) {
  deleteTarget.value = agent;
}

async function executeDelete() {
  if (!deleteTarget.value) return;
  deleteInProgress.value = true;
  const success = await deleteAgent(deleteTarget.value.id);
  deleteInProgress.value = false;
  if (success) {
    deleteTarget.value = null;
  }
}

// --- Avatar ---
function triggerAvatarInput() {
  avatarInputRef.value?.click();
}
const onAvatarDrop = (event) => {
  dragging.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file && file.type.startsWith("image/")) applyAvatarFile(file);
};
function onAvatarFileChange(event) {
  const file = event.target.files?.[0];
  if (file) applyAvatarFile(file);
}
function applyAvatarFile(file) {
  if (file.size > 2 * 1024 * 1024) {
    formErrors.avatar = "Fichier trop lourd (max 2 Mo)";
    return;
  }
  avatarFile.value = file;
  avatarRemoved.value = false;
  formErrors.avatar = "";
  const reader = new FileReader();
  reader.onload = (e) => {
    avatarPreview.value = e.target.result;
  };
  reader.readAsDataURL(file);
}
function removeAvatar() {
  avatarFile.value = null;
  avatarPreview.value = null;
  avatarRemoved.value = true;
  if (avatarInputRef.value) avatarInputRef.value.value = "";
  if (panelMode.value === "edit") {
    form.avatar_url = null;
  }
}

// --- Helpers ---
function getInitials(name) {
  return (name || "").substring(0, 2).toUpperCase();
}
function avatarColor(name) {
  let hash = 0;
  for (let i = 0; i < (name || "").length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const h = hash % 360;
  return `hsl(${h}, 40%, 45%)`;
}
function getAvatarFullUrl(relativeUrl) {
  if (!relativeUrl) return "";
  try {
    const backendUrl = new URL(apiClient.defaults.baseURL);
    return `${backendUrl.protocol}//${backendUrl.host}${relativeUrl}`;
  } catch (e) {
    return relativeUrl;
  }
}

onMounted(() => {
  init();
  loadAgentTypes();
});
</script>
