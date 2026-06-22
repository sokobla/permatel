<template>
  <div class="crud-view-container">
    <div class="ops-body">
      <main class="ops-main">
        <!-- En-tête section -->
        <div class="section-hdr">
          <div class="section-hdr__left">
            <h1 class="section-title">GESTION DES SITES</h1>
            <div class="section-subtitle">
              CRM_MODULE&nbsp;/&nbsp;SITES_POOL
            </div>
          </div>
          <div class="section-hdr__right">
            <button class="btn-add" @click="openCreatePanel">
              <v-icon size="13" color="white" style="margin-right: 6px"
                >mdi-plus</v-icon
              >
              AJOUTER UN SITE
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
              @change="loadSites"
            >
              <option value="">TOUS</option>
              <option value="true">ACTIF</option>
              <option value="false">INACTIF</option>
            </select>
          </div>
          <div class="cb-filter" style="margin-left: 10px">
            <label class="cb-filter__label">CLIENT</label>
            <select
              v-model="clientFilter"
              class="cb-filter__select"
              @change="loadSites"
            >
              <option value="">TOUS</option>
              <option v-for="c in clients" :key="c.id" :value="c.id">
                {{ c.nom }}
              </option>
            </select>
          </div>
          <div class="cb-spacer"></div>
          <div class="cb-meta">
            <span class="cb-meta__count">{{ loading ? "—" : totalSites }}</span>
            <span class="cb-meta__label"> SITES</span>
          </div>
          <button
            class="cb-refresh"
            :class="{ 'cb-refresh--spinning': loading }"
            @click="loadSites"
          >
            <v-icon size="14" color="#555">mdi-refresh</v-icon>
          </button>
        </div>

        <!-- Alerte erreur liste -->
        <div v-if="listError" class="list-error">
          <v-icon size="14" color="#E74C3C">mdi-alert-circle-outline</v-icon>
          {{ listError }}
          <button class="list-error__retry" @click="loadSites">
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
            :headers="headers"
            :items="sites"
            :items-length="totalSites"
            :loading="loading"
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
                    v-if="item.logo_url"
                    :src="getLogoFullUrl(item.logo_url)"
                    alt="logo"
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
                  <span class="user-cell__handle">{{ item.nom }}</span>
                  <span class="mono-text cell-email">{{ item.code_site }}</span>
                </div>
              </div>
            </template>

            <template #[`item.client`]="{ item }">
              <span>{{ item.client?.nom }}</span>
            </template>

            <template #[`item.adresse`]="{ item }">
              <span>{{ item.adresse }}</span>
            </template>

            <template #[`item.ville`]="{ item }">
              <span>{{ item.ville || "—" }}</span>
            </template>

            <template #[`item.code_postal`]="{ item }">
              <span class="mono-text">{{ item.code_postal || "—" }}</span>
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
                  class="act-btn"
                  title="Gérer les contacts"
                  @click="manageContacts(item)"
                >
                  <v-icon size="13">mdi-account-group</v-icon>
                </button>
                <button
                  class="act-btn act-btn--delete"
                  title="Désactiver"
                  @click="confirmDelete(item)"
                >
                  <v-icon size="13">mdi-delete-outline</v-icon>
                </button>
              </div>
            </template>

            <template v-slot:no-data>
              <div class="table-empty">
                <v-icon size="36" color="#ddd">mdi-domain-off</v-icon>
                <p class="table-empty__text">AUCUN SITE TROUVÉ</p>
                <p class="table-empty__sub">
                  Modifiez les filtres ou créez un nouveau site
                </p>
              </div>
            </template>
          </v-data-table-server>

          <!-- Pagination -->
          <div class="table-pagination">
            <span class="pag-info">
              PAGE&nbsp;<span class="mono-text">{{ page }}</span
              >&nbsp;/&nbsp;<span class="mono-text">{{ totalPages }}</span
              >&nbsp;—&nbsp;<span class="mono-text">{{ totalSites }}</span
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
          <div
            class="avatar-upload"
            :class="{ 'avatar-upload--drag': dragging }"
            @click="triggerLogoInput"
            @dragover.prevent="dragging = true"
            @dragleave.prevent="dragging = false"
            @drop.prevent="onLogoDrop"
          >
            <input
              ref="logoInputRef"
              type="file"
              accept="image/*"
              hidden
              @change="onLogoFileChange"
            />
            <template v-if="!logoPreview">
              <v-icon size="28" color="#bbb">mdi-camera-plus-outline</v-icon>
              <span class="avatar-upload__label">UPLOAD LOGO</span>
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
                <v-icon size="12">mdi-close</v-icon>
              </button>
            </template>
          </div>
          <span
            v-if="formErrors.logo"
            class="form-errmsg"
            style="
              display: block;
              text-align: center;
              margin-top: -10px;
              margin-bottom: 10px;
            "
          >
            {{ formErrors.logo }}
          </span>

          <form class="create-form" @submit.prevent="saveSite" novalidate>
            <div class="form-group">
              <label class="form-label"
                >CLIENT <span class="form-req">*</span></label
              >
              <div class="select-wrapper">
                <select
                  v-model="form.client_id"
                  class="form-input form-select"
                  :class="{ 'form-input--err': formErrors.client_id }"
                  :disabled="panelMode === 'edit'"
                >
                  <option :value="null">— SÉLECTIONNER —</option>
                  <option v-for="c in clients" :key="c.id" :value="c.id">
                    {{ c.nom }}
                  </option>
                </select>
                <v-icon size="13" color="#888" class="select-caret"
                  >mdi-chevron-down</v-icon
                >
              </div>
              <span v-if="formErrors.client_id" class="form-errmsg">{{
                formErrors.client_id
              }}</span>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label"
                  >NOM DU SITE <span class="form-req">*</span></label
                >
                <input
                  v-model="form.nom"
                  class="form-input"
                  :class="{ 'form-input--err': formErrors.nom }"
                />
                <span v-if="formErrors.nom" class="form-errmsg">{{
                  formErrors.nom
                }}</span>
              </div>
              <div class="form-group">
                <label class="form-label"
                  >CODE SITE <span class="form-req">*</span></label
                >
                <input
                  v-model="form.code_site"
                  class="form-input"
                  :class="{ 'form-input--err': formErrors.code_site }"
                />
                <span v-if="formErrors.code_site" class="form-errmsg">{{
                  formErrors.code_site
                }}</span>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">ADRESSE</label>
              <input v-model="form.adresse" class="form-input" />
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">VILLE</label>
                <input v-model="form.ville" class="form-input" />
              </div>
              <div class="form-group">
                <label class="form-label">CODE POSTAL</label>
                <input v-model="form.code_postal" class="form-input" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">TYPE DE SITE</label>
              <div class="select-wrapper">
                <select v-model="form.type_site" class="form-input form-select">
                  <option value="">— SÉLECTIONNER —</option>
                  <option value="bureau">Bureau / Siège social</option>
                  <option value="entrepot">Entrepôt / Logistique</option>
                  <option value="commerce">Commerce / Grande surface</option>
                  <option value="chantier">Chantier</option>
                  <option value="evenement">Site événementiel</option>
                  <option value="residentiel">Résidentiel</option>
                  <option value="industriel">Industriel</option>
                  <option value="autre">Autre</option>
                </select>
                <v-icon size="13" color="#888" class="select-caret">mdi-chevron-down</v-icon>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">TÉLÉPHONE</label>
                <input v-model="form.telephone" class="form-input" />
              </div>
              <div class="form-group">
                <label class="form-label">EMAIL</label>
                <input
                  v-model="form.email"
                  type="email"
                  class="form-input"
                  :class="{ 'form-input--err': formErrors.email }"
                />
                <span v-if="formErrors.email" class="form-errmsg">{{
                  formErrors.email
                }}</span>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">CONTACT PRINCIPAL</label>
              <div class="select-wrapper">
                <select
                  v-model="form.contact_principal_id"
                  class="form-input form-select"
                  :disabled="contactsLoading"
                >
                  <option :value="null">
                    {{ contactsLoading ? "CHARGEMENT..." : "— SÉLECTIONNER —" }}
                  </option>
                  <optgroup
                    v-for="(liste, groupType) in contactOptionsGrouped"
                    :key="groupType"
                    :label="groupType"
                  >
                    <option v-for="c in liste" :key="c.id" :value="c.id">
                      {{ c.nom }} {{ c.prenom
                      }}{{ c.fonction ? " - " + c.fonction : "" }}
                    </option>
                  </optgroup>
                </select>
                <v-icon size="13" color="#888" class="select-caret"
                  >mdi-chevron-down</v-icon
                >
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">EFFECTIF REQUIS</label>
                <input
                  v-model.number="form.effectif_requis"
                  type="number"
                  class="form-input"
                />
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

    <!-- Dialog Confirmation Soft Delete -->
    <div v-if="deleteTarget" class="confirm-overlay">
      <div class="confirm-dialog">
        <div class="confirm-dialog__icon">
          <v-icon size="28" color="#E74C3C">mdi-alert-circle-outline</v-icon>
        </div>
        <div class="confirm-dialog__title">DÉSACTIVER LE SITE</div>
        <div class="confirm-dialog__msg">
          Confirmer la désactivation de&nbsp;<span
            class="mono-text"
            style="font-weight: bold"
          >
            {{ deleteTarget.nom }} </span
          >&nbsp;?
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
import { ref, reactive, onMounted, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useSites } from "@/composables/useSites";
import apiClient from "@/services/http/axios";
import "@/assets/styles/crud-view.css";

