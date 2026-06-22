<template>
  <!-- Page wrapper -->
  <div class="tn-page">

    <!-- === BARRE D'ACTIONS === -->
    <header class="tn-toolbar">
      <div class="tn-toolbar__title">
        <h1 class="tn-title">GESTION DES TENANTS</h1>
        <span class="tn-count">({{ tenants.length }} tenant{{ tenants.length > 1 ? 's' : '' }})</span>
      </div>

      <div class="tn-toolbar__actions">
        <div class="tn-search">
          <svg class="tn-search__icon" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
            <path fill="currentColor" d="M9.5 3a6.5 6.5 0 0 1 5.25 10.33l5.46 5.46-1.42 1.42-5.46-5.46A6.5 6.5 0 1 1 9.5 3m0 2a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9" />
          </svg>
          <input
            v-model="search"
            class="tn-search__input"
            type="text"
            placeholder="Rechercher par nom ou code…"
          />
        </div>

        <button class="tn-btn tn-btn--primary" @click="openCreate">
          + NOUVEAU TENANT
        </button>
      </div>
    </header>

    <!-- Bandeau erreur globale -->
    <div v-if="loadError" class="tn-banner tn-banner--error">
      <span>{{ loadError }}</span>
      <button class="tn-banner__retry" @click="fetchTenants">RÉESSAYER</button>
    </div>

    <!-- === TABLEAU PRINCIPAL === -->
    <div class="tn-table-wrap">
      <table class="tn-table">
        <thead>
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              :class="['tn-th', { 'tn-th--sortable': col.sortable, 'tn-th--active': sortKey === col.key }]"
              @click="col.sortable && toggleSort(col.key)"
            >
              <span class="tn-th__label">{{ col.label }}</span>
              <span v-if="col.sortable" class="tn-th__arrow">
                <template v-if="sortKey === col.key">{{ sortDir === 'asc' ? '▲' : '▼' }}</template>
                <template v-else>⇅</template>
              </span>
            </th>
          </tr>
        </thead>

        <tbody>
          <!-- Skeleton loader -->
          <template v-if="loading">
            <tr v-for="n in 5" :key="`sk-${n}`" class="tn-row tn-row--skeleton">
              <td v-for="col in columns" :key="col.key" class="tn-td">
                <span class="tn-skel"></span>
              </td>
            </tr>
          </template>

          <!-- Liste vide -->
          <tr v-else-if="displayedTenants.length === 0" class="tn-row tn-row--empty">
            <td :colspan="columns.length">
              <div class="tn-empty">
                <p class="tn-empty__title">Aucun tenant trouvé.</p>
                <p class="tn-empty__sub">
                  {{ search ? 'Affinez votre recherche ou réinitialisez le filtre.' : 'Créez un premier tenant avec le bouton « + NOUVEAU TENANT ».' }}
                </p>
              </div>
            </td>
          </tr>

          <!-- Données -->
          <tr v-for="t in displayedTenants" :key="t.id" class="tn-row">
            <td class="tn-td tn-td--name">
              <div class="tn-name-cell">
                <img v-if="t.logo_url" :src="fileUrl(t.logo_url)" class="tn-logo" alt="" />
                <span v-else class="tn-logo tn-logo--ph">{{ initials(t.nom) }}</span>
                <span>{{ t.nom }}</span>
              </div>
            </td>
            <td class="tn-td tn-mono">{{ t.code }}</td>
            <td class="tn-td tn-mono">{{ t.slug }}</td>
            <td class="tn-td">
              <span :class="['tn-badge', t.is_active ? 'tn-badge--on' : 'tn-badge--off']">
                <span class="tn-badge__dot"></span>
                {{ t.is_active ? 'ACTIF' : 'INACTIF' }}
              </span>
            </td>
            <td class="tn-td tn-mono tn-td--date">{{ formatDate(t.created_at) }}</td>
            <td class="tn-td tn-td--actions">
              <button
                class="tn-icon-btn"
                :title="t.is_active ? 'Désactiver' : 'Activer'"
                :disabled="togglingId === t.id"
                @click="toggleActive(t)"
              >
                <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                  <path fill="currentColor" d="M13 3h-2v10h2zm4.83 2.17-1.42 1.42A7 7 0 1 1 7.59 6.6L6.17 5.17a9 9 0 1 0 11.66 0" />
                </svg>
              </button>
              <button class="tn-icon-btn" title="Modifier" @click="openEdit(t)">
                <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                  <path fill="currentColor" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75z" />
                </svg>
              </button>
              <button class="tn-icon-btn tn-icon-btn--danger" title="Supprimer" @click="openDelete(t)">
                <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                  <path fill="currentColor" d="M6 7h12l-1 14H7zm3-3h6l1 2H8zM4 6h16v2H4z" />
                </svg>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- === SIDE DRAWER (CRÉATION / MODIFICATION) === -->
    <transition name="tn-drawer">
      <div v-if="drawerOpen" class="tn-overlay" @click.self="closeDrawer">
        <aside class="tn-drawer" role="dialog" aria-modal="true">
          <header class="tn-drawer__head">
            <h2 class="tn-drawer__title">
              {{ isEditMode ? 'MODIFIER LE TENANT' : 'CRÉER UN TENANT' }}
            </h2>
            <button class="tn-icon-btn" title="Fermer" @click="closeDrawer">
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path fill="currentColor" d="M18.3 5.71 12 12l6.3 6.29-1.42 1.42L10.59 13.4 4.3 19.71 2.88 18.3 9.17 12 2.88 5.71 4.3 4.29l6.29 6.3 6.29-6.3z" />
              </svg>
            </button>
          </header>

          <div class="tn-drawer__body">
            <!-- LOGO -->
            <div class="tn-field">
              <label class="tn-label">LOGO</label>
              <div class="tn-logo-upload">
                <div class="tn-logo-preview">
                  <img v-if="logoPreview" :src="logoPreview" alt="Aperçu du logo" />
                  <span v-else class="tn-logo-preview__ph">{{ initials(form.nom) || '—' }}</span>
                </div>
                <div class="tn-logo-actions">
                  <button type="button" class="tn-btn tn-btn--ghost tn-btn--sm" @click="logoInput?.click()">
                    {{ logoPreview ? 'CHANGER' : 'CHOISIR UN FICHIER' }}
                  </button>
                  <button
                    v-if="logoPreview"
                    type="button"
                    class="tn-btn tn-btn--ghost tn-btn--sm"
                    @click="clearLogo"
                  >
                    RETIRER
                  </button>
                  <input
                    ref="logoInput"
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    class="tn-file-hidden"
                    @change="onLogoChange"
                  />
                </div>
              </div>
              <p class="tn-hint">PNG, JPG ou WEBP — 2 Mo max.</p>
              <p v-if="logoError" class="tn-field-error">{{ logoError }}</p>
            </div>

            <!-- NOM -->
            <div class="tn-field">
              <label class="tn-label" for="tn-nom">NOM</label>
              <input
                id="tn-nom"
                v-model="form.nom"
                class="tn-input"
                :class="{ 'tn-input--error': fieldErrors.nom }"
                type="text"
                placeholder="Nom complet du tenant"
              />
              <p v-if="fieldErrors.nom" class="tn-field-error">{{ fieldErrors.nom }}</p>
            </div>

            <!-- CODE -->
            <div class="tn-field">
              <label class="tn-label" for="tn-code">CODE</label>
              <input
                id="tn-code"
                v-model="form.code"
                class="tn-input tn-mono"
                :class="{ 'tn-input--error': fieldErrors.code }"
                type="text"
                placeholder="CODE_TENANT"
                @input="onCodeInput"
              />
              <p class="tn-hint">Identifiant unique, lettres majuscules.</p>
              <p v-if="fieldErrors.code" class="tn-field-error">{{ fieldErrors.code }}</p>
            </div>

            <!-- SLUG -->
            <div class="tn-field">
              <label class="tn-label" for="tn-slug">SLUG</label>
              <input
                id="tn-slug"
                v-model="form.slug"
                class="tn-input tn-mono"
                :class="{ 'tn-input--error': fieldErrors.slug }"
                type="text"
                placeholder="nom-du-tenant"
                @input="onSlugInput"
              />
              <p class="tn-hint">Lettres minuscules, chiffres, tirets.</p>
              <p v-if="fieldErrors.slug" class="tn-field-error">{{ fieldErrors.slug }}</p>
            </div>

            <!-- STATUT (édition uniquement) -->
            <div v-if="isEditMode" class="tn-field">
              <label class="tn-label">STATUT</label>
              <button
                type="button"
                :class="['tn-toggle', { 'tn-toggle--on': form.is_active }]"
                role="switch"
                :aria-checked="form.is_active"
                @click="form.is_active = !form.is_active"
              >
                <span class="tn-toggle__track"><span class="tn-toggle__thumb"></span></span>
                <span class="tn-toggle__text">{{ form.is_active ? 'ACTIF' : 'INACTIF' }}</span>
              </button>
            </div>

            <!-- CANAUX MÉTIER (pilotage admin global) -->
            <div class="tn-field">
              <label class="tn-label">CANAUX MÉTIER</label>
              <p class="tn-hint">
                Pilotent la visibilité des onglets du workspace et des sections de configuration.
                SMTP (emails système) reste toujours actif.
              </p>
              <div
                v-for="c in CHANNELS"
                :key="c.key"
                class="tn-channel-row"
              >
                <button
                  type="button"
                  :class="['tn-toggle', { 'tn-toggle--on': form.channels[c.key] }]"
                  role="switch"
                  :aria-checked="form.channels[c.key]"
                  @click="form.channels[c.key] = !form.channels[c.key]"
                >
                  <span class="tn-toggle__track"><span class="tn-toggle__thumb"></span></span>
                  <span class="tn-toggle__text">{{ c.label }}</span>
                </button>
              </div>
            </div>

            <!-- Erreur de formulaire générale -->
            <div v-if="formError" class="tn-banner tn-banner--error tn-banner--inline">
              {{ formError }}
            </div>
          </div>

          <footer class="tn-drawer__foot">
            <button class="tn-btn tn-btn--ghost" :disabled="saving" @click="closeDrawer">
              ANNULER
            </button>
            <button class="tn-btn tn-btn--primary" :disabled="saving" @click="submitForm">
              {{ saving ? 'ENREGISTREMENT…' : 'ENREGISTRER' }}
            </button>
          </footer>
        </aside>
      </div>
    </transition>

    <!-- === MODALE DE CONFIRMATION SUPPRESSION === -->
    <transition name="tn-fade">
      <div v-if="deleteTarget" class="tn-modal-overlay" @click.self="closeDelete">
        <div class="tn-modal" role="alertdialog" aria-modal="true">
          <header class="tn-modal__head">
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path fill="currentColor" d="M1 21h22L12 2zm12-3h-2v-2h2zm0-4h-2v-4h2z" />
            </svg>
            <h2 class="tn-modal__title">SUPPRESSION IRRÉVERSIBLE</h2>
          </header>

          <div class="tn-modal__body">
            <p class="tn-modal__warn">
              Vous êtes sur le point de supprimer définitivement le tenant
              <strong>{{ deleteTarget.nom }}</strong>
              (<span class="tn-mono">{{ deleteTarget.code }}</span>).
              Cette opération est <strong>irréversible</strong> et déclenche une suppression
              en cascade des données suivantes :
            </p>

            <ul class="tn-cascade">
              <li>Clients</li>
              <li>Sites</li>
              <li>Demandes</li>
              <li>Interactions</li>
              <li>Fichiers</li>
              <li>Agents de sécurité</li>
              <li>Prestataires</li>
              <li>Événements de téléphonie</li>
              <li>Logs d'audit</li>
            </ul>

            <p class="tn-modal__note">
              Si des utilisateurs sont encore rattachés à ce tenant, la suppression sera
              refusée (409).
            </p>

            <div class="tn-field">
              <label class="tn-label" for="tn-confirm">
                Saisissez le code du tenant pour confirmer :
                <span class="tn-mono tn-modal__code">{{ deleteTarget.code }}</span>
              </label>
              <input
                id="tn-confirm"
                v-model="deleteConfirm"
                class="tn-input tn-mono"
                type="text"
                :placeholder="deleteTarget.code"
                autocomplete="off"
              />
            </div>

            <div v-if="deleteError" class="tn-banner tn-banner--error tn-banner--inline">
              {{ deleteError }}
            </div>
          </div>

          <footer class="tn-modal__foot">
            <button class="tn-btn tn-btn--ghost" :disabled="deleting" @click="closeDelete">
              ANNULER
            </button>
            <button
              class="tn-btn tn-btn--danger"
              :disabled="!canConfirmDelete || deleting"
              @click="confirmDelete"
            >
              {{ deleting ? 'SUPPRESSION…' : 'SUPPRIMER DÉFINITIVEMENT' }}
            </button>
          </footer>
        </div>
      </div>
    </transition>

  </div>
