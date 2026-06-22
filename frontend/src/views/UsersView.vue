<template>
  <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
  <!-- ║  PERMATEL OPS — GESTION DES UTILISATEURS                           ║ -->
  <!-- ║  Vue CRUD standardisée                                             ║ -->
  <!-- ║  Respecte strictement DESIGN.md — The Digital Architect            ║ -->
  <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->
  <div class="crud-view-container">
    <!-- ══════════════════════════════════════════════════════════════════════
         CORPS — sidebar + contenu + panneau droit
         ══════════════════════════════════════════════════════════════════════ -->
    <div class="ops-body">
      <!-- ────────────────────────────────────────────────────────────────────
           ZONE CENTRALE — tableau utilisateurs
           ──────────────────────────────────────────────────────────────────── -->
      <main class="ops-main">
        <!-- En-tête section -->
        <div class="section-hdr">
          <div class="section-hdr__left">
            <h1 class="section-title">GESTION DES UTILISATEURS</h1>
            <div class="section-subtitle">
              SYSTEM_AUTH_SERVICE&nbsp;/&nbsp;USER_POOL_ALPHA
            </div>
          </div>
          <div class="section-hdr__right">
            <button class="btn-add" @click="handleOpenCreatePanel">
              <v-icon size="13" color="white" style="margin-right: 6px"
                >mdi-plus</v-icon
              >
              AJOUTER UN UTILISATEUR
            </button>
          </div>
        </div>

        <!-- Barre de contrôle -->
        <div class="controls-bar">
          <!-- Recherche -->
          <div class="cb-search">
            <v-icon size="13" color="#999">mdi-magnify</v-icon>
            <input
              v-model="searchQuery"
              class="cb-search__input"
              placeholder="RECHERCHER ID, NOM, EMAIL..."
              @input="onSearchInput"
            />
            <button
              v-if="searchQuery"
              class="cb-search__clear"
              @click="
                searchQuery = '';
                loadUsers();
              "
            >
              <v-icon size="12" color="#bbb">mdi-close</v-icon>
            </button>
          </div>

          <!-- Filtre statut -->
          <div class="cb-filter">
            <label class="cb-filter__label">STATUT</label>
            <select
              v-model="statusFilter"
              class="cb-filter__select"
              @change="
                page = 1;
                loadUsers();
              "
            >
              <option value="">TOUS</option>
              <option value="active">ACTIF</option>
              <option value="inactive">INACTIF</option>
              <option value="suspended">SUSPENDU</option>
            </select>
          </div>

          <div class="cb-spacer"></div>

          <!-- Compteur total -->
          <div class="cb-meta">
            <span class="cb-meta__count">
              {{ loading ? "—" : totalUsers }}
            </span>
            <span class="cb-meta__label">UTILISATEURS</span>
          </div>

          <!-- Bouton refresh -->
          <button
            class="cb-refresh"
            :class="{ 'cb-refresh--spinning': loading }"
            @click="loadUsers"
          >
            <v-icon size="14" color="#555">mdi-refresh</v-icon>
          </button>
        </div>

        <!-- Alerte erreur liste -->
        <div v-if="listError" class="list-error">
          <v-icon size="14" color="#E74C3C">mdi-alert-circle-outline</v-icon>
          {{ listError }}
          <button class="list-error__retry" @click="loadUsers">
            RÉESSAYER
          </button>
        </div>

        <!-- Wrapper tableau -->
        <div class="table-wrapper">
          <!-- Loader barre -->
          <div v-if="loading" class="table-loader">
            <div class="table-loader__bar"></div>
          </div>

          <v-data-table-server
            v-model:page="page"
            v-model:items-per-page="itemsPerPage"
            :headers="tableHeaders"
            :items="users"
            :items-length="totalUsers"
            :loading="loading"
            density="compact"
            class="users-table"
            item-value="id"
            hide-default-footer
            @update:options="onTableOptions"
          >
            <!-- ── Colonne ID ── -->
            <template v-slot:[`item.id`]="{ item }">
              <span class="mono-text cell-id">#{{ item.id }}</span>
            </template>

            <!-- ── Colonne UTILISATEUR ── -->
            <template v-slot:[`item.username`]="{ item }">
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
                    :style="{ background: userAvatarColor(item.username) }"
                  >
                    {{ getInitials(item.username) }}
                  </div>
                </div>
                <div class="user-cell__info">
                  <span class="mono-text user-cell__handle"
                    >@{{ item.username }}</span
                  >
                  <span v-if="item.last_seen" class="user-cell__seen">{{
                    item.last_seen
                  }}</span>
                </div>
              </div>
            </template>

            <!-- ── Colonne EMAIL ── -->
            <template v-slot:[`item.email`]="{ item }">
              <span class="mono-text cell-email">{{ item.email }}</span>
            </template>

            <!-- ── Colonne EXTENSION ── -->
            <template v-slot:[`item.station_extension`]="{ item }">
              <span class="mono-tag">{{ item.station_extension || "—" }}</span>
            </template>

            <!-- ── Colonne RÔLE ── -->
            <template v-slot:[`item.role`]="{ item }">
              <span class="role-badge">{{ item.role }}</span>
            </template>

            <!-- ── Colonne TENANT ── -->
            <template v-slot:[`item.tenants`]="{ item }">
              <span
                v-if="item.tenants && item.tenants.length > 0"
                class="tenant-badge"
                >{{ item.tenants[0].nom }}</span
              >
              <span v-else class="tenant-badge">—</span>
            </template>

            <!-- ── Colonne STATUT ── -->
            <template v-slot:[`item.status`]="{ item }">
              <span :class="['status-badge', `status-badge--${item.status}`]">
                <span class="status-badge__dot"></span>
                {{ STATUS_LABELS[item.status] ?? item.status }}
              </span>
            </template>

            <!-- ── Colonne ACTIONS ── -->
            <template v-slot:[`item.actions`]="{ item }">
              <div class="actions-cell">
                <button
                  class="act-btn act-btn--edit"
                  title="Modifier"
                  @click="onEditUser(item)"
                >
                  <v-icon size="13">mdi-pencil-outline</v-icon>
                </button>
                <button
                  class="act-btn act-btn--key"
                  title="Réinitialiser le mot de passe"
                  @click="onResetPassword(item)"
                >
                  <v-icon size="13">mdi-key-variant</v-icon>
                </button>
                <button
                  class="act-btn act-btn--delete"
                  title="Supprimer"
                  @click="onDeleteUser(item)"
                >
                  <v-icon size="13">mdi-delete-outline</v-icon>
                </button>
              </div>
            </template>

            <!-- ── Empty state ── -->
            <template v-slot:no-data>
              <div class="table-empty">
                <v-icon size="36" color="#ddd">mdi-account-off-outline</v-icon>
                <p class="table-empty__text">AUCUN UTILISATEUR TROUVÉ</p>
                <p class="table-empty__sub">
                  Modifiez les filtres ou créez un utilisateur
                </p>
              </div>
            </template>
          </v-data-table-server>

          <!-- ── Pagination ── -->
          <div class="table-pagination">
            <span class="pag-info">
              PAGE&nbsp;<span class="mono-text">{{ page }}</span
              >&nbsp;/&nbsp;<span class="mono-text">{{ totalPages }}</span>
              &nbsp;—&nbsp;<span class="mono-text">{{ totalUsers }}</span
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
           PANNEAU DROIT — CRÉATION UTILISATEUR
           ──────────────────────────────────────────────────────────────────── -->
      <aside :class="['ops-panel', { 'ops-panel--open': panelOpen }]">
        <!-- Header panneau -->
        <div class="panel-hdr">
          <div class="panel-hdr__content">
            <div class="panel-title">{{ panelTitle }}</div>
            <div class="panel-subtitle">
              USER_CREATION_PRTCL&nbsp;//&nbsp;VER_2.4
            </div>
          </div>
          <button class="panel-close" @click="closeCreatePanel" title="Fermer">
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
              <v-icon size="28" color="#bbb">mdi-account-plus-outline</v-icon>
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
            <!-- NOM / PRÉNOM -->
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
                  :readonly="panelMode === 'reset_password'"
                  autocomplete="family-name"
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
                  :readonly="panelMode === 'reset_password'"
                  autocomplete="given-name"
                />
                <span v-if="formErrors.prenom" class="form-errmsg">{{
                  formErrors.prenom
                }}</span>
              </div>
            </div>

            <!-- EMAIL (= identifiant de connexion) -->
            <div class="form-group">
              <label class="form-label"
                >EMAIL <span class="form-req">*</span></label
              >
              <input
                v-model="form.email"
                type="email"
                class="form-input"
                :class="{ 'form-input--err': formErrors.email }"
                :readonly="panelMode === 'reset_password'"
                placeholder="jean.dupont@domain.com"
                autocomplete="email"
              />
              <span v-if="formErrors.email" class="form-errmsg">{{
                formErrors.email
              }}</span>
            </div>

            <!-- EXTENSION / RÔLE -->
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">EXTENSION</label>
                <input
                  v-model="form.station_extension"
                  class="form-input mono-text"
                  placeholder="1234"
                  :readonly="panelMode === 'reset_password'"
                  inputmode="numeric"
                />
              </div>
              <div class="form-group">
                <label class="form-label"
                  >RÔLE <span class="form-req">*</span></label
                >
                <div class="select-wrapper">
                  <select
                    v-model="form.role"
                    class="form-input form-select"
                    :class="{
                      'form-input--err': formErrors.role,
                    }"
                    :disabled="panelMode === 'reset_password' || rolesLoading"
                  >
                    <option value="">
                      {{ rolesLoading ? "CHARGEMENT..." : "— RÔLE —" }}
                    </option>
                    <option
                      v-for="r in localRoles"
                      :key="r.value"
                      :value="r.value"
                    >
                      {{ r.label }}
                    </option>
                  </select>
                  <v-icon size="13" color="#888" class="select-caret"
                    >mdi-chevron-down</v-icon
                  >
                </div>
                <span v-if="formErrors.role" class="form-errmsg">{{
                  formErrors.role
                }}</span>
              </div>
            </div>

            <!-- TENANTS (multi-affectation) -->
            <div class="form-group">
              <label class="form-label">TENANTS</label>
              <v-select
                v-model="form.tenant_ids"
                :items="tenants"
                item-title="nom"
                item-value="id"
                multiple
                chips
                closable-chips
                density="comfortable"
                variant="outlined"
                :loading="tenantsLoading"
                :disabled="panelMode === 'reset_password'"
                :error-messages="formErrors.tenant_ids ? [formErrors.tenant_ids] : []"
                placeholder="Sélectionner un ou plusieurs tenants"
                hint="Obligatoire pour un rôle non-administrateur."
                persistent-hint
              />
            </div>

            <!-- Séparateur mot de passe -->
            <div class="form-sep">
              <span>SÉCURITÉ</span>
            </div>

            <!-- MOT DE PASSE -->
            <div class="form-group">
              <label class="form-label"
                >MOT DE PASSE
                <span v-if="panelMode !== 'edit'" class="form-req"
                  >*</span
                ></label
              >
              <div class="input-eye-wrapper">
                <input
                  v-model="form.password"
                  :type="showPwd ? 'text' : 'password'"
                  class="form-input"
                  :class="{ 'form-input--err': formErrors.password }"
                  placeholder="••••••••"
                  autocomplete="new-password"
                />
                <button
                  type="button"
                  class="eye-btn"
                  @click="showPwd = !showPwd"
                  :title="showPwd ? 'Masquer' : 'Afficher'"
                >
                  <v-icon size="14" color="#888">
                    {{ showPwd ? "mdi-eye-off-outline" : "mdi-eye-outline" }}
                  </v-icon>
                </button>
              </div>
              <span v-if="formErrors.password" class="form-errmsg">{{
                formErrors.password
              }}</span>
            </div>

            <!-- CONFIRMER MOT DE PASSE -->
            <div class="form-group">
              <label class="form-label"
                >CONFIRMER MDP
                <span v-if="panelMode !== 'edit'" class="form-req"
                  >*</span
                ></label
              >
              <div class="input-eye-wrapper">
                <input
                  v-model="form.confirmPassword"
                  :type="showPwdConfirm ? 'text' : 'password'"
                  class="form-input"
                  :class="{ 'form-input--err': formErrors.confirmPassword }"
                  placeholder="••••••••"
                  autocomplete="new-password"
                />
                <button
                  type="button"
                  class="eye-btn"
                  @click="showPwdConfirm = !showPwdConfirm"
                  :title="showPwdConfirm ? 'Masquer' : 'Afficher'"
                >
                  <v-icon size="14" color="#888">
                    {{
                      showPwdConfirm ? "mdi-eye-off-outline" : "mdi-eye-outline"
                    }}
                  </v-icon>
                </button>
              </div>
              <span v-if="formErrors.confirmPassword" class="form-errmsg">{{
                formErrors.confirmPassword
              }}</span>
            </div>

            <!-- Feedback création -->
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

            <!-- Bouton submit -->
            <button
              type="button"
              class="btn-submit"
              :disabled="submissionLoading"
              @click="submitForm"
            >
              <template v-if="submissionLoading">
                <span class="btn-submit__spinner"></span>
                VALIDATION EN COURS...
              </template>
              <template v-else>
                <v-icon size="14" color="white" style="margin-right: 8px"
                  >mdi-check-bold</v-icon
                >
                {{ submitButtonText }}
              </template>
            </button>

            <!-- Reset formulaire -->
            <template v-if="panelMode === 'edit'">
              <button type="button" class="btn-reset" @click="resetForm">
                RÉINITIALISER
              </button>
            </template>
          </form>
        </div>
      </aside>
    </div>
    <!-- /ops-body -->

    <!-- ══════════════════════════════════════════════════════════════════════
         DIALOG CONFIRMATION SUPPRESSION
         ══════════════════════════════════════════════════════════════════════ -->
    <div v-if="deleteTarget" class="confirm-overlay">
      <div class="confirm-dialog">
        <div class="confirm-dialog__icon">
          <v-icon size="28" color="#E74C3C">mdi-delete-alert-outline</v-icon>
        </div>
        <div class="confirm-dialog__title">SUPPRIMER L'UTILISATEUR</div>
        <div class="confirm-dialog__msg">
          Confirmer la suppression de&nbsp;
          <span class="mono-text">@{{ deleteTarget.username }}</span
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
            <template v-if="deleteInProgress">
              <span class="btn-submit__spinner"></span>
              SUPPRESSION...
            </template>
            <template v-else> CONFIRMER </template>
          </button>
        </div>
      </div>
    </div>
  </div>
  <!-- /users-view-container -->
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { useUsers } from "@/composables/useUsers";
import apiClient from "@/services/http/axios";
import "@/assets/styles/crud-view.css";