const {
  sites,
  totalSites,
  loading,
  submissionLoading,
  submissionError,
  listError, // Assuming this will be added to the composable
  submissionSuccess,
  searchQuery,
  statusFilter,
  clientFilter,
  itemsPerPage,
  page,
  totalPages,
  loadSites,
  goToPage,
  onSearchInput,
  onTableOptions,
  createSite,
  updateSite,
  deleteSite,
  resetSubmissionState,
} = useSites();

const route = useRoute();
const router = useRouter();

const panelOpen = ref(false);
const panelMode = ref("create");
const form = reactive({
  id: null,
  client_id: null,
  nom: "",
  code_site: "",
  adresse: "",
  ville: "",
  code_postal: "",
  type_site: "",
  telephone: "",
  email: "",
  contact_principal_id: null,
  effectif_requis: null,
  latitude: null,
  longitude: null,
  is_active: true,
});
const formErrors = reactive({
  client_id: "",
  nom: "",
  code_site: "",
  email: "",
  logo: "",
});
const logoFile = ref(null);
const logoPreview = ref(null);
const logoRemoved = ref(false);
const logoInputRef = ref(null);
const deleteTarget = ref(null);
const deleteInProgress = ref(false);
const dragging = ref(false);

const clients = ref([]);
const contactOptionsGrouped = ref({});
const contactsLoading = ref(false);