</template>

<script setup>
// === IMPORTS ===
import { ref, reactive, computed, onMounted } from "vue";
import apiClient from "@/services/http/axios";

// === STATE ===
const tenants = ref([]);
const loading = ref(false);
const loadError = ref("");

const search = ref("");
const sortKey = ref("nom");
const sortDir = ref("asc"); // 'asc' | 'desc'

// Drawer création / édition
const drawerOpen = ref(false);
const isEditMode = ref(false);
const editingId = ref(null);
const saving = ref(false);
const CHANNELS = [
  { key: "telephonie", label: "Téléphonie" },
  { key: "email", label: "Email" },
  { key: "chat", label: "Chat" },
];
const form = reactive({
  nom: "", code: "", slug: "", is_active: true,
  channels: { telephonie: false, email: false, chat: false },
});
const fieldErrors = reactive({ nom: "", code: "", slug: "" });
const formError = ref("");

// Upload logo
const logoInput = ref(null);
const logoFile = ref(null); // nouveau fichier sélectionné
const logoPreview = ref(null); // URL d'aperçu (blob: ou serveur)
const removeLogo = ref(false); // demande de suppression du logo existant
const logoError = ref("");

// Origine backend (pour préfixer les chemins /uploads)
const BACKEND_ORIGIN = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api"
).replace(/\/api\/?$/, "");

