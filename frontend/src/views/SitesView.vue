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
          <button
            class="cb-group-btn"
            :class="{ 'cb-group-btn--active': groupEnabled }"
            @click="groupEnabled = !groupEnabled"
          >
            <v-icon size="13">mdi-format-list-group</v-icon>
            GROUPER
          </button>
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
          <div class="sv-table-wrap">
            <table class="sv-table">
              <thead>
                <tr>
                  <th class="sv-th" style="width: 34%">Site</th>
                  <th class="sv-th" style="width: 20%">Contact</th>
                  <th class="sv-th" style="width: 20%">Ville / Code postal</th>
                  <th class="sv-th" style="width: 16%; text-align: center">
                    Statut
                  </th>
                  <th class="sv-th" style="width: 100px; text-align: right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                <template v-if="groupEnabled">
                  <template v-for="group in groupedSites" :key="group.key">
                    <tr class="sv-group-row" @click="toggleGroup(group.key)">
                      <td colspan="5" class="sv-group-row__cell">
                        <div class="sv-group-row__inner">
                          <v-icon
                            size="12"
                            :class="[
                              'sv-group-row__chevron',
                              openGroups.has(group.key)
                                ? 'sv-group-row__chevron--open'
                                : '',
                            ]"
                            >mdi-chevron-right</v-icon
                          >
                          <span
                            class="sv-group-row__dot"
                            :style="{ background: group.color }"
                          ></span>
                          <span class="sv-group-row__name">{{
                            group.name
                          }}</span>
                          <span class="sv-group-row__count">{{
                            group.items.length
                          }}</span>
                          <span class="sv-group-row__spacer"></span>
                          <button
                            class="sv-group-row__link"
                            @click.stop="goToClientFiche(group)"
                          >
                            Voir la fiche client
                            <v-icon size="10">mdi-arrow-right</v-icon>
                          </button>
                        </div>
                      </td>
                    </tr>
                    <template v-if="openGroups.has(group.key)">
                      <tr
                        v-for="item in group.items"
                        :key="item.id"
                        class="sv-data-row"
                      >
                        <td class="sv-td sv-td--site">
                          <div class="sv-name-cell">
                            <span
                              class="sv-type-icon"
                              :style="{ background: group.color }"
                            >
                              <v-icon size="14" color="#fff">mdi-domain</v-icon>
                            </span>
                            <div class="sv-name-text-block">
                              <span class="sv-titre">{{ item.nom }}</span>
                              <span class="sv-name-sub">
                                <span
                                  class="sv-client-dot"
                                  :style="{ background: group.color }"
                                ></span>
                                {{ item.client?.nom ?? "Sans client" }}
                                <template v-if="item.ville">
                                  · {{ item.ville }}</template
                                >
                              </span>
                            </div>
                          </div>
                        </td>
                        <td class="sv-td">
                          <span class="sv-nature-badge">{{
                            item.code_site
                          }}</span>
                          <div class="sv-cat-sub">
                            {{ item.telephone || "—" }}
                          </div>
                        </td>
                        <td class="sv-td sv-td--date">
                          {{ item.ville || "—" }}
                          <div class="sv-date-sub">
                            {{ item.code_postal || "—" }}
                          </div>
                        </td>
                        <td class="sv-td" style="text-align: center">
                          <span
                            :class="[
                              'sv-statut-chip',
                              item.is_active
                                ? 'sv-statut-chip--actif'
                                : 'sv-statut-chip--inactif',
                            ]"
                          >
                            <span class="sv-statut-chip__dot"></span>
                            {{ item.is_active ? "Actif" : "Inactif" }}
                          </span>
                        </td>
                        <td class="sv-td" style="text-align: right">
                          <div class="sv-row-actions">
                            <button
                              class="sv-action-btn"
                              title="Modifier"
                              @click="openEditPanel(item)"
                            >
                              <v-icon size="15">mdi-pencil-outline</v-icon>
                            </button>
                            <button
                              class="sv-action-btn"
                              title="Gérer les contacts"
                              @click="manageContacts(item)"
                            >
                              <v-icon size="15">mdi-account-group</v-icon>
                            </button>
                            <button
                              class="sv-action-btn"
                              title="Désactiver"
                              @click="confirmDelete(item)"
                            >
                              <v-icon size="15">mdi-delete-outline</v-icon>
                            </button>
                          </div>
                        </td>
                      </tr>
                    </template>
                  </template>
                </template>

                <template v-else>
                  <tr v-for="item in sites" :key="item.id" class="sv-data-row">
                    <td class="sv-td sv-td--site">
                      <div class="sv-name-cell">
                        <span
                          class="sv-type-icon"
                          :style="{
                            background: avatarColor(
                              item.client?.nom ?? 'Sans client',
                            ),
                          }"
                        >
                          <v-icon size="14" color="#fff">mdi-domain</v-icon>
                        </span>
                        <div class="sv-name-text-block">
                          <span class="sv-titre">{{ item.nom }}</span>
                          <span class="sv-name-sub">
                            <span
                              class="sv-client-dot"
                              :style="{
                                background: avatarColor(
                                  item.client?.nom ?? 'Sans client',
                                ),
                              }"
                            ></span>
                            {{ item.client?.nom ?? "Sans client" }}
                            <template v-if="item.ville">
                              · {{ item.ville }}</template
                            >
                          </span>
                        </div>
                      </div>
                    </td>
                    <td class="sv-td">
                      <span class="sv-nature-badge">{{ item.code_site }}</span>
                      <div class="sv-cat-sub">{{ item.telephone || "—" }}</div>
                    </td>
                    <td class="sv-td sv-td--date">
                      {{ item.ville || "—" }}
                      <div class="sv-date-sub">
                        {{ item.code_postal || "—" }}
                      </div>
                    </td>
                    <td class="sv-td" style="text-align: center">
                      <span
                        :class="[
                          'sv-statut-chip',
                          item.is_active
                            ? 'sv-statut-chip--actif'
                            : 'sv-statut-chip--inactif',
                        ]"
                      >
                        <span class="sv-statut-chip__dot"></span>
                        {{ item.is_active ? "Actif" : "Inactif" }}
                      </span>
                    </td>
                    <td class="sv-td" style="text-align: right">
                      <div class="sv-row-actions">
                        <button
                          class="sv-action-btn"
                          title="Modifier"
                          @click="openEditPanel(item)"
                        >
                          <v-icon size="15">mdi-pencil-outline</v-icon>
                        </button>
                        <button
                          class="sv-action-btn"
                          title="Gérer les contacts"
                          @click="manageContacts(item)"
                        >
                          <v-icon size="15">mdi-account-group</v-icon>
                        </button>
                        <button
                          class="sv-action-btn"
                          title="Désactiver"
                          @click="confirmDelete(item)"
                        >
                          <v-icon size="15">mdi-delete-outline</v-icon>
                        </button>
                      </div>
                    </td>
                  </tr>
                </template>

                <tr
                  v-if="
                    !loading &&
                    (groupEnabled ? groupedSites : sites).length === 0
                  "
                >
                  <td colspan="5">
                    <div class="table-empty">
                      <v-icon size="36" color="#ddd">mdi-domain-off</v-icon>
                      <p class="table-empty__text">AUCUN SITE TROUVÉ</p>
                      <p class="table-empty__sub">
                        Modifiez les filtres ou créez un nouveau site
                      </p>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
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
                <v-icon size="13" color="#888" class="select-caret"
                  >mdi-chevron-down</v-icon
                >
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
  listError,
  submissionSuccess,
  searchQuery,
  statusFilter,
  clientFilter,
  itemsPerPage,
  page,
  loadSites,
  onSearchInput,
  createSite,
  updateSite,
  deleteSite,
  resetSubmissionState,
} = useSites();

