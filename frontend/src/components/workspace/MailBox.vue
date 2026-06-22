<template>
  <div class="mbx-root">

    <!-- ══ TOPBAR ══════════════════════════════════════════════════════════ -->
    <div class="mbx-topbar">
      <h1 class="mbx-topbar__title">Gestion de Messagerie Email Permatel</h1>
      <button class="mbx-new-btn">
        <v-icon size="13">mdi-plus</v-icon>
        NOUVEL EMAIL
      </button>
    </div>

    <!-- ══ BODY ════════════════════════════════════════════════════════════ -->
    <div class="mbx-body">

      <!-- ── Sidebar dossiers ── -->
      <aside class="mbx-sidebar">
        <div class="mbx-search-wrap">
          <v-icon size="13" color="#ccc" class="mbx-search-icon">mdi-magnify</v-icon>
          <input
            v-model="folderSearch"
            class="mbx-search-input"
            placeholder="Search folders..."
            autocomplete="off"
          />
        </div>

        <div class="mbx-folders-label">FOLDERS</div>

        <nav class="mbx-folders">
          <button
            v-for="f in filteredFolders"
            :key="f.id"
            class="mbx-folder-btn"
            :class="{ 'mbx-folder-btn--active': activeFolderId === f.id }"
            @click="selectFolder(f)"
          >
            <v-icon size="14" :color="activeFolderId === f.id ? '#00a8a8' : '#bbb'">
              {{ f.icon }}
            </v-icon>
            <span class="mbx-folder-lbl">{{ f.label }}</span>
            <span
              v-if="f.badge"
              class="mbx-folder-badge"
              :class="f.badgeUrgent ? 'mbx-folder-badge--urgent' : 'mbx-folder-badge--default'"
            >{{ f.badge }}</span>
          </button>
        </nav>
      </aside>

      <!-- ── Zone principale ── -->
      <div class="mbx-main">

        <!-- Liste des emails -->
        <div class="mbx-list">
          <div class="mbx-list-hdr">
            <span class="mbx-hdr-dot"></span>
            <span class="mbx-hdr-cell mbx-hdr-sender">SENDER / CLIENT CODE</span>
            <span class="mbx-hdr-cell mbx-hdr-subject">SUBJECT</span>
            <span class="mbx-hdr-cell mbx-hdr-priority">PRIORITY</span>
          </div>

          <button
            v-for="email in folderEmails"
            :key="email.id"
            class="mbx-row"
            :class="{
              'mbx-row--active': activeEmailId === email.id,
              'mbx-row--unread': email.unread,
            }"
            @click="selectEmail(email)"
          >
            <span
              class="mbx-row-dot"
              :class="email.unread ? 'mbx-row-dot--on' : ''"
            ></span>
            <div class="mbx-row-sender">
              <span class="mbx-row-sender__name">{{ email.sender }}</span>
              <span class="mbx-row-sender__code">{{ email.clientCode }}</span>
            </div>
            <div class="mbx-row-subject">{{ truncate(email.subject, 54) }}</div>
            <div class="mbx-row-priority">
              <span
                class="mbx-prio-badge"
                :class="`mbx-prio-badge--${email.priority.toLowerCase()}`"
              >{{ email.priority }}</span>
            </div>
          </button>

          <div v-if="folderEmails.length === 0" class="mbx-list-empty">
            Aucun email dans ce dossier.
          </div>
        </div>

        <!-- ── Panneau de lecture ── -->
        <template v-if="activeEmail">
          <div class="mbx-reader">

            <!-- En-tête -->
            <div class="mbx-reader-hdr">
              <h2 class="mbx-reader-subject">{{ activeEmail.subject }}</h2>
              <span class="mbx-reader-date">{{ activeEmail.date }}</span>
            </div>

            <!-- Expéditeur -->
            <div class="mbx-reader-from">
              <div
                class="mbx-from-avatar"
                :style="{ background: avatarColor(activeEmail.sender) }"
              >{{ getInitials(activeEmail.sender) }}</div>
              <div class="mbx-from-info">
                <div class="mbx-from-name">
                  {{ activeEmail.sender }}
                  <span class="mbx-from-addr">&lt;{{ activeEmail.from }}&gt;</span>
                </div>
                <div class="mbx-from-meta">
                  To: {{ activeEmail.to.join(', ') }}&ensp;|&ensp;Client Code:
                  <span class="mbx-from-code">{{ activeEmail.clientCode }}</span>
                </div>
              </div>
            </div>

            <!-- Corps -->
            <div class="mbx-reader-body">
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="mbx-body-text" v-html="formatBody(activeEmail.body)"></div>

              <div v-if="activeEmail.technicalLog" class="mbx-tech-log">
                <div class="mbx-tech-log__label">SYSTEM DIAGNOSTIC LOG</div>
                <pre class="mbx-tech-log__content">{{ activeEmail.technicalLog }}</pre>
              </div>
            </div>

            <!-- Actions -->
            <div class="mbx-reader-actions">
              <button class="mbx-act mbx-act--ghost">
                <v-icon size="12">mdi-delete-outline</v-icon>
                SUPPRIMER
              </button>
              <button class="mbx-act mbx-act--ghost">
                <v-icon size="12">mdi-share-outline</v-icon>
                TRANSFÉRER
              </button>
              <button class="mbx-act mbx-act--primary">
                <v-icon size="12">mdi-reply-outline</v-icon>
                RÉPONDRE
              </button>
            </div>

          </div>
        </template>

        <!-- État vide -->
        <div v-else class="mbx-reader-empty">
          <v-icon size="34" color="#ddd">mdi-email-open-outline</v-icon>
          <p class="mbx-reader-empty__text">Sélectionner un email pour le lire</p>
        </div>

      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

