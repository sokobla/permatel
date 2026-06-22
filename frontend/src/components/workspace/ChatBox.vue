<template>
  <div class="cbx-root">

    <!-- ══ SIDEBAR ══════════════════════════════════════════════════════════ -->
    <aside :class="['cbx-sidebar', { 'cbx-sidebar--full': !activeConversation }]">

      <div class="cbx-brand">Messagerie Opérationnelle</div>

      <!-- Search -->
      <div class="cbx-search">
        <input
          v-model="searchQuery"
          class="cbx-search__input"
          placeholder="Search"
          autocomplete="off"
        />
        <v-icon size="14" color="#bbb" class="cbx-search__icon">mdi-magnify</v-icon>
      </div>

      <!-- Channels -->
      <div class="cbx-section">
        <div class="cbx-section-hdr">
          <span class="cbx-section-lbl">CHANNELS</span>
          <button class="cbx-section-add" title="Nouveau salon">
            <v-icon size="13">mdi-plus</v-icon>
          </button>
        </div>
        <button
          v-for="ch in filteredChannels"
          :key="ch.id"
          class="cbx-channel-item"
          :class="{ 'cbx-channel-item--active': activeChannelId === ch.id }"
          @click="selectChannel(ch)"
        >
          <span class="cbx-ch-hash">#</span>
          <span class="cbx-ch-name">{{ ch.name }}</span>
          <span v-if="ch.unread" class="cbx-ch-badge">{{ ch.unread }}</span>
        </button>
      </div>

      <!-- Messages Directs -->
      <div class="cbx-section">
        <div class="cbx-section-hdr">
          <span class="cbx-section-lbl">MESSAGES DIRECTS</span>
          <button class="cbx-section-add" title="Nouveau message direct">
            <v-icon size="13">mdi-plus</v-icon>
          </button>
        </div>
        <button
          v-for="dm in filteredDMs"
          :key="dm.id"
          class="cbx-dm-item"
          :class="{ 'cbx-dm-item--active': activeDmId === dm.id }"
          @click="selectDm(dm)"
        >
          <div class="cbx-dm-avatar-wrap">
            <div
              class="cbx-dm-avatar"
              :style="{ background: avatarColor(dm.name) }"
            >
              {{ dm.initials }}
            </div>
            <span
              class="cbx-dm-dot"
              :class="dm.status === 'online' ? 'cbx-dm-dot--on' : 'cbx-dm-dot--off'"
            ></span>
          </div>
          <span class="cbx-dm-name">{{ dm.name }}</span>
        </button>
      </div>

    </aside>

    <!-- ══ CONVERSATION + PROFIL : visibles seulement si conversation active ══ -->
    <template v-if="activeConversation">

    <!-- ══ CONVERSATION ══════════════════════════════════════════════════════ -->
    <main class="cbx-conv">

      <!-- Header -->
      <header class="cbx-conv-hdr">
        <div class="cbx-conv-hdr__left">
          <span v-if="activeConversation?.type === 'channel'" class="cbx-conv-hdr__hash">#</span>
          <span class="cbx-conv-hdr__name">{{ activeConversation?.name ?? '—' }}</span>
        </div>
        <div class="cbx-conv-hdr__actions">
          <button
            class="cbx-conv-hdr__action"
            title="Afficher / masquer le profil"
            @click="showProfile = !showProfile"
          >
            <v-icon size="15" color="#999">mdi-account-outline</v-icon>
          </button>
          <button
            class="cbx-conv-hdr__action"
            title="Fermer la conversation"
            @click="activeConversation = null"
          >
            <v-icon size="15" color="#bbb">mdi-close</v-icon>
          </button>
        </div>
      </header>

      <!-- Messages -->
      <div ref="messagesEl" class="cbx-messages">
        <div
          v-for="msg in activeMessages"
          :key="msg.id"
          class="cbx-msg"
          :class="msg.isMine ? 'cbx-msg--mine' : 'cbx-msg--other'"
        >
          <!-- Avatar auteur (gauche) -->
          <div
            v-if="!msg.isMine"
            class="cbx-msg-avatar"
            :style="{ background: avatarColor(msg.author) }"
          >
            {{ msgInitials(msg.author) }}
          </div>

          <div class="cbx-msg-content">
            <div class="cbx-msg-meta">
              <span class="cbx-msg-author">{{ msg.author }}</span>
              <span class="cbx-msg-time">{{ msg.time }}</span>
            </div>

            <!-- Bulle texte -->
            <div
              v-if="msg.text"
              class="cbx-msg-bubble"
              :class="msg.isMine ? 'cbx-msg-bubble--mine' : ''"
            >
              <!-- eslint-disable-next-line vue/no-v-html -->
              <p class="cbx-msg-text" v-html="formatText(msg.text)"></p>
            </div>

            <!-- Fichier partagé -->
            <div v-if="msg.file" class="cbx-msg-file">
              <v-icon size="22" color="#c0392b">mdi-file-pdf-box</v-icon>
              <div class="cbx-msg-file__info">
                <span class="cbx-msg-file__name">{{ msg.file.name }}</span>
                <span class="cbx-msg-file__type">PDF</span>
              </div>
            </div>

            <!-- Pied de message : réactions + lu -->
            <div class="cbx-msg-footer">
              <template v-if="msg.reactions?.length">
                <button
                  v-for="(r, i) in msg.reactions"
                  :key="i"
                  class="cbx-reaction"
                >
                  {{ r.emoji }}&nbsp;{{ r.count }}
                </button>
                <button class="cbx-reaction cbx-reaction--add">
                  <v-icon size="11" color="#bbb">mdi-emoticon-outline</v-icon>
                </button>
              </template>
              <div v-if="msg.isMine && msg.read" class="cbx-read">
                <v-icon size="12" color="#00a8a8">mdi-check-all</v-icon>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Zone saisie -->
      <div class="cbx-input-area">
        <div class="cbx-toolbar">
          <button class="cbx-tool" title="Gras"><b>B</b></button>
          <button class="cbx-tool cbx-tool--i" title="Italique"><i>I</i></button>
          <button class="cbx-tool cbx-tool--u" title="Souligné"><u>U</u></button>
          <button class="cbx-tool cbx-tool--s" title="Barré"><s>S</s></button>
          <span class="cbx-tool-sep"></span>
          <button class="cbx-tool" title="Lien">
            <v-icon size="13">mdi-link-variant</v-icon>
          </button>
          <button class="cbx-tool" title="Pièce jointe">
            <v-icon size="13">mdi-paperclip</v-icon>
          </button>
          <button class="cbx-tool" title="Audio">
            <v-icon size="13">mdi-microphone-outline</v-icon>
          </button>
        </div>
        <div class="cbx-input-row">
          <input
            ref="inputEl"
            v-model="newMessage"
            class="cbx-input"
            placeholder="Écrire un message…"
            autocomplete="off"
            @keydown.enter.prevent="sendMessage"
          />
          <button
            class="cbx-send-btn"
            :disabled="!newMessage.trim()"
            @click="sendMessage"
          >
            SEND
          </button>
        </div>
      </div>

    </main>

    <!-- ══ PROFIL ════════════════════════════════════════════════════════════ -->
    <transition name="cbx-profile-slide">
      <aside v-if="showProfile && activeConversation?.type !== 'channel'" class="cbx-profile">

        <div class="cbx-profile-hdr">
          <span class="cbx-profile-title">PROFILE</span>
          <button class="cbx-profile-close" @click="showProfile = false">
            <v-icon size="13">mdi-close</v-icon>
          </button>
        </div>

        <div class="cbx-profile-body">

          <!-- Avatar -->
          <div class="cbx-profile-avatar-wrap">
            <img
              v-if="profileUser.avatarUrl"
              :src="profileUser.avatarUrl"
              :alt="profileUser.name"
              class="cbx-profile-avatar"
            />
            <div
              v-else
              class="cbx-profile-avatar cbx-profile-avatar--fallback"
              :style="{ background: avatarColor(profileUser.name) }"
            >
              {{ msgInitials(profileUser.name) }}
            </div>
          </div>

          <div class="cbx-profile-name">{{ profileUser.name }}</div>
          <div class="cbx-profile-role">{{ profileUser.role }}</div>
          <div class="cbx-profile-status">
            <span class="cbx-profile-status__dot"></span>
            Online
          </div>

          <!-- Actions -->
          <div class="cbx-profile-actions">
            <button class="cbx-prof-btn cbx-prof-btn--outline">
              <v-icon size="13">mdi-phone</v-icon>
              Start Call
            </button>
            <button class="cbx-prof-btn cbx-prof-btn--solid">
              <v-icon size="13">mdi-message-outline</v-icon>
              Message
            </button>
          </div>

          <!-- Contact Information -->
          <div class="cbx-profile-section">
            <div class="cbx-profile-section-lbl">Contact Information</div>
            <div class="cbx-profile-info-list">
              <div class="cbx-profile-info-item">
                <v-icon size="14" color="#ccc">mdi-email-outline</v-icon>
                <div>
                  <div class="cbx-info-lbl">Email</div>
                  <div class="cbx-info-val">{{ profileUser.email }}</div>
                </div>
              </div>
              <div class="cbx-profile-info-item">
                <v-icon size="14" color="#ccc">mdi-phone</v-icon>
                <div>
                  <div class="cbx-info-lbl">Phone</div>
                  <div class="cbx-info-val">{{ profileUser.phone }}</div>
                </div>
              </div>
              <div class="cbx-profile-info-item">
                <v-icon size="14" color="#ccc">mdi-map-marker-outline</v-icon>
                <div>
                  <div class="cbx-info-lbl">Location</div>
                  <div class="cbx-info-val">{{ profileUser.location }}</div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </aside>
    </transition>

    </template>
    <!-- ══ fin bloc conversation + profil ══════════════════════════════════ -->

  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import DOMPurify from 'dompurify'

