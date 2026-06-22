<template>
  <div class="mc-root">
    <!-- ══ SIDEBAR : liste ════════════════════════════════════════════════ -->
    <aside class="mc-sidebar">
      <!-- Barre haute : écrire + recherche -->
      <div class="mc-top">
        <button class="mc-write" @click="startCompose">
          <v-icon size="15">mdi-pencil-outline</v-icon>
          Écrire un email
        </button>
        <button
          class="mc-icon-btn"
          :class="{ 'mc-icon-btn--on': searchOpen }"
          title="Rechercher"
          @click="searchOpen = !searchOpen"
        >
          <v-icon size="16">mdi-magnify</v-icon>
        </button>
        <button
          class="mc-icon-btn"
          title="Synchroniser les emails entrants"
          :disabled="syncing"
          @click="syncNow"
        >
          <v-icon size="16" :class="{ 'mc-spin': syncing }">mdi-sync</v-icon>
        </button>
      </div>

      <div v-if="searchOpen" class="mc-search">
        <v-icon size="14" color="#9aa0aa">mdi-magnify</v-icon>
        <input
          v-model="search"
          class="mc-search__input"
          placeholder="Rechercher (destinataire, objet)…"
          autocomplete="off"
        />
        <button v-if="search" class="mc-search__clear" @click="search = ''">
          <v-icon size="13">mdi-close</v-icon>
        </button>
      </div>

      <!-- Onglets -->
      <div class="mc-tabs">
        <button
          v-for="t in TABS"
          :key="t.key"
          :class="['mc-tab', { 'mc-tab--on': tab === t.key }]"
          @click="tab = t.key"
        >
          {{ t.label }}
          <span v-if="counts[t.key]" class="mc-tab__count">{{
            counts[t.key]
          }}</span>
        </button>
      </div>

      <!-- Liste -->
      <div class="mc-list">
        <div v-if="loadingList && !inbox.length && !sent.length" class="mc-state">
          <v-progress-circular indeterminate size="20" color="#00a8a8" />
        </div>
        <div v-else-if="!filtered.length" class="mc-state mc-state--empty">
          <v-icon size="28" color="#d0d4da">mdi-email-outline</v-icon>
          <span>Aucun email</span>
        </div>

        <button
          v-for="m in filtered"
          :key="m.id"
          :class="[
            'mc-item',
            { 'mc-item--active': selectedEmail && selectedEmail.id === m.id },
            { 'mc-item--unread': m.direction === 'inbound' && m.status === 'non_lu' },
          ]"
          @click="selectEmail(m)"
        >
          <span class="mc-avatar" :style="avatarStyle(peerAddress(m))">{{
            initials(peerAddress(m))
          }}</span>
          <span class="mc-item__body">
            <span class="mc-item__line">
              <span class="mc-item__name">
                <span
                  v-if="m.direction === 'inbound' && m.status === 'non_lu'"
                  class="mc-unread-dot"
                ></span>
                {{ displayName(peerAddress(m)) }}
              </span>
              <span class="mc-item__time">{{
                shortDate(m.received_at || m.sent_at || m.created_at)
              }}</span>
            </span>
            <span class="mc-item__subject">{{
              m.subject || "(sans objet)"
            }}</span>
            <span class="mc-item__preview">{{ preview(m.body_text) }}</span>
            <span class="mc-item__tags">
              <span v-if="m.has_attachments" class="mc-tag-att">
                <v-icon size="11">mdi-paperclip</v-icon>
              </span>
              <span
                v-if="m.direction === 'outbound'"
                :class="['mc-pill', `mc-pill--${m.status}`]"
              >
                <v-icon size="9">{{
                  m.status === "sent" ? "mdi-check" : "mdi-alert-circle-outline"
                }}</v-icon>
                {{ m.status === "sent" ? "Envoyé" : "Échec" }}
              </span>
            </span>
          </span>
        </button>
      </div>
    </aside>

    <!-- ══ VOLET PRINCIPAL ════════════════════════════════════════════════ -->
    <section class="mc-main">
      <!-- ── Mode lecture ───────────────────────────────────────────────── -->
      <template v-if="mode === 'read' && selectedEmail">
        <div class="mc-read">
          <header class="mc-read__head">
            <span
              class="mc-avatar mc-avatar--lg"
              :style="avatarStyle(peerAddress(selectedEmail))"
            >
              {{ initials(peerAddress(selectedEmail)) }}
            </span>
            <div class="mc-read__who">
              <span class="mc-read__name">{{
                displayName(peerAddress(selectedEmail))
              }}</span>
              <span class="mc-read__addr">
                {{ selectedEmail.direction === "inbound" ? "De" : "À" }} :
                {{ peerAddress(selectedEmail) }}
              </span>
            </div>
            <div class="mc-read__meta">
              <span :class="['mc-pill', `mc-pill--${selectedEmail.status}`]">
                {{ STATUS_LABELS[selectedEmail.status] ?? selectedEmail.status }}
              </span>
              <span class="mc-read__date">{{
                longDate(
                  selectedEmail.received_at ||
                    selectedEmail.sent_at ||
                    selectedEmail.created_at,
                )
              }}</span>
            </div>
          </header>

          <div class="mc-read__scroll">
            <h2 class="mc-read__subject">
              {{ selectedEmail.subject || "(sans objet)" }}
            </h2>
            <p v-if="selectedEmail.cc" class="mc-read__cc">
              Cc : {{ selectedEmail.cc }}
            </p>
            <p v-if="selectedEmail.error" class="mc-read__error">
              <v-icon size="13" color="#e74c3c"
                >mdi-alert-circle-outline</v-icon
              >
              {{ selectedEmail.error }}
            </p>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div
              v-if="selectedEmail.body_html"
              class="mc-read__body mc-read__body--html"
              v-html="renderedHtml"
            ></div>
            <div v-else class="mc-read__body">{{ selectedEmail.body_text }}</div>

            <!-- Pièces jointes -->
            <div
              v-if="
                selectedEmail.attachments && selectedEmail.attachments.length
              "
              class="mc-attach"
            >
              <span class="mc-attach__lbl"
                >Pièces jointes ({{ selectedEmail.attachments.length }})</span
              >
              <div class="mc-attach__grid">
                <button
                  v-for="a in selectedEmail.attachments"
                  :key="a.id"
                  class="mc-attach__item"
                  :title="`Télécharger ${a.filename}`"
                  @click="download(a)"
                >
                  <v-icon size="18" color="#00a8a8"
                    >mdi-file-download-outline</v-icon
                  >
                  <span class="mc-attach__name">{{ a.filename }}</span>
                  <span class="mc-attach__size">{{ humanSize(a.size) }}</span>
                </button>
              </div>
            </div>
          </div>

          <footer class="mc-read__foot">
            <v-btn
              color="#00a8a8"
              variant="flat"
              class="text-none"
              prepend-icon="mdi-reply"
              @click="startReply"
            >
              Répondre
            </v-btn>
            <v-btn
              variant="outlined"
              class="text-none ml-2"
              prepend-icon="mdi-clipboard-plus-outline"
              @click="convertOpen = true"
            >
              {{ selectedEmail.demande_id ? "Rattacher à une autre" : "Convertir en demande" }}
            </v-btn>
            <v-btn
              v-if="
                selectedEmail.direction === 'inbound' &&
                selectedEmail.status !== 'archive'
              "
              variant="outlined"
              class="text-none ml-2"
              prepend-icon="mdi-archive-arrow-down-outline"
              @click="archive(selectedEmail)"
            >
              Archiver
            </v-btn>
            <v-spacer />
            <span v-if="selectedEmail.demande_id" class="mc-linked">
              <v-icon size="14" color="#15803d">mdi-check-circle-outline</v-icon>
              Rattaché à la demande #{{ selectedEmail.demande_id }}
            </span>
          </footer>
        </div>
      </template>

      <!-- ── Mode composition ───────────────────────────────────────────── -->
      <template v-else-if="mode === 'compose'">
        <div class="mc-compose">
          <header class="mc-compose__head">
            <span>{{ replying ? "Répondre" : "Nouvel email" }}</span>
            <button class="mc-icon-btn" title="Fermer" @click="cancelCompose">
              <v-icon size="16">mdi-close</v-icon>
            </button>
          </header>

          <v-alert
            v-if="feedback.text"
            :type="feedback.type"
            variant="tonal"
            density="compact"
            border="start"
            class="mc-alert"
            closable
            @click:close="feedback.text = ''"
          >
            {{ feedback.text }}
          </v-alert>

          <v-form ref="formRef" class="mc-form" @submit.prevent="send">
            <!-- Destinataire -->
            <div class="mc-field">
              <span class="mc-field__lbl">À</span>
              <v-autocomplete
                v-model="recipient"
                :items="recipientItems"
                :loading="searching"
                item-title="label"
                return-object
                variant="plain"
                density="compact"
                placeholder="Rechercher un contact…"
                no-filter
                hide-details="auto"
                :rules="[rules.recipient]"
                @update:search="onSearch"
              >
                <template #no-data>
                  <div class="mc-nodata">
                    {{
                      searching ? "Recherche…" : "Tapez un nom pour rechercher"
                    }}
                  </div>
                </template>
                <template #append-inner>
                  <button
                    v-if="!ccOpen"
                    type="button"
                    class="mc-cc-toggle"
                    @mousedown.prevent="ccOpen = true"
                  >
                    Cc
                  </button>
                </template>
              </v-autocomplete>
            </div>

            <!-- Cc -->
            <div v-if="ccOpen" class="mc-field">
              <span class="mc-field__lbl">Cc</span>
              <v-combobox
                v-model="cc"
                multiple
                chips
                closable-chips
                variant="plain"
                density="compact"
                placeholder="Adresses séparées par Entrée…"
                hide-details="auto"
              />
            </div>

            <!-- Objet -->
            <div class="mc-field">
              <span class="mc-field__lbl">Objet</span>
              <input
                v-model="subject"
                class="mc-input"
                placeholder="Objet du message"
              />
            </div>

            <!-- Corps -->
            <textarea
              v-model="body"
              class="mc-textarea"
              placeholder="Rédigez votre message…"
            ></textarea>

            <!-- Pièces jointes -->
            <EmailAttachments v-model="attachments" class="mc-attachments" />

            <div class="mc-compose__foot">
              <v-btn
                variant="text"
                class="text-none"
                :disabled="sending"
                @click="cancelCompose"
                >Annuler</v-btn
              >
              <v-spacer />
              <v-btn
                color="#00a8a8"
                variant="flat"
                class="text-none mc-send"
                :loading="sending"
                prepend-icon="mdi-send-outline"
                @click="send"
              >
                Envoyer
              </v-btn>
            </div>
          </v-form>
        </div>
      </template>

      <!-- ── État vide ──────────────────────────────────────────────────── -->
      <template v-else>
        <div class="mc-empty">
          <v-icon size="46" color="#d8dce1">mdi-email-open-outline</v-icon>
          <p class="mc-empty__title">Sélectionnez un email</p>
          <p class="mc-empty__sub">
            ou cliquez sur « Écrire un email » pour composer un message.
          </p>
        </div>
      </template>
    </section>

    <!-- Conversion email → demande / interaction -->
    <MailConvertDialog
      v-model="convertOpen"
      :email="selectedEmail"
      @converted="onConverted"
    />

    <v-snackbar v-model="syncSnack.show" :color="syncSnack.color" timeout="3000" location="bottom right">
      {{ syncSnack.text }}
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { emailService } from "@/services/emailService";
import { searchContacts } from "@/services/contactService";
import EmailAttachments from "@/components/workspace/EmailAttachments.vue";
import MailConvertDialog from "@/components/workspace/MailConvertDialog.vue";
import { sanitizeEmailHtml } from "@/utils/sanitizeHtml";

