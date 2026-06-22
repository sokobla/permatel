<template>
  <div class="crud-view-container">
    <div class="ops-body">
      <main class="ops-main">
        <!-- En-tête section -->
        <div class="section-hdr">
          <div class="section-hdr__left">
            <h1 class="section-title">GESTION DES PRESTATAIRES</h1>
            <div class="section-subtitle">
              PARTNER_RELATIONSHIP_MODULE&nbsp;/&nbsp;PROVIDER_POOL
            </div>
          </div>
          <div class="section-hdr__right">
            <button class="btn-add" @click="handleOpenCreatePanel">
              <v-icon size="13" color="white" style="margin-right: 6px"
                >mdi-plus</v-icon
              >
              AJOUTER UN PRESTATAIRE
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
              placeholder="RECHERCHER NOM, CODE..."
              @input="onSearchInput"
            />
          </div>
          <div class="cb-filter">
            <label class="cb-filter__label">STATUT</label>
            <select
              v-model="statusFilter"
              class="cb-filter__select"
              @change="loadPartners"
            >
              <option value="">TOUS</option>
              <option value="active">ACTIF</option>
              <option value="inactive">INACTIF</option>
            </select>
          </div>
          <div class="cb-spacer"></div>
          <div class="cb-meta">
            <span class="cb-meta__count">{{
              loading ? "—" : totalPartners
            }}</span>
            <span class="cb-meta__label">PRESTATAIRES</span>
          </div>
          <button
            class="cb-refresh"
            :class="{ 'cb-refresh--spinning': loading }"
            @click="loadPartners"
          >
            <v-icon size="14" color="#555">mdi-refresh</v-icon>
          </button>
        </div>

        <!-- Alerte erreur liste -->
        <div v-if="listError" class="list-error">
          <v-icon size="14" color="#E74C3C">mdi-alert-circle-outline</v-icon>
          {{ listError }}
          <button class="list-error__retry" @click="loadPartners">
            RÉESSAYER
          </button>
        </div>

        <!-- Tableau -->
        <div class="table-wrapper">
          <div v-if="loading" class="table-loader">
            <div class="table-loader__bar"></div>
          </div>
          <v-data-table-server
            v-model:page="page"
            v-model:items-per-page="itemsPerPage"
            :headers="tableHeaders"
            :items="partners"
            :items-length="totalPartners"
            :loading="loading"
            density="compact"
            class="users-table"
            item-value="id"
            hide-default-footer
            @update:options="onTableOptions"
          >
            <!-- Colonnes personnalisées -->
            <template v-slot:[`item.nom`]="{ item }">
              <div class="user-cell">
                <div class="user-cell__avatar">
                  <img
                    v-if="item.logo_url"
                    :src="getLogoFullUrl(item.logo_url)"
                    alt="logo"
                    class="user-cell__avatar-img"
                  />
                  <div
                    v-else
                    class="user-cell__avatar-initials"
                    :style="{ background: partnerAvatarColor(item.nom) }"
                  >
                    {{ getInitials(item.nom) }}
                  </div>
                </div>
                <div class="user-cell__info">
                  <span class="mono-text user-cell__handle">{{
                    item.nom
                  }}</span>
                  <span v-if="item.code" class="user-cell__seen"
                    >#{{ item.code }}</span
                  >
                </div>
              </div>
            </template>

            <template v-slot:[`item.adresse`]="{ item }">
              <span class="cell-email">{{ item.adresse || "—" }}</span>
            </template>

            <template v-slot:[`item.ville`]="{ item }">
              <span>{{ item.ville || "—" }}</span>
            </template>

            <template v-slot:[`item.telephone`]="{ item }">
              <span class="mono-text">{{ item.telephone || "—" }}</span>
            </template>

            <template v-slot:[`item.email`]="{ item }">
              <span class="mono-text cell-email">{{ item.email || "—" }}</span>
            </template>

            <template v-slot:[`item.is_active`]="{ item }">
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

            <template v-slot:[`item.actions`]="{ item }">
              <div class="actions-cell">
                <button
                  class="act-btn act-btn--edit"
                  title="Modifier"
                  @click="onEditPartner(item)"
                >
                  <v-icon size="13">mdi-pencil-outline</v-icon>
                </button>
                <button
                  class="act-btn"
                  title="Gérer les contacts"
                  @click="manageContacts(item)"
                >
                  <v-icon size="13">mdi-account-group</v-icon>
                </button>
                <button
                  class="act-btn act-btn--delete"
                  title="Désactiver"
                  @click="onDeletePartner(item)"
                >
                  <v-icon size="13">mdi-delete-outline</v-icon>
                </button>
              </div>
            </template>

            <template v-slot:no-data>
              <div class="table-empty">
                <v-icon size="36" color="#ddd">mdi-handshake-outline</v-icon>
                <p class="table-empty__text">AUCUN PRESTATAIRE TROUVÉ</p>
                <p class="table-empty__sub">
                  Modifiez les filtres ou créez un nouveau prestataire
                </p>
              </div>
            </template>
          </v-data-table-server>
          <!-- Pagination (copiée de UsersView) -->
          <div class="table-pagination">
            <span class="pag-info">
              PAGE&nbsp;<span class="mono-text">{{ page }}</span
              >&nbsp;/&nbsp;<span class="mono-text">{{ totalPages }}</span>
              &nbsp;—&nbsp;<span class="mono-text">{{ totalPartners }}</span
              >&nbsp;ENTRÉE(S)
            </span>

            <div class="pag-controls">
              <button
                class="pag-btn"
                :disabled="page <= 1"
                @click="goToPage(1)"
                title="Première page"
              >
                <v-icon size="13">mdi-page-first</v-icon>
              </button>
              <button
                class="pag-btn"
                :disabled="page <= 1"
                @click="goToPage(page - 1)"
              >
                <v-icon size="13">mdi-chevron-left</v-icon>
              </button>
              <button
                v-for="p in visiblePages"
                :key="p"
                :class="['pag-btn', { 'pag-btn--active': p === page }]"
                @click="goToPage(p)"
              >
                {{ p }}
              </button>
              <button
                class="pag-btn"
                :disabled="page >= totalPages"
                @click="goToPage(page + 1)"
              >
                <v-icon size="13">mdi-chevron-right</v-icon>
              </button>
              <button
                class="pag-btn"
                :disabled="page >= totalPages"
                @click="goToPage(totalPages)"
                title="Dernière page"
              >
                <v-icon size="13">mdi-page-last</v-icon>
              </button>
            </div>
            <div class="pag-perpage">
              <label class="pag-perpage__label">PAR PAGE</label>
              <select
                v-model="itemsPerPage"
                class="pag-perpage__select"
                @change="goToPage(1)"
              >
                <option :value="10">10</option>
                <option :value="25">25</option>
                <option :value="50">50</option>
                <option :value="100">100</option>
              </select>
            </div>
          </div>
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
          <!-- Upload Logo -->
          <div class="avatar-upload" @click="triggerLogoInput">
            <input
              ref="logoInputRef"
              type="file"
              accept="image/png,image/jpeg,image/svg+xml,image/webp"
              hidden
              @change="onLogoFileChange"
            />
            <template v-if="!logoPreview">
              <v-icon size="28" color="#bbb">mdi-image-plus</v-icon>
              <span class="avatar-upload__label">UPLOAD LOGO</span>
              <span class="avatar-upload__hint">PNG/JPG/SVG/WEBP</span>
            </template>
            <template v-else>
              <img
                :src="logoPreview"
                alt="logo preview"
                class="avatar-upload__img"
              />
              <button
                class="avatar-upload__remove"
                @click.stop="removeLogo"
                title="Supprimer"
              >
                <v-icon size="12" color="white">mdi-close</v-icon>
              </button>
            </template>
          </div>

          <!-- Formulaire -->
          <form class="create-form" @submit.prevent="submitForm" novalidate>
            <div class="form-group">
              <label class="form-label"
                >RAISON SOCIALE <span class="form-req">*</span></label
              >
              <input
                v-model="form.nom"
                class="form-input"
                :class="{ 'form-input--err': formErrors.nom }"
                placeholder="Nom de l'entreprise"
              />
              <span v-if="formErrors.nom" class="form-errmsg">{{
                formErrors.nom
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
            <div class="form-group">
              <label class="form-label">EMAIL</label>
              <input
                v-model="form.email"
                type="email"
                class="form-input"
                :class="{ 'form-input--err': formErrors.email }"
                placeholder="contact@entreprise.com"
              />
              <span v-if="formErrors.email" class="form-errmsg">{{
                formErrors.email
              }}</span>
            </div>
            <div class="form-group">
              <label class="form-label">STATUT</label>
              <div class="select-wrapper">
                <select v-model="form.is_active" class="form-input form-select">
                  <option :value="true">ACTIF</option>
                  <option :value="false">INACTIF</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">CONTACT PRINCIPAL</label>
              <div
                class="select-wrapper"
                :class="{ 'is-loading': contactsLoading }"
              >
                <select
                  v-model="form.contact_principal"
                  class="form-input form-select"
                  :disabled="contactsLoading"
                >
                  <option value="">
                    {{ contactsLoading ? "CHARGEMENT..." : "— SÉLECTIONNER —" }}
                  </option>
                  <optgroup
                    v-for="(liste, groupType) in contactOptionsGrouped"
                    :key="groupType"
                    :label="groupType"
                  >
                    <option v-for="c in liste" :key="c.id" :value="`${c.nom} ${c.prenom}`">
                      {{ c.nom }} {{ c.prenom }}{{ c.fonction ? ' - ' + c.fonction : '' }}
                    </option>
                  </optgroup>
                </select>
                <v-icon size="13" color="#888" class="select-caret"
                  >mdi-chevron-down</v-icon
                >
              </div>
            </div>

            <!-- Feedback -->
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

            <!-- Bouton submit -->
            <button
              type="button"
              class="btn-submit"
              :disabled="submissionLoading"
              @click="submitForm"
            >
              <template v-if="submissionLoading">
                <span class="btn-submit__spinner"></span>
                VALIDATION...
              </template>
              <template v-else>{{ submitButtonText }}</template>
            </button>
          </form>
        </div>
      </aside>
    </div>

    <!-- Dialog Confirmation Suppression -->
    <div v-if="deleteTarget" class="confirm-overlay">
      <div class="confirm-dialog">
        <div class="confirm-dialog__icon">
          <v-icon size="28" color="#E74C3C">mdi-alert-circle-outline</v-icon>
        </div>
        <div class="confirm-dialog__title">DÉSACTIVER LE PRESTATAIRE</div>
        <div class="confirm-dialog__msg">
          Confirmer la désactivation de&nbsp;<span class="mono-text">{{
            deleteTarget.nom
          }}</span
          >&nbsp;?
          <br />
          <span class="confirm-dialog__warn"
            >Les agents associés seront aussi désactivés.</span
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
            <template v-if="deleteInProgress">
              <span class="btn-submit__spinner"></span>
              DÉSACTIVATION...
            </template>
            <template v-else>CONFIRMER</template>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { usePartners } from "@/composables/usePartners";
import apiClient from "@/services/http/axios";

const router = useRouter();

// --- Composable ---
const {
  partners,
  totalPartners,
  loading,
  page,
  itemsPerPage,
  searchQuery,
  statusFilter,
  loadPartners,
  totalPages,
  visiblePages,
  goToPage,
  onSearchInput,
  onTableOptions,
  createPartner,
  updatePartner,
  deactivatePartner,
  resetSubmissionState,
  init,
  submissionLoading,
  submissionError,
  listError, // Assuming this will be added to the composable
  submissionSuccess,
} = usePartners();

// --- Constantes ---
const tableHeaders = [
  { title: "RAISON SOCIALE", key: "nom", sortable: true },
  { title: "ADRESSE", key: "adresse", sortable: false },
  { title: "VILLE", key: "ville", sortable: false },
  { title: "TÉLÉPHONE", key: "telephone", sortable: false },
  { title: "EMAIL", key: "email", sortable: false },
  { title: "STATUT", key: "is_active", sortable: true },
  { title: "ACTIONS", key: "actions", sortable: false, align: "center" },
];

// --- Panneau latéral ---
const panelOpen = ref(false);
const panelMode = ref("create"); // 'create' ou 'edit'
const selectedPartner = ref(null);

const panelTitle = computed(() =>
  panelMode.value === "edit"
    ? "MODIFIER LE PRESTATAIRE"
    : "AJOUTER UN PRESTATAIRE",
);
const submitButtonText = computed(() =>
  panelMode.value === "edit" ? "ENREGISTRER" : "VALIDER",
);
const successMessage = computed(() =>
  panelMode.value === "create"
    ? "Prestataire créé avec succès."
    : "Prestataire mis à jour avec succès.",
);

// --- Formulaire ---
const form = reactive({
  id: null,
  nom: "",
  adresse: "",
  ville: "",
  telephone: "",
  email: "",
  contact_principal: "",
  is_active: true,
});
const formErrors = reactive({});
const logoFile = ref(null);
const logoPreview = ref(null);
const logoInputRef = ref(null);

function resetForm() {
  Object.assign(form, {
    id: null,
    nom: "",
    adresse: "",
    ville: "",
    telephone: "",
    email: "",
    contact_principal: "",
    is_active: true,
  });
  Object.keys(formErrors).forEach((k) => (formErrors[k] = ""));
  logoFile.value = null;
  logoPreview.value = null;
  resetSubmissionState();
}

function handleOpenCreatePanel() {
  resetForm();
  panelMode.value = "create";
  panelOpen.value = true;
}

function onEditPartner(partner) {
  resetForm();
  panelMode.value = "edit";
  selectedPartner.value = partner;
  Object.assign(form, { ...partner });
  if (!form.contact_principal) form.contact_principal = "";
  if (partner.logo_url) {
    logoPreview.value = getLogoFullUrl(partner.logo_url);
  }
  panelOpen.value = true;
}

function closePanel() {
  panelOpen.value = false;
}

// --- Logo ---
function triggerLogoInput() {
  logoInputRef.value?.click();
}
function onLogoFileChange(event) {
  const file = event.target.files?.[0];
  if (file) {
    logoFile.value = file;
    logoPreview.value = URL.createObjectURL(file);
  }
}
function removeLogo() {
  logoFile.value = null;
  logoPreview.value = null;
  if (logoInputRef.value) logoInputRef.value.value = "";
  // Pour la mise à jour, il faut un signal pour dire au backend de supprimer le logo
  if (panelMode.value === "edit") {
    form.logo_url = null;
  }
}

// --- Contacts ---
const contactOptionsGrouped = ref({});
const contactsLoading = ref(false);

async function loadContacts() {
  contactsLoading.value = true;
  try {
    const response = await apiClient.get("/contacts", { params: { per_page: 1000 } });
    const contactsList = response.data.contacts || [];
    const filteredGroups = {};
    for (const c of contactsList) {
      const type = c.type || "Autre";
      if (!filteredGroups[type]) filteredGroups[type] = [];
      filteredGroups[type].push(c);
    }
    contactOptionsGrouped.value = filteredGroups;
  } catch (err) {
    console.error("Erreur lors du chargement des contacts:", err);
  } finally {
    contactsLoading.value = false;
  }
}

// --- Validation & Soumission ---
function validateForm() {
  Object.keys(formErrors).forEach((k) => (formErrors[k] = ""));
  let isValid = true;
  if (!form.nom) {
    formErrors.nom = "La raison sociale est requise.";
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
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    formErrors.email = "Format d'email invalide.";
    isValid = false;
  }
  return isValid;
}

async function submitForm() {
  if (!validateForm()) return;

  const formData = new FormData();
  const dataToSubmit = { ...form };
  // En mode édition, si le logo n'a pas changé, on n'envoie pas l'URL
  if (panelMode.value === "edit" && logoPreview.value && !logoFile.value) {
    delete dataToSubmit.logo_url;
  }

  formData.append("data", JSON.stringify(dataToSubmit));

  if (logoFile.value) {
    formData.append("logo", logoFile.value);
  }

  let success;
  if (panelMode.value === "create") {
    success = await createPartner(formData);
  } else {
    success = await updatePartner(form.id, formData);
  }

  if (success) {
    setTimeout(() => closePanel(), 1800);
  }
}

// --- Suppression ---
const deleteTarget = ref(null);
const deleteInProgress = ref(false);
function onDeletePartner(partner) {
  deleteTarget.value = partner;
}
async function executeDelete() {
  if (!deleteTarget.value) return;
  deleteInProgress.value = true;
  const success = await deactivatePartner(deleteTarget.value.id);
  deleteInProgress.value = false;
  if (success) {
    deleteTarget.value = null;
  }
}

// --- Helpers ---
function getInitials(name) {
  return (name || "").substring(0, 2).toUpperCase();
}
function partnerAvatarColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const h = hash % 360;
  return `hsl(${h}, 40%, 45%)`;
}
function getLogoFullUrl(relativeUrl) {
  if (!relativeUrl) return "";
  try {
    const backendUrl = new URL(apiClient.defaults.baseURL);
    return `${backendUrl.protocol}//${backendUrl.host}${relativeUrl}`;
  } catch (e) {
    return relativeUrl;
  }
}

function manageContacts(partner) {
  router.push({ path: "/contacts", query: { prestataire_id: partner.id } });
}

// --- Cycle de vie ---
onMounted(() => {
  init();
  loadContacts();
});
</script>

<style>
@import "@/assets/styles/crud-view.css";
</style>