// ─── Props ───────────────────────────────────────────────────────────────────
const props = defineProps({
  // Passé par WorkspaceView quand le bouton CHAT du banner est cliqué.
  // Null quand l'onglet est juste ouvert sans action explicite.
  openWith: { type: Object, default: null },
})

// ─── Données statiques ───────────────────────────────────────────────────────
const CHANNELS = [
  { id: 1, name: 'Equipe-Nuit',      unread: 0 },
  { id: 2, name: 'Exploitation-Sud', unread: 0 },
  { id: 3, name: 'Supervision',      unread: 0 },
]

const DM_CONTACTS_INIT = [
  { id: 1, name: 'Jean Dupont',  status: 'offline', initials: 'JD' },
  { id: 2, name: 'Marie Dubois', status: 'online',  initials: 'MD' },
  { id: 3, name: 'Sarah Lee',    status: 'online',  initials: 'SL' },
  { id: 4, name: 'Sarah Beaun',  status: 'offline', initials: 'SB' },
]

const INITIAL_MESSAGES = [
  {
    id: 1,
    author: 'Marie Dubois',
    time: '10:00 AM',
    text: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulia cat lacus. Checkau security check siiis, **ave eget pousere**, et, vehicla dignissim gilia qua mt cmmodo gravidia.',
    reactions: [{ emoji: '👍', count: 1 }],
    isMine: false,
  },
  {
    id: 2,
    author: 'Marie Dubois',
    time: '10:15 AM',
    text: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulia rat lacus. Aliquam check num sed?',
    reactions: [{ emoji: '👍', count: 1 }],
    read: false,
    isMine: false,
  },
  {
    id: 3,
    author: 'Jean Dupont',
    time: '12:31 AM',
    file: { name: 'Rapport_Incident_01.pdf', type: 'pdf' },
    read: true,
    isMine: true,
  },
  {
    id: 4,
    author: 'Marie Dubois',
    time: '10:10 AM',
    text: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulia rat lacus. Aliquam maximus. Etiam orci rius, **avida eget pousere** et, vehicla dignissim ligula. Sed at diam dictor gravida ou om venenatis nulla leugiat lacinia agostas.',
    reactions: [{ emoji: '👍', count: 1 }],
    isMine: false,
  },
]

