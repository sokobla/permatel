<template>
  <div class="tn-page">
    <header class="tn-toolbar">
      <div class="tn-toolbar__title">
        <h1 class="tn-title">CONNECTEURS PBX</h1>
        <span class="tn-count"
          >({{ connectors.length }} connecteur{{
            connectors.length > 1 ? "s" : ""
          }})</span
        >
      </div>
      <div class="tn-toolbar__actions">
        <button class="tn-btn tn-btn--primary" @click="openCreate">
          + NOUVEAU CONNECTEUR
        </button>
      </div>
    </header>

    <div v-if="loadError" class="tn-banner tn-banner--error">
      <span>{{ loadError }}</span>
      <button class="tn-banner__retry" @click="fetchConnectors">
        RÉESSAYER
      </button>
    </div>

    <div class="tn-table-wrap">
      <table class="tn-table">
        <thead>
          <tr>
            <th class="tn-th">NOM</th>
            <th class="tn-th">TYPE</th>
            <th class="tn-th">HÔTE</th>
            <th class="tn-th">STATUT</th>
            <th class="tn-th">DOMAINES RATTACHÉS</th>
            <th class="tn-th">ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          <template v-if="loading">
            <tr v-for="n in 3" :key="`sk-${n}`" class="tn-row tn-row--skeleton">
              <td v-for="c in 6" :key="c" class="tn-td">
                <span class="tn-skel"></span>
              </td>
            </tr>
          </template>

          <tr v-else-if="connectors.length === 0" class="tn-row tn-row--empty">
            <td colspan="6">
              <div class="tn-empty">
                <p class="tn-empty__title">Aucun connecteur PBX configuré.</p>
                <p class="tn-empty__sub">
                  Créez-en un avec le bouton « + NOUVEAU CONNECTEUR ».
                </p>
              </div>
            </td>
          </tr>

          <tr v-for="c in connectors" :key="c.id" class="tn-row">
            <td class="tn-td tn-td--name">{{ c.name }}</td>
            <td class="tn-td tn-mono">{{ c.type }}</td>
            <td class="tn-td tn-mono">{{ c.host }}:{{ c.port }}</td>
            <td class="tn-td">
              <span
                :class="[
                  'tn-badge',
                  c.is_active ? 'tn-badge--on' : 'tn-badge--off',
                ]"
              >
                <span class="tn-badge__dot"></span>
                {{ c.is_active ? "ACTIF" : "INACTIF" }}
              </span>
            </td>
            <td class="tn-td">{{ domainsCount[c.id] ?? "—" }}</td>
            <td class="tn-td tn-td--actions">
              <button
                class="tn-icon-btn"
                title="Domaines rattachés"
                @click="openDomains(c)"
              >
                <v-icon size="16">mdi-domain</v-icon>
              </button>
              <button class="tn-icon-btn" title="Modifier" @click="openEdit(c)">
                <v-icon size="16">mdi-pencil-outline</v-icon>
              </button>
              <button
                class="tn-icon-btn tn-icon-btn--danger"
                title="Supprimer"
                @click="openDelete(c)"
              >
                <v-icon size="16">mdi-delete-outline</v-icon>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- === DRAWER CRÉATION / MODIFICATION CONNECTEUR === -->
    <transition name="tn-drawer">
      <div v-if="drawerOpen" class="tn-overlay" @click.self="closeDrawer">
        <aside class="tn-drawer" role="dialog" aria-modal="true">
          <header class="tn-drawer__head">
            <h2 class="tn-drawer__title">
              {{ isEditMode ? "MODIFIER LE CONNECTEUR" : "NOUVEAU CONNECTEUR" }}
            </h2>
            <button class="tn-icon-btn" title="Fermer" @click="closeDrawer">
              <v-icon size="18">mdi-close</v-icon>
            </button>
          </header>

          <div class="tn-drawer__body">
            <div class="tn-field">
              <label class="tn-label" for="pc-name">NOM</label>
              <input
                id="pc-name"
                v-model="form.name"
                class="tn-input"
                :class="{ 'tn-input--error': fieldErrors.name }"
                placeholder="FusionPBX Prod"
              />
              <p v-if="fieldErrors.name" class="tn-field-error">
                {{ fieldErrors.name }}
              </p>
            </div>

            <div class="tn-field">
              <label class="tn-label" for="pc-type">TYPE</label>
              <select id="pc-type" v-model="form.type" class="tn-input">
                <option value="ESL">ESL (FusionPBX / FreeSWITCH)</option>
                <option value="AMI">AMI (Asterisk)</option>
                <option value="TSAPI">TSAPI (Avaya / Genesys)</option>
              </select>
            </div>

            <div class="tn-field">
              <label class="tn-label" for="pc-host">HÔTE</label>
              <input
                id="pc-host"
                v-model="form.host"
                class="tn-input tn-mono"
                :class="{ 'tn-input--error': fieldErrors.host }"
                placeholder="pbx.exemple.com"
              />
              <p v-if="fieldErrors.host" class="tn-field-error">
                {{ fieldErrors.host }}
              </p>
            </div>

            <div class="tn-field">
              <label class="tn-label" for="pc-port">PORT</label>
              <input
                id="pc-port"
                v-model.number="form.port"
                type="number"
                class="tn-input tn-mono"
                :class="{ 'tn-input--error': fieldErrors.port }"
                placeholder="8021"
              />
              <p class="tn-hint">ESL : 8021 par défaut (mod_event_socket).</p>
              <p v-if="fieldErrors.port" class="tn-field-error">
                {{ fieldErrors.port }}
              </p>
            </div>

            <div class="tn-field">
              <label class="tn-label" for="pc-username">UTILISATEUR</label>
              <input
                id="pc-username"
                v-model="form.username"
                class="tn-input"
                placeholder="Requis pour AMI, inutile pour ESL"
              />
            </div>

            <div class="tn-field">
              <label class="tn-label" for="pc-password">MOT DE PASSE</label>
              <input
                id="pc-password"
                v-model="form.password"
                type="password"
                class="tn-input"
                autocomplete="new-password"
                :placeholder="
                  isEditMode ? 'Laisser vide pour ne pas changer' : ''
                "
              />
              <p class="tn-hint">
                Chiffré au repos. Requis à la création pour ESL (mot de passe
                mod_event_socket).
              </p>
            </div>

            <div v-if="isEditMode" class="tn-field">
              <label class="tn-label">STATUT</label>
              <button
                type="button"
                :class="['tn-toggle', { 'tn-toggle--on': form.is_active }]"
                role="switch"
                :aria-checked="form.is_active"
                @click="form.is_active = !form.is_active"
              >
                <span class="tn-toggle__track"
                  ><span class="tn-toggle__thumb"></span
                ></span>
                <span class="tn-toggle__text">{{
                  form.is_active ? "ACTIF" : "INACTIF"
                }}</span>
              </button>
              <p class="tn-hint">
                Un connecteur inactif est ignoré par le Core Connector au
                prochain rechargement de config.
              </p>
            </div>

            <div
              v-if="formError"
              class="tn-banner tn-banner--error tn-banner--inline"
            >
              {{ formError }}
            </div>
          </div>

          <footer class="tn-drawer__foot">
            <button
              class="tn-btn tn-btn--ghost"
              :disabled="saving"
              @click="closeDrawer"
            >
              ANNULER
            </button>
            <button
              class="tn-btn tn-btn--primary"
              :disabled="saving"
              @click="submitForm"
            >
              {{ saving ? "ENREGISTREMENT…" : "ENREGISTRER" }}
            </button>
          </footer>
        </aside>
      </div>
    </transition>

    <!-- === MODALE DOMAINES RATTACHÉS === -->
    <transition name="tn-fade">
      <div
        v-if="domainsTarget"
        class="tn-modal-overlay"
        @click.self="closeDomains"
      >
        <div class="tn-modal tn-modal--wide" role="dialog" aria-modal="true">
          <header class="tn-drawer__head">
            <h2 class="tn-drawer__title">
              DOMAINES — {{ domainsTarget.name }}
            </h2>
            <button class="tn-icon-btn" title="Fermer" @click="closeDomains">
              <v-icon size="18">mdi-close</v-icon>
            </button>
          </header>

          <div class="tn-modal__body">
            <p class="tn-hint">
              Chaque domaine PBX (ex.
              <span class="tn-mono">tenant-core.pbx.local</span>) porté par les
              événements FreeSWITCH/Asterisk est rattaché ici à un tenant
              PERMATEL, avec les files d'attente supervisées.
            </p>

            <table class="tn-table">
              <thead>
                <tr>
                  <th class="tn-th">DOMAINE PBX</th>
                  <th class="tn-th">TENANT</th>
                  <th class="tn-th">QUEUES SUPERVISÉES</th>
                  <th class="tn-th">ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="domainsLoading" class="tn-row">
                  <td colspan="4" class="tn-td">Chargement…</td>
                </tr>
                <tr
                  v-else-if="domains.length === 0"
                  class="tn-row tn-row--empty"
                >
                  <td colspan="4" class="tn-td">
                    <div class="tn-empty">
                      <p class="tn-empty__sub">Aucun domaine rattaché.</p>
                    </div>
                  </td>
                </tr>
                <tr v-for="d in domains" :key="d.id" class="tn-row">
                  <td class="tn-td tn-mono">{{ d.pbx_domain }}</td>
                  <td class="tn-td">{{ tenantName(d.tenant_id) }}</td>
                  <td class="tn-td tn-mono">
                    {{ (d.queue_ids || []).join(", ") || "—" }}
                  </td>
                  <td class="tn-td tn-td--actions">
                    <button
                      class="tn-icon-btn tn-icon-btn--danger"
                      title="Supprimer"
                      @click="removeDomain(d)"
                    >
                      <v-icon size="16">mdi-delete-outline</v-icon>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>

            <div class="pc-add-domain">
              <div class="tn-field">
                <label class="tn-label" for="pd-domain">DOMAINE PBX</label>
                <input
                  id="pd-domain"
                  v-model="newDomain.pbx_domain"
                  class="tn-input tn-mono"
                  placeholder="tenant-core.pbx.local"
                />
              </div>
              <div class="tn-field">
                <label class="tn-label" for="pd-tenant">TENANT</label>
                <select
                  id="pd-tenant"
                  v-model="newDomain.tenant_id"
                  class="tn-input"
                >
                  <option :value="null">— Sélectionner —</option>
                  <option v-for="t in tenants" :key="t.id" :value="t.id">
                    {{ t.nom }}
                  </option>
                </select>
              </div>
              <div class="tn-field">
                <label class="tn-label" for="pd-queues"
                  >QUEUES (séparées par des virgules)</label
                >
                <input
                  id="pd-queues"
                  v-model="newDomain.queue_ids_raw"
                  class="tn-input tn-mono"
                  placeholder="queue-support, queue-astreinte"
                />
              </div>
              <button
                class="tn-btn tn-btn--primary"
                :disabled="addingDomain"
                @click="addDomain"
              >
                {{ addingDomain ? "AJOUT…" : "+ RATTACHER" }}
              </button>
            </div>

            <div
              v-if="domainsError"
              class="tn-banner tn-banner--error tn-banner--inline"
            >
              {{ domainsError }}
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- === MODALE SUPPRESSION CONNECTEUR === -->
    <transition name="tn-fade">
      <div
        v-if="deleteTarget"
        class="tn-modal-overlay"
        @click.self="closeDelete"
      >
        <div class="tn-modal" role="alertdialog" aria-modal="true">
          <header class="tn-modal__head">
            <v-icon size="20" color="#fff">mdi-alert</v-icon>
            <h2 class="tn-modal__title">SUPPRIMER LE CONNECTEUR</h2>
          </header>
          <div class="tn-modal__body">
            <p class="tn-modal__warn">
              Supprimer <strong>{{ deleteTarget.name }}</strong> supprime
              également tous ses rattachements de domaines. Le Core Connector
              cessera de superviser ce PBX au prochain rechargement de config.
            </p>
            <div
              v-if="deleteError"
              class="tn-banner tn-banner--error tn-banner--inline"
            >
              {{ deleteError }}
            </div>
          </div>
          <footer class="tn-modal__foot">
            <button
              class="tn-btn tn-btn--ghost"
              :disabled="deleting"
              @click="closeDelete"
            >
              ANNULER
            </button>
            <button
              class="tn-btn tn-btn--danger"
              :disabled="deleting"
              @click="confirmDelete"
            >
              {{ deleting ? "SUPPRESSION…" : "SUPPRIMER" }}
            </button>
          </footer>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import apiClient from "@/services/http/axios";