const props = defineProps({
  // Contact pré-rempli (ouverture depuis le bandeau contact) : { id, fullName, email }
  initialContact: { type: Object, default: null },
});

const TABS = [
  { key: "inbox", label: "Reçus" },
  { key: "unread", label: "Non lus" },
  { key: "sent", label: "Envoyés" },
  { key: "archived", label: "Archivés" },
];

const STATUS_LABELS = {
  non_lu: "Non lu",
  lu: "Lu",
  traite: "Traité",
  archive: "Archivé",
  spam: "Spam",
  sent: "Envoyé",
  failed: "Échec",
};

const inbox = ref([]); // emails entrants
const sent = ref([]); // emails sortants
const loadingList = ref(false);
const search = ref("");
const searchOpen = ref(false);
const tab = ref("inbox");
const syncing = ref(false);
const syncSnack = reactive({ show: false, text: "", color: "#00a8a8" });

const mode = ref("empty"); // 'empty' | 'read' | 'compose'
const selectedEmail = ref(null);
const replying = ref(false);
const replyToId = ref(null); // email d'origine pour une réponse threadée
const convertOpen = ref(false);

const recipient = ref(null);
const recipientItems = ref([]);
const searching = ref(false);
const subject = ref("");
const body = ref("");
const cc = ref([]); // adresses Cc (chaînes)
const ccOpen = ref(false);
const attachments = ref([]); // File[] en attente d'envoi
const sending = ref(false);
const formRef = ref(null);
const feedback = reactive({ type: "success", text: "" });

