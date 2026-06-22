<template>
  <div class="login-page">
    <v-row no-gutters class="h-100">
      <!-- Left Banner Panel -->
      <v-col
        cols="12"
        md="6"
        class="login-banner-panel d-none d-md-flex flex-column"
      >
        <!-- Image de fond + overlay -->
        <div class="banner-bg"></div>
        <div class="banner-overlay"></div>

        <!-- Contenu superposé -->
        <div class="banner-body">
          <!-- Logo / marque en haut -->
          <div class="banner-brand">
            <span class="banner-brand__mark"></span>
            <span class="banner-brand__name">PERMATEL</span>
          </div>

          <!-- Texte principal au centre -->
          <div class="banner-center">
            <p class="banner-kicker reveal reveal--1">
              PLATEFORME DE PERMANENCE
            </p>
            <h2 class="banner-headline reveal reveal--1">
              Supervision &amp;<br />Gestion opérationnelle<br />des agents de
              sécurité
            </h2>
            <p class="banner-desc reveal reveal--2">
              Centralisez le suivi des anomalies, des commandes de
              prestations<br />
              et des interventions terrain en temps réel.
            </p>
          </div>

          <!-- Pastilles de features en bas -->
          <div class="banner-features reveal reveal--3">
            <div class="banner-feature">
              <span class="banner-feature__icon">
                <v-icon size="14" color="#00a8a8"
                  >mdi-shield-check-outline</v-icon
                >
              </span>
              <span>Alertes en temps réel</span>
            </div>
            <div class="banner-feature">
              <span class="banner-feature__icon">
                <v-icon size="14" color="#00a8a8"
                  >mdi-account-multiple-outline</v-icon
                >
              </span>
              <span>Multi-clients &amp; multi-sites</span>
            </div>
            <div class="banner-feature">
              <span class="banner-feature__icon">
                <v-icon size="14" color="#00a8a8">mdi-chart-line</v-icon>
              </span>
              <span>Reporting &amp; traçabilité</span>
            </div>
          </div>
        </div>
      </v-col>

      <!-- Right Form Panel -->
      <v-col
        cols="12"
        md="6"
        class="d-flex align-center justify-center pa-4 form-panel"
      >
        <v-card
          class="form-container reveal-form"
          elevation="4"
          width="100%"
          max-width="450"
          color="white"
        >
          <v-card-item class="text-center">
            <v-card-title class="form-title">Accès Opérateur</v-card-title>
            <v-card-subtitle class="form-subtitle">
              Veuillez vous authentifier pour accéder au tableau de bord.
            </v-card-subtitle>
          </v-card-item>

          <v-card-text>
            <v-form @submit.prevent="handleLogin">
              <v-alert
                v-if="errorMessage"
                type="error"
                variant="tonal"
                density="compact"
                class="mb-6"
                border="start"
                closable
                @click:close="errorMessage = null"
              >
                {{ errorMessage }}
              </v-alert>

              <v-text-field
                v-model="username"
                label="Email"
                placeholder="ex: prenom.nom@exemple.com"
                type="email"
                variant="outlined"
                prepend-inner-icon="mdi-email-outline"
                required
                autofocus
                class="input-fira-code"
              ></v-text-field>

              <v-text-field
                v-model="password"
                label="Mot de passe"
                placeholder="••••••••••••"
                type="password"
                variant="outlined"
                prepend-inner-icon="mdi-lock-outline"
                required
                class="mt-3 input-fira-code"
              ></v-text-field>

              <v-btn
                :loading="loading"
                :disabled="loading"
                type="submit"
                color="secondary"
                block
                size="large"
                class="mt-6 text-none"
                text="Se Connecter"
              >
              </v-btn>
            </v-form>
          </v-card-text>

          <v-card-text class="text-center login-footer">
            Problème de connexion ?
            <a href="#" @click.prevent="supportOpen = true">Contacter le support</a>.
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Dialog : contacter le support -->
    <v-dialog v-model="supportOpen" max-width="600" transition="dialog-bottom-transition">
      <ContactSupportView @close="supportOpen = false" />
    </v-dialog>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/store/auth";
import ContactSupportView from "@/components/auth/ContactSupportView.vue";

const username = ref("");
const password = ref("");
const errorMessage = ref(null);
const loading = ref(false);
const supportOpen = ref(false);

const router = useRouter();
const authStore = useAuthStore();

const handleLogin = async () => {
  loading.value = true;
  errorMessage.value = null;
  const result = await authStore.login(username.value, password.value);
  loading.value = false;

  if (result.success) {
    // Multi-tenant : si une sélection est requise, passer par l'écran dédié
    // (mémorise la destination initiale pour y revenir après le choix).
    if (authStore.needsTenantSelection) {
      authStore.returnUrl = result.returnUrl;
      router.push({ name: "SelectTenant" });
    } else {
      router.push(result.returnUrl);
    }
  } else {
    errorMessage.value =
      result.error || "Identifiants incorrects ou erreur serveur.";
  }
};
</script>