const connectors = ref([]);
const loading = ref(false);
const loadError = ref("");
const domainsCount = reactive({});
const tenants = ref([]);

const drawerOpen = ref(false);
const isEditMode = ref(false);
const editingId = ref(null);
const saving = ref(false);
const form = reactive({
  name: "",
  type: "ESL",
  host: "",
  port: 8021,
  username: "",
  password: "",
  is_active: true,
});
const fieldErrors = reactive({ name: "", host: "", port: "" });
const formError = ref("");

const domainsTarget = ref(null);
const domains = ref([]);
const domainsLoading = ref(false);
const domainsError = ref("");
const addingDomain = ref(false);
const newDomain = reactive({
  pbx_domain: "",
  tenant_id: null,
  queue_ids_raw: "",
});

const deleteTarget = ref(null);
const deleteError = ref("");
const deleting = ref(false);

async function fetchConnectors() {
  loading.value = true;
  loadError.value = "";
  try {
    const { data } = await apiClient.get("/telephony/connectors");
    connectors.value = Array.isArray(data) ? data : [];
    await Promise.all(
      connectors.value.map(async (c) => {
        try {
          const { data: d } = await apiClient.get(
            `/telephony/connectors/${c.id}/domains`,
          );
          domainsCount[c.id] = Array.isArray(d) ? d.length : 0;
        } catch {
          domainsCount[c.id] = "—";
        }
      }),
    );
  } catch (err) {
    loadError.value =
      err?.response?.data?.error || "Impossible de charger les connecteurs.";
  } finally {
    loading.value = false;
  }
}