const headers = [
  { title: "NOM DU SITE", key: "nom", sortable: true, width: "25%" },
  { title: "CLIENT", key: "client", sortable: false },
  { title: "ADRESSE", key: "adresse", sortable: true },
  { title: "VILLE", key: "ville", sortable: true },
  { title: "CODE POSTAL", key: "code_postal", sortable: true, width: "120px" },
  { title: "TÉLÉPHONE", key: "telephone", sortable: false },
  {
    title: "EFFECTIF",
    key: "effectif_requis",
    sortable: true,
    align: "center",
  },
  { title: "STATUT", key: "is_active", sortable: true, align: "center" },
  {
    title: "ACTIONS",
    key: "actions",
    sortable: false,
    align: "center",
    width: "100px",
  },
];

const panelTitle = computed(() =>
  panelMode.value === "edit" ? "MODIFIER LE SITE" : "NOUVEAU SITE",
);
const submitButtonText = computed(() =>
  panelMode.value === "edit" ? "ENREGISTRER" : "VALIDER",
);
const successMessage = computed(() =>
  panelMode.value === "create"
    ? "Site créé avec succès."
    : "Site mis à jour avec succès.",
);

function getLogoFullUrl(url) {
  if (!url) return "";
  try {
    const base = new URL(apiClient.defaults.baseURL);
    return `${base.protocol}//${base.host}${url}`;
  } catch (e) {
    return url;
  }
}

function resetForm() {
  Object.assign(form, {
    id: null,
    client_id: null,
    nom: "",
    code_site: "",
    adresse: "",
    ville: "",
    code_postal: "",
    type_site: "",
    telephone: "",
    email: "",
    contact_principal_id: null,
    effectif_requis: null,
    latitude: null,
    longitude: null,
    is_active: true,
  });
  Object.keys(formErrors).forEach((k) => (formErrors[k] = ""));
  logoFile.value = null;
  logoPreview.value = null;
  logoRemoved.value = false;
  resetSubmissionState();
}

const visiblePages = computed(() => {
  const total = totalPages.value || 1;
  const current = page.value || 1;
  const max = 5;
  let start = Math.max(1, current - Math.floor(max / 2));
  let end = Math.min(total, start + max - 1);
  start = Math.max(1, end - max + 1);
  const res = [];
  for (let i = start; i <= end; i++) res.push(i);
  return res;
});

const openCreatePanel = () => {
  resetForm();
  // Bonus UX: Pré-remplir le client si la vue est actuellement filtrée
  if (clientFilter.value) {
    form.client_id = parseInt(clientFilter.value, 10);
  }
  panelMode.value = "create";
  panelOpen.value = true;
};