<style scoped>
/* ── Page ───────────────────────────────────────────────────────── */
.login-page {
  height: 100vh;
  width: 100vw;
  background-color: #f2f2f2;
  font-family: "Fira Sans", sans-serif;
}

/* ══ BANNIÈRE GAUCHE ════════════════════════════════════════════════ */

/* Override Vuetify col-6 (50%) → 47% pour un élargissement subtil
   sans que le formulaire soit à l'étroit */
.login-banner-panel {
  flex: 0 0 60% !important;
  max-width: 60% !important;
  position: relative;
  overflow: hidden;
}

/* Le panneau formulaire prend le reste, avec un minimum pour le card */
.form-panel {
  flex: 0 0 40% !important;
  max-width: 40% !important;
  min-width: 380px;
}

/* Image de fond — plein cadre, centrée (ajuster background-position si besoin) */
.banner-bg {
  position: absolute;
  inset: 0;
  background: url("../assets/login_banner-security-company.jpg") no-repeat;
  background-size: cover;
  background-position: center center;
  z-index: 0;
}

/* Double overlay : dégradé haut (navy dense) → bas (teal léger) */
.banner-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    165deg,
    rgba(0, 11, 35, 0.88) 0%,
    rgba(0, 11, 35, 0.72) 50%,
    rgba(0, 40, 40, 0.65) 100%
  );
  z-index: 1;
}

/* Contenu superposé */
.banner-body {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 36px 40px;
}

/* ── Marque ─────────────────────────────────────────────────────── */
.banner-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.banner-brand__mark {
  display: inline-block;
  width: 4px;
  height: 22px;
  background: #00a8a8;
  border-radius: 2px;
  flex-shrink: 0;
}

.banner-brand__name {
  font-family: "Fira Code", monospace;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.22em;
  color: #ffffff;
  text-transform: uppercase;
}

/* ── Bloc central ───────────────────────────────────────────────── */
.banner-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding-bottom: 24px;
}

.banner-kicker {
  font-family: "Fira Code", monospace;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.22em;
  color: #00a8a8;
  text-transform: uppercase;
  margin: 0 0 18px;
}

.banner-headline {
  font-family: "Fira Sans", sans-serif;
  font-size: clamp(22px, 2.4vw, 30px);
  font-weight: 800;
  line-height: 1.25;
  color: #ffffff;
  margin: 0 0 20px;
  letter-spacing: -0.01em;
}

.banner-desc {
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  font-weight: 400;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.6);
  margin: 0;
}

/* ── Features ───────────────────────────────────────────────────── */
.banner-features {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 28px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.banner-feature {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: "Fira Sans", sans-serif;
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.72);
}

.banner-feature__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: rgba(0, 168, 168, 0.15);
  border: 1px solid rgba(0, 168, 168, 0.3);
  flex-shrink: 0;
}

/* ══ PANEL FORMULAIRE ══════════════════════════════════════════════ */
.form-container {
  border: 1px solid rgba(197, 198, 206, 0.15) !important;
  background-color: var(--surface-container-lowest);
}

.form-title {
  font-family: "Fira Code", monospace;
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--primary);
  line-height: 1.2;
}

.form-subtitle {
  font-family: "Fira Sans", sans-serif;
  white-space: normal;
}

.login-footer {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.8rem;
  color: #6c757d;
}

.login-footer a {
  color: var(--secondary);
  text-decoration: none;
  font-weight: 600;
}
.login-footer a:hover {
  text-decoration: underline;
}

.input-fira-code :deep(input) {
  font-family: "Fira Code", monospace;
}

.v-btn[color="primary-container"] {
  background-color: var(--primary-container);
  color: var(--on-primary);
}

/* ══ Révélation au chargement (sobre / premium) ════════════════════════ */
@keyframes revealSlideLeft {
  from {
    opacity: 0;
    transform: translateX(-24px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
@keyframes revealFade {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Texte gauche : slide-left doux, 3 lots successifs (brand reste fixe) */
.reveal {
  opacity: 0;
  will-change: opacity, transform;
  animation: revealSlideLeft 0.6s cubic-bezier(0.22, 0.61, 0.36, 1) both;
}
.reveal--1 {
  animation-delay: 0.05s;
}
.reveal--2 {
  animation-delay: 0.25s;
}
.reveal--3 {
  animation-delay: 0.45s;
}

/* Formulaire : fade-in discret, après la fin des textes */
.reveal-form {
  opacity: 0;
  will-change: opacity, transform;
  animation: revealFade 0.5s ease-out both;
  animation-delay: 1s;
}

/* Bannière masquée < md : le formulaire apparaît quasi immédiatement */
@media (max-width: 959.98px) {
  .reveal-form {
    animation-delay: 0.12s;
  }
}

/* Accessibilité : aucun mouvement, contenu lisible immédiatement */
@media (prefers-reduced-motion: reduce) {
  .reveal,
  .reveal-form {
    animation: none;
    opacity: 1;
    transform: none;
  }
}
</style>