async function fetchTenants() {
  try {
    const { data } = await apiClient.get("/tenants");
    tenants.value = Array.isArray(data) ? data : [];
  } catch {
    tenants.value = [];
  }
}

function tenantName(id) {
  return tenants.value.find((t) => t.id === id)?.nom ?? id;
}

function resetForm() {
  form.name = "";
  form.type = "ESL";
  form.host = "";
  form.port = 8021;
  form.username = "";
  form.password = "";
  form.is_active = true;
  fieldErrors.name = "";
  fieldErrors.host = "";
  fieldErrors.port = "";
  formError.value = "";
}

function openCreate() {
  isEditMode.value = false;
  editingId.value = null;
  resetForm();
  drawerOpen.value = true;
}

function openEdit(c) {
  isEditMode.value = true;
  editingId.value = c.id;
  form.name = c.name;
  form.type = c.type;
  form.host = c.host;
  form.port = c.port;
  form.username = c.username || "";
  form.password = "";
  form.is_active = !!c.is_active;
  fieldErrors.name = "";
  fieldErrors.host = "";
  fieldErrors.port = "";
  formError.value = "";
  drawerOpen.value = true;
}

function closeDrawer() {
  if (saving.value) return;
  drawerOpen.value = false;
}

async function submitForm() {
  fieldErrors.name = "";
  fieldErrors.host = "";
  fieldErrors.port = "";
  formError.value = "";

  if (!form.name.trim()) fieldErrors.name = "Le nom est requis.";
  if (!form.host.trim()) fieldErrors.host = "L'hôte est requis.";
  if (!form.port) fieldErrors.port = "Le port est requis.";
  if (fieldErrors.name || fieldErrors.host || fieldErrors.port) return;

  const payload = {
    name: form.name.trim(),
    type: form.type,
    host: form.host.trim(),
    port: form.port,
    username: form.username.trim() || null,
    is_active: form.is_active,
  };
  if (form.password) payload.password = form.password;

  saving.value = true;
  try {
    if (isEditMode.value) {
      const { data } = await apiClient.put(
        `/telephony/connectors/${editingId.value}`,
        payload,
      );
      const idx = connectors.value.findIndex((c) => c.id === editingId.value);
      if (idx !== -1) connectors.value[idx] = data;
    } else {
      const { data } = await apiClient.post("/telephony/connectors", payload);
      connectors.value.push(data);
      domainsCount[data.id] = 0;
    }
    drawerOpen.value = false;
  } catch (err) {
    formError.value = err?.response?.data?.error || "Une erreur est survenue.";
  } finally {
    saving.value = false;
  }
}

