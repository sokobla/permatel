<template>
  <v-sheet
    class="d-flex align-center pa-2 mb-6"
    color="surface-container-high"
    rounded="lg"
    border
  >
    <v-icon start>mdi-tune-variant</v-icon>
    <span class="text-overline mr-4">Filtres</span>
    <v-divider vertical class="mx-2"></v-divider>
    <v-chip size="small" class="mr-2"
      >Période: <strong>Dernière 24h</strong></v-chip
    >
    <v-chip size="small" class="mr-2">Zone: <strong>Toutes</strong></v-chip>
    <v-chip size="small">Équipe: <strong>Toutes</strong></v-chip>
    <v-spacer></v-spacer>
    <div class="d-flex align-center">
      <span class="text-overline mr-2">État Opérationnel:</span>
      <v-chip color="green" variant="flat" size="small" label>
        <v-icon start>mdi-check-circle</v-icon>
        NORMAL
      </v-chip>
    </div>
  </v-sheet>
</template>

<script setup>
// Logique des filtres à implémenter
</script>