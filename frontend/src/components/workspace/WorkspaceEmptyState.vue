<template>
  <div class="ws-empty-state" role="status" aria-live="polite">
    <v-icon size="52" color="#ddd">mdi-account-search-outline</v-icon>
    <p class="ws-empty__title">Aucune interaction active</p>
    <p class="ws-empty__sub">
      Veuillez identifier un contact dans la liste à gauche pour voir ses
      interactions et démarrer une prise en charge.
    </p>

    <v-menu location="bottom">
      <template #activator="{ props }">
        <v-btn
          v-bind="props"
          color="#00a8a8"
          variant="flat"
          class="text-none mt-4"
          prepend-icon="mdi-plus"
        >
          Nouvelle demande
        </v-btn>
      </template>
      <v-list density="compact">
        <v-list-item
          v-for="t in TYPES"
          :key="t.value"
          :prepend-icon="t.icon"
          :title="t.label"
          @click="$emit('new-demande', t.value)"
        />
      </v-list>
    </v-menu>
  </div>
</template>

<script setup>
defineEmits(["new-demande"]);

const TYPES = [
  { value: "anomalie", label: "Anomalie", icon: "mdi-alert-outline" },
  { value: "commande", label: "Commande", icon: "mdi-package-variant-closed" },
  { value: "planning", label: "Planning", icon: "mdi-calendar-edit" },
  { value: "admin", label: "Administratif", icon: "mdi-file-document-outline" },
];
</script>

<script>
export default { name: "WorkspaceEmptyState" };
</script>