let searchTimer = null;

const rules = {
  required: (v) => (!!v && String(v).trim().length > 0) || "Champ requis.",
  recipient: (v) =>
    (!!v && (v.contact_id || v.email)) || "Sélectionnez un destinataire.",
};

// ── Liste filtrée + compteurs ────────────────────────────────────────────────
// Adresse "interlocuteur" : expéditeur si reçu, destinataire si envoyé
function peerAddress(m) {
  return m.direction === "inbound" ? m.from_address : m.to_addresses;
}

// Corps HTML assaini (rendu sûr anti-XSS)
const renderedHtml = computed(() =>
  selectedEmail.value?.body_html ? sanitizeEmailHtml(selectedEmail.value.body_html) : "",
);

const filtered = computed(() => {
  let list;
  if (tab.value === "sent") list = sent.value;
  else if (tab.value === "unread") list = inbox.value.filter((m) => m.status === "non_lu");
  else if (tab.value === "archived") list = inbox.value.filter((m) => m.status === "archive");
  else list = inbox.value.filter((m) => m.status !== "archive"); // inbox

  const q = search.value.trim().toLowerCase();
  if (q) {
    list = list.filter(
      (m) =>
        (peerAddress(m) || "").toLowerCase().includes(q) ||
        (m.subject || "").toLowerCase().includes(q),
    );
  }
  return list;
});

