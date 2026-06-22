<template>
  <v-card variant="flat" rounded="lg" color="surface-container-lowest">
    <v-card-item>
      <v-card-title class="card-title">
        <v-icon start color="tertiary-container"
          >mdi-alert-circle-outline</v-icon
        >
        Tâches Prioritaires
      </v-card-title>
    </v-card-item>
    <v-list lines="two" density="compact" class="bg-transparent">
      <v-list-item v-for="task in tasks" :key="task.id" :title="task.text">
        <template v-slot:subtitle>
          <v-chip
            :color="
              task.type === 'Escalade'
                ? 'tertiary-container'
                : 'orange-darken-2'
            "
            size="x-small"
            class="mt-1"
            label
            variant="tonal"
          >
            {{ task.type }}
          </v-chip>
        </template>
      </v-list-item>
    </v-list>
  </v-card>
</template>

<script setup>
defineProps({
  tasks: {
    type: Array,
    required: true,
  },
});
</script>