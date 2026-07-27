<template>
  <v-card variant="flat" class="tel-card" rounded="lg" border>
    <div class="tel-head">
      <div>
        <h2 class="tel-title">Téléphonie</h2>
        <p class="tel-sub">
          Connecteur PBX de votre organisation (ESL/AMI), domaines rattachés et
          files d'attente supervisées dans le Workspace.
        </p>
      </div>
      <v-btn
        color="#00a8a8"
        variant="flat"
        size="small"
        class="text-none"
        prepend-icon="mdi-plus"
        @click="openCreateConnector"
      >
        Nouveau connecteur
      </v-btn>
    </div>

    <v-divider />

    <v-alert
      v-if="feedback.text"
      :type="feedback.type"
      variant="tonal"
      density="compact"
      class="ma-3"
      closable
      @click:close="feedback.text = ''"
    >
      {{ feedback.text }}
    </v-alert>

    <div v-if="!loading && connectors.length === 0" class="tel-empty">
      <v-icon size="28" color="#cbd0d6">mdi-phone-off-outline</v-icon>
      <p class="tel-empty__text">
        Aucun connecteur PBX configuré pour votre organisation. Créez-en un avec
        le bouton « Nouveau connecteur ».
      </p>
    </div>

    <v-data-table
      v-else
      v-model:expanded="expanded"
      :headers="headers"
      :items="connectors"
      :loading="loading"
      density="comfortable"
      items-per-page="25"
      show-expand
      item-value="id"
      class="tel-table"
    >
      <template #[`item.name`]="{ item }">
        {{ item.name }}
        <v-chip size="x-small" variant="tonal" class="ml-1">{{
          item.type
        }}</v-chip>
      </template>
      <template #[`item.host`]="{ item }">
        <span class="tel-mono">{{ item.host }}:{{ item.port }}</span>
      </template>
      <template #[`item.status`]="{ item }">
        <v-chip size="small" variant="tonal" :color="statusColor(item)">
          <v-icon start size="10">mdi-circle</v-icon>
          {{ statusLabel(item) }}
        </v-chip>
      </template>
      <template #[`item.actions`]="{ item }">
        <v-btn
          icon="mdi-sync"
          variant="text"
          size="x-small"
          title="Forcer la reconnexion"
          :loading="syncingId === item.id"
          @click="sync(item)"
        />
        <v-btn
          icon="mdi-pencil-outline"
          variant="text"
          size="x-small"
          @click="openEditConnector(item)"
        />
        <v-btn
          icon="mdi-delete-outline"
          variant="text"
          size="x-small"
          color="#e74c3c"
          @click="removeConnector(item)"
        />
      </template>

      <!-- Sous-ligne : statut détaillé de l'adapter + domaines rattachés -->
      <template #expanded-row="{ columns, item }">
        <tr>
          <td :colspan="columns.length" class="tel-expand">
            <div class="tel-adapter-status">
              <div class="tel-adapter-status__row">
                <span class="tel-adapter-status__label">ADAPTER</span>
                <v-chip size="small" variant="tonal" :color="statusColor(item)">
                  <v-icon start size="10">mdi-circle</v-icon>
                  {{ statusLabel(item) }}
                </v-chip>
              </div>
              <div class="tel-adapter-status__row">
                <span class="tel-adapter-status__label">DERNIÈRE ACTIVITÉ</span>
                <span>{{ formatDate(item.last_seen_at) }}</span>
              </div>
              <div v-if="item.last_error" class="tel-adapter-status__row">
                <span class="tel-adapter-status__label">DERNIÈRE ERREUR</span>
                <span class="tel-error-text">{{ item.last_error }}</span>
              </div>
            </div>

            <v-divider class="my-3" />

            <div class="tel-domains-head">
              <span class="tel-domains-head__title"
                >DOMAINES PBX RATTACHÉS</span
              >
            </div>

            <table class="tel-domains-table">
              <thead>
                <tr>
                  <th>Domaine PBX</th>
                  <th>Files d'attente supervisées</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!domainsByConnector[item.id]?.length">
                  <td colspan="3" class="tel-muted">Aucun domaine rattaché.</td>
                </tr>
                <tr v-for="d in domainsByConnector[item.id]" :key="d.id">
                  <td class="tel-mono">{{ d.pbx_domain }}</td>
                  <td>
                    <v-chip
                      v-for="q in d.queue_ids"
                      :key="q"
                      size="x-small"
                      variant="tonal"
                      class="mr-1 mb-1"
                    >
                      {{ q }}
                    </v-chip>
                    <span v-if="!d.queue_ids?.length" class="tel-muted"
                      >Aucune</span
                    >
                  </td>
                  <td class="tel-domains-table__actions">
                    <v-btn
                      icon="mdi-pencil-outline"
                      variant="text"
                      size="x-small"
                      @click="openEditDomain(item, d)"
                    />
                    <v-btn
                      icon="mdi-delete-outline"
                      variant="text"
                      size="x-small"
                      color="#e74c3c"
                      @click="removeDomain(item, d)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>

            <v-btn
              variant="text"
              size="small"
              class="text-none mt-2"
              prepend-icon="mdi-plus"
              @click="openCreateDomain(item)"
            >
              Ajouter un domaine
            </v-btn>
          </td>
        </tr>
      </template>
    </v-data-table>

    <!-- Dialog création / édition connecteur -->
    <v-dialog v-model="connectorDialog" max-width="480">
      <v-card rounded="lg">
        <v-card-title class="tel-dlg-title">
          {{
            editingConnector ? "Modifier le connecteur" : "Nouveau connecteur"
          }}
        </v-card-title>
        <v-divider />
        <v-card-text>
          <v-alert
            v-if="connectorFormError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ connectorFormError }}
          </v-alert>
          <v-text-field
            v-model="connectorForm.name"
            label="Nom"
            variant="outlined"
            density="comfortable"
          />
          <v-select
            v-model="connectorForm.type"
            :items="['ESL', 'AMI', 'TSAPI']"
            label="Type"
            variant="outlined"
            density="comfortable"
          />
          <div class="tel-row">
            <v-text-field
              v-model="connectorForm.host"
              label="Hôte"
              variant="outlined"
              density="comfortable"
            />
            <v-text-field
              v-model.number="connectorForm.port"
              type="number"
              label="Port"
              variant="outlined"
              density="comfortable"
            />
          </div>
          <v-text-field
            v-model="connectorForm.username"
            label="Utilisateur (AMI)"
            variant="outlined"
            density="comfortable"
          />
          <v-text-field
            v-model="connectorForm.password"
            type="password"
            autocomplete="new-password"
            :label="
              editingConnector
                ? 'Mot de passe (laisser vide pour ne pas changer)'
                : 'Mot de passe'
            "
            variant="outlined"
            density="comfortable"
          />
          <v-switch
            v-if="editingConnector"
            v-model="connectorForm.is_active"
            color="#00a8a8"
            label="Actif"
            hide-details
          />
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-btn
            variant="text"
            class="text-none"
            @click="connectorDialog = false"
            >Annuler</v-btn
          >
          <v-spacer />
          <v-btn
            :loading="savingConnector"
            color="#00a8a8"
            class="text-none"
            @click="saveConnector"
          >
            Enregistrer
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Dialog création / édition domaine -->
    <v-dialog v-model="domainDialog" max-width="480">
      <v-card rounded="lg">
        <v-card-title class="tel-dlg-title">
          {{ editingDomain ? "Modifier le domaine" : "Nouveau domaine PBX" }}
        </v-card-title>
        <v-divider />
        <v-card-text>
          <v-alert
            v-if="domainFormError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ domainFormError }}
          </v-alert>
          <v-text-field
            v-if="!editingDomain"
            v-model="domainForm.pbx_domain"
            label="Domaine PBX"
            hint="Tel que porté par les événements FreeSWITCH (variable_domain_name)."
            persistent-hint
            variant="outlined"
            density="comfortable"
          />
          <v-combobox
            v-model="domainForm.queue_ids"
            label="Files d'attente supervisées (Entrée pour ajouter)"
            variant="outlined"
            density="comfortable"
            class="mt-3"
            multiple
            chips
            closable-chips
            hint="Identifiant tel que défini côté PBX (ex. queue-support)."
            persistent-hint
          />
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-btn variant="text" class="text-none" @click="domainDialog = false"
            >Annuler</v-btn
          >
          <v-spacer />
          <v-btn
            :loading="savingDomain"
            color="#00a8a8"
            class="text-none"
            @click="saveDomain"
          >
            Enregistrer
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import apiClient from "@/services/http/axios";

