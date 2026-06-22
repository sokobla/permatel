<template>
  <v-card variant="outlined" rounded="lg">
    <v-card-item>
      <v-card-title class="card-title">Performance par Équipe</v-card-title>
    </v-card-item>
    <v-table density="compact" class="themed-table">
      <thead>
        <tr>
          <th class="text-left">Équipe / Superviseur</th>
          <th class="text-center">Volume Traité</th>
          <th class="text-center">SLA</th>
          <th class="text-center">Tps. Moyen</th>
          <th class="text-center">Incidents en Retard</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="team in teams" :key="team.name">
          <td>
            <strong>{{ team.name }}</strong>
            <span class="text-grey-darken-1 ml-2">/ {{ team.supervisor }}</span>
          </td>
          <td class="text-center font-fira-code">{{ team.volume }}</td>
          <td
            :class="team.sla < 96 ? 'text-orange-darken-2' : 'text-teal'"
            class="text-center font-fira-code font-weight-bold"
          >
            {{ team.sla.toFixed(1) }}%
          </td>
          <td class="text-center font-fira-code">{{ team.avgTime }}s</td>
          <td
            :class="team.late > 0 ? 'text-red-darken-2' : ''"
            class="text-center font-fira-code font-weight-bold"
          >
            {{ team.late }}
          </td>
        </tr>
      </tbody>
    </v-table>
  </v-card>
</template>

<script setup>
defineProps({
  teams: {
    type: Array,
    required: true,
  },
});
</script>
