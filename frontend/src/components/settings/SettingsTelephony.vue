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

            <v-divider class="my-3" />

            <!-- Panneau événements ESL en temps réel (masquable, filtrable) -->
            <div class="live-head" @click="toggleLivePanel(item.id)">
              <v-icon
                size="16"
                class="live-chevron"
                :class="{ 'live-chevron--open': isLivePanelOpen(item.id) }"
              >
                mdi-chevron-right
              </v-icon>
              <span class="live-head__title">
                <span
                  class="pulse-dot"
                  :class="{
                    'pulse-dot--paused': !socketConnected || livePaused,
                  }"
                ></span>
                Événements ESL en temps réel
              </span>
              <v-chip size="x-small" variant="tonal" class="ml-2">
                {{ connectorEvents(item.id).length }}
              </v-chip>
              <v-spacer />
              <v-chip
                size="x-small"
                variant="tonal"
                :color="socketConnected ? '#22c55e' : '#9aa0aa'"
                @click.stop
              >
                <v-icon start size="8">mdi-circle</v-icon>
                {{ socketConnected ? "Connecté" : "Déconnecté" }}
              </v-chip>
              <v-btn
                :icon="
                  isLivePanelOpen(item.id)
                    ? 'mdi-eye-off-outline'
                    : 'mdi-eye-outline'
                "
                variant="text"
                size="x-small"
                :title="
                  isLivePanelOpen(item.id)
                    ? 'Masquer ce panneau'
                    : 'Afficher ce panneau'
                "
                @click.stop="toggleLivePanel(item.id)"
              />
            </div>

            <div v-if="isLivePanelOpen(item.id)" class="live-body">
              <div class="live-filters">
                <v-chip
                  v-for="def_ in EVENT_TYPE_LIST"
                  :key="def_.key"
                  size="small"
                  variant="tonal"
                  class="live-filter-chip"
                  :class="{
                    'live-filter-chip--active': liveFilters.has(def_.key),
                  }"
                  :style="{ '--chip-color': def_.color }"
                  @click="toggleLiveFilter(def_.key)"
                >
                  <span
                    class="live-filter-chip__swatch"
                    :style="{ background: def_.color }"
                  ></span>
                  {{ def_.label }}
                  <span class="live-filter-chip__count">{{
                    eventTypeCount(item.id, def_.key)
                  }}</span>
                </v-chip>
                <v-spacer />
                <v-btn
                  size="small"
                  variant="outlined"
                  class="text-none"
                  :prepend-icon="livePaused ? 'mdi-play' : 'mdi-pause'"
                  @click="togglePause"
                >
                  {{ livePaused ? "Reprendre" : "Pause" }}
                </v-btn>
                <v-btn
                  size="small"
                  variant="outlined"
                  class="text-none ml-2"
                  prepend-icon="mdi-broom"
                  @click="clearLiveEvents"
                >
                  Effacer
                </v-btn>
              </div>

              <div class="live-feed-wrap">
                <table class="live-feed">
                  <thead>
                    <tr>
                      <th>Heure</th>
                      <th>Événement</th>
                      <th>Appel / File</th>
                      <th>Statut</th>
                      <th>UUID</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="connectorEvents(item.id).length === 0">
                      <td colspan="5" class="tel-muted live-empty">
                        En attente du prochain événement PBX…
                      </td>
                    </tr>
                    <tr
                      v-for="e in connectorEvents(item.id)"
                      :key="e._receivedAt + (e.call_uuid || '')"
                    >
                      <td class="tel-mono live-time">
                        {{ formatTime(e._receivedAt) }}
                      </td>
                      <td>
                        <span
                          class="live-ev-badge"
                          :style="{
                            color: eventTypeMeta(e.event_type).color,
                            background:
                              eventTypeMeta(e.event_type).color + '1f',
                          }"
                        >
                          <span
                            class="live-filter-chip__swatch"
                            :style="{
                              background: eventTypeMeta(e.event_type).color,
                            }"
                          ></span>
                          {{ eventTypeMeta(e.event_type).label }}
                        </span>
                      </td>
                      <td>
                        <span v-if="e.caller || e.callee"
                          >{{ e.caller || "?" }} → {{ e.callee || "?" }}</span
                        >
                        <span v-else-if="e.queue_id"
                          >file {{ e.queue_id }}</span
                        >
                        <span v-else class="tel-muted">—</span>
                      </td>
                      <td class="tel-muted">
                        {{
                          STATUS_LABEL[e.call_status] || e.call_status || "—"
                        }}
                      </td>
                      <td class="tel-mono live-uuid">
                        {{ (e.call_uuid || "").slice(0, 13) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
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
import { ref, reactive, onMounted, onUnmounted } from "vue";
import apiClient from "@/services/http/axios";
import { useTelephonySocket } from "@/composables/useTelephonySocket";

const connectors = ref([]);
const domainsByConnector = reactive({});
const expanded = ref([]);
const loading = ref(false);
const feedback = reactive({ text: "", type: "success" });

// ── Événements ESL en temps réel (namespace /telephony, room = tenant) ────
const telephonySocket = useTelephonySocket();
const socketConnected = telephonySocket.connected;
const livePaused = ref(false);
const pausedSnapshot = ref(null); // copie figée de telephonySocket.events pendant la pause
const openLivePanels = reactive({}); // connector.id -> bool, replié par défaut

const EVENT_TYPE_LIST = [
  { key: "CHANNEL_CREATE", label: "Création", color: "#f59e0b" },
  { key: "CHANNEL_PROGRESS_MEDIA", label: "Sonnerie", color: "#0ea5e9" },
  { key: "CHANNEL_ANSWER", label: "Décroché", color: "#22c55e" },
  { key: "CHANNEL_HANGUP_COMPLETE", label: "Raccroché", color: "#6b7280" },
  { key: "CALLCENTER_QUEUE_ENTER", label: "Entrée file", color: "#8b5cf6" },
  {
    key: "CALLCENTER_AGENT_STATE_CHANGE",
    label: "État agent",
    color: "#00a8a8",
  },
];
const EVENT_TYPE_MAP = Object.fromEntries(
  EVENT_TYPE_LIST.map((d) => [d.key, d]),
);
const liveFilters = reactive(new Set(EVENT_TYPE_LIST.map((d) => d.key)));

const STATUS_LABEL = {
  ringing: "En sonnerie",
  early_media: "Pré-décroché",
  answered: "En cours",
  ended: "Terminé",
  missed: "Manqué",
  on_hold: "En attente",
  abandoned: "Abandonné",
  technical_failure: "Échec technique",
};

function eventTypeMeta(type) {
  return EVENT_TYPE_MAP[type] || { label: type || "?", color: "#9aa0aa" };
}
function isLivePanelOpen(connectorId) {
  return !!openLivePanels[connectorId];
}
function toggleLivePanel(connectorId) {
  openLivePanels[connectorId] = !openLivePanels[connectorId];
}
function toggleLiveFilter(key) {
  if (liveFilters.has(key)) liveFilters.delete(key);
  else liveFilters.add(key);
}
function clearLiveEvents() {
  telephonySocket.clear();
  pausedSnapshot.value = livePaused.value ? [] : null;
}
function togglePause() {
  pausedSnapshot.value = livePaused.value
    ? null
    : telephonySocket.events.value.slice();
  livePaused.value = !livePaused.value;
}
function connectorEvents(connectorId) {
  const source =
    livePaused.value && pausedSnapshot.value
      ? pausedSnapshot.value
      : telephonySocket.events.value;
  return source
    .filter(
      (e) =>
        e.pbx_connector_id === connectorId && liveFilters.has(e.event_type),
    )
    .slice()
    .reverse();
}
function eventTypeCount(connectorId, key) {
  return telephonySocket.events.value.filter(
    (e) => e.pbx_connector_id === connectorId && e.event_type === key,
  ).length;
}
function formatTime(ts) {
  return new Date(ts).toLocaleTimeString("fr-FR", { hour12: false });
}

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

onMounted(() => {
  fetchConnectors();
  telephonySocket.connect();
});
onUnmounted(() => {
  telephonySocket.disconnect();
});
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

/* ── Événements ESL en temps réel ── */
.live-head {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  padding: 6px 4px;
  border-radius: 6px;
}
.live-head:hover {
  background: #eef0f3;
}
.live-chevron {
  color: #9aa0aa;
  transition: transform 0.18s ease;
}
.live-chevron--open {
  transform: rotate(90deg);
}
.live-head__title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: #1a1a2e;
}
.pulse-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.6);
  animation: tel-pulse 1.8s infinite;
}
.pulse-dot--paused {
  background: #9aa0aa;
  animation: none;
}
@keyframes tel-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.55);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(34, 197, 94, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0);
  }
}