const connectors = ref([]);
const domainsByConnector = reactive({});
const expanded = ref([]);
const loading = ref(false);
const feedback = reactive({ text: "", type: "success" });

const headers = [
  { title: "Nom", key: "name" },
  { title: "Hôte", key: "host" },
  { title: "Statut", key: "status", sortable: false },
  { title: "", key: "actions", sortable: false, align: "end" },
];

function statusColor(item) {
  if (item.is_connected === true) return "#22c55e";
  if (item.is_connected === false) return "#e74c3c";
  return "#9aa0aa";
}
function statusLabel(item) {
  if (item.is_connected === true) return "Connecté";
  if (item.is_connected === false) return "Déconnecté";
  return "Jamais rapporté";
}
function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("fr-FR");
}

async function fetchConnectors() {
  loading.value = true;
  try {
    const { data } = await apiClient.get("/telephony/connectors");
    connectors.value = Array.isArray(data) ? data : [];
    await Promise.all(connectors.value.map((c) => fetchDomains(c.id)));
  } catch (err) {
    feedback.type = "error";
    feedback.text =
      err?.response?.data?.error ||
      "Impossible de charger la configuration téléphonie.";
  } finally {
    loading.value = false;
  }
}

async function fetchDomains(connectorId) {
  try {
    const { data } = await apiClient.get(
      `/telephony/connectors/${connectorId}/domains`,
    );
    domainsByConnector[connectorId] = Array.isArray(data) ? data : [];
  } catch {
    domainsByConnector[connectorId] = [];
  }
}

