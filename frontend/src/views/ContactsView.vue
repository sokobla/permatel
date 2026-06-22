<template>
  <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
  <!-- ║  PERMATEL OPS — GESTION DES CONTACTS                               ║ -->
  <!-- ║  Vue CRUD standardisée                                             ║ -->
  <!-- ║  Respecte strictement DESIGN.md — The Digital Architect            ║ -->
  <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->
  <div class="crud-view-container">
    <div class="ops-body">
      <!-- ────────────────────────────────────────────────────────────────────
           ZONE CENTRALE — tableau des contacts
           ──────────────────────────────────────────────────────────────────── -->
      <main class="ops-main">
        <!-- En-tête section -->
        <div class="section-hdr">
          <div class="section-hdr__left">
            <h1 class="section-title">GESTION DES CONTACTS</h1>
            <div class="section-subtitle">
              SYSTEM_CONTACT_SERVICE&nbsp;/&nbsp;CONTACT_POOL_ALPHA
            </div>
          </div>
          <div class="section-hdr__right">
            <button class="btn-add" @click="openCreatePanel">
              <v-icon size="13" color="white" style="margin-right: 6px"
                >mdi-plus</v-icon
              >
              AJOUTER UN CONTACT
            </button>
          </div>
        </div>

        <!-- Barre de contrôle -->
        <div class="controls-bar">
          <!-- Recherche Globale -->
          <div class="cb-search">
            <v-icon size="13" color="#999">mdi-magnify</v-icon>
            <input
              v-model="filters.search"
              class="cb-search__input"
              placeholder="RECHERCHER NOM, PRÉNOM, VILLE, TÉL..."
              @input="onSearchInput"
            />
            <button
              v-if="filters.search"
              class="cb-search__clear"
              @click="
                filters.search = '';
                loadContacts();
              "
            >
              <v-icon size="12" color="#bbb">mdi-close</v-icon>
            </button>
          </div>

          <!-- Filtre Client -->
          <div class="cb-filter">
            <label class="cb-filter__label">CLIENT</label>
            <select
              v-model="filters.client_id"
              class="cb-filter__select"
              @change="goToPage(1)"
            >
              <option value="">TOUS</option>
              <option v-for="c in clientsList" :key="c.id" :value="c.id">
                {{ c.nom }}
              </option>
            </select>
          </div>

          <!-- Filtre Prestataire -->
          <div class="cb-filter">
            <label class="cb-filter__label">PRESTATAIRE</label>
            <select
              v-model="filters.prestataire_id"
              class="cb-filter__select"
              @change="goToPage(1)"
            >
              <option value="">TOUS</option>
              <option v-for="p in prestatairesList" :key="p.id" :value="p.id">
                {{ p.nom }}
              </option>
            </select>
          </div>

          <div class="cb-filter">
            <label class="cb-filter__label">STATUT</label>
            <select
              v-model="filters.status"
              class="cb-filter__select"
              @change="goToPage(1)"
            >
              <option value="">TOUS</option>
              <option value="true">ACTIF</option>
              <option value="false">INACTIF</option>
            </select>
          </div>

          <div class="cb-spacer"></div>

          <!-- Compteur total -->
          <div class="cb-meta">
            <span class="cb-meta__count">{{ loading ? "—" : totalItems }}</span>
            <span class="cb-meta__label">CONTACTS</span>
          </div>

          <!-- Bouton refresh -->
          <button
            class="cb-refresh"
            :class="{ 'cb-refresh--spinning': loading }"
            @click="loadContacts"
          >
            <v-icon size="14" color="#555">mdi-refresh</v-icon>
          </button>
        </div>

        <!-- Alerte erreur liste -->
        <div v-if="listError" class="list-error">
          <v-icon size="14" color="#E74C3C">mdi-alert-circle-outline</v-icon>
          {{ listError }}
          <button class="list-error__retry" @click="loadContacts">
            RÉESSAYER
          </button>
        </div>

        <!-- Wrapper tableau -->
        <div class="table-wrapper">
          <div v-if="loading" class="table-loader">
            <div class="table-loader__bar"></div>
          </div>

          <v-data-table-server
            v-model:page="page"
            v-model:items-per-page="itemsPerPage"
            :headers="headers"
            :items="contacts"
            :items-length="totalItems"
            :loading="loading"
            density="compact"
            class="users-table"
            item-value="id"
            hide-default-footer
            @update:options="loadContacts"
          >
            <!-- Colonne Contact (Avatar + Nom/Prénom) -->
            <template v-slot:[`item.contact`]="{ item }">
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
                    :style="{ background: userAvatarColor(item.nom) }"
                  >
                    {{ getInitials(item.nom, item.prenom) }}
                  </div>
                </div>
                <div class="user-cell__info">
                  <span class="mono-text user-cell__handle"
                    >{{ item.nom }} {{ item.prenom }}</span
                  >
                  <span v-if="item.ville" class="user-cell__seen">{{
                    item.ville
                  }}</span>
                </div>
              </div>
            </template>

            <!-- Colonne Email -->
            <template v-slot:[`item.email`]="{ item }">
              <span class="mono-text cell-email">{{ item.email || "—" }}</span>
            </template>

            <!-- Colonne Téléphone -->
            <template v-slot:[`item.telephone`]="{ item }">
              <span class="mono-text">{{ item.telephone || "—" }}</span>
            </template>

            <!-- Colonne Type -->
            <template v-slot:[`item.type`]="{ item }">
              <span class="role-badge">{{ item.type || "—" }}</span>
            </template>

            <!-- Colonne Fonction -->
            <template v-slot:[`item.fonction`]="{ item }">
              <span class="mono-tag">{{ item.fonction || "—" }}</span>
            </template>

            <!-- Colonne Liens -->
            <template v-slot:[`item.liens`]="{ item }">
              <div
                v-if="
                  item.type === 'Client' && item.clients && item.clients.length
                "
              >
                <span
                  class="tenant-badge"
                  v-for="c in item.clients"
                  :key="c.id"
                  style="margin-right: 4px"
                  >{{ c.nom }}</span
                >
              </div>
              <div v-else-if="item.type === 'Prestataire' && item.prestataire">
                <span class="tenant-badge">{{ item.prestataire.nom }}</span>
              </div>
              <span v-else class="tenant-badge">—</span>
            </template>

            <!-- Actions -->
            <template v-slot:[`item.actions`]="{ item }">
              <div class="actions-cell">
                <button
                  class="act-btn act-btn--edit"
                  title="Modifier"
                  :disabled="item.type === 'Agent de sécurité'"
                  @click="openEditPanel(item)"
                >
                  <v-icon size="13">mdi-pencil-outline</v-icon>
                </button>
                <button
                  v-if="canDelete"
                  class="act-btn act-btn--delete"
                  title="Supprimer"
                  :disabled="item.type === 'Agent de sécurité'"
                  @click="deleteContact(item)"
                >
                  <v-icon size="13">mdi-delete-outline</v-icon>
                </button>
                <button
                  class="act-btn act-btn--anomalie"
                  title="Suivi des anomalies"
                  @click="router.push(`/issues?contact_id=${item.id}`)"
                >
                  <v-icon size="13">mdi-alert-circle-outline</v-icon>
                </button>
                <button
                  v-if="item.type !== 'Agent de sécurité'"
                  class="act-btn act-btn--commande"
                  title="Suivi des commandes"
                  @click="router.push(`/orders?contact_id=${item.id}`)"
                >
                  <v-icon size="13">mdi-package-variant-outline</v-icon>
                </button>
              </div>
            </template>

            <!-- Empty state -->
            <template v-slot:no-data>
              <div class="table-empty">
                <v-icon size="36" color="#ddd"
                  >mdi-card-account-mail-outline</v-icon
                >
                <p class="table-empty__text">AUCUN CONTACT TROUVÉ</p>
                <p class="table-empty__sub">
                  Modifiez les filtres ou créez un contact
                </p>
              </div>
            </template>
          </v-data-table-server>

          <!-- Pagination -->
          <div class="table-pagination">
            <span class="pag-info">
              PAGE&nbsp;<span class="mono-text">{{ page }}</span
              >&nbsp;/&nbsp;<span class="mono-text">{{ totalPages }}</span>
              &nbsp;—&nbsp;<span class="mono-text">{{ totalItems }}</span
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

      <!-- ────────────────────────────────────────────────────────────────────
           PANNEAU DROIT — CRÉATION / MODIFICATION CONTACT
           ──────────────────────────────────────────────────────────────────── -->
      <aside :class="['ops-panel', { 'ops-panel--open': panelOpen }]">
        <!-- Header panneau -->
        <div class="panel-hdr">
          <div class="panel-hdr__content">
            <div class="panel-title">
              {{
                panelMode === "edit"
                  ? "MODIFIER LE CONTACT"
                  : "AJOUTER UN CONTACT"
              }}
            </div>
            <div class="panel-subtitle">
              CONTACT_CREATION_PRTCL&nbsp;//&nbsp;VER_2.4
            </div>
          </div>
          <button class="panel-close" @click="closePanel" title="Fermer">
            <v-icon size="16" color="rgba(255,255,255,0.5)">mdi-close</v-icon>
          </button>
        </div>

        <!-- Corps panneau scrollable -->
        <div class="panel-body">
          <!-- Upload avatar -->
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
              accept="image/png,image/jpeg,image/webp"
              hidden
              @change="onAvatarFileChange"
            />
            <template v-if="!avatarPreview">
              <v-icon size="28" color="#bbb">mdi-camera-plus-outline</v-icon>
              <span class="avatar-upload__label">UPLOAD AVATAR</span>
              <span class="avatar-upload__hint">PNG / JPG — 2 MB MAX</span>
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

          <!-- Formulaire -->
          <form class="create-form" @submit.prevent="submitForm" novalidate>
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
                <label class="form-label"
                  >PRÉNOM <span class="form-req">*</span></label
                >
                <input
                  v-model="form.prenom"
                  class="form-input"
                  :class="{ 'form-input--err': formErrors.prenom }"
                  placeholder="JEAN"
                />
                <span v-if="formErrors.prenom" class="form-errmsg">{{
                  formErrors.prenom
                }}</span>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">ADRESSE</label>
              <input
                v-model="form.adresse"
                class="form-input"
                placeholder="123 AVENUE DES CHAMPS"
              />
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">VILLE</label>
                <input
                  v-model="form.ville"
                  class="form-input"
                  placeholder="PARIS"
                />
              </div>
              <div class="form-group">
                <label class="form-label">TÉLÉPHONE</label>
                <input
                  v-model="form.telephone"
                  class="form-input mono-text"
                  placeholder="+33 1 23 45 67 89"
                />
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">EMAIL</label>
                <input
                  v-model="form.email"
                  type="email"
                  class="form-input mono-text"
                  placeholder="jean@domain.com"
                />
                <span v-if="formErrors.email" class="form-errmsg">{{
                  formErrors.email
                }}</span>
              </div>
              <div class="form-group">
                <label class="form-label">FONCTION</label>
                <input
                  v-model="form.fonction"
                  class="form-input"
                  placeholder="DIRECTEUR OPÉRATIONNEL"
                />
              </div>
            </div>

            <div class="form-sep">
              <span>RÔLE ET LIAISONS</span>
            </div>

            <div class="form-group">
              <label class="form-label"
                >TYPE DE CONTACT <span class="form-req">*</span></label
              >
              <div class="select-wrapper">
                <select
                  v-model="form.type"
                  class="form-input form-select"
                  :class="{ 'form-input--err': formErrors.type }"
                >
                  <option value="">— SÉLECTIONNER —</option>
                  <option v-for="t in formTypeOptions" :key="t" :value="t">
                    {{ t }}
                  </option>
                </select>
                <v-icon size="13" color="#888" class="select-caret"
                  >mdi-chevron-down</v-icon
                >
              </div>
              <span v-if="formErrors.type" class="form-errmsg">{{
                formErrors.type
              }}</span>
            </div>

            <!-- Champs Prestataire (Conditionnel) -->
            <div class="form-group" v-if="form.type === 'Prestataire'">
              <label class="form-label"
                >PRESTATAIRE LIÉ <span class="form-req">*</span></label
              >
              <div class="select-wrapper">
                <select
                  v-model="form.prestataire_id"
                  class="form-input form-select"
                  :class="{ 'form-input--err': formErrors.prestataire_id }"
                >
                  <option :value="null">— PRESTATAIRE —</option>
                  <option
                    v-for="p in prestatairesList"
                    :key="p.id"
                    :value="p.id"
                  >
                    {{ p.nom }}
                  </option>
                </select>
                <v-icon size="13" color="#888" class="select-caret"
                  >mdi-chevron-down</v-icon
                >
              </div>
              <span v-if="formErrors.prestataire_id" class="form-errmsg">{{
                formErrors.prestataire_id
              }}</span>
            </div>

            <!-- Champs Client & Sites (Conditionnel) -->
            <template v-if="form.type === 'Client'">
              <div class="form-group">
                <label class="form-label"
                  >CLIENT(S) LIÉ(S) <span class="form-req">*</span></label
                >
                <select
                  v-model="form.client_ids"
                  multiple
                  class="form-input form-select"
                  :class="{ 'form-input--err': formErrors.client_ids }"
                  style="height: 100px"
                >
                  <option v-for="c in clientsList" :key="c.id" :value="c.id">
                    {{ c.nom }}
                  </option>
                </select>
                <span v-if="formErrors.client_ids" class="form-errmsg">{{
                  formErrors.client_ids
                }}</span>
              </div>

              <div class="form-group" v-if="filteredSitesList.length > 0">
                <label class="form-label">SITE(S) LIÉ(S) (OPTIONNEL)</label>
                <select
                  v-model="form.site_ids"
                  multiple
                  class="form-input form-select"
                  style="height: 100px"
                >
                  <option
                    v-for="s in filteredSitesList"
                    :key="s.id"
                    :value="s.id"
                  >
                    {{ s.nom }}
                  </option>
                </select>
              </div>
            </template>

            <!-- Feedbacks Formulaire -->
            <div
              v-if="submissionError"
              class="form-feedback form-feedback--error"
            >
              <v-icon size="13" color="#E74C3C"
                >mdi-alert-circle-outline</v-icon
              >
              {{ submissionError }}
            </div>
            <div
              v-if="submissionSuccess"
              class="form-feedback form-feedback--success"
            >
              <v-icon size="13" color="#00A8A8"
                >mdi-check-circle-outline</v-icon
              >
              {{ successMessage }}
            </div>

            <!-- Boutons actions -->
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
              <template v-else>
                <v-icon size="14" color="white" style="margin-right: 8px"
                  >mdi-check-bold</v-icon
                >
                {{
                  panelMode === "edit"
                    ? "ENREGISTRER LES MODIFICATIONS"
                    : "VALIDER LE CONTACT"
                }}
              </template>
            </button>

            <button
              type="button"
              v-if="panelMode === 'edit'"
              class="btn-reset"
              @click="resetFormState"
            >
              RÉINITIALISER
            </button>
          </form>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import apiClient from "@/services/http/axios";