const counts = computed(() => ({
  inbox: inbox.value.filter((m) => m.status !== "archive").length,
  unread: inbox.value.filter((m) => m.status === "non_lu").length,
  sent: sent.value.length,
  archived: inbox.value.filter((m) => m.status === "archive").length,
}));

// ── Helpers d'affichage ──────────────────────────────────────────────────────
function displayName(addr) {
  if (!addr) return "—";
  const local = addr.split("@")[0] || addr;
  return local.replace(/[._-]+/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}
function initials(addr) {
  return (
    displayName(addr)
      .split(" ")
      .slice(0, 2)
      .map((w) => w[0] ?? "")
      .join("")
      .toUpperCase() || "?"
  );
}
function avatarStyle(addr) {
  // Couleur stable dérivée de l'adresse, dans une palette sobre
  const palette = [
    "#00a8a8",
    "#15223a",
    "#3498db",
    "#8e44ad",
    "#e67e22",
    "#16a085",
  ];
  let h = 0;
  for (const ch of addr || "") h = (h * 31 + ch.charCodeAt(0)) % palette.length;
  return { background: palette[h] };
}
function preview(text) {
  return (text || "").replace(/\s+/g, " ").trim().slice(0, 70);
}
function shortDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date();
  if (d.toDateString() === today.toDateString())
    return d.toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });
}
function longDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return (
    d.toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    }) +
    " · " +
    d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
  );
}