// ─── Config & constantes ───────────────────────────────────────────────────────
/**
 * Labels d'affichage des statuts utilisateurs.
 * Clés = valeurs renvoyées par l'API backend.
 */
const STATUS_LABELS = {
  active: "ACTIF",
  inactive: "INACTIF",
  suspended: "SUSPENDU",
  pending: "EN ATTENTE",
};

/**
 * Définition des colonnes du tableau.
 * Aucune valeur métier hardcodée — structure uniquement.
 */
const tableHeaders = [
  { title: "ID", key: "id", align: "start", sortable: true, width: "72px" },
  {
    title: "UTILISATEUR",
    key: "username",
    align: "start",
    sortable: true,
    width: "170px",
  },
  {
    title: "NOM",
    key: "nom",
    align: "start",
    sortable: true,
    width: "170px",
  },
  {
    title: "PRENOM",
    key: "prenom",
    align: "start",
    sortable: true,
    width: "170px",
  },
  { title: "EMAIL", key: "email", align: "start", sortable: true },
  {
    title: "EXTENSION",
    key: "station_extension",
    align: "center",
    sortable: false,
    width: "100px",
  },
  {
    title: "LOGIN ID",
    key: "agent_login",
    align: "center",
    sortable: false,
    width: "100px",
  },
  {
    title: "RÔLE",
    key: "role",
    align: "start",
    sortable: true,
    width: "120px",
  },
  {
    title: "TENANT",
    key: "tenants",
    align: "start",
    sortable: false,
    width: "120px",
  },
  {
    title: "LAST LOGIN",
    key: "last_login",
    align: "center",
    sortable: true,
    width: "110px",
  },
  {
    title: "STATUT",
    key: "status",
    align: "center",
    sortable: true,
    width: "110px",
  },
  {
    title: "ACTIONS",
    key: "actions",
    align: "center",
    sortable: false,
    width: "96px",
  },
];
// ─── Composable users ─────────────────────────────────────────────────────────
const {
  users,
  totalUsers,
  loading,
  listError,
  page,
  itemsPerPage,
  searchQuery,
  statusFilter,
  totalPages,
  visiblePages,
  tenants,
  tenantsLoading,
  submissionLoading,
  submissionError,
  submissionSuccess,
  loadUsers,
  onSearchInput,
  onTableOptions,
  goToPage,
  createUser,
  updateUser,
  resetPassword,
  deleteUser,
  resetSubmissionState,
  init,
} = useUsers();
// Le composable `useUsers` ne fournit pas toutes les méthodes nécessaires (getById, update, etc.).
// Pour répondre à la demande sans modifier le composable, la logique est ajoutée ici.
// Idéalement, elle devrait être centralisée dans le composable.