import { useAuthStore } from "@/store/auth";
import "@/assets/styles/crud-view.css";

// ─── CONFIGURATION & CONSTANTES ───────────────────────────────────────────────
const route = useRoute();
const router = useRouter();

// RBAC : seuls ADMIN/MANAGER peuvent supprimer
const authStore = useAuthStore();
const canDelete = computed(() => authStore.canDelete);

const headers = [
  {
    title: "CONTACT",
    key: "contact",
    align: "start",
    sortable: true,
    width: "250px",
  },
  { title: "EMAIL", key: "email", align: "start", sortable: true },
  {
    title: "TÉLÉPHONE",
    key: "telephone",
    align: "start",
    sortable: false,
    width: "140px",
  },
  {
    title: "TYPE",
    key: "type",
    align: "start",
    sortable: true,
    width: "120px",
  },
  {
    title: "FONCTION",
    key: "fonction",
    align: "start",
    sortable: false,
    width: "180px",
  },
  {
    title: "LIENS (CL/PR)",
    key: "liens",
    align: "start",
    sortable: false,
    width: "200px",
  },
  {
    title: "ACTIONS",
    key: "actions",
    align: "center",
    sortable: false,
    width: "130px",
  },
];

// ─── ÉTAT DU TABLEAU ──────────────────────────────────────────────────────────
const contacts = ref([]);
const loading = ref(false);
const totalItems = ref(0);
const page = ref(1);
const itemsPerPage = ref(10);
const listError = ref("");