// Toggle actif/inactif
const togglingId = ref(null);

// Modale suppression
const deleteTarget = ref(null);
const deleteConfirm = ref("");
const deleteError = ref("");
const deleting = ref(false);

const columns = [
  { key: "nom", label: "NOM", sortable: true },
  { key: "code", label: "CODE", sortable: true },
  { key: "slug", label: "SLUG", sortable: true },
  { key: "is_active", label: "STATUT", sortable: true },
  { key: "created_at", label: "CRÉÉ LE", sortable: true },
  { key: "actions", label: "ACTIONS", sortable: false },
];

// === COMPUTED ===
const displayedTenants = computed(() => {
  const q = search.value.trim().toLowerCase();
  let list = tenants.value;

  // Filtre temps réel sur nom ET code
  if (q) {
    list = list.filter(
      (t) =>
        (t.nom || "").toLowerCase().includes(q) ||
        (t.code || "").toLowerCase().includes(q),
    );
  }

  // Tri client-side
  const dir = sortDir.value === "asc" ? 1 : -1;
  return [...list].sort((a, b) => {
    let va = a[sortKey.value];
    let vb = b[sortKey.value];
    if (typeof va === "boolean") va = va ? 1 : 0;
    if (typeof vb === "boolean") vb = vb ? 1 : 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    if (va < vb) return -1 * dir;
    if (va > vb) return 1 * dir;
    return 0;
  });
});