function humanSize(b) {
  if (!b && b !== 0) return "";
  if (b < 1024) return `${b} o`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} Ko`;
  return `${(b / 1024 / 1024).toFixed(1)} Mo`;
}
async function download(att) {
  try {
    await emailService.downloadAttachment(selectedEmail.value.id, att);
  } catch {
    /* erreur de téléchargement ignorée silencieusement */
  }
}

// ── Sélection / modes ────────────────────────────────────────────────────────
async function selectEmail(m) {
  selectedEmail.value = m;
  mode.value = "read";
  // Détail complet (pièces jointes incluses)
  try {
    selectedEmail.value = await emailService.getEmail(m.id);
  } catch {
    /* on garde la version liste */
  }
  // Marquer comme lu si email entrant non lu
  if (m.direction === "inbound" && m.status === "non_lu") {
    try {
      await emailService.updateStatus(m.id, { status: "lu" });
      m.status = "lu";
      if (selectedEmail.value) selectedEmail.value.status = "lu";
    } catch {
      /* non bloquant */
    }
  }
}

async function archive(m) {
  try {
    await emailService.updateStatus(m.id, { status: "archive" });
    m.status = "archive";
    if (selectedEmail.value?.id === m.id) selectedEmail.value.status = "archive";
  } catch {
    /* non bloquant */
  }
}

function onConverted(updated) {
  selectedEmail.value = updated;
  // Synchronise la liste (statut traité + rattachement)
  const arr = updated.direction === "inbound" ? inbox.value : sent.value;
  const idx = arr.findIndex((m) => m.id === updated.id);
  if (idx !== -1) {
    arr[idx].status = updated.status;
    arr[idx].demande_id = updated.demande_id;
  }
}
function startCompose() {
  replying.value = false;
  replyToId.value = null;
  recipient.value = null;
  recipientItems.value = [];
  subject.value = "";
  body.value = "";
  cc.value = [];
  ccOpen.value = false;
  attachments.value = [];
  feedback.text = "";
  selectedEmail.value = null;
  mode.value = "compose";
}
function startReply() {
  const m = selectedEmail.value;
  if (!m) return;
  replying.value = true;
  replyToId.value = m.id;
  // Réponse : on écrit à l'interlocuteur (expéditeur si reçu, destinataire si envoyé)
  const email = peerAddress(m);
  const item = {
    contact_id: m.contact_id || null,
    email,
    label: `${displayName(email)} <${email}>`,
  };
  recipientItems.value = [item];
  recipient.value = item;
  subject.value = (m.subject || "").startsWith("Re:")
    ? m.subject
    : `Re: ${m.subject || ""}`;
  body.value = "";
  cc.value = [];
  ccOpen.value = false;
  attachments.value = [];
  feedback.text = "";
  mode.value = "compose";
}
function cancelCompose() {
  mode.value = selectedEmail.value ? "read" : "empty";
}

// ── Recherche contacts ───────────────────────────────────────────────────────
function toItem(c) {
  const name =
    [c.prenom, c.nom].filter(Boolean).join(" ") || c.fullName || c.email;
  return {
    contact_id: c.id,
    email: c.email,
    label: c.email ? `${name} <${c.email}>` : name,
  };
}
function onSearch(q) {
  clearTimeout(searchTimer);
  if (!q || q.length < 2) return;
  searchTimer = setTimeout(async () => {
    searching.value = true;
    try {
      const data = await searchContacts({ name: q, perPage: 10 });
      const list = data.contacts ?? data ?? [];
      recipientItems.value = list.filter((c) => c.email).map(toItem);
    } catch {
      recipientItems.value = [];
    } finally {
      searching.value = false;
    }
  }, 300);
}

async function syncNow() {
  syncing.value = true;
  try {
    const res = await emailService.fetchNow();
    await loadEmails();
    const n = res.fetched ?? 0;
    syncSnack.color = "#00a8a8";
    syncSnack.text = n > 0
      ? `${n} nouvel(s) email(s) collecté(s).`
      : "Aucun nouvel email.";
    syncSnack.show = true;
    if (!tab.value || tab.value === "sent") tab.value = "inbox";
  } catch (err) {
    syncSnack.color = "#e74c3c";
    syncSnack.text = err?.response?.data?.error || "Échec de la synchronisation.";
    syncSnack.show = true;
  } finally {
    syncing.value = false;
  }
}

// ── Données / envoi ──────────────────────────────────────────────────────────
async function loadEmails() {
  loadingList.value = true;
  try {
    const [inb, out] = await Promise.all([
      emailService.listEmails({ direction: "inbound", limit: 100 }),
      emailService.listEmails({ direction: "outbound", limit: 100 }),
    ]);
    inbox.value = inb.emails ?? [];
    sent.value = out.emails ?? [];
  } catch {
    /* silencieux */
  } finally {
    loadingList.value = false;
  }
}

async function send() {
  feedback.text = "";
  const { valid } = await formRef.value.validate();
  if (!valid) return;
  sending.value = true;
  try {
    await emailService.sendEmail({
      to_contact_id: recipient.value?.contact_id || undefined,
      to: recipient.value?.contact_id ? undefined : recipient.value?.email,
      cc: cc.value,
      subject: subject.value.trim(),
      body: body.value.trim(),
      reply_to: replyToId.value || undefined,
      attachments: attachments.value,
    });
    feedback.type = "success";
    feedback.text = "Email envoyé.";
    subject.value = "";
    body.value = "";
    cc.value = [];
    ccOpen.value = false;
    replyToId.value = null;
    attachments.value = [];
    await loadEmails();
    cancelCompose();
  } catch (err) {
    feedback.type = "error";
    feedback.text = err?.response?.data?.error || "Échec de l'envoi.";
  } finally {
    sending.value = false;
  }
}

function applyInitialContact() {
  if (props.initialContact?.email) {
    startCompose();
    const item = toItem({
      id: props.initialContact.id,
      nom: props.initialContact.fullName,
      email: props.initialContact.email,
    });
    recipientItems.value = [item];
    recipient.value = item;
  }
}

onMounted(() => {
  loadEmails();
  applyInitialContact();
});
</script>

<style scoped>
.mc-root {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: 340px 1fr;
  height: 100%;
  min-height: 420px;
  font-family: "Fira Sans", sans-serif;
  background: #fff;
  color: #1a1a2e;
}

/* ══ SIDEBAR ══════════════════════════════════════════════════════════════ */
.mc-sidebar {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e5e7eb;
  overflow: hidden;
  background: #fafbfc;
}

.mc-top {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
}
.mc-write {
  flex: 1;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  font-weight: 600;
  color: #000b23;
  cursor: pointer;
  transition:
    border-color 0.15s,
    color 0.15s;
}
.mc-write:hover {
  border-color: #00a8a8;
  color: #00a8a8;
}

.mc-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.15s;
}
.mc-icon-btn:hover,
.mc-icon-btn--on {
  border-color: #00a8a8;
  color: #00a8a8;
}
.mc-icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.mc-spin {
  animation: mc-rotate 0.8s linear infinite;
}
@keyframes mc-rotate {
  to {
    transform: rotate(360deg);
  }
}

.mc-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 14px 8px;
  padding: 0 10px;
  height: 34px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}
.mc-search__input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 12.5px;
  font-family: "Fira Sans", sans-serif;
  background: transparent;
}
.mc-search__clear {
  border: none;
  background: none;
  cursor: pointer;
  color: #9aa0aa;
  display: flex;
}

/* Onglets */
.mc-tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  margin: 0 14px 6px;
  background: #eef0f3;
  border-radius: 8px;
}
.mc-tab {
  flex: 1;
  height: 30px;
  border: none;
  border-radius: 6px;
  background: transparent;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  transition:
    background 0.15s,
    color 0.15s;
}
.mc-tab--on {
  background: #fff;
  color: #000b23;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.mc-tab__count {
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-weight: 700;
  color: #00a8a8;
  background: rgba(0, 168, 168, 0.1);
  border-radius: 8px;
  padding: 0 5px;
}

/* Liste */
.mc-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px 12px;
}
.mc-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 16px;
  color: #9aa0aa;
  font-size: 12.5px;
}

.mc-item {
  width: 100%;
  display: flex;
  gap: 11px;
  text-align: left;
  padding: 11px;
  border: none;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  transition: background 0.12s;
  margin-bottom: 2px;
}
.mc-item:hover {
  background: #f1f3f5;
}
.mc-item--active {
  background: #fff;
  box-shadow:
    0 0 0 1px #e5e7eb,
    0 2px 6px rgba(0, 11, 35, 0.05);
}

.mc-avatar {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  font-family: "Fira Sans", sans-serif;
}
.mc-avatar--lg {
  width: 42px;
  height: 42px;
  font-size: 14px;
}

.mc-item__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.mc-item__line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.mc-item__name {
  font-size: 13px;
  font-weight: 700;
  color: #000b23;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mc-item__time {
  font-size: 10.5px;
  color: #9aa0aa;
  font-family: "Fira Code", monospace;
  flex-shrink: 0;
}
.mc-item__subject {
  font-size: 12.5px;
  font-weight: 600;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mc-item__preview {
  font-size: 11.5px;
  color: #9aa0aa;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mc-item__tags {
  margin-top: 3px;
}

.mc-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 10px;
}
.mc-pill--sent,
.mc-pill--traite {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}
.mc-pill--failed,
.mc-pill--spam {
  background: rgba(231, 76, 60, 0.1);
  color: #c0392b;
}
.mc-pill--non_lu {
  background: rgba(0, 168, 168, 0.12);
  color: #007a7a;
}
.mc-pill--lu,
.mc-pill--archive {
  background: #f0f1f3;
  color: #6b7280;
}

/* Email non lu : mise en avant */
.mc-item--unread .mc-item__name,
.mc-item--unread .mc-item__subject {
  font-weight: 800;
  color: #000b23;
}
.mc-unread-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #00a8a8;
  margin-right: 5px;
  vertical-align: middle;
}
.mc-tag-att {
  color: #9aa0aa;
  margin-right: 4px;
}

/* ══ VOLET PRINCIPAL ══════════════════════════════════════════════════════ */
.mc-main {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Lecture ── */
.mc-read {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.mc-read__head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 24px;
  border-bottom: 1px solid #e5e7eb;
}
.mc-read__who {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.mc-read__name {
  font-size: 15px;
  font-weight: 700;
  color: #000b23;
}
.mc-read__addr {
  font-size: 12.5px;
  color: #6b7280;
}
.mc-read__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
.mc-read__date {
  font-size: 11px;
  color: #9aa0aa;
  font-family: "Fira Code", monospace;
}

.mc-read__scroll {
  flex: 1;
  overflow-y: auto;
  padding: 22px 24px;
}
.mc-read__subject {
  font-size: 18px;
  font-weight: 700;
  color: #000b23;
  margin: 0 0 14px;
}
.mc-read__error {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: #c0392b;
  margin: 0 0 12px;
}
.mc-read__body {
  font-size: 14px;
  line-height: 1.65;
  color: #374151;
  white-space: pre-wrap;
}
/* Rendu HTML : on neutralise le pre-wrap et on borne les médias */
.mc-read__body--html {
  white-space: normal;
}
.mc-read__body--html :deep(img) {
  max-width: 100%;
  height: auto;
}
.mc-read__body--html :deep(a) {
  color: #00a8a8;
}
.mc-read__body--html :deep(table) {
  border-collapse: collapse;
  max-width: 100%;
}
.mc-read__body--html :deep(td),
.mc-read__body--html :deep(th) {
  border: 1px solid #e5e7eb;
  padding: 4px 8px;
}
.mc-read__body--html :deep(blockquote) {
  border-left: 3px solid #e5e7eb;
  margin: 8px 0;
  padding-left: 12px;
  color: #6b7280;
}

.mc-attach {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid #eef0f3;
}
.mc-attach__lbl {
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
}
.mc-attach__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.mc-attach__item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafbfc;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s;
  max-width: 260px;
}
.mc-attach__item:hover {
  border-color: #00a8a8;
  background: #fff;
}
.mc-attach__name {
  font-size: 12.5px;
  font-weight: 600;
  color: #15223a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mc-attach__size {
  font-size: 10.5px;
  color: #9aa0aa;
  font-family: "Fira Code", monospace;
  flex-shrink: 0;
}
.mc-attachments {
  margin-top: 14px;
}
.mc-cc-toggle {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  color: #00a8a8;
  padding: 0 4px;
}
.mc-cc-toggle:hover {
  text-decoration: underline;
}
.mc-read__cc {
  font-size: 12.5px;
  color: #6b7280;
  margin: -8px 0 14px;
}

.mc-read__foot {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  padding: 14px 24px;
  border-top: 1px solid #e5e7eb;
}
.mc-linked {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  color: #15803d;
}

/* ── Composition ── */
.mc-compose {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.mc-compose__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid #e5e7eb;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #000b23;
}
.mc-alert {
  margin: 14px 24px 0;
}
.mc-form {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 8px 24px 16px;
  overflow: hidden;
}

.mc-field {
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #eef0f3;
  padding: 6px 0;
}
.mc-field__lbl {
  width: 48px;
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  flex-shrink: 0;
}
.mc-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  font-weight: 600;
  color: #000b23;
  font-family: "Fira Sans", sans-serif;
  background: transparent;
}

.mc-textarea {
  flex: 1;
  margin-top: 14px;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  color: #374151;
  font-family: "Fira Sans", sans-serif;
  background: transparent;
  min-height: 160px;
}
.mc-textarea::placeholder {
  color: #c4c9d0;
}

.mc-compose__foot {
  display: flex;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #eef0f3;
}
.mc-send {
  min-width: 130px;
}
.mc-nodata {
  padding: 8px 12px;
  font-size: 12px;
  color: #9aa0aa;
}

/* ── Vide ── */
.mc-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 8px;
  padding: 32px;
  text-align: center;
}
.mc-empty__title {
  font-size: 15px;
  font-weight: 700;
  color: #000b23;
  margin: 6px 0 0;
}
.mc-empty__sub {
  font-size: 12.5px;
  color: #9aa0aa;
  margin: 0;
  max-width: 320px;
}
</style>