const DEFAULT_PROFILE = {
  name: 'Marie Dubois',
  role: 'Opérateur Sécurité',
  email: 'marie.dubois@permatel.com',
  phone: '+33 1 23 45 67 89',
  location: 'Paris, France',
  avatarUrl: null,
}

// ─── État ─────────────────────────────────────────────────────────────────────
const dmContacts       = ref([...DM_CONTACTS_INIT])  // mutable : un contact externe peut être ajouté
const searchQuery      = ref('')
const activeChannelId  = ref(null)    // salon sélectionné (visuel sidebar)
const activeDmId       = ref(null)    // DM sélectionné (visuel sidebar)
const messages         = ref([...INITIAL_MESSAGES])
const newMessage       = ref('')
const showProfile      = ref(true)
const messagesEl       = ref(null)
const inputEl          = ref(null)

// Conversation active : null = sidebar only ; objet = conv + profil visibles
const activeConversation = ref(null)

// ─── Dérivés ──────────────────────────────────────────────────────────────────
const activeChannel = computed(() =>
  CHANNELS.find(c => c.id === activeChannelId.value) ?? null
)

const filteredChannels = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return q ? CHANNELS.filter(c => c.name.toLowerCase().includes(q)) : CHANNELS
})

const filteredDMs = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return q
    ? dmContacts.value.filter(d => d.name.toLowerCase().includes(q))
    : dmContacts.value
})