// ─── Données statiques ────────────────────────────────────────────────────

const FOLDERS = [
  { id: 'inbox',   label: 'Boîte de réception', icon: 'mdi-monitor-outline',   badge: 12, badgeUrgent: false },
  { id: 'sent',    label: 'Envoyés',             icon: 'mdi-send-outline',      badge: null },
  { id: 'drafts',  label: 'Brouillons',          icon: 'mdi-file-outline',      badge: null },
  { id: 'archive', label: 'Archives',            icon: 'mdi-archive-outline',   badge: null },
  { id: 'urgent',  label: 'Urgences',            icon: 'mdi-alert-outline',     badge: 1,  badgeUrgent: true  },
]

const EMAILS_DATA = [
  {
    id: 1,
    folder: 'inbox',
    sender: 'Marie Dubois',
    clientCode: 'CLI-8942-A',
    subject: 'Alerte de sécurité - Incident critique détecté',
    priority: 'HIGH',
    unread: true,
    date: 'Today, 10:24',
    from: 'marie.dubois@permatel.com',
    to: ['Security Ops Team'],
    body: "Bonjour l'équipe,\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla cat lacus. Checkau security check sriis, **avr eget pousere**, et vehicula dignissim gilias qua mt commodo gravida.",
    technicalLog: "ERR_CODE:  0x8892_AUTH_FAIL\nTIMESTAMP: 2023-10-27T09:58:12Z\nNODE:      PRO-AUTH-EUR-02\nSEVERITY:  CRITICAL",
  },
  {
    id: 2,
    folder: 'inbox',
    sender: 'Jean Dupont',
    clientCode: 'CLI-1102-B',
    subject: 'Rapport de nuit - Check security check résumé',
    priority: 'NORMAL',
    unread: false,
    date: 'Today, 08:15',
    from: 'jean.dupont@permatel.com',
    to: ['Équipe Sécurité'],
    body: "Bonsoir,\n\nVoici le rapport de surveillance de la nuit du 26 au 27 octobre. Toutes les rondes ont été effectuées sans incident majeur. Les accès enregistrés correspondent aux badges autorisés.",
    technicalLog: null,
  },
  {
    id: 3,
    folder: 'inbox',
    sender: 'Support Technique',
    clientCode: 'INT-SYS-01',
    subject: 'Mise à jour système - Une maintenance planifiée',
    priority: 'INFO',
    unread: false,
    date: 'Yesterday',
    from: 'support@permatel.com',
    to: ['Tous les utilisateurs'],
    body: "Bonjour,\n\nUne maintenance système est planifiée pour le 28 octobre de 02h00 à 04h00. Les services seront temporairement indisponibles durant cette fenêtre de maintenance.\n\nMerci de votre compréhension.",
    technicalLog: null,
  },
]

// ─── État ─────────────────────────────────────────────────────────────────

const folderSearch   = ref('')
const activeFolderId = ref('inbox')
const activeEmailId  = ref(1)

// ─── Dérivés ──────────────────────────────────────────────────────────────

const filteredFolders = computed(() => {
  const q = folderSearch.value.trim().toLowerCase()
  return q ? FOLDERS.filter(f => f.label.toLowerCase().includes(q)) : FOLDERS
})

const folderEmails = computed(() =>
  EMAILS_DATA.filter(e => e.folder === activeFolderId.value)
)

const activeEmail = computed(() =>
  EMAILS_DATA.find(e => e.id === activeEmailId.value) ?? null
)

// ─── Actions ──────────────────────────────────────────────────────────────

function selectFolder(f) {
  activeFolderId.value = f.id
  const first = EMAILS_DATA.find(e => e.folder === f.id)
  activeEmailId.value = first?.id ?? null
}

function selectEmail(e) {
  activeEmailId.value = e.id
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function avatarColor(name) {
  let h = 0
  for (let i = 0; i < (name ?? '').length; i++)
    h = (name.charCodeAt(i) + ((h << 5) - h)) | 0
  return `hsl(${Math.abs(h) % 360}, 36%, 40%)`
}

function getInitials(name) {
  return (name ?? '').split(' ').filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join('')
}

function truncate(str, len) {
  return str.length > len ? str.slice(0, len) + '…' : str
}

function formatBody(text) {
  return (text ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
    .replace(/^/, '<p>').replace(/$/, '</p>')
}
</script>

<script>
export default { name: 'MailBox' }
</script>

<style scoped>
/* ══ Root ══════════════════════════════════════════════════════════════════ */
.mbx-root {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 4px;
  overflow: hidden;
  font-family: "Fira Sans", sans-serif;
}

/* ══ Topbar ════════════════════════════════════════════════════════════════ */
.mbx-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 13px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  flex-shrink: 0;
  background: #fff;
}

.mbx-topbar__title {
  font-size: 13.5px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #000b23;
  margin: 0;
}

.mbx-new-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 14px;
  border: none;
  border-radius: 3px;
  background: #00a8a8;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.mbx-new-btn:hover { background: #008888; }

/* ══ Body ══════════════════════════════════════════════════════════════════ */
.mbx-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* ══ Sidebar ═══════════════════════════════════════════════════════════════ */
.mbx-sidebar {
  width: 195px;
  flex-shrink: 0;
  border-right: 1px solid rgba(0, 0, 0, 0.07);
  display: flex;
  flex-direction: column;
  padding: 12px 0 10px;
  overflow-y: auto;
  background: #fafafa;
}

.mbx-sidebar::-webkit-scrollbar { width: 3px; }
.mbx-sidebar::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.1); border-radius: 2px; }

/* Recherche */
.mbx-search-wrap {
  position: relative;
  padding: 0 12px 10px;
  flex-shrink: 0;
}