// Rôles assignables via l'UI. Le rôle ADMIN (super-admin global, accès à TOUS
// les tenants) est volontairement EXCLU : il se gère uniquement via la CLI
// `flask superadmin` pour éviter toute escalade involontaire.
const localRoles = ref([
  { value: "MANAGER", label: "MANAGER" },
  { value: "PERMANENCIER", label: "PERMANENCIER" },
]);
const rolesLoading = ref(false);

// ─── Panneau création ──────────────────────────────────────────────────────────
const panelOpen = ref(false);
const panelMode = ref("create"); // 'create', 'edit', 'reset_password'
const selectedUser = ref(null);

const panelTitle = computed(() => {
  if (panelMode.value === "edit") return "MODIFIER L'UTILISATEUR";
  if (panelMode.value === "reset_password")
    return "RÉINITIALISER LE MOT DE PASSE";
  return "AJOUTER UN UTILISATEUR";
});

const submitButtonText = computed(() => {
  if (panelMode.value === "edit") return "ENREGISTRER LES MODIFICATIONS";
  if (panelMode.value === "reset_password")
    return "VALIDER LE NOUVEAU MOT DE PASSE";
  return "VALIDER L'UTILISATEUR";
});

const successMessage = computed(() => {
  if (panelMode.value === "create") return "Utilisateur créé avec succès.";
  if (panelMode.value === "edit") return "Utilisateur mis à jour avec succès.";
  if (panelMode.value === "reset_password")
    return "Mot de passe réinitialisé avec succès.";
  return "Opération réussie.";
});

