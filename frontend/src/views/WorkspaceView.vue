<template>
  <!-- ╔══════════════════════════════════════════════════════════════════════╗ -->
  <!-- ║  PERMATEL OPS — WORKSPACE AGENT                                    ║ -->
  <!-- ║  Zone de travail : identification contact + canal + interaction     ║ -->
  <!-- ╚══════════════════════════════════════════════════════════════════════╝ -->
  <div class="workspace-root">

    <!-- ══════════════════════════════════════════════════════════════════════
         COLONNE GAUCHE — Recherche contact + Historique
         ══════════════════════════════════════════════════════════════════════ -->
    <aside class="ws-left-col">

      <ContactSearchPanel
        :contacts="contacts"
        :is-searching="isSearching"
        :search-error="searchError"
        :selected-contact-id="selectedContact?.id ?? null"
        :has-searched="hasSearched"
        @search="onSearch"
        @contact-selected="onContactSelected"
      />

      <WorkspaceOpenDemandes ref="openDemandesRef" @select="onSelectDemande" />

    </aside>

    <!-- ══════════════════════════════════════════════════════════════════════
         COLONNE DROITE — Onglets canal + Panneau principal
         ══════════════════════════════════════════════════════════════════════ -->
    <main class="ws-right-col">

      <!-- Sélecteur de canal (onglets pilotés par les canaux du tenant) -->
      <ChannelTabs
        :selected-channel="selectedChannel"
        :tabs="visibleTabs"
        @change="onChannelChange"
      />

      <!-- Panneau principal -->
      <div class="ws-main-panel">

        <!-- ── Canal MAIL (visible seulement si canal email + SMTP/IMAP configurés) ── -->
        <template v-if="selectedChannel === 'mail'">
          <MailChannel :initial-contact="composeContact" />
        </template>

        <!-- ── Canal CHAT (visible si canal chat activé) ─────────────────── -->
        <template v-else-if="selectedChannel === 'chat'">
          <ChatBox />
        </template>

        <!-- ── Canal WORKSPACE (par défaut) ─────────────────────────────── -->
        <template v-else>
          <!-- Création d'une demande (avec OU sans contact) -->
          <div v-if="activeDemandeType" class="ws-form-area ws-form-area--filled">
            <v-slide-y-transition>
              <component
                :is="FORM_COMPONENTS[activeDemandeType]"
                :key="activeDemandeType"
                :contact-id="selectedContact?.id ?? null"
                @submitted="onDemandeSubmitted"
                @cancel="activeDemandeType = null"
              />
            </v-slide-y-transition>
          </div>

          <!-- État vide — aucun contact + bouton nouvelle demande -->
          <WorkspaceEmptyState v-else-if="!selectedContact" @new-demande="onNewDemande" />

          <!-- Panneau actif — contact identifié -->
          <div v-else class="ws-active-content">
            <SelectedContactBanner
              :contact="bannerContact"
              :loading="historyLoading"
              :can-create-demande="true"
              @email="onAction('email')"
              @call="onAction('call')"
              @new-demande="onNewDemande"
            />
            <div class="ws-form-area">
              <DemandesListPanel
                :contact-id="selectedContact?.id ?? null"
                :contact-nom="selectedContact?.fullName ?? null"
                :key="`dlp-${selectedContact?.id}-${demandeListKey}`"
                @refresh="demandeListKey++"
              />
            </div>
          </div>
        </template>

      </div>

    </main>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAuthStore }           from '@/store/auth'
import ContactSearchPanel        from '@/components/workspace/ContactSearchPanel.vue'
import WorkspaceOpenDemandes     from '@/components/workspace/WorkspaceOpenDemandes.vue'
import ChannelTabs               from '@/components/workspace/ChannelTabs.vue'
import WorkspaceEmptyState       from '@/components/workspace/WorkspaceEmptyState.vue'
import SelectedContactBanner     from '@/components/workspace/SelectedContactBanner.vue'
import { searchContacts }        from '@/services/contactService'
import apiClient                  from '@/services/http/axios'
import DemandeAnomalieForm        from '@/components/workspace/forms/DemandeAnomalieForm.vue'
import DemandeCommandeForm        from '@/components/workspace/forms/DemandeCommandeForm.vue'
import DemandeAdminForm           from '@/components/workspace/forms/DemandeAdminForm.vue'
import DemandePlanningForm        from '@/components/workspace/forms/DemandePlanningForm.vue'
import DemandesListPanel          from '@/components/workspace/DemandesListPanel.vue'
import ChatBox                    from '@/components/workspace/ChatBox.vue'
import MailChannel               from '@/components/workspace/MailChannel.vue'
import '@/assets/styles/crud-view.css'
import '@/assets/styles/workspace.css'

const FORM_COMPONENTS = {
  anomalie: DemandeAnomalieForm,
  commande: DemandeCommandeForm,
  admin:    DemandeAdminForm,
  planning: DemandePlanningForm,
}

function resolveAvatarUrl(relativeUrl) {
  if (!relativeUrl) return ''
  try {
    const backendUrl = new URL(apiClient.defaults.baseURL)
    return `${backendUrl.protocol}//${backendUrl.host}${relativeUrl}`
  } catch {
    return relativeUrl
  }
}

function normalizeContact(c) {
  const fullName = [c.prenom, c.nom].filter(Boolean).join(' ')
  return {
    id:          c.id,
    name:        fullName || c.email || `#${c.id}`,
    phone:       c.telephone ?? '',
    status:      'active',
    fullName:    fullName || '—',
    jobTitle:    c.fonction ?? '—',
    contactId:   `ID-${c.id}`,
    avatarUrl:   resolveAvatarUrl(c.avatar_url),
    statusColor: 'teal',
    email:       c.email ?? null,
  }
}