const canConfirmDelete = computed(
  () => !!deleteTarget.value && deleteConfirm.value === deleteTarget.value.code,
);

// === API CALLS ===
async function fetchTenants() {
  loading.value = true;
  loadError.value = "";
  try {
    const { data } = await apiClient.get("/tenants");
    tenants.value = Array.isArray(data) ? data : [];
  } catch (err) {
    loadError.value =
      err?.response?.data?.error || "Impossible de charger les tenants.";
  } finally {
    loading.value = false;
  }
}

async function createTenant(payload) {
  const cfg =
    payload instanceof FormData
      ? { headers: { "Content-Type": "multipart/form-data" } }
      : undefined;
  const { data } = await apiClient.post("/tenants", payload, cfg);
  return data;
}

async function updateTenant(id, payload) {
  const cfg =
    payload instanceof FormData
      ? { headers: { "Content-Type": "multipart/form-data" } }
      : undefined;
  const { data } = await apiClient.put(`/tenants/${id}`, payload, cfg);
  return data;
}

async function deleteTenant(id) {
  await apiClient.delete(`/tenants/${id}`);
}

// === HANDLERS ===
function fileUrl(path) {
  if (!path) return null;
  if (/^(https?:|blob:)/.test(path)) return path;
  return BACKEND_ORIGIN + path;
}