function handleOpenCreatePanel() {
  resetForm();
  resetSubmissionState();
  panelMode.value = "create";
  selectedUser.value = null;
  panelOpen.value = true;
}

function closeCreatePanel() {
  panelOpen.value = false;
}

// ─── Avatar upload ─────────────────────────────────────────────────────────────
const avatarInputRef = ref(null);
const avatarFile = ref(null);
const avatarPreview = ref(null);
const dragging = ref(false);
const avatarRemoved = ref(false);

function triggerAvatarInput() {
  avatarInputRef.value?.click();
}

function onAvatarFileChange(event) {
  const file = event.target.files?.[0];
  if (file) applyAvatarFile(file);
}

function onAvatarDrop(event) {
  dragging.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file && file.type.startsWith("image/")) applyAvatarFile(file);
}

function applyAvatarFile(file) {
  if (file.size > 2 * 1024 * 1024) {
    formErrors.avatar = "Fichier trop lourd (max 2 Mo)";
    return;
  }
  avatarFile.value = file;
  avatarRemoved.value = false; // Un nouvel upload annule une demande de suppression
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

// ─── Formulaire création ───────────────────────────────────────────────────────
const form = reactive({
  nom: "",
  prenom: "",
  email: "",
  station_extension: "",
  role: "",
  tenant_ids: [],
  password: "",
  confirmPassword: "",
});

const formErrors = reactive({
  nom: "",
  prenom: "",
  email: "",
  role: "",
  tenant_ids: "",
  password: "",
  confirmPassword: "",
  avatar: "",
});

const showPwd = ref(false);
const showPwdConfirm = ref(false);

function resetForm() {
  Object.keys(form).forEach((k) => {
    form[k] = "";
  });
  form.tenant_ids = [];
  Object.keys(formErrors).forEach((k) => {
    formErrors[k] = "";
  });
  showPwd.value = false;
  showPwdConfirm.value = false;
  // Réinitialisation manuelle de l'avatar sans déclencher la logique de suppression
  avatarFile.value = null;
  avatarPreview.value = null;
  if (avatarInputRef.value) avatarInputRef.value.value = "";
  avatarRemoved.value = false;
  resetSubmissionState();
}

/**
 * Validation locale côté client — bloque la soumission si erreurs.
 * @returns {boolean} true si tous les champs requis sont valides
 */
function validateForm() {
  let isValid = true;
  Object.keys(formErrors).forEach((k) => {
    formErrors[k] = "";
  });

  // --- Validation pour les modes 'create' et 'edit' ---
  if (panelMode.value === "create" || panelMode.value === "edit") {
    if (!form.nom.trim()) {
      formErrors.nom = "Le nom est requis";
      isValid = false;
    }
    if (!form.prenom.trim()) {
      formErrors.prenom = "Le prénom est requis";
      isValid = false;
    }

    const emailRx = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!form.email.trim()) {
      formErrors.email = "L'email est requis";
      isValid = false;
    } else if (!emailRx.test(form.email)) {
      formErrors.email = "Format email invalide";
      isValid = false;
    }

    if (!form.role) {
      formErrors.role = "Le rôle est requis";
      isValid = false;
    }
    // Un rôle non-administrateur doit être rattaché à ≥1 tenant (anti-lockout).
    if (form.role !== "ADMIN" && (!form.tenant_ids || form.tenant_ids.length === 0)) {
      formErrors.tenant_ids = "Au moins un tenant est requis (sauf administrateur global).";
      isValid = false;
    }
  }

  // --- Validation du mot de passe (logique différente par mode) ---
  const isPasswordRequired =
    panelMode.value === "create" || panelMode.value === "reset_password";
  const isPasswordFilled = form.password || form.confirmPassword;

  if (isPasswordRequired || isPasswordFilled) {
    if (!form.password) {
      formErrors.password = "Le mot de passe est requis";
      isValid = false;
    } else if (form.password.length < 8) {
      formErrors.password = "Minimum 8 caractères";
      isValid = false;
    }

    if (!form.confirmPassword) {
      formErrors.confirmPassword = "La confirmation est requise";
      isValid = false;
    } else if (form.password !== form.confirmPassword) {
      formErrors.confirmPassword = "Les mots de passe ne correspondent pas";
      isValid = false;
    }
  }

  return isValid;
}