const activeMessages = computed(() => messages.value)

const profileUser = computed(() => activeConversation.value ?? DEFAULT_PROFILE)

// Ouvre une conversation depuis le banner CHAT (prop openWith)
watch(
  () => props.openWith,
  (contact) => {
    if (!contact) return

    // 1. Trouve ou crée l'entrée dans la liste MESSAGES DIRECTS
    const nameNorm = (contact.fullName ?? '').toLowerCase()
    let dm = dmContacts.value.find(d => d.name.toLowerCase() === nameNorm)
    if (!dm) {
      dm = {
        id:       `ext-${Date.now()}`,
        name:     contact.fullName ?? '—',
        status:   'online',
        initials: msgInitials(contact.fullName ?? ''),
      }
      dmContacts.value.push(dm)
    }

    // 2. Sélectionne visuellement dans la sidebar
    activeDmId.value      = dm.id
    activeChannelId.value = null

    // 3. Ouvre la conversation avec les infos complètes du contact
    const slug = nameNorm.replace(/\s+/g, '.')
    activeConversation.value = {
      type:      'dm',
      name:      contact.fullName  ?? DEFAULT_PROFILE.name,
      role:      contact.jobTitle  ?? DEFAULT_PROFILE.role,
      email:     `${slug}@permatel.com`,
      phone:     contact.phone     ?? DEFAULT_PROFILE.phone,
      location:  'Paris, France',
      avatarUrl: contact.avatarUrl ?? null,
    }
    showProfile.value = true
  },
)

// ─── Helpers ──────────────────────────────────────────────────────────────────
function avatarColor(name) {
  let hash = 0
  for (let i = 0; i < (name ?? '').length; i++)
    hash = (name.charCodeAt(i) + ((hash << 5) - hash)) | 0
  return `hsl(${Math.abs(hash) % 360}, 38%, 40%)`
}