const route = useRoute();
const router = useRouter();

// Groupement par client : la liste complète est toujours chargée (pas de
// pagination serveur), le toggle ne fait que changer le mode d'affichage.
const groupEnabled = ref(true);
const openGroups = ref(new Set());

function toggleGroup(key) {
  const s = new Set(openGroups.value);
  s.has(key) ? s.delete(key) : s.add(key);
  openGroups.value = s;
}

const groupedSites = computed(() => {
  const map = {};
  for (const site of sites.value) {
    const key = site.client_id ?? "none";
    if (!map[key]) {
      const name = site.client?.nom ?? "Sans client";
      map[key] = { key, name, color: avatarColor(name), items: [] };
    }
    map[key].items.push(site);
  }
  return Object.values(map);
});

watch(
  groupedSites,
  (groups) => {
    const s = new Set(openGroups.value);
    groups.forEach((g) => s.add(g.key));
    openGroups.value = s;
  },
  { immediate: true },
);

function goToClientFiche(group) {
  router.push({ path: "/clients", query: { search: group.name } });
}

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

  // Plus de pagination serveur côté table : on charge toujours la liste
  // complète (regroupée ou non, c'est le même jeu de données déjà en
  // mémoire), en reprenant la convention "bulk" déjà utilisée ailleurs
  // dans ce fichier (per_page: 1000).
  page.value = 1;
  itemsPerPage.value = 1000;

  loadSites();
  fetchRelatedData();
});