// ─── FILTRES & PAGINATION ─────────────────────────────────────────────────────
const filters = reactive({
  search: "",
  client_id: "",
  prestataire_id: "",
  site_id: "",
  status: "",
});

const totalPages = computed(
  () => Math.ceil(totalItems.value / itemsPerPage.value) || 1,
);
const visiblePages = computed(() => {
  let pages = [];
  for (let i = 1; i <= totalPages.value; i++) pages.push(i);
  return pages;
});
const goToPage = (p) => {
  page.value = p;
};

let searchTimeout = null;
const onSearchInput = () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    page.value = 1;
  }, 500);
};

// ─── ÉTAT DU PANNEAU (FORMULAIRE) ─────────────────────────────────────────────
const panelOpen = ref(false);
const panelMode = ref("create"); // 'create' | 'edit'
const selectedContact = ref(null);
const submissionLoading = ref(false);
const submissionError = ref("");
const submissionSuccess = ref(false);

const successMessage = computed(() => {
  return panelMode.value === "create"
    ? "Contact créé avec succès."
    : "Contact mis à jour.";
});

const formTypeOptions = ["Tenant", "Client", "Prestataire"]; // Agent exclu
const prestatairesList = ref([]);
const clientsList = ref([]);
const allSitesList = ref([]);