async function submitForm() {
  if (!validateForm()) return;

  const payload = { ...form };
  let success;

  if (panelMode.value === "create") {
    success = await createUser(payload, avatarFile.value);
  } else if (panelMode.value === "edit") {
    // Ajoute un signal pour la suppression si l'avatar a été enlevé manuellement
    if (avatarRemoved.value && !avatarFile.value) {
      payload.avatar_url = null;
    }
    success = await updateUser(
      selectedUser.value.id,
      payload,
      avatarFile.value,
    );
  } else if (panelMode.value === "reset_password") {
    success = await resetPassword(selectedUser.value.id, payload.password);
  }

  if (success) {
    setTimeout(() => {
      closeCreatePanel();
    }, 1800);
  }
}

async function onEditUser(user) {
  resetForm();
  panelMode.value = "edit";
  selectedUser.value = user;
  // NOTE: Idéalement, un appel `GET /api/users/${user.id}` devrait être fait ici.
  // On simule en remplissant avec les données de la table.
  form.nom = user.nom || "";
  form.prenom = user.prenom || "";
  form.email = user.email || "";
  form.station_extension = user.station_extension || "";
  form.role = user.role || "";
  // Pré-remplir avec TOUS les tenants de l'utilisateur (multi-affectation).
  form.tenant_ids = (user.tenants || []).map((t) => t.id);
  if (user.avatar_url) {
    avatarPreview.value = getAvatarFullUrl(user.avatar_url);
  }
  panelOpen.value = true;
}

async function onResetPassword(user) {
  resetForm();
  panelMode.value = "reset_password";
  selectedUser.value = user;
  // NOTE: Idéalement, un appel `GET /api/users/${user.id}` devrait être fait ici.
  // On simule en remplissant avec les données de la table.
  form.nom = user.nom || "";
  form.prenom = user.prenom || "";
  form.email = user.email || "";
  form.station_extension = user.station_extension || "";
  form.role = user.role || "";
  form.tenant_ids = (user.tenants || []).map((t) => t.id);
  if (user.avatar_url) {
    avatarPreview.value = getAvatarFullUrl(user.avatar_url);
  }
  panelOpen.value = true;
}

// ─── Suppression ───────────────────────────────────────────────────────────────
const deleteTarget = ref(null);
const deleteInProgress = ref(false);

function onDeleteUser(user) {
  deleteTarget.value = user;
}

async function executeDelete() {
  if (!deleteTarget.value) return;
  deleteInProgress.value = true;
  const success = await deleteUser(deleteTarget.value.id);
  deleteInProgress.value = false;
  if (success) {
    deleteTarget.value = null;
  }
}

// ─── Helpers affichage ────────────────────────────────────────────────────────
function getInitials(username) {
  return (username || "").substring(0, 2).toUpperCase();
}

function userAvatarColor(username) {
  let hash = 0;
  username = username.replace(/^@/, "");

  for (let i = 0; i < username.length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash);
  }

  const h = hash % 360;
  return `hsl(${h}, 50%, 45%)`;
}

function getAvatarFullUrl(relativeUrl) {
  if (!relativeUrl) return "";
  try {
    // Construit l'URL absolue de l'avatar à partir de la baseURL d'apiClient.
    const backendUrl = new URL(apiClient.defaults.baseURL);
    return `${backendUrl.protocol}//${backendUrl.host}${relativeUrl}`;
  } catch (e) {
    // Fallback si la baseURL n'est pas une URL valide.
    return relativeUrl;
  }
}

// ─── Cycle de vie ─────────────────────────────────────────────────────────────
onMounted(() => {
  init();
});
</script>

<style scoped>
@import "@/assets/styles/crud-view.css";
</style>