function initials(name) {
  if (!name) return "";
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function onLogoChange(e) {
  logoError.value = "";
  const file = e.target.files?.[0];
  if (!file) return;
  const allowed = ["image/png", "image/jpeg", "image/webp"];
  if (!allowed.includes(file.type)) {
    logoError.value = "Format non supporté (PNG, JPG ou WEBP).";
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    logoError.value = "Fichier trop volumineux (2 Mo max).";
    return;
  }
  logoFile.value = file;
  logoPreview.value = URL.createObjectURL(file);
  removeLogo.value = false;
}

function clearLogo() {
  logoFile.value = null;
  logoPreview.value = null;
  removeLogo.value = true;
  if (logoInput.value) logoInput.value.value = "";
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === "asc" ? "desc" : "asc";
  } else {
    sortKey.value = key;
    sortDir.value = "asc";
  }
}

// Transformations de saisie (reflètent les règles backend)
function onCodeInput(e) {
  form.code = e.target.value.toUpperCase();
}
function onSlugInput(e) {
  form.slug = e.target.value
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9\-]/g, "");
}

function resetFormErrors() {
  fieldErrors.nom = "";
  fieldErrors.code = "";
  fieldErrors.slug = "";
  formError.value = "";
}

function resetLogoState(existingUrl = null) {
  logoFile.value = null;
  logoPreview.value = existingUrl ? fileUrl(existingUrl) : null;
  removeLogo.value = false;
  logoError.value = "";
  if (logoInput.value) logoInput.value.value = "";
}

function openCreate() {
  isEditMode.value = false;
  editingId.value = null;
  form.nom = "";
  form.code = "";
  form.slug = "";
  form.is_active = true;
  form.channels = { telephonie: false, email: false, chat: false };
  resetFormErrors();
  resetLogoState();
  drawerOpen.value = true;
}

function openEdit(t) {
  isEditMode.value = true;
  editingId.value = t.id;
  form.nom = t.nom ?? "";
  form.code = t.code ?? "";
  form.slug = t.slug ?? "";
  form.is_active = !!t.is_active;
  form.channels = {
    telephonie: !!t.channels?.telephonie,
    email: !!t.channels?.email,
    chat: !!t.channels?.chat,
  };
  resetFormErrors();
  resetLogoState(t.logo_url);
  drawerOpen.value = true;
}

function closeDrawer() {
  if (saving.value) return;
  drawerOpen.value = false;
}

// Mappe une erreur API { error } vers le bon champ inline
function applyApiError(err) {
  const msg = err?.response?.data?.error || "Une erreur est survenue.";
  const low = msg.toLowerCase();
  if (low.includes("slug")) fieldErrors.slug = msg;
  else if (low.includes("code")) fieldErrors.code = msg;
  else if (low.includes("nom")) fieldErrors.nom = msg;
  else formError.value = msg;
}

async function submitForm() {
  resetFormErrors();

  // Validation client minimale
  if (!form.nom.trim()) fieldErrors.nom = "Le champ 'nom' est obligatoire.";
  if (!form.code.trim()) fieldErrors.code = "Le champ 'code' est obligatoire.";
  if (!form.slug.trim()) fieldErrors.slug = "Le champ 'slug' est obligatoire.";
  if (fieldErrors.nom || fieldErrors.code || fieldErrors.slug) return;

  // Payload de base
  const payload = {
    nom: form.nom.trim(),
    code: form.code.trim(),
    slug: form.slug.trim(),
    channels: { ...form.channels },
  };
  if (isEditMode.value) payload.is_active = form.is_active;
  // Demande explicite de suppression du logo existant (édition)
  if (isEditMode.value && removeLogo.value && !logoFile.value) {
    payload.logo_url = null;
  }

  // Multipart seulement si un fichier logo est joint ou retiré
  let body = payload;
  if (logoFile.value || (isEditMode.value && removeLogo.value)) {
    const fd = new FormData();
    fd.append("data", JSON.stringify(payload));
    if (logoFile.value) fd.append("logo", logoFile.value);
    body = fd;
  }

  saving.value = true;
  try {
    if (isEditMode.value) {
      const updated = await updateTenant(editingId.value, body);
      const idx = tenants.value.findIndex((t) => t.id === editingId.value);
      if (idx !== -1) tenants.value[idx] = updated;
    } else {
      const created = await createTenant(body);
      tenants.value.push(created);
    }
    drawerOpen.value = false;
  } catch (err) {
    applyApiError(err);
  } finally {
    saving.value = false;
  }
}

async function toggleActive(t) {
  togglingId.value = t.id;
  try {
    const updated = await updateTenant(t.id, { is_active: !t.is_active });
    const idx = tenants.value.findIndex((x) => x.id === t.id);
    if (idx !== -1) tenants.value[idx] = updated;
  } catch (err) {
    loadError.value =
      err?.response?.data?.error || "Échec de la mise à jour du statut.";
  } finally {
    togglingId.value = null;
  }
}

function openDelete(t) {
  deleteTarget.value = t;
  deleteConfirm.value = "";
  deleteError.value = "";
}

function closeDelete() {
  if (deleting.value) return;
  deleteTarget.value = null;
}

async function confirmDelete() {
  if (!canConfirmDelete.value) return;
  deleting.value = true;
  deleteError.value = "";
  try {
    await deleteTenant(deleteTarget.value.id);
    tenants.value = tenants.value.filter((t) => t.id !== deleteTarget.value.id);
    deleteTarget.value = null;
  } catch (err) {
    // 409 (utilisateurs rattachés) ou autre : garder la modale ouverte
    deleteError.value =
      err?.response?.data?.error || "La suppression a échoué.";
  } finally {
    deleting.value = false;
  }
}

// === LIFECYCLE ===
onMounted(fetchTenants);
</script>

<style scoped>
/* === VARIABLES CSS PERMATEL === */
.tn-page {
  --color-bg: #f2f2f2;
  --color-surface: #ffffff;
  --color-authority: #000b23;
  --color-navy: #15223a;
  --color-teal: #00a8a8;
  --color-danger: #e74c3c;
  --color-text: #1a1a2e;
  --color-muted: #6b7280;
  --color-border: #e5e7eb;
  --color-ok: #22c55e;

  font-family: "Fira Sans", system-ui, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  min-height: 100%;
  padding: 24px;
  box-sizing: border-box;
}

.tn-mono {
  font-family: "Fira Code", ui-monospace, monospace;
}

/* === LAYOUT — BARRE D'ACTIONS === */
.tn-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.tn-toolbar__title {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.tn-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--color-authority);
  margin: 0;
}

.tn-count {
  font-size: 13px;
  color: var(--color-muted);
}

.tn-toolbar__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tn-search {
  position: relative;
  display: flex;
  align-items: center;
}

.tn-search__icon {
  position: absolute;
  left: 10px;
  color: var(--color-muted);
  pointer-events: none;
}

.tn-search__input {
  height: 36px;
  width: 260px;
  padding: 0 12px 0 32px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  color: var(--color-text);
  outline: none;
}
.tn-search__input:focus {
  border-color: var(--color-teal);
}

/* === BOUTONS === */
.tn-btn {
  height: 36px;
  padding: 0 16px;
  border: 1px solid transparent;
  border-radius: 4px;
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  cursor: pointer;
  transition: filter 0.15s, background 0.15s, border-color 0.15s;
}
.tn-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.tn-btn--primary {
  background: var(--color-teal);
  color: #fff;
}
.tn-btn--primary:not(:disabled):hover {
  filter: brightness(0.93);
}
.tn-btn--danger {
  background: var(--color-danger);
  color: #fff;
}
.tn-btn--danger:not(:disabled):hover {
  filter: brightness(0.93);
}
.tn-btn--ghost {
  background: transparent;
  border-color: var(--color-border);
  color: var(--color-text);
}
.tn-btn--ghost:not(:disabled):hover {
  background: #f7f7f8;
}

/* === BANDEAUX === */
.tn-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 4px;
  font-size: 13px;
  margin-bottom: 12px;
}
.tn-banner--error {
  background: rgba(231, 76, 60, 0.08);
  border: 1px solid rgba(231, 76, 60, 0.3);
  color: #a93226;
}
.tn-banner--inline {
  margin-bottom: 0;
}
.tn-banner__retry {
  background: none;
  border: none;
  color: #a93226;
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.06em;
  cursor: pointer;
}

/* === TABLEAU === */
.tn-table-wrap {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}

.tn-table {
  width: 100%;
  border-collapse: collapse;
}

.tn-th {
  text-align: left;
  padding: 12px 16px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-muted);
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
  user-select: none;
}
.tn-th--sortable {
  cursor: pointer;
}
.tn-th--active {
  color: var(--color-authority);
}
.tn-th__arrow {
  margin-left: 6px;
  font-size: 9px;
  opacity: 0.7;
}

.tn-row {
  transition: background 0.12s;
}
.tn-row:not(.tn-row--empty):not(.tn-row--skeleton):hover {
  background: #f7f8fa;
}

.tn-td {
  padding: 12px 16px;
  font-size: 13px;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border);
  vertical-align: middle;
}
.tn-table tbody tr:last-child .tn-td {
  border-bottom: none;
}
.tn-td--name {
  font-weight: 600;
}
.tn-td--date {
  color: var(--color-muted);
}
.tn-td--actions {
  white-space: nowrap;
  text-align: right;
}

/* === BADGES === */
.tn-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
}
.tn-badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.tn-badge--on {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}
.tn-badge--on .tn-badge__dot {
  background: var(--color-ok);
}
.tn-badge--off {
  background: rgba(231, 76, 60, 0.1);
  color: #a93226;
}
.tn-badge--off .tn-badge__dot {
  background: var(--color-danger);
}

/* === BOUTONS ICÔNES === */
.tn-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  margin-left: 4px;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  color: var(--color-muted);
  cursor: pointer;
  transition: background 0.12s, color 0.12s, border-color 0.12s;
}
.tn-icon-btn:not(:disabled):hover {
  background: #eef0f3;
  color: var(--color-authority);
}
.tn-icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.tn-icon-btn--danger:not(:disabled):hover {
  background: rgba(231, 76, 60, 0.1);
  color: var(--color-danger);
}

/* === LOGO (miniature tableau + aperçu) === */
.tn-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.tn-logo {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  object-fit: cover;
  background: #f2f2f2;
  border: 1px solid var(--color-border);
  flex-shrink: 0;
}
.tn-logo--ph {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-weight: 700;
  color: var(--color-muted);
}

/* Zone d'upload dans le drawer */
.tn-logo-upload {
  display: flex;
  align-items: center;
  gap: 14px;
}
.tn-logo-preview {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: #f7f7f8;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tn-logo-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.tn-logo-preview__ph {
  font-family: "Fira Code", monospace;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-muted);
}
.tn-logo-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tn-btn--sm {
  height: 30px;
  padding: 0 12px;
  font-size: 11px;
}
.tn-file-hidden {
  display: none;
}