const form = reactive({
  nom: "",
  prenom: "",
  adresse: "",
  ville: "",
  telephone: "",
  email: "",
  type: "Tenant",
  fonction: "",
  prestataire_id: null,
  client_ids: [],
  site_ids: [],
});

const formErrors = reactive({
  nom: "",
  prenom: "",
  type: "",
  prestataire_id: "",
  client_ids: "",
  email: "",
});

// ─── AVATAR UPLOAD ────────────────────────────────────────────────────────────
const avatarInputRef = ref(null);
const avatarFile = ref(null);
const avatarPreview = ref(null);
const dragging = ref(false);
const avatarRemoved = ref(false);

function triggerAvatarInput() {
  avatarInputRef.value?.click();
}
function onAvatarFileChange(e) {
  const file = e.target.files?.[0];
  if (file) applyAvatarFile(file);
}
function onAvatarDrop(e) {
  dragging.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (file && file.type.startsWith("image/")) applyAvatarFile(file);
}
function applyAvatarFile(file) {
  if (file.size > 2 * 1024 * 1024) return;
  avatarFile.value = file;
  avatarRemoved.value = false;
  const reader = new FileReader();
  reader.onload = (e) => {
    avatarPreview.value = e.target.result;
  };
  reader.readAsDataURL(file);
}
function removeAvatar() {
  avatarFile.value = null;
  avatarPreview.value = null;
  if (avatarInputRef.value) avatarInputRef.value.value = "";
  avatarRemoved.value = true;
}