function msgInitials(name) {
  return (name ?? '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(w => w[0].toUpperCase())
    .join('')
}

function formatText(text) {
  // Échappement d'abord (les < > & deviennent des entités), puis mise en gras
  // **…**, et enfin sanitisation DOMPurify comme garde-fou autoritaire :
  // seules <strong> et <br> sont autorisées (défense en profondeur — SEC-04).
  const escaped = (text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
  return DOMPurify.sanitize(escaped, { ALLOWED_TAGS: ['strong', 'br'], ALLOWED_ATTR: [] })
}

// ─── Actions ──────────────────────────────────────────────────────────────────
function selectChannel(ch) {
  activeChannelId.value    = ch.id
  activeDmId.value         = null
  activeConversation.value = { type: 'channel', name: ch.name }
  showProfile.value        = false   // profil jamais visible pour un channel
}

function selectDm(dm) {
  activeDmId.value      = dm.id
  activeChannelId.value = null
  const slug = dm.name.toLowerCase().replace(/\s+/g, '.')
  activeConversation.value = {
    type:      'dm',
    name:      dm.name,
    role:      '—',
    email:     `${slug}@permatel.com`,
    phone:     '—',
    location:  '—',
    avatarUrl: null,
  }
  showProfile.value = true
}

function sendMessage() {
  const text = newMessage.value.trim()
  if (!text) return
  messages.value.push({
    id:     Date.now(),
    author: 'Jean Dupont',
    time:   new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    text,
    isMine: true,
    read:   false,
  })
  newMessage.value = ''
  scrollToBottom()
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value)
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}

watch(() => messages.value.length, scrollToBottom)
</script>

<script>
export default { name: 'ChatBox' }
</script>

<style scoped>
/* ══ RACINE ══════════════════════════════════════════════════════════════════ */

.cbx-root {
  flex: 1;
  display: flex;
  min-height: 0;
  min-width: 0;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 4px;
  overflow: hidden;
  font-family: "Fira Sans", sans-serif;
}

/* ══ SIDEBAR ═════════════════════════════════════════════════════════════════ */

.cbx-sidebar {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  background: #fafafa;
  overflow-y: auto;
  padding-bottom: 16px;
  transition: width 0.2s ease;
}

/* Sidebar seule : prend tout l'espace disponible */
.cbx-sidebar--full {
  width: 100%;
  border-right: none;
}

.cbx-sidebar::-webkit-scrollbar { width: 3px; }
.cbx-sidebar::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 2px; }

.cbx-brand {
  padding: 14px 14px 10px;
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #000b23;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

/* Search */
.cbx-search {
  position: relative;
  padding: 10px 12px 6px;
  flex-shrink: 0;
}

.cbx-search__input {
  width: 100%;
  height: 28px;
  padding: 0 26px 0 10px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #333;
  background: #fff;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.cbx-search__input:focus { border-color: rgba(0, 168, 168, 0.4); }
.cbx-search__input::placeholder { color: #c0c0c0; }

.cbx-search__icon {
  position: absolute;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
}

/* Section */
.cbx-section {
  display: flex;
  flex-direction: column;
  padding: 10px 0 4px;
}

.cbx-section-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px 6px;
}

.cbx-section-lbl {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #bbb;
  text-transform: uppercase;
}

.cbx-section-add {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 2px;
  cursor: pointer;
  color: #bbb;
  transition: background 0.12s, color 0.12s;
}
.cbx-section-add:hover { background: rgba(0,0,0,0.06); color: #555; }

/* Channel items */
.cbx-channel-item {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 5px 12px;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
  border-radius: 0;
  transition: background 0.1s;
}
.cbx-channel-item:hover { background: rgba(0, 0, 0, 0.04); }
.cbx-channel-item--active {
  background: rgba(0, 168, 168, 0.1);
}
.cbx-channel-item--active .cbx-ch-hash,
.cbx-channel-item--active .cbx-ch-name {
  color: #007a7a;
  font-weight: 700;
}

.cbx-ch-hash {
  font-size: 12px;
  font-weight: 600;
  color: #bbb;
  flex-shrink: 0;
  line-height: 1;
}
.cbx-ch-name {
  font-size: 11px;
  font-weight: 500;
  color: #444;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cbx-ch-badge {
  font-size: 9px;
  font-weight: 800;
  background: #e74c3c;
  color: #fff;
  border-radius: 2px;
  padding: 0 4px;
  min-width: 16px;
  text-align: center;
}

/* DM items */
.cbx-dm-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 5px 12px;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}
.cbx-dm-item:hover { background: rgba(0, 0, 0, 0.04); }
.cbx-dm-item--active { background: rgba(0, 168, 168, 0.08); }

.cbx-dm-avatar-wrap {
  position: relative;
  flex-shrink: 0;
}

.cbx-dm-avatar {
  width: 26px;
  height: 26px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: "Fira Code", monospace;
  font-size: 9px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
}

.cbx-dm-dot {
  position: absolute;
  bottom: -2px;
  right: -2px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 2px solid #fafafa;
}
.cbx-dm-dot--on  { background: #27ae60; }
.cbx-dm-dot--off { background: #ccc; }

.cbx-dm-name {
  font-size: 11px;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ══ CONVERSATION ════════════════════════════════════════════════════════════ */

.cbx-conv {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Header canal */
.cbx-conv-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 46px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  flex-shrink: 0;
}

.cbx-conv-hdr__left {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.cbx-conv-hdr__hash {
  font-size: 16px;
  font-weight: 300;
  color: #bbb;
  line-height: 1;
}

.cbx-conv-hdr__name {
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #000b23;
}

.cbx-conv-hdr__actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.cbx-conv-hdr__action {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.12s;
}
.cbx-conv-hdr__action:hover { background: rgba(0, 0, 0, 0.05); }

/* Messages */
.cbx-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
}

.cbx-messages::-webkit-scrollbar { width: 4px; }
.cbx-messages::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 2px; }

/* Bulle de message */
.cbx-msg {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.cbx-msg--mine {
  flex-direction: row-reverse;
}

.cbx-msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 3px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
}

.cbx-msg-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 72%;
}
.cbx-msg--mine .cbx-msg-content {
  align-items: flex-end;
}

.cbx-msg-meta {
  display: flex;
  align-items: baseline;
  gap: 7px;
}
.cbx-msg--mine .cbx-msg-meta {
  flex-direction: row-reverse;
}

.cbx-msg-author {
  font-size: 11px;
  font-weight: 700;
  color: #000b23;
}
.cbx-msg-time {
  font-family: "Fira Code", monospace;
  font-size: 9.5px;
  color: #bbb;
}

/* Bulle texte */
.cbx-msg-bubble {
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 3px;
  padding: 8px 11px;
}
.cbx-msg-bubble--mine {
  background: rgba(0, 168, 168, 0.07);
  border-color: rgba(0, 168, 168, 0.14);
}

.cbx-msg-text {
  font-size: 11.5px;
  color: #333;
  line-height: 1.55;
  margin: 0;
}

/* Fichier partagé */
.cbx-msg-file {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 3px;
  padding: 8px 12px;
}
.cbx-msg-file__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cbx-msg-file__name {
  font-size: 11px;
  font-weight: 600;
  color: #222;
}
.cbx-msg-file__type {
  font-family: "Fira Code", monospace;
  font-size: 9px;
  color: #aaa;
  text-transform: uppercase;
}

/* Pied de message */
.cbx-msg-footer {
  display: flex;
  align-items: center;
  gap: 5px;
  min-height: 18px;
}
.cbx-msg--mine .cbx-msg-footer {
  justify-content: flex-end;
}

.cbx-reaction {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  height: 20px;
  padding: 0 7px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 10px;
  background: #fff;
  font-size: 10px;
  color: #555;
  cursor: pointer;
  transition: border-color 0.12s, background 0.12s;
}
.cbx-reaction:hover { background: rgba(0, 0, 0, 0.04); border-color: rgba(0,0,0,0.18); }
.cbx-reaction--add {
  padding: 0 6px;
  color: #bbb;
}

.cbx-read {
  display: flex;
  align-items: center;
}

/* ══ ZONE SAISIE ══════════════════════════════════════════════════════════════ */

.cbx-input-area {
  flex-shrink: 0;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
  padding: 10px 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* Barre d'outils */
.cbx-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
}

.cbx-tool {
  width: 26px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  color: #888;
  transition: background 0.1s, color 0.1s;
}
.cbx-tool:hover { background: rgba(0,0,0,0.06); color: #333; }
.cbx-tool--i { font-style: italic; }
.cbx-tool--u { text-decoration: underline; }
.cbx-tool--s { text-decoration: line-through; }

.cbx-tool-sep {
  width: 1px;
  height: 14px;
  background: rgba(0, 0, 0, 0.1);
  margin: 0 3px;
  flex-shrink: 0;
}

/* Ligne input + bouton */
.cbx-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.cbx-input {
  flex: 1;
  height: 32px;
  padding: 0 10px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  color: #222;
  background: #fff;
  outline: none;
  transition: border-color 0.15s;
}
.cbx-input:focus { border-color: rgba(0, 168, 168, 0.4); }
.cbx-input::placeholder { color: #ccc; }

.cbx-send-btn {
  height: 32px;
  padding: 0 16px;
  border: none;
  border-radius: 3px;
  background: #00a8a8;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #fff;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s;
}
.cbx-send-btn:hover:not(:disabled) { background: #008888; }
.cbx-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ══ PROFIL ══════════════════════════════════════════════════════════════════ */

.cbx-profile {
  width: 220px;
  flex-shrink: 0;
  border-left: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: #fff;
}

.cbx-profile::-webkit-scrollbar { width: 3px; }
.cbx-profile::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 2px; }

.cbx-profile-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 14px 10px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  flex-shrink: 0;
}

.cbx-profile-title {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #000b23;
  text-transform: uppercase;
}

.cbx-profile-close {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 2px;
  cursor: pointer;
  color: #bbb;
  transition: background 0.1s, color 0.1s;
}
.cbx-profile-close:hover { background: rgba(0,0,0,0.06); color: #555; }

.cbx-profile-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 14px 16px;
  gap: 6px;
}

.cbx-profile-avatar-wrap {
  margin-bottom: 6px;
}

.cbx-profile-avatar {
  width: 72px;
  height: 72px;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  object-fit: cover;
  display: block;
}

.cbx-profile-avatar--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: "Fira Code", monospace;
  font-size: 18px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
}

.cbx-profile-name {
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.05em;
  color: #000b23;
  text-align: center;
}

.cbx-profile-role {
  font-size: 10.5px;
  color: #888;
  text-align: center;
}

.cbx-profile-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10.5px;
  color: #27ae60;
  font-weight: 600;
  margin-top: 2px;
}

.cbx-profile-status__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #27ae60;
  flex-shrink: 0;
}

.cbx-profile-actions {
  display: flex;
  flex-direction: column;
  gap: 7px;
  width: 100%;
  margin-top: 10px;
}

.cbx-prof-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 30px;
  width: 100%;
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.14s, border-color 0.14s;
}