// ── Connecteur : création / édition / suppression / sync ──────────────────

const connectorDialog = ref(false);
const editingConnector = ref(null);
const savingConnector = ref(false);
const connectorFormError = ref("");
const connectorForm = reactive({
  name: "",
  type: "ESL",
  host: "",
  port: 8021,
  username: "",
  password: "",
  is_active: true,
});
const syncingId = ref(null);

function openCreateConnector() {
  editingConnector.value = null;
  Object.assign(connectorForm, {
    name: "",
    type: "ESL",
    host: "",
    port: 8021,
    username: "",
    password: "",
    is_active: true,
  });
  connectorFormError.value = "";
  connectorDialog.value = true;
}

function openEditConnector(connector) {
  editingConnector.value = connector;
  Object.assign(connectorForm, {
    name: connector.name,
    type: connector.type,
    host: connector.host,
    port: connector.port,
    username: connector.username || "",
    password: "",
    is_active: !!connector.is_active,
  });
  connectorFormError.value = "";
  connectorDialog.value = true;
}

async function saveConnector() {
  connectorFormError.value = "";
  if (
    !connectorForm.name.trim() ||
    !connectorForm.host.trim() ||
    !connectorForm.port
  ) {
    connectorFormError.value = "Nom, hôte et port sont requis.";
    return;
  }
  const payload = {
    name: connectorForm.name.trim(),
    type: connectorForm.type,
    host: connectorForm.host.trim(),
    port: connectorForm.port,
    username: connectorForm.username.trim() || null,
  };
  if (editingConnector.value) payload.is_active = connectorForm.is_active;
  if (connectorForm.password) payload.password = connectorForm.password;

  savingConnector.value = true;
  try {
    if (editingConnector.value) {
      const { data } = await apiClient.put(
        `/telephony/connectors/${editingConnector.value.id}`,
        payload,
      );
      const idx = connectors.value.findIndex(
        (c) => c.id === editingConnector.value.id,
      );
      if (idx !== -1) connectors.value[idx] = data;
    } else {
      const { data } = await apiClient.post("/telephony/connectors", payload);
      connectors.value.push(data);
      domainsByConnector[data.id] = [];
    }
    connectorDialog.value = false;
  } catch (err) {
    connectorFormError.value =
      err?.response?.data?.error || "Une erreur est survenue.";
  } finally {
    savingConnector.value = false;
  }
}

async function removeConnector(connector) {
  if (
    !window.confirm(
      `Supprimer le connecteur « ${connector.name} » ? Le Core Connector cessera de le superviser.`,
    )
  ) {
    return;
  }
  try {
    await apiClient.delete(`/telephony/connectors/${connector.id}`);
    connectors.value = connectors.value.filter((c) => c.id !== connector.id);
    delete domainsByConnector[connector.id];
  } catch (err) {
    feedback.type = "error";
    feedback.text = err?.response?.data?.error || "La suppression a échoué.";
  }
}

async function sync(connector) {
  syncingId.value = connector.id;
  try {
    const { data } = await apiClient.post(
      `/telephony/connectors/${connector.id}/sync`,
    );
    const idx = connectors.value.findIndex((c) => c.id === connector.id);
    if (idx !== -1) connectors.value[idx] = data;
    feedback.type = "success";
    feedback.text = "Reconnexion demandée — appliquée sous quelques secondes.";
  } catch (err) {
    feedback.type = "error";
    feedback.text =
      err?.response?.data?.error || "La demande de synchronisation a échoué.";
  } finally {
    syncingId.value = null;
  }
}