// ─── APPELS API ───────────────────────────────────────────────────────────────
const loadContacts = async () => {
  listError.value = "";
  loading.value = true;
  try {
    const params = {
      page: page.value,
      per_page: itemsPerPage.value,
      search: filters.search || undefined,
      client_id: filters.client_id || undefined,
      prestataire_id: filters.prestataire_id || undefined,
      site_id: filters.site_id || undefined,
      status: filters.status || undefined,
    };

    const { data } = await apiClient.get(`/contacts`, { params });
    contacts.value = data.contacts || [];
    totalItems.value = data.total || 0;
  } catch (error) {
    listError.value = "Impossible de charger les contacts.";
  } finally {
    loading.value = false;
  }
};

const loadRelatedEntities = async () => {
  try {
    const [clients, prestataires, sites] = await Promise.all([
      apiClient
        .get("/clients?per_page=100")
        .then((r) => r.data)
        .catch(() => ({ clients: [] })),
      apiClient
        .get("/prestataires?per_page=100")
        .then((r) => r.data)
        .catch(() => ({ prestataires: [] })),
      apiClient
        .get("/sites?per_page=100")
        .then((r) => r.data)
        .catch(() => ({ sites: [] })),
    ]);
    clientsList.value = clients.clients || [];
    prestatairesList.value = prestataires.prestataires || [];
    allSitesList.value = sites.sites || [];
  } catch (error) {
    console.error("Erreur chargement entités liées", error);
  }
};

