<template>
  <div class="tm-wrap">
    <div class="tm-header">
      <div>
        <h1 class="tm-title">Membres de l'espace</h1>
        <p class="tm-sub">Gérez les accès et les invitations de ce tenant.</p>
      </div>
      <v-btn color="#00a8a8" class="text-none" prepend-icon="mdi-account-plus" @click="openInvite">
        Inviter
      </v-btn>
    </div>

    <v-alert v-if="feedback.text" :type="feedback.type" variant="tonal" density="compact" class="mb-4" closable @click:close="feedback.text = ''">
      {{ feedback.text }}
    </v-alert>

    <!-- Membres -->
    <v-card variant="flat" border class="mb-6">
      <v-card-title class="tm-card-title">Membres actifs & inactifs</v-card-title>
      <v-data-table
        :headers="memberHeaders"
        :items="members"
        :loading="loadingMembers"
        density="comfortable"
        items-per-page="25"
      >
        <template #[`item.name`]="{ item }">
          {{ item.prenom }} {{ item.nom }}
        </template>
        <template #[`item.membership_role`]="{ item }">
          <v-chip size="small" :color="item.membership_role === 'admin' ? '#00a8a8' : undefined" variant="tonal">
            {{ item.membership_role === "admin" ? "Admin tenant" : "Membre" }}
          </v-chip>
        </template>
        <template #[`item.is_active`]="{ item }">
          <v-chip size="small" :color="item.is_active ? 'green' : 'grey'" variant="tonal">
            {{ item.is_active ? "Actif" : "Inactif" }}
          </v-chip>
        </template>
        <template #[`item.actions`]="{ item }">
          <v-menu>
            <template #activator="{ props }">
              <v-btn v-bind="props" icon="mdi-dots-vertical" variant="text" size="small" />
            </template>
            <v-list density="compact">
              <v-list-item @click="toggleRole(item)">
                <v-list-item-title>
                  {{ item.membership_role === "admin" ? "Rétrograder en membre" : "Promouvoir admin tenant" }}
                </v-list-item-title>
              </v-list-item>
              <v-list-item @click="toggleActive(item)">
                <v-list-item-title>{{ item.is_active ? "Désactiver l'accès" : "Réactiver l'accès" }}</v-list-item-title>
              </v-list-item>
              <v-list-item @click="removeMember(item)">
                <v-list-item-title class="text-error">Retirer du tenant</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-menu>
        </template>
      </v-data-table>
    </v-card>

    <!-- Invitations -->
    <v-card variant="flat" border>
      <v-card-title class="tm-card-title">Invitations</v-card-title>
      <v-data-table
        :headers="inviteHeaders"
        :items="invitations"
        :loading="loadingInvites"
        density="comfortable"
        items-per-page="10"
      >
        <template #[`item.status`]="{ item }">
          <v-chip size="small" :color="STATUS_COLOR[item.status]" variant="tonal">
            {{ STATUS_LABEL[item.status] || item.status }}
          </v-chip>
        </template>
        <template #[`item.expires_at`]="{ item }">
          {{ formatDate(item.expires_at) }}
        </template>
        <template #[`item.actions`]="{ item }">
          <template v-if="item.status === 'pending'">
            <v-btn variant="text" size="small" class="text-none" @click="resend(item)">Relancer</v-btn>
            <v-btn variant="text" size="small" color="error" class="text-none" @click="revoke(item)">Révoquer</v-btn>
          </template>
        </template>
      </v-data-table>
    </v-card>

    <!-- Dialog inviter -->
    <v-dialog v-model="inviteOpen" max-width="460">
      <v-card>
        <v-card-title class="tm-card-title">Inviter un utilisateur</v-card-title>
        <v-card-text>
          <v-alert v-if="inviteError" type="error" variant="tonal" density="compact" class="mb-3">
            {{ inviteError }}
          </v-alert>
          <v-text-field v-model="inviteForm.email" label="Email" type="email" variant="outlined" density="comfortable" />
          <v-select v-model="inviteForm.role" :items="roleItems" label="Rôle fonctionnel" variant="outlined" density="comfortable" />
          <v-select v-model="inviteForm.membership_role" :items="membershipItems" label="Capacité dans le tenant" variant="outlined" density="comfortable" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" class="text-none" @click="inviteOpen = false">Annuler</v-btn>
          <v-btn :loading="inviting" color="#00a8a8" class="text-none" @click="sendInvite">Envoyer l'invitation</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { tenantMemberService } from "@/services/tenantMemberService";