const openEditPanel = (site) => {
  resetForm();
  panelMode.value = "edit";
  Object.assign(form, site);
  if (site.logo_url) logoPreview.value = getLogoFullUrl(site.logo_url);
  else logoPreview.value = null;
  panelOpen.value = true;
};

const closePanel = () => (panelOpen.value = false);

function validateForm() {
  Object.keys(formErrors).forEach((k) => (formErrors[k] = ""));
  let isValid = true;
  if (!form.nom) {
    formErrors.nom = "Le nom est requis.";
    isValid = false;
  }
  if (!form.code_site) {
    formErrors.code_site = "Le code est requis.";
    isValid = false;
  }
  if (!form.client_id) {
    formErrors.client_id = "Le client est requis.";
    isValid = false;
  }
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    formErrors.email = "Format d'email invalide.";
    isValid = false;
  }
  return isValid;
}

async function saveSite() {
  if (!validateForm()) return;
  let payload = { ...form };
  if (panelMode.value === "edit" && logoRemoved.value) payload.logo_url = null;
  const success = form.id
    ? await updateSite(form.id, payload, logoFile.value)
    : await createSite(payload, logoFile.value);
  if (success) setTimeout(() => closePanel(), 1800);
}

function confirmDelete(site) {
  deleteTarget.value = site;
}

async function executeDelete() {
  if (!deleteTarget.value) return;
  deleteInProgress.value = true;
  if (await deleteSite(deleteTarget.value.id)) deleteTarget.value = null;
  deleteInProgress.value = false;
}

function triggerLogoInput() {
  logoInputRef.value?.click();
}

const onLogoDrop = (event) => {
  dragging.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file && file.type.startsWith("image/")) applyLogoFile(file);
};

function onLogoFileChange(event) {
  const file = event.target.files?.[0];
  if (file) applyLogoFile(file);
}
function applyLogoFile(file) {
  if (file.size > 2 * 1024 * 1024) {
    formErrors.logo = "Fichier trop lourd (max 2 Mo)";
    return;
  }
  logoFile.value = file;
  logoRemoved.value = false;
  formErrors.logo = "";
  const reader = new FileReader();
  reader.onload = (e) => {
    logoPreview.value = e.target.result;
  };
  reader.readAsDataURL(file);
}
function removeLogo() {
  logoFile.value = null;
  logoPreview.value = null;
  logoRemoved.value = true;
  if (logoInputRef.value) logoInputRef.value.value = "";
  if (panelMode.value === "edit") form.logo_url = null;
}

function getInitials(name) {
  return (name || "").substring(0, 2).toUpperCase();
}
function avatarColor(name) {
  let hash = 0;
  for (let i = 0; i < (name || "").length; i++)
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return `hsl(${hash % 360}, 40%, 45%)`;
}

async function fetchRelatedData() {
  // Récupération des clients séparée avec un grand nombre d'items par page
  try {
    const clientsRes = await apiClient.get("/clients", {
      params: { per_page: 1000 },
    });
    clients.value = clientsRes.data.clients || [];
  } catch (error) {
    console.error("Erreur chargement clients:", error);
  }

  await loadContactsGrouped();
}

async function loadContactsGrouped() {
  contactsLoading.value = true;
  try {
    const response = await apiClient.get("/contacts", {
      params: { per_page: 1000 },
    });
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

function manageContacts(site) {
  router.push({ path: "/contacts", query: { site_id: site.id } });
}

onMounted(() => {
  // Initialisation de l'état local depuis les paramètres de l'URL
  if (route.query.client_id) clientFilter.value = route.query.client_id;
  if (route.query.status) statusFilter.value = route.query.status;
  if (route.query.search) searchQuery.value = route.query.search;
  if (route.query.page) page.value = parseInt(route.query.page, 10);
  if (route.query.per_page)
    itemsPerPage.value = parseInt(route.query.per_page, 10);

  loadSites();
  fetchRelatedData();
});

// Mise à jour dynamique de l'URL lorsque l'utilisateur modifie un filtre
watch(
  [clientFilter, statusFilter, searchQuery, page, itemsPerPage],
  ([newClient, newStatus, newSearch, newPage, newPerPage]) => {
    const query = {};
    if (newClient) query.client_id = newClient;
    if (newStatus) query.status = newStatus;
    if (newSearch) query.search = newSearch;
    if (newPage > 1) query.page = newPage;
    if (newPerPage !== 10) query.per_page = newPerPage;

    router.replace({ query }).catch(() => {});
  },
);
</script>