const MOCK_HISTORY = [
  {
    id: 1,
    role: 'client',
    text: "Bonjour, j'ai une coupure totale d'internet depuis ce matin. Ma box clignote en rouge.",
    time: '10:45:14',
    type: 'TRANSCRIPTION',
  },
  {
    id: 2,
    role: 'agent',
    text: "Bien reçu. Je détecte effectivement une alerte sur votre secteur. Je lance un diagnostic à distance.",
    time: '10:45:38',
    type: 'AUDIO',
  },
  {
    id: 3,
    role: 'client',
    text: "D'accord. Ça fait combien de temps en moyenne pour que ça revienne ?",
    time: '10:46:02',
    type: 'TRANSCRIPTION',
  },
  {
    id: 4,
    role: 'agent',
    text: "Selon le diagnostic, l'incident devrait être résolu sous 30 à 45 minutes. Je vous envoie un SMS de confirmation dès la restauration.",
    time: '10:46:21',
    type: 'AUDIO',
  },
]

// ─── État local ────────────────────────────────────────────────────────────
const contacts             = ref([])
const isSearching          = ref(false)
const searchError          = ref('')
const hasSearched          = ref(false)
const selectedContact      = ref(null)

const activeDemandeType    = ref(null)
const demandeListKey       = ref(0)

const selectedChannel      = ref('workspace')
const composeContact       = ref(null)  // contact pré-rempli pour le composer email
const openDemandesRef      = ref(null)  // réf du panneau "demandes en cours" (gauche)

// ─── Onglets pilotés par les canaux du tenant (source : backend, store) ──────
const authStore = useAuthStore()
const ALL_TABS = [
  { key: 'workspace', label: 'WORKSPACE', icon: 'mdi-headset' },
  { key: 'mail', label: 'MAIL', icon: 'mdi-email-outline' },
  { key: 'chat', label: 'CHAT', icon: 'mdi-message-text-outline' },
]
const visibleTabs = computed(() => {
  const wt = authStore.featureMap.workspace_tabs || {}
  return ALL_TABS.filter((t) => t.key === 'workspace' || wt[t.key] === true)
})

// Si le canal courant devient invisible (toggle off / changement de tenant), retomber sur Workspace.
watch(visibleTabs, (tabs) => {
  if (!tabs.some((t) => t.key === selectedChannel.value)) selectedChannel.value = 'workspace'
})

onMounted(() => {
  // S'assure que les disponibilités sont à jour pour le tenant actif.
  if (!authStore.features) authStore.fetchFeatures()
})

const communicationHistory = ref([])
const historyLoading       = ref(false)

const channelMeta = computed(() => ({
  channel:   selectedContact.value ? 'WORKSPACE' : '',
  sessionId: selectedContact.value ? 'A1'        : '',
}))

// ─── Recherche ─────────────────────────────────────────────────────────────
async function onSearch({ name, phone }) {
  isSearching.value = true
  searchError.value = ''
  hasSearched.value = true
  contacts.value    = []

  try {
    const { contacts: raw } = await searchContacts({ name, phone })
    contacts.value = raw.map(normalizeContact)
  } catch (err) {
    const status = err?.response?.status
    searchError.value =
      status === 401 ? 'Session expirée, veuillez vous reconnecter.'
      : status === 403 ? 'Accès non autorisé.'
      : 'Une erreur est survenue lors de la recherche.'
  } finally {
    isSearching.value = false
  }
}

// ─── Sélection contact ─────────────────────────────────────────────────────
function onNewDemande(type) {
  activeDemandeType.value = type
}

function onDemandeSubmitted(demande) {
  activeDemandeType.value = null
  demandeListKey.value++
  openDemandesRef.value?.reload?.()   // rafraîchit la liste des demandes en cours
  console.log('[Workspace] demande créée →', demande.numero_ticket)
}

// Sélection d'une demande dans la liste de gauche → charge son contact
function onSelectDemande(d) {
  activeDemandeType.value = null
  if (d.contact_id) {
    selectedContact.value = {
      id: d.contact_id,
      contactId: `ID-${d.contact_id}`,
      name: d.contact_nom || `#${d.contact_id}`,
      fullName: d.contact_nom || '—',
      status: 'active',
    }
  }
}

function onContactSelected(contact) {
  selectedContact.value      = contact
  activeDemandeType.value    = null
  communicationHistory.value = []
  historyLoading.value       = true

  setTimeout(() => {
    communicationHistory.value = MOCK_HISTORY
    historyLoading.value       = false
  }, 800)
}

// ─── Changement de canal ────────────────────────────────────────────────────
function onChannelChange(channel) {
  selectedChannel.value = channel
}

// ─── Contact formaté pour le banner ───────────────────────────────────────
const bannerContact = computed(() => {
  const c = selectedContact.value
  if (!c) return null
  return {
    id:          c.contactId ?? `ID-${c.id}`,
    fullName:    c.fullName  ?? c.name,
    jobTitle:    c.jobTitle  ?? '—',
    avatarUrl:   c.avatarUrl ?? '',
    statusColor: c.statusColor ?? (c.status === 'active' ? 'teal' : 'gray'),
    statusLabel: c.status === 'active' ? 'En ligne' : 'Hors ligne',
  }
})

// ─── Actions rapides du banner ─────────────────────────────────────────────
function onAction(type) {
  if (type === 'email') {
    const c = selectedContact.value
    composeContact.value = c
      ? { id: c.id, fullName: c.fullName, email: c.email }
      : null
    selectedChannel.value = 'mail'
    return
  }
  console.log(`[Workspace] action → ${type}`, selectedContact.value)
}
</script>

<script>
export default { name: 'WorkspaceView' }
</script>
