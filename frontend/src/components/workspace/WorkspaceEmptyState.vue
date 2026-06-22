<template>
  <div class="ws-empty-state" role="status" aria-live="polite">
    <v-icon size="52" color="#ddd">mdi-account-search-outline</v-icon>
    <p class="ws-empty__title">Aucune interaction active</p>
    <p class="ws-empty__sub">
      Veuillez identifier un contact dans la liste à gauche pour voir ses
      interactions et démarrer une prise en charge.
    </p>
  </div>
</template>

<script>
export default { name: 'WorkspaceEmptyState' }
</script>