// ─── LOGIQUE FORMULAIRE ───────────────────────────────────────────────────────
const filteredSitesList = computed(() => {
  if (!form.client_ids || form.client_ids.length === 0) return [];
  return allSitesList.value.filter((site) =>
    form.client_ids.includes(site.client_id),
  );
});

watch(
  () => form.client_ids,
  (newVal) => {
    if (!newVal || newVal.length === 0) {
      form.site_ids = [];
    } else {
      form.site_ids = form.site_ids.filter((siteId) => {
        const site = allSitesList.value.find((s) => s.id === siteId);
        return site && newVal.includes(site.client_id);
      });
    }
  },
);

const resetFormState = () => {
  form.nom = "";
  form.prenom = "";
  form.adresse = "";
  form.ville = "";
  form.telephone = "";
  form.email = "";
  form.fonction = "";
  form.type = "Tenant";
  form.prestataire_id = null;
  form.client_ids = [];
  form.site_ids = [];
  Object.keys(formErrors).forEach((k) => (formErrors[k] = ""));
  avatarFile.value = null;
  avatarPreview.value = null;
  avatarRemoved.value = false;
  if (avatarInputRef.value) avatarInputRef.value.value = "";
  submissionError.value = "";
  submissionSuccess.value = false;
};

const openCreatePanel = () => {
  resetFormState();
  panelMode.value = "create";
  selectedContact.value = null;
  panelOpen.value = true;
};

const openEditPanel = (item) => {
  resetFormState();
  panelMode.value = "edit";
  selectedContact.value = item;
  form.nom = item.nom || "";
  form.prenom = item.prenom || "";
  form.adresse = item.adresse || "";
  form.ville = item.ville || "";
  form.telephone = item.telephone || "";
  form.email = item.email || "";
  form.type = item.type || "Tenant";
  form.fonction = item.fonction || "";
  form.prestataire_id = item.prestataire_id || null;
  form.client_ids = item.clients ? item.clients.map((c) => c.id) : [];
  form.site_ids = item.sites ? item.sites.map((s) => s.id) : [];
  if (item.avatar_url) avatarPreview.value = getAvatarFullUrl(item.avatar_url);
  panelOpen.value = true;
};

const closePanel = () => {
  panelOpen.value = false;
};

const validateForm = () => {
  let isValid = true;
  Object.keys(formErrors).forEach((k) => (formErrors[k] = ""));

  if (!form.nom.trim()) {
    formErrors.nom = "Requis";
    isValid = false;
  }
  if (!form.prenom.trim()) {
    formErrors.prenom = "Requis";
    isValid = false;
  }
  if (!form.type) {
    formErrors.type = "Requis";
    isValid = false;
  }

  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    formErrors.email = "Format invalide";
    isValid = false;
  }

  if (form.type === "Prestataire" && !form.prestataire_id) {
    formErrors.prestataire_id = "Requis";
    isValid = false;
  }
  if (
    form.type === "Client" &&
    (!form.client_ids || form.client_ids.length === 0)
  ) {
    formErrors.client_ids = "Au moins un client requis";
    isValid = false;
  }

  return isValid;
};

