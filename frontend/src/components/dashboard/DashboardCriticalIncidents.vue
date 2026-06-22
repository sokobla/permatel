<template>
  <v-card variant="outlined" rounded="lg">
    <v-card-item>
      <v-card-title class="card-title"
        >Journal des Incidents Critiques</v-card-title
      >
    </v-card-item>
    <v-table density="compact" class="themed-table">
      <thead>
        <tr>
          <th class="text-left">ID Incident</th>
          <th class="text-left">Heure</th>
          <th class="text-left">Site</th>
          <th class="text-left">Type</th>
          <th class="text-left">Priorité</th>
          <th class="text-left">Action</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="incident in incidents" :key="incident.id">
          <td class="font-fira-code">{{ incident.id }}</td>
          <td class="font-fira-code">{{ incident.time }}</td>
          <td class="font-fira-code">{{ incident.site }}</td>
          <td>{{ incident.type }}</td>
          <td>
            <v-chip
              :color="priorityColor(incident.priority)"
              size="x-small"
              label
              variant="flat"
              >{{ incident.priority }}</v-chip
            >
          </td>
          <td>{{ incident.action }}</td>
        </tr>
      </tbody>
    </v-table>
  </v-card>
</template>

<script setup>
defineProps({
  incidents: {
    type: Array,
    required: true,
  },
});

const priorityColor = (priority) => {
  const colors = {
    CRITIQUE: "#E74C3C",
    HAUTE: "orange-darken-2",
    MOYENNE: "amber",
  };
  return colors[priority] || "grey";
};
</script>