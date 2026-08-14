<template>
  <div class="mp-root">
    <div class="mp-hdr">
      <div class="mp-hdr-title-row">
        <span class="mp-hdr-marker"></span>
        <h1 class="mp-title">Mon Profil</h1>
      </div>
      <p class="mp-subtitle">
        Gérez vos informations personnelles, votre avatar et votre mot de passe.
      </p>
    </div>

    <div class="mp-body">
      <!-- ── Section Avatar ─────────────────────────────────────────── -->
      <section class="mp-sec">
        <header class="mp-sec-hdr">
          <span class="mp-sec-mark mp-sec-mark--teal"></span>
          <span class="mp-sec-lbl">AVATAR</span>
          <span class="mp-sec-rule"></span>
        </header>

        <div v-if="avatarError" class="mp-error-bar">
          <v-icon size="12" color="#e74c3c">mdi-alert-circle-outline</v-icon>
          {{ avatarError }}
        </div>

        <div class="mp-avatar-row">
          <div class="mp-avatar-preview">
            <img
              v-if="avatarPreviewUrl"
              :src="avatarPreviewUrl"
              alt="Avatar"
              class="mp-avatar-img"
            />
            <span v-else class="mp-avatar-initials">{{ userInitials }}</span>
          </div>
          <div class="mp-avatar-actions">
            <input
              ref="fileInput"
              type="file"
              accept=".png,.jpg,.jpeg,.gif,.webp"
              class="mp-file-input"
              @change="onAvatarSelected"
            />
            <button
              class="mp-btn-outline"
              :disabled="avatarSaving"
              @click="fileInput?.click()"
            >
              <v-icon size="13">mdi-camera-outline</v-icon>
              Changer l'avatar
            </button>
            <button
              v-if="authStore.user?.avatar_url"
              class="mp-btn-outline mp-btn-outline--danger"
              :disabled="avatarSaving"
              @click="removeAvatar"
            >
              <v-icon size="13">mdi-trash-can-outline</v-icon>
              Supprimer
            </button>
          </div>
        </div>
      </section>

      <!-- ── Section Identité ───────────────────────────────────────── -->
      <section class="mp-sec">
        <header class="mp-sec-hdr">
          <span class="mp-sec-mark mp-sec-mark--navy"></span>
          <span class="mp-sec-lbl">IDENTITÉ</span>
          <span class="mp-sec-rule"></span>
        </header>

        <div v-if="identityError" class="mp-error-bar">
          <v-icon size="12" color="#e74c3c">mdi-alert-circle-outline</v-icon>
          {{ identityError }}
        </div>
        <div v-if="identitySuccess" class="mp-success-bar">
          <v-icon size="12" color="#00a884">mdi-check-circle-outline</v-icon>
          Profil mis à jour.
        </div>

        <div class="mp-grid">
          <div class="form-group">
            <label class="form-label">PRÉNOM</label>
            <input
              v-model="identityForm.prenom"
              class="form-input"
              autocomplete="off"
            />
          </div>
          <div class="form-group">
            <label class="form-label">NOM</label>
            <input
              v-model="identityForm.nom"
              class="form-input"
              autocomplete="off"
            />
          </div>
        </div>

        <div class="mp-sec-footer">
          <button
            class="mp-btn-save"
            :disabled="identitySaving"
            @click="saveIdentity"
          >
            <span v-if="identitySaving" class="mp-spinner"></span>
            ENREGISTRER
          </button>
        </div>
      </section>

      <!-- ── Section Mot de passe ───────────────────────────────────── -->
      <section class="mp-sec">
        <header class="mp-sec-hdr">
          <span class="mp-sec-mark mp-sec-mark--amber"></span>
          <span class="mp-sec-lbl">MOT DE PASSE</span>
          <span class="mp-sec-rule"></span>
        </header>

        <div v-if="passwordError" class="mp-error-bar">
          <v-icon size="12" color="#e74c3c">mdi-alert-circle-outline</v-icon>
          {{ passwordError }}
        </div>
        <div v-if="passwordSuccess" class="mp-success-bar">
          <v-icon size="12" color="#00a884">mdi-check-circle-outline</v-icon>
          Mot de passe mis à jour.
        </div>

        <div class="mp-grid">
          <div class="form-group mp-full">
            <label class="form-label">MOT DE PASSE ACTUEL</label>
            <input
              v-model="passwordForm.old_password"
              type="password"
              class="form-input"
              autocomplete="current-password"
            />
          </div>
          <div class="form-group">
            <label class="form-label">NOUVEAU MOT DE PASSE</label>
            <input
              v-model="passwordForm.new_password"
              type="password"
              class="form-input"
              autocomplete="new-password"
            />
          </div>
          <div class="form-group">
            <label class="form-label">CONFIRMATION</label>
            <input
              v-model="passwordForm.confirm_password"
              type="password"
              class="form-input"
              autocomplete="new-password"
            />
          </div>
        </div>
        <p class="mp-hint">Minimum 12 caractères.</p>

        <div class="mp-sec-footer">
          <button
            class="mp-btn-save"
            :disabled="passwordSaving"
            @click="savePassword"
          >
            <span v-if="passwordSaving" class="mp-spinner"></span>
            CHANGER LE MOT DE PASSE
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from "vue";
import { useAuthStore } from "@/store/auth";
import { userService } from "@/services/userService";

const authStore = useAuthStore();

const BACKEND_ORIGIN = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api"
).replace(/\/api\/?$/, "");

const userInitials = computed(() => {
  const u = authStore.user;
  const ini = `${u?.prenom?.[0] ?? ""}${u?.nom?.[0] ?? ""}`.trim();
  return (ini || u?.username?.slice(0, 2) || "?").toUpperCase();
});

const avatarPreviewUrl = computed(() => {
  const path = authStore.user?.avatar_url;
  if (!path) return null;
  return /^https?:\/\//.test(path) ? path : BACKEND_ORIGIN + path;
});

// ── Avatar ─────────────────────────────────────────────────────────────
const fileInput = ref(null);
const avatarSaving = ref(false);
const avatarError = ref("");

async function onAvatarSelected(e) {
  const file = e.target.files?.[0];
  e.target.value = "";
  if (!file) return;

  avatarError.value = "";
  avatarSaving.value = true;
  try {
    const payload = new FormData();
    payload.append("data", JSON.stringify({}));
    payload.append("avatar", file);
    const { data } = await userService.updateMyProfile(payload);
    authStore.updateUserLocal(data.user);
  } catch (err) {
    avatarError.value =
      err?.response?.data?.message ?? "Erreur lors de l'envoi de l'avatar.";
  } finally {
    avatarSaving.value = false;
  }
}

async function removeAvatar() {
  avatarError.value = "";
  avatarSaving.value = true;
  try {
    const { data } = await userService.updateMyProfile({ avatar_url: null });
    authStore.updateUserLocal(data.user);
  } catch (err) {
    avatarError.value =
      err?.response?.data?.message ?? "Erreur lors de la suppression.";
  } finally {
    avatarSaving.value = false;
  }
}

// ── Identité ───────────────────────────────────────────────────────────
const identitySaving = ref(false);
const identityError = ref("");
const identitySuccess = ref(false);

const identityForm = reactive({
  nom: authStore.user?.nom ?? "",
  prenom: authStore.user?.prenom ?? "",
});

async function saveIdentity() {
  identityError.value = "";
  identitySuccess.value = false;
  if (!identityForm.nom.trim() || !identityForm.prenom.trim()) {
    identityError.value = "Le nom et le prénom sont requis.";
    return;
  }

  identitySaving.value = true;
  try {
    const { data } = await userService.updateMyProfile({
      nom: identityForm.nom.trim(),
      prenom: identityForm.prenom.trim(),
    });
    authStore.updateUserLocal(data.user);
    identitySuccess.value = true;
  } catch (err) {
    identityError.value =
      err?.response?.data?.message ?? "Erreur lors de la sauvegarde.";
  } finally {
    identitySaving.value = false;
  }
}

// ── Mot de passe ──────────────────────────────────────────────────────
const passwordSaving = ref(false);
const passwordError = ref("");
const passwordSuccess = ref(false);

const passwordForm = reactive({
  old_password: "",
  new_password: "",
  confirm_password: "",
});

async function savePassword() {
  passwordError.value = "";
  passwordSuccess.value = false;

  if (!passwordForm.old_password) {
    passwordError.value = "Le mot de passe actuel est requis.";
    return;
  }
  if (passwordForm.new_password.length < 12) {
    passwordError.value =
      "Le nouveau mot de passe doit comporter au moins 12 caractères.";
    return;
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    passwordError.value = "La confirmation ne correspond pas.";
    return;
  }

  passwordSaving.value = true;
  try {
    await userService.changePassword(
      authStore.user.id,
      passwordForm.old_password,
      passwordForm.new_password,
    );
    passwordForm.old_password = "";
    passwordForm.new_password = "";
    passwordForm.confirm_password = "";
    passwordSuccess.value = true;
  } catch (err) {
    passwordError.value =
      err?.response?.data?.message ??
      "Erreur lors du changement de mot de passe.";
  } finally {
    passwordSaving.value = false;
  }
}
</script>

<style scoped>
.mp-root {
  padding: 20px 24px 40px;
  max-width: 720px;
  margin: 0 auto;
}

.mp-hdr {
  margin-bottom: 20px;
}

.mp-hdr-title-row {
  display: flex;
  align-items: center;
  gap: 9px;
}

.mp-hdr-marker {
  width: 3px;
  height: 18px;
  background: #00a8a8;
  border-radius: 1px;
  flex-shrink: 0;
}

.mp-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #000b23;
  margin: 0;
}

.mp-subtitle {
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  color: #888;
  margin: 6px 0 0 12px;
}

.mp-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.mp-sec {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 6px;
}

.mp-sec-hdr {
  display: flex;
  align-items: center;
  gap: 7px;
}

.mp-sec-mark {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  flex-shrink: 0;
}
.mp-sec-mark--teal {
  background: #00a8a8;
}
.mp-sec-mark--navy {
  background: #000b23;
}
.mp-sec-mark--amber {
  background: #f39c12;
}

.mp-sec-lbl {
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #aaa;
  text-transform: uppercase;
  white-space: nowrap;
}

.mp-sec-rule {
  flex: 1;
  height: 1px;
  background: rgba(0, 0, 0, 0.06);
}

.mp-error-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(231, 76, 60, 0.07);
  border-radius: 4px;
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  color: #e74c3c;
}

.mp-success-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(0, 168, 132, 0.08);
  border-radius: 4px;
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  color: #00a884;
}

.mp-avatar-row {
  display: flex;
  align-items: center;
  gap: 18px;
}

.mp-avatar-preview {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: #000b23;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}

.mp-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mp-avatar-initials {
  font-family: "Fira Sans", sans-serif;
  font-size: 24px;
  font-weight: 700;
  color: #fff;
}

.mp-avatar-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mp-file-input {
  display: none;
}

.mp-btn-outline {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 12px;
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 3px;
  background: #fff;
  font-family: "Fira Sans", sans-serif;
  font-size: 12.5px;
  font-weight: 600;
  color: #555;
  cursor: pointer;
  width: fit-content;
}
.mp-btn-outline:hover:not(:disabled) {
  border-color: #00a8a8;
  color: #00a8a8;
}
.mp-btn-outline:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.mp-btn-outline--danger:hover:not(:disabled) {
  border-color: #e74c3c;
  color: #e74c3c;
}

.mp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 14px;
}

.mp-full {
  grid-column: 1 / -1;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-family: "Fira Sans", sans-serif;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #bbb;
  text-transform: uppercase;
}

.form-input {
  height: 32px;
  padding: 0 8px;
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 3px;
  font-family: "Fira Sans", sans-serif;
  font-size: 12.5px;
  color: #000b23;
  background: #fff;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
  box-sizing: border-box;
}
.form-input:focus {
  border-color: #00a8a8;
}

.mp-hint {
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  color: #999;
  margin: 0;
}

.mp-sec-footer {
  display: flex;
  justify-content: flex-end;
}

.mp-btn-save {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 16px;
  border: none;
  border-radius: 3px;
  background: #000b23;
  font-family: "Fira Sans", sans-serif;
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.mp-btn-save:hover:not(:disabled) {
  background: #00a8a8;
}
.mp-btn-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.mp-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: mp-spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes mp-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