function openDelete(c) {
  deleteTarget.value = c;
  deleteError.value = "";
}
function closeDelete() {
  if (deleting.value) return;
  deleteTarget.value = null;
}
async function confirmDelete() {
  deleting.value = true;
  deleteError.value = "";
  try {
    await apiClient.delete(`/telephony/connectors/${deleteTarget.value.id}`);
    connectors.value = connectors.value.filter(
      (c) => c.id !== deleteTarget.value.id,
    );
    deleteTarget.value = null;
  } catch (err) {
    deleteError.value =
      err?.response?.data?.error || "La suppression a échoué.";
  } finally {
    deleting.value = false;
  }
}

async function openDomains(c) {
  domainsTarget.value = c;
  domainsError.value = "";
  newDomain.pbx_domain = "";
  newDomain.tenant_id = null;
  newDomain.queue_ids_raw = "";
  domainsLoading.value = true;
  try {
    const { data } = await apiClient.get(
      `/telephony/connectors/${c.id}/domains`,
    );
    domains.value = Array.isArray(data) ? data : [];
  } catch (err) {
    domainsError.value =
      err?.response?.data?.error || "Impossible de charger les domaines.";
    domains.value = [];
  } finally {
    domainsLoading.value = false;
  }
}
function closeDomains() {
  domainsTarget.value = null;
}