.mbx-search-input {
  width: 100%;
  height: 28px;
  padding: 0 28px 0 10px;
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
.mbx-search-input:focus { border-color: rgba(0, 168, 168, 0.4); }
.mbx-search-input::placeholder { color: #ccc; }

.mbx-search-icon {
  position: absolute;
  right: 20px;
  top: 50%;
  transform: translateY(-68%);
  pointer-events: none;
}

/* Dossiers */
.mbx-folders-label {
  padding: 0 12px 6px;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #ccc;
  text-transform: uppercase;
}

.mbx-folders {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.mbx-folder-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border: none;
  background: none;
  cursor: pointer;
  width: 100%;
  text-align: left;
  transition: background 0.1s;
}
.mbx-folder-btn:hover { background: rgba(0, 0, 0, 0.03); }
.mbx-folder-btn--active { background: rgba(0, 168, 168, 0.07); }
.mbx-folder-btn--active .mbx-folder-lbl { color: #007a7a; font-weight: 700; }

.mbx-folder-lbl {
  flex: 1;
  font-size: 11.5px;
  font-weight: 500;
  color: #444;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mbx-folder-badge {
  font-size: 9px;
  font-weight: 800;
  padding: 1px 6px;
  border-radius: 2px;
  min-width: 18px;
  text-align: center;
  line-height: 1.6;
}
.mbx-folder-badge--default { background: rgba(0, 168, 168, 0.12); color: #00a8a8; }
.mbx-folder-badge--urgent  { background: rgba(231, 76, 60, 0.12);  color: #e74c3c; }

/* ══ Zone principale ═══════════════════════════════════════════════════════ */
.mbx-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* ══ Liste emails ══════════════════════════════════════════════════════════ */
.mbx-list {
  flex-shrink: 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  overflow-y: auto;
  max-height: 240px;
}

.mbx-list::-webkit-scrollbar { width: 3px; }
.mbx-list::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.1); border-radius: 2px; }

/* En-tête colonnes */
.mbx-list-hdr {
  display: grid;
  grid-template-columns: 28px 190px 1fr 96px;
  align-items: center;
  padding: 0 14px;
  height: 32px;
  background: #f7f7f7;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  position: sticky;
  top: 0;
  z-index: 1;
}

.mbx-hdr-dot { /* spacer */ }

.mbx-hdr-cell {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #bbb;
  text-transform: uppercase;
}
.mbx-hdr-priority { text-align: center; }

/* Lignes email */
.mbx-row {
  display: grid;
  grid-template-columns: 28px 190px 1fr 96px;
  align-items: center;
  padding: 0 14px;
  height: 56px;
  width: 100%;
  border: none;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  border-left: 2px solid transparent;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s, border-left-color 0.1s;
  box-sizing: border-box;
}
.mbx-row:hover { background: rgba(0, 0, 0, 0.02); }
.mbx-row--active {
  background: rgba(0, 168, 168, 0.05);
  border-left-color: #00a8a8;
}
.mbx-row--unread .mbx-row-sender__name { font-weight: 700; color: #000b23; }
.mbx-row--unread .mbx-row-subject { font-weight: 600; color: #222; }

/* Dot statut */
.mbx-row-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1.5px solid #ddd;
  flex-shrink: 0;
}
.mbx-row-dot--on { background: #00a8a8; border-color: #00a8a8; }

/* Colonne expéditeur */
.mbx-row-sender {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding-right: 14px;
}
.mbx-row-sender__name {
  font-size: 11.5px;
  font-weight: 500;
  color: #1a1a2e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mbx-row-sender__code {
  font-family: "Fira Code", monospace;
  font-size: 9.5px;
  color: #00a8a8;
  letter-spacing: 0.04em;
}

/* Colonne sujet */
.mbx-row-subject {
  font-size: 11px;
  color: #666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 14px;
}

/* Colonne priorité */
.mbx-row-priority {
  display: flex;
  justify-content: center;
}

.mbx-prio-badge {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  padding: 2px 8px;
  border-radius: 2px;
  border: 1px solid;
  text-transform: uppercase;
}
.mbx-prio-badge--high   { color: #e74c3c; background: rgba(231,76,60,.07);   border-color: rgba(231,76,60,.2); }
.mbx-prio-badge--normal { color: #777;    background: rgba(0,0,0,.04);       border-color: rgba(0,0,0,.1);    }
.mbx-prio-badge--info   { color: #2980b9; background: rgba(41,128,185,.07);  border-color: rgba(41,128,185,.2);}

/* Vide */
.mbx-list-empty {
  padding: 18px 14px;
  font-size: 11px;
  color: #ccc;
  text-align: center;
}

/* ══ Panneau de lecture ════════════════════════════════════════════════════ */
.mbx-reader {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* En-tête sujet + date */
.mbx-reader-hdr {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.mbx-reader-subject {
  font-family: "Fira Sans", sans-serif;
  font-size: 14px;
  font-weight: 800;
  color: #000b23;
  letter-spacing: 0.02em;
  margin: 0;
  line-height: 1.35;
}

.mbx-reader-date {
  font-family: "Fira Code", monospace;
  font-size: 10px;
  color: #bbb;
  white-space: nowrap;
  flex-shrink: 0;
  padding-top: 3px;
}

/* Expéditeur */
.mbx-reader-from {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 18px 11px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  flex-shrink: 0;
}

.mbx-from-avatar {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: "Fira Code", monospace;
  font-size: 12px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.92);
  letter-spacing: 0.04em;
}

.mbx-from-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mbx-from-name {
  font-size: 12.5px;
  font-weight: 700;
  color: #000b23;
}

.mbx-from-addr {
  font-weight: 400;
  font-size: 11px;
  color: #999;
}

.mbx-from-meta {
  font-size: 10.5px;
  color: #bbb;
}

.mbx-from-code {
  font-family: "Fira Code", monospace;
  color: #00a8a8;
  font-size: 10px;
}

/* Corps */
.mbx-reader-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.mbx-reader-body::-webkit-scrollbar { width: 4px; }
.mbx-reader-body::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.1); border-radius: 2px; }

.mbx-body-text {
  font-size: 12.5px;
  color: #333;
  line-height: 1.7;
}
.mbx-body-text :deep(p)      { margin: 0 0 10px; }
.mbx-body-text :deep(p:last-child) { margin-bottom: 0; }
.mbx-body-text :deep(strong) { font-weight: 700; color: #000b23; }

/* Bloc log technique */
.mbx-tech-log {
  border-left: 3px solid rgba(231, 76, 60, 0.5);
  background: rgba(231, 76, 60, 0.04);
  border-radius: 0 3px 3px 0;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.mbx-tech-log__label {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.16em;
  color: #c0392b;
  text-transform: uppercase;
}

.mbx-tech-log__content {
  font-family: "Fira Code", monospace;
  font-size: 10.5px;
  color: #c0392b;
  margin: 0;
  line-height: 1.7;
  white-space: pre;
}

/* Actions */
.mbx-reader-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 18px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
  flex-shrink: 0;
}

.mbx-act {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 14px;
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: background 0.14s, border-color 0.14s;
}

.mbx-act--ghost {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.14);
  color: #555;
}
.mbx-act--ghost:hover { background: rgba(0, 0, 0, 0.04); border-color: rgba(0, 0, 0, 0.22); }

.mbx-act--primary {
  background: #00a8a8;
  border: 1px solid transparent;
  color: #fff;
}
.mbx-act--primary:hover { background: #008888; }

/* ── État vide ── */
.mbx-reader-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.mbx-reader-empty__text {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #d0d0d0;
  text-transform: uppercase;
  margin: 0;
}
</style>