.live-body {
  margin-top: 8px;
}
.live-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px;
  background: #fafafa;
  border: 1px solid #eceef1;
  border-radius: 8px 8px 0 0;
  border-bottom: none;
}
.live-filter-chip {
  cursor: pointer;
  opacity: 0.55;
  transition: opacity 0.15s ease;
}
.live-filter-chip--active {
  opacity: 1;
  color: var(--chip-color);
}
.live-filter-chip__swatch {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 4px;
}
.live-filter-chip__count {
  font-family: "Fira Code", ui-monospace, monospace;
  font-size: 10px;
  opacity: 0.75;
  margin-left: 4px;
}

.live-feed-wrap {
  max-height: 260px;
  overflow-y: auto;
  overflow-x: auto;
  border: 1px solid #eceef1;
  border-radius: 0 0 8px 8px;
}
.live-feed {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}
.live-feed thead th {
  position: sticky;
  top: 0;
  text-align: left;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #9aa0aa;
  background: #fff;
  padding: 6px 8px;
  border-bottom: 1px solid #eceef1;
  white-space: nowrap;
}
.live-feed tbody tr {
  border-bottom: 1px solid #f2f2f2;
}
.live-feed td {
  padding: 5px 8px;
  vertical-align: middle;
}
.live-time {
  color: #9aa0aa;
  white-space: nowrap;
  font-size: 10.5px;
}
.live-uuid {
  color: #9aa0aa;
  font-size: 10px;
}
.live-empty {
  text-align: center;
  padding: 20px 8px !important;
}
.live-ev-badge {
  display: inline-flex;
  align-items: center;
  font-size: 9.5px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
}
</style>