async function addDomain() {
  domainsError.value = "";
  if (!newDomain.pbx_domain.trim() || !newDomain.tenant_id) {
    domainsError.value = "Le domaine PBX et le tenant sont requis.";
    return;
  }
  const queue_ids = newDomain.queue_ids_raw
    .split(",")
    .map((q) => q.trim())
    .filter(Boolean);

  addingDomain.value = true;
  try {
    const { data } = await apiClient.post(
      `/telephony/connectors/${domainsTarget.value.id}/domains`,
      {
        pbx_domain: newDomain.pbx_domain.trim(),
        tenant_id: newDomain.tenant_id,
        queue_ids,
      },
    );
    domains.value.push(data);
    domainsCount[domainsTarget.value.id] = domains.value.length;
    newDomain.pbx_domain = "";
    newDomain.tenant_id = null;
    newDomain.queue_ids_raw = "";
  } catch (err) {
    domainsError.value =
      err?.response?.data?.error || "Le rattachement a échoué.";
  } finally {
    addingDomain.value = false;
  }
}

async function removeDomain(d) {
  domainsError.value = "";
  try {
    await apiClient.delete(
      `/telephony/connectors/${domainsTarget.value.id}/domains/${d.id}`,
    );
    domains.value = domains.value.filter((x) => x.id !== d.id);
    domainsCount[domainsTarget.value.id] = domains.value.length;
  } catch (err) {
    domainsError.value =
      err?.response?.data?.error || "La suppression a échoué.";
  }
}

onMounted(() => {
  fetchConnectors();
  fetchTenants();
});
</script>

<style scoped>
/* === VARIABLES CSS PERMATEL (identique à TenantsView) === */
.tn-page {
  --color-bg: #f2f2f2;
  --color-surface: #ffffff;
  --color-authority: #000b23;
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
  transition:
    filter 0.15s,
    background 0.15s,
    border-color 0.15s;
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
  margin-top: 8px;
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
.tn-td--actions {
  white-space: nowrap;
  text-align: right;
}

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
  transition:
    background 0.12s,
    color 0.12s;
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

.tn-skel {
  display: block;
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, #ececec 25%, #f4f4f4 37%, #ececec 63%);
  background-size: 400% 100%;
  animation: tn-shimmer 1.3s ease infinite;
}
@keyframes tn-shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

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
.tn-modal--wide {
  width: 760px;
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
.tn-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid var(--color-border);
}

.pc-add-domain {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr auto;
  gap: 12px;
  align-items: end;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

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