const STATUS_LABEL = { pending: "En attente", accepted: "Acceptée", revoked: "Révoquée", expired: "Expirée" };
const STATUS_COLOR = { pending: "orange", accepted: "green", revoked: "grey", expired: "red" };

const memberHeaders = [
  { title: "Nom", key: "name" },
  { title: "Email", key: "email" },
  { title: "Rôle", key: "role" },
  { title: "Capacité", key: "membership_role" },
  { title: "Statut", key: "is_active" },
  { title: "", key: "actions", sortable: false, align: "end" },
];
const inviteHeaders = [
  { title: "Email", key: "email" },
  { title: "Rôle", key: "role" },
  { title: "Statut", key: "status" },
  { title: "Expire le", key: "expires_at" },
  { title: "", key: "actions", sortable: false, align: "end" },
];
const roleItems = [
  { title: "Manager", value: "MANAGER" },
  { title: "Permanencier", value: "PERMANENCIER" },
];
const membershipItems = [
  { title: "Membre", value: "member" },
  { title: "Admin du tenant", value: "admin" },
];

const members = ref([]);
const invitations = ref([]);
const loadingMembers = ref(false);
const loadingInvites = ref(false);
const feedback = reactive({ text: "", type: "success" });

const inviteOpen = ref(false);
const inviting = ref(false);
const inviteError = ref("");
const inviteForm = reactive({ email: "", role: "PERMANENCIER", membership_role: "member" });

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}
function notify(text, type = "success") {
  feedback.text = text;
  feedback.type = type;
}

async function loadMembers() {
  loadingMembers.value = true;
  try {
    const { data } = await tenantMemberService.listMembers();
    members.value = data.members ?? [];
  } finally {
    loadingMembers.value = false;
  }
}
async function loadInvitations() {
  loadingInvites.value = true;
  try {
    const { data } = await tenantMemberService.listInvitations();
    invitations.value = data.invitations ?? [];
  } finally {
    loadingInvites.value = false;
  }
}

async function toggleRole(item) {
  const next = item.membership_role === "admin" ? "member" : "admin";
  try {
    await tenantMemberService.updateMember(item.user_id, { membership_role: next });
    notify("Capacité mise à jour.");
    loadMembers();
  } catch (e) {
    notify(e?.response?.data?.error || "Échec de la mise à jour.", "error");
  }
}
async function toggleActive(item) {
  try {
    await tenantMemberService.updateMember(item.user_id, { is_active: !item.is_active });
    notify("Accès mis à jour.");
    loadMembers();
  } catch (e) {
    notify(e?.response?.data?.error || "Échec de la mise à jour.", "error");
  }
}
async function removeMember(item) {
  try {
    await tenantMemberService.removeMember(item.user_id);
    notify("Membre retiré du tenant.");
    loadMembers();
  } catch (e) {
    notify(e?.response?.data?.error || "Échec du retrait.", "error");
  }
}

function openInvite() {
  inviteError.value = "";
  inviteForm.email = "";
  inviteForm.role = "PERMANENCIER";
  inviteForm.membership_role = "member";
  inviteOpen.value = true;
}
async function sendInvite() {
  inviteError.value = "";
  inviting.value = true;
  try {
    await tenantMemberService.createInvitation({ ...inviteForm });
    inviteOpen.value = false;
    notify("Invitation envoyée.");
    loadInvitations();
  } catch (e) {
    inviteError.value = e?.response?.data?.error || "Échec de l'envoi.";
  } finally {
    inviting.value = false;
  }
}
async function resend(item) {
  try {
    await tenantMemberService.resendInvitation(item.id);
    notify("Invitation relancée.");
    loadInvitations();
  } catch (e) {
    notify(e?.response?.data?.error || "Échec de la relance.", "error");
  }
}
async function revoke(item) {
  try {
    await tenantMemberService.revokeInvitation(item.id);
    notify("Invitation révoquée.");
    loadInvitations();
  } catch (e) {
    notify(e?.response?.data?.error || "Échec de la révocation.", "error");
  }
}

onMounted(() => {
  loadMembers();
  loadInvitations();
});
</script>

<style scoped>
.tm-wrap {
  padding: 24px;
  font-family: "Fira Sans", sans-serif;
}
.tm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}
.tm-title {
  font-size: 20px;
  font-weight: 800;
  color: #000b23;
  margin: 0;
}
.tm-sub {
  font-size: 13px;
  color: #6b7280;
  margin: 2px 0 0;
}
.tm-card-title {
  font-size: 14px;
  font-weight: 700;
  color: #000b23;
}
</style>