const submitForm = async () => {
  if (!validateForm()) return;
  submissionLoading.value = true;
  submissionError.value = "";
  submissionSuccess.value = false;

  try {
    // Préparation multipart (pour l'avatar potentiel)
    const payload = new FormData();
    const data = {
      nom: form.nom,
      prenom: form.prenom,
      adresse: form.adresse,
      ville: form.ville,
      telephone: form.telephone,
      email: form.email,
      type: form.type,
      fonction: form.fonction,
    };
    if (form.type === "Prestataire") data.prestataire_id = form.prestataire_id;
    if (form.type === "Client") {
      data.client_ids = form.client_ids;
      data.site_ids = form.site_ids;
    }

    // Gestion effacement avatar à l'édition
    if (
      panelMode.value === "edit" &&
      avatarRemoved.value &&
      !avatarFile.value
    ) {
      data.avatar_url = null;
    }

    payload.append("data", JSON.stringify(data));
    if (avatarFile.value) payload.append("avatar", avatarFile.value);

    if (panelMode.value === "create") {
      await apiClient.post("/contacts", payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    } else {
      await apiClient.put(`/contacts/${selectedContact.value.id}`, payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    }

    submissionSuccess.value = true;
    loadContacts();
    setTimeout(() => {
      closePanel();
    }, 1800);
  } catch (error) {
    submissionError.value =
      error.response?.data?.error || "Erreur de sauvegarde.";
  } finally {
    submissionLoading.value = false;
  }
};

const deleteContact = async (item) => {
  if (item.type === "Agent de sécurité") return;
  if (
    !confirm(
      "Voulez-vous vraiment supprimer le contact " +
        item.nom +
        " " +
        item.prenom +
        " ?",
    )
  ) {
    return;
  }

  try {
    await apiClient.delete(`/contacts/${item.id}`);
    loadContacts();
  } catch (error) {
    listError.value =
      error.response?.data?.error ||
      "Erreur lors de la suppression du contact.";
  }
};

// ─── HELPERS AFFICHAGE ────────────────────────────────────────────────────────
function getInitials(nom, prenom) {
  return (
    `${(prenom || "").charAt(0)}${(nom || "").charAt(0)}`.toUpperCase() || "CT"
  );
}
function userAvatarColor(nom) {
  let hash = 0;
  const str = nom || "Contact";
  for (let i = 0; i < str.length; i++)
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  return `hsl(${hash % 360}, 50%, 45%)`;
}
function getAvatarFullUrl(relativeUrl) {
  if (!relativeUrl) return "";
  try {
    const backendUrl = new URL(apiClient.defaults.baseURL);
    return `${backendUrl.protocol}//${backendUrl.host}${relativeUrl}`;
  } catch {
    return relativeUrl;
  }
}

// ─── INITIALISATION ───────────────────────────────────────────────────────────
watch(
  () => route.query,
  (newQuery) => {
    filters.search = newQuery.search || "";
    filters.client_id = newQuery.client_id || "";
    filters.prestataire_id = newQuery.prestataire_id || "";
    filters.site_id = newQuery.site_id || "";
    filters.status = newQuery.status || "";

    page.value = newQuery.page ? Number(newQuery.page) : 1;
    itemsPerPage.value = newQuery.per_page ? Number(newQuery.per_page) : 10;

    loadContacts();
  },
  { immediate: true },
);

watch(
  [
    () => filters.search,
    () => filters.client_id,
    () => filters.prestataire_id,
    () => filters.site_id,
    () => filters.status,
    page,
    itemsPerPage,
  ],
  ([
    newSearch,
    newClientId,
    newPrestataireId,
    newSiteId,
    newStatus,
    newPage,
    newPerPage,
  ]) => {
    const query = {};
    if (newSearch) query.search = newSearch;
    if (newClientId) query.client_id = newClientId;
    if (newPrestataireId) query.prestataire_id = newPrestataireId;
    if (newSiteId) query.site_id = newSiteId;
    if (newStatus) query.status = newStatus;
    if (newPage > 1) query.page = newPage;
    if (newPerPage !== 10) query.per_page = newPerPage;
    router.replace({ query }).catch(() => {});
  },
);

onMounted(() => {
  loadRelatedEntities();
});
</script>

<style scoped>
@import "@/assets/styles/crud-view.css";

</style>