/* === SKELETON LOADER === */
.tn-skel {
  display: block;
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, #ececec 25%, #f4f4f4 37%, #ececec 63%);
  background-size: 400% 100%;
  animation: tn-shimmer 1.3s ease infinite;
}
@keyframes tn-shimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}

/* === ÉTAT VIDE === */
.tn-empty {
  text-align: center;
  padding: 48px 16px;
}
.tn-empty__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-authority);
  margin: 0 0 4px;
}
.tn-empty__sub {
  font-size: 13px;
  color: var(--color-muted);
  margin: 0;
}

/* === SIDE DRAWER === */
.tn-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 11, 35, 0.45);
  display: flex;
  justify-content: flex-end;
  z-index: 1000;
}

.tn-drawer {
  width: 480px;
  max-width: 100vw;
  height: 100%;
  background: var(--color-surface);
  display: flex;
  flex-direction: column;
  box-shadow: -2px 0 16px rgba(0, 11, 35, 0.12);
}

.tn-drawer__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}
.tn-drawer__title {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--color-authority);
  margin: 0;
}

.tn-drawer__body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.tn-drawer__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 24px;
  border-top: 1px solid var(--color-border);
}

/* === CHAMPS DE FORMULAIRE === */
.tn-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tn-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-muted);
}
.tn-input {
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface);
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  color: var(--color-text);
  outline: none;
  transition: border-color 0.15s;
}
.tn-input:focus {
  border-color: var(--color-teal);
}
.tn-input--error {
  border-color: var(--color-danger);
}
.tn-hint {
  font-size: 11px;
  color: var(--color-muted);
  margin: 0;
}
.tn-field-error {
  font-size: 12px;
  color: var(--color-danger);
  margin: 0;
}

/* === TOGGLE SWITCH === */
.tn-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
}
.tn-toggle__track {
  position: relative;
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: #cbd2da;
  transition: background 0.18s;
}
.tn-toggle__thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.18s;
}
.tn-toggle--on .tn-toggle__track {
  background: var(--color-teal);
}
.tn-toggle--on .tn-toggle__thumb {
  transform: translateX(20px);
}
.tn-toggle__text {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--color-text);
}

/* === MODALE === */
.tn-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 11, 35, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
  padding: 16px;
}
.tn-modal {
  width: 520px;
  max-width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  background: var(--color-surface);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
}
.tn-modal__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  background: var(--color-danger);
  color: #fff;
  border-radius: 8px 8px 0 0;
}
.tn-modal__title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.06em;
  margin: 0;
}
.tn-modal__body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.tn-modal__warn {
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text);
  margin: 0;
}
.tn-cascade {
  margin: 0;
  padding-left: 18px;
  columns: 2;
  font-size: 12px;
  color: var(--color-muted);
}
.tn-cascade li {
  margin: 2px 0;
}
.tn-modal__note {
  font-size: 12px;
  line-height: 1.5;
  color: #a93226;
  background: rgba(231, 76, 60, 0.08);
  border: 1px solid rgba(231, 76, 60, 0.25);
  border-radius: 4px;
  padding: 8px 10px;
  margin: 0;
}
.tn-modal__code {
  background: #f2f2f2;
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--color-authority);
}
.tn-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid var(--color-border);
}

/* === ANIMATIONS === */
.tn-drawer-enter-active,
.tn-drawer-leave-active {
  transition: opacity 0.2s ease;
}
.tn-drawer-enter-active .tn-drawer,
.tn-drawer-leave-active .tn-drawer {
  transition: transform 0.25s ease;
}
.tn-drawer-enter-from,
.tn-drawer-leave-to {
  opacity: 0;
}
.tn-drawer-enter-from .tn-drawer,
.tn-drawer-leave-to .tn-drawer {
  transform: translateX(100%);
}

.tn-fade-enter-active,
.tn-fade-leave-active {
  transition: opacity 0.18s ease;
}
.tn-fade-enter-from,
.tn-fade-leave-to {
  opacity: 0;
}
</style>