// ── Domaine PBX : création / édition / suppression ─────────────────────────

const domainDialog = ref(false);
const editingDomain = ref(null);
const editingDomainConnectorId = ref(null);
const savingDomain = ref(false);
const domainFormError = ref("");
const domainForm = reactive({ pbx_domain: "", queue_ids: [] });

function openCreateDomain(connector) {
  editingDomain.value = null;
  editingDomainConnectorId.value = connector.id;
  Object.assign(domainForm, { pbx_domain: "", queue_ids: [] });
  domainFormError.value = "";
  domainDialog.value = true;
}

function openEditDomain(connector, domain) {
  editingDomain.value = domain;
  editingDomainConnectorId.value = connector.id;
  Object.assign(domainForm, {
    pbx_domain: domain.pbx_domain,
    queue_ids: [...(domain.queue_ids || [])],
  });
  domainFormError.value = "";
  domainDialog.value = true;
}

async function saveDomain() {
  domainFormError.value = "";
  const connectorId = editingDomainConnectorId.value;

  savingDomain.value = true;
  try {
    if (editingDomain.value) {
      const { data } = await apiClient.put(
        `/telephony/connectors/${connectorId}/domains/${editingDomain.value.id}`,
        { queue_ids: domainForm.queue_ids },
      );
      const idx = domainsByConnector[connectorId].findIndex(
        (d) => d.id === editingDomain.value.id,
      );
      if (idx !== -1) domainsByConnector[connectorId][idx] = data;
    } else {
      if (!domainForm.pbx_domain.trim()) {
        domainFormError.value = "Le domaine PBX est requis.";
        savingDomain.value = false;
        return;
      }
      const { data } = await apiClient.post(
        `/telephony/connectors/${connectorId}/domains`,
        {
          pbx_domain: domainForm.pbx_domain.trim(),
          queue_ids: domainForm.queue_ids,
        },
      );
      domainsByConnector[connectorId].push(data);
    }
    domainDialog.value = false;
  } catch (err) {
    domainFormError.value =
      err?.response?.data?.error || "Une erreur est survenue.";
  } finally {
    savingDomain.value = false;
  }
}

async function removeDomain(connector, domain) {
  if (!window.confirm(`Supprimer le domaine « ${domain.pbx_domain} » ?`))
    return;
  try {
    await apiClient.delete(
      `/telephony/connectors/${connector.id}/domains/${domain.id}`,
    );
    domainsByConnector[connector.id] = domainsByConnector[connector.id].filter(
      (d) => d.id !== domain.id,
    );
  } catch (err) {
    feedback.type = "error";
    feedback.text = err?.response?.data?.error || "La suppression a échoué.";
  }
}

onMounted(fetchConnectors);
</script>

<style scoped>
.tel-card {
  font-family: "Fira Sans", sans-serif;
}
.tel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
}
.tel-title {
  font-size: 15px;
  font-weight: 700;
  color: #000b23;
  margin: 0;
}
.tel-sub {
  font-size: 12.5px;
  color: #6b7280;
  margin: 2px 0 0;
  max-width: 560px;
  line-height: 1.5;
}
.tel-muted {
  font-size: 12px;
  color: #9aa0aa;
}
.tel-mono {
  font-family: "Fira Code", ui-monospace, monospace;
  font-size: 12.5px;
}
.tel-dlg-title {
  font-size: 15px;
  font-weight: 700;
  color: #000b23;
}
.tel-row {
  display: flex;
  gap: 12px;
}
.tel-row > * {
  flex: 1;
}

.tel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 20px;
  text-align: center;
}
.tel-empty__text {
  font-size: 12.5px;
  color: #6b7280;
  max-width: 420px;
  margin: 0;
}

.tel-expand {
  background: #fafafa;
  padding: 16px 20px !important;
}
.tel-adapter-status {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tel-adapter-status__row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12.5px;
}
.tel-adapter-status__label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #9aa0aa;
  min-width: 130px;
}
.tel-error-text {
  color: #e74c3c;
  font-family: "Fira Code", ui-monospace, monospace;
  font-size: 11.5px;
}

.tel-domains-head__title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #9aa0aa;
}
.tel-domains-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
  font-size: 12.5px;
}
.tel-domains-table th {
  text-align: left;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #9aa0aa;
  padding: 4px 8px;
}
.tel-domains-table td {
  padding: 6px 8px;
  border-top: 1px solid #eceef1;
}
.tel-domains-table__actions {
  white-space: nowrap;
  text-align: right;
}
</style>