// Mise à jour dynamique de l'URL lorsque l'utilisateur modifie un filtre
watch(
  [clientFilter, statusFilter, searchQuery],
  ([newClient, newStatus, newSearch]) => {
    const query = {};
    if (newClient) query.client_id = newClient;
    if (newStatus) query.status = newStatus;
    if (newSearch) query.search = newSearch;

    router.replace({ query }).catch(() => {});
  },
);
</script>

<style scoped>
/* ══ TABLE (av-* visual language, "sv-" prefix — cf. AnomaliesView.vue) ══ */
.sv-table-wrap {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 3px;
  overflow: hidden;
}

.sv-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
}

.sv-th {
  padding: 9px 12px;
  text-align: left;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #bbb;
  text-transform: uppercase;
  background: #fafafa;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  white-space: nowrap;
  user-select: none;
}

/* Ligne de groupe accordéon */
.sv-group-row {
  cursor: pointer;
}
.sv-group-row:hover .sv-group-row__cell {
  background: rgba(0, 168, 168, 0.04);
}

.sv-group-row__cell {
  padding: 7px 12px;
  background: rgba(0, 11, 35, 0.02);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  transition: background 0.1s;
}

.sv-group-row__inner {
  display: flex;
  align-items: center;
  gap: 7px;
}

.sv-group-row__chevron {
  color: #bbb;
  transition: transform 0.18s;
  flex-shrink: 0;
}
.sv-group-row__chevron--open {
  transform: rotate(90deg);
}

.sv-group-row__dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}

.sv-group-row__name {
  font-size: 14px;
  font-weight: 700;
  color: #000b23;
  letter-spacing: 0.01em;
}

.sv-group-row__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: rgba(0, 0, 0, 0.07);
  font-family: "Fira Code", monospace;
  font-size: 12px;
  font-weight: 700;
  color: #555;
}

.sv-group-row__spacer {
  flex: 1;
}

.sv-group-row__link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  font-weight: 600;
  color: #00a8a8;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  white-space: nowrap;
}

/* Lignes de données */
.sv-data-row {
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  transition: background 0.1s;
}
.sv-data-row:hover {
  background: rgba(0, 168, 168, 0.025);
}
.sv-data-row:last-child {
  border-bottom: none;
}

.sv-td {
  padding: 10px 12px;
  font-size: 11.5px;
  color: #333;
  vertical-align: top;
}

.sv-td--site {
  max-width: 0;
}
.sv-td--date {
  font-family: "Fira Code", monospace;
  font-size: 13px;
  color: #333;
  white-space: nowrap;
}
.sv-date-sub {
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  color: #9aa0aa;
  margin-top: 2px;
}
.sv-cat-sub {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-top: 4px;
  color: #9aa0aa;
}
.sv-muted {
  color: #9aa0aa;
  font-size: 13px;
}

/* Cellule "Site" (icône + titre + client/ville + statut) */
.sv-name-cell {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.sv-type-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}
.sv-name-text-block {
  min-width: 0;
}
.sv-name-sub {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #9aa0aa;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sv-name-status {
  margin-top: 5px;
}

.sv-cell-flex {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
}

.sv-client-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.sv-titre {
  font-weight: 600;
  color: #000b23;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

/* Badge "Contact" (code site) */
.sv-nature-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 7px;
  border-radius: 2px;
  background: rgba(0, 11, 35, 0.06);
  font-family: "Fira Code", monospace;
  font-size: 11px;
  font-weight: 700;
  color: #555;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

/* Statut */
.sv-statut-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.sv-statut-chip__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.sv-statut-chip--actif {
  background: rgba(39, 174, 96, 0.1);
  color: #27ae60;
}
.sv-statut-chip--inactif {
  background: rgba(0, 0, 0, 0.06);
  color: #95a5a6;
}

/* Pile d'avatars "Contacts" */
.sv-avatar-stack {
  display: flex;
  align-items: center;
}
.sv-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(0, 11, 35, 0.08);
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-weight: 700;
  color: #000b23;
  flex-shrink: 0;
}
.sv-avatar--stack {
  margin-left: -7px;
  border: 2px solid #fff;
}
.sv-avatar--stack:first-child {
  margin-left: 0;
}

/* Actions de ligne */
.sv-row-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  justify-content: flex-end;
}
.sv-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 3px;
  background: transparent;
  cursor: pointer;
  color: #ccc;
  transition:
    background 0.1s,
    color 0.1s;
}
.sv-action-btn:hover {
  background: rgba(0, 0, 0, 0.06);
  color: #555;
}
</style>