.cbx-prof-btn--outline {
  background: #fff;
  border: 1px solid #00a8a8;
  color: #00a8a8;
}
.cbx-prof-btn--outline:hover { background: rgba(0, 168, 168, 0.06); }

.cbx-prof-btn--solid {
  background: #000b23;
  border: 1px solid transparent;
  color: #fff;
}
.cbx-prof-btn--solid:hover { background: #111c3a; }

/* Section contact info */
.cbx-profile-section {
  width: 100%;
  margin-top: 14px;
}

.cbx-profile-section-lbl {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #000b23;
  text-transform: uppercase;
  margin-bottom: 12px;
}

.cbx-profile-info-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cbx-profile-info-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.cbx-info-lbl {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #bbb;
  text-transform: uppercase;
  margin-bottom: 2px;
}

.cbx-info-val {
  font-size: 10.5px;
  color: #333;
  word-break: break-all;
}

/* ══ TRANSITION PROFIL ═══════════════════════════════════════════════════════ */

.cbx-profile-slide-enter-active,
.cbx-profile-slide-leave-active {
  transition: width 0.22s ease, opacity 0.2s ease;
  overflow: hidden;
}
.cbx-profile-slide-enter-from,
.cbx-profile-slide-leave-to {
  width: 0;
  opacity: 0;
}
.cbx-profile-slide-enter-to,
.cbx-profile-slide-leave-from {
  width: 220px;
  opacity: 1;
}
</style>
