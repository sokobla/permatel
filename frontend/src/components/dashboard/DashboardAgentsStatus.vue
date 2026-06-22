<template>
  <v-sheet color="surface-container-high" rounded="lg" class="pa-3 fill-height">
    <div class="text-overline mb-2">Statut des Opérateurs</div>
    <v-table density="compact" class="themed-table">
      <thead>
        <tr>
          <th class="text-left">Agent</th>
          <th class="text-left">Statut</th>
          <th class="text-right">Durée</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="agent in agents" :key="agent.id">
          <td class="font-fira-code text-caption">{{ agent.id }}</td>
          <td>
            <v-chip :color="statusColor(agent.status)" size="x-small" label>{{
              agent.status
            }}</v-chip>
          </td>
          <td class="text-right font-fira-code text-caption">
            {{ formatDuration(agent.duration) }}
          </td>
        </tr>
      </tbody>
    </v-table>
  </v-sheet>
</template>

<script setup>
defineProps({
  agents: {
    type: Array,
    required: true,
  },
});

const statusColor = (status) => {
  const colors = {
    DISPONIBLE: "teal",
    "EN TRAITEMENT": "blue",
    "EN APPEL": "blue-darken-2",
    PAUSE: "grey",
    "HORS LIGNE": "default",
    "EN INTERVENTION": "orange-darken-2",
  };
  return colors[status] || "default";
};

const formatDuration = (seconds) => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
};
</script>

<style scoped>
/* Styles are inherited from DashboardView via .themed-table */
</style>