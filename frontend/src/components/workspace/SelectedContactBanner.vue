<template>
  <div class="scb-root">
    <!-- Barre de progression (loading) -->
    <div v-if="loading" class="scb-loader" aria-hidden="true">
      <div class="scb-loader__bar"></div>
    </div>

    <!-- ── Bloc gauche : identité ─────────────────────────────────────────── -->
    <div class="scb-identity">
      <!-- Avatar -->
      <div class="scb-avatar-wrap">
        <img
          v-if="contact.avatarUrl"
          :src="contact.avatarUrl"
          :alt="`Photo de ${contact.fullName}`"
          class="scb-avatar"
        />
        <div
          v-else
          class="scb-avatar scb-avatar--fallback"
          :style="{ background: avatarBg }"
          aria-hidden="true"
        >
          {{ initials }}
        </div>
        <span
          class="scb-status-dot"
          :style="{ background: resolvedStatusColor }"
          :title="`Statut : ${contact.statusLabel ?? 'En ligne'}`"
          role="img"
          :aria-label="`Statut : ${contact.statusLabel ?? 'En ligne'}`"
        ></span>
      </div>

      <!-- Nom + métadonnées -->
      <div class="scb-info">
        <div class="scb-name">{{ contact.fullName }}</div>
        <div class="scb-meta">
          <span class="scb-meta__item">
            <v-icon size="11" color="#aaa" aria-hidden="true">
              mdi-briefcase-outline
            </v-icon>
            {{ contact.jobTitle }}
          </span>
          <span class="scb-meta__sep" aria-hidden="true"></span>
          <span class="scb-meta__item scb-meta__item--mono">
            <v-icon size="11" color="#aaa" aria-hidden="true">
              mdi-identifier
            </v-icon>
            {{ contact.id }}
          </span>
        </div>
      </div>
    </div>

    <!-- ── Bloc droit : actions ───────────────────────────────────────────── -->
    <div
      v-if="showActions"
      class="scb-actions"
      role="toolbar"
      aria-label="Actions rapides contact"
    >
      <button
        v-if="showCall"
        class="scb-btn scb-btn--secondary"
        :disabled="loading"
        aria-label="Passer un appel"
        @click="emit('call')"
      >
        <v-icon size="13" aria-hidden="true">mdi-phone</v-icon>
        APPEL
      </button>

      <button
        v-if="showEmail"
        class="scb-btn scb-btn--secondary"
        :disabled="loading"
        aria-label="Envoyer un email"
        @click="emit('email')"
      >
        <v-icon size="13" aria-hidden="true">mdi-email-outline</v-icon>
        EMAIL
      </button>

      <v-menu location="bottom end" :close-on-content-click="true">
        <template #activator="{ props: menuProps }">
          <button
            class="scb-btn scb-btn--primary scb-btn--wide"
            :disabled="!canCreateDemande || loading"
            aria-haspopup="listbox"
            aria-label="Créer une nouvelle demande"
            v-bind="menuProps"
          >
            <v-icon size="13" aria-hidden="true"
              >mdi-plus-circle-outline</v-icon
            >
            NOUVELLE DEMANDE
            <v-icon size="11" aria-hidden="true" style="margin-left: 3px"
              >mdi-chevron-down</v-icon
            >
          </button>
        </template>
        <v-list density="compact" min-width="220">
          <v-list-item
            v-for="opt in demandeTypes"
            :key="opt.type"
            :prepend-icon="opt.icon"
            :title="opt.label"
            :subtitle="opt.disabled ? 'Bientôt disponible' : undefined"
            :disabled="opt.disabled"
            @click="!opt.disabled && emit('new-demande', opt.type)"
          />
        </v-list>
      </v-menu>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useAuthStore } from "@/store/auth";

const authStore = useAuthStore();
const features = computed(() => authStore.featureMap);

// EMAIL : visible seulement si la messagerie est complètement fonctionnelle
// (canal email + SMTP + IMAP configurés → workspace_tabs.mail).
const showEmail = computed(() => features.value.workspace_tabs?.mail === true);
// APPEL : visible seulement si l'intégration téléphonie est activée.
const showCall = computed(() => features.value.integrations?.telephony === true);

const DEMANDE_TYPES = [
  { type: "anomalie", label: "Anomalie", icon: "mdi-alert-circle-outline" },
  { type: "commande", label: "Commande", icon: "mdi-cart-outline" },
  {
    type: "admin",
    label: "Demande Administrative",
    icon: "mdi-file-document-outline",
    disabled: true,
  },
  {
    type: "planning",
    label: "Gestion Planning",
    icon: "mdi-calendar-clock-outline",
    disabled: true,
  },
];

// "Prise de service" : exclusivement pour les contacts de type agent.
const demandeTypes = computed(() =>
  props.isAgent
    ? [...DEMANDE_TYPES, { type: "prise_de_service", label: "Prise de service", icon: "mdi-clock-start" }]
    : DEMANDE_TYPES,
);

const props = defineProps({
  contact: {
    type: Object,
    required: true,
    // Shape attendu :
    // {
    //   id: String,
    //   fullName: String,
    //   jobTitle: String,
    //   avatarUrl?: String,
    //   statusColor?: 'teal' | 'green' | 'red' | 'orange' | 'gray',
    //   statusLabel?: String,
    // }
  },
  showActions: { type: Boolean, default: true },
  canCreateDemande: { type: Boolean, default: true },
  loading: { type: Boolean, default: false },
  isAgent: { type: Boolean, default: false },
});

const emit = defineEmits(["call", "email", "new-demande"]);

// ─── Initiales (max 2 caractères) ─────────────────────────────────────────
const initials = computed(() =>
  (props.contact.fullName ?? "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join(""),
);

// ─── Couleur avatar (déterministe, calquée sur UsersView.userAvatarColor) ─
const avatarBg = computed(() => {
  const str = (props.contact.fullName ?? "").replace(/\s/g, "");
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return `hsl(${Math.abs(hash) % 360}, 45%, 42%)`;
});

// ─── Couleur du point de statut ───────────────────────────────────────────
const STATUS_COLORS = {
  teal: "#00a8a8",
  green: "#27ae60",
  red: "#e74c3c",
  orange: "#f39c12",
  gray: "#bbb",
};

const resolvedStatusColor = computed(
  () => STATUS_COLORS[props.contact.statusColor] ?? STATUS_COLORS.teal,
);
</script>

<script>
export default { name: "SelectedContactBanner" };
</script>

<style scoped>
/* ══ RACINE ════════════════════════════════════════════════════════════════ */

.scb-root {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 4px;
  padding: 10px 16px;
  flex-shrink: 0;
  overflow: hidden;
}

/* ══ LOADER ════════════════════════════════════════════════════════════════ */

.scb-loader {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  overflow: hidden;
  z-index: 1;
}

.scb-loader__bar {
  height: 100%;
  background: #00a8a8;
  animation: scb-slide 1.2s ease-in-out infinite;
  transform-origin: left;
}

@keyframes scb-slide {
  0% {
    transform: translateX(-100%) scaleX(0.5);
  }
  50% {
    transform: translateX(25%) scaleX(0.6);
  }
  100% {
    transform: translateX(100%) scaleX(0.4);
  }
}

/* ══ IDENTITÉ ══════════════════════════════════════════════════════════════ */

.scb-identity {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

/* Avatar wrapper */
.scb-avatar-wrap {
  position: relative;
  flex-shrink: 0;
}

/* Avatar image ou fallback */
.scb-avatar {
  width: 44px;
  height: 44px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  display: block;
  object-fit: cover;
}

.scb-avatar--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: "Fira Code", monospace;
  font-size: 13px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.92);
  user-select: none;
}

/* Indicateur de statut (coin bas-droit) */
.scb-status-dot {
  position: absolute;
  bottom: -3px;
  right: -3px;
  width: 11px;
  height: 11px;
  border-radius: 2px;
  border: 2px solid #fff;
}

/* Infos texte */
.scb-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.scb-name {
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #000b23;
  text-transform: uppercase;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Ligne de métadonnées */
.scb-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.scb-meta__item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10.5px;
  color: #888;
  white-space: nowrap;
}

.scb-meta__item--mono {
  font-family: "Fira Code", monospace;
  font-size: 10px;
  letter-spacing: 0.06em;
}

.scb-meta__sep {
  width: 1px;
  height: 11px;
  background: rgba(0, 0, 0, 0.12);
  flex-shrink: 0;
}

/* ══ ACTIONS ═══════════════════════════════════════════════════════════════ */

.scb-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

/* Base bouton */
.scb-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 12px;
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background 0.15s,
    border-color 0.15s,
    opacity 0.15s;
  outline: none;
}

.scb-btn:focus-visible {
  outline: 2px solid #00a8a8;
  outline-offset: 2px;
}

.scb-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Secondaire — APPEL */
.scb-btn--secondary {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.14);
  color: #444;
}

.scb-btn--secondary:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.04);
  border-color: rgba(0, 0, 0, 0.22);
}

/* Primaire — APPEL, NOUVELLE INTERACTION */
.scb-btn--primary {
  background: #009090;
  border: 1px solid transparent;
  color: #fff;
}

.scb-btn--primary:hover:not(:disabled) {
  background: #0a0c14;
}

/* Bouton large */
.scb-btn--wide {
  padding: 0 16px;
}

/* ══ RESPONSIVE ════════════════════════════════════════════════════════════ */

@media (max-width: 900px) {
  .scb-root {
    flex-wrap: wrap;
    gap: 10px;
    padding: 10px 12px;
  }
  .scb-actions {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 480px) {
  .scb-btn--wide {
    flex: 1;
    justify-content: center;
  }
}
</style>
