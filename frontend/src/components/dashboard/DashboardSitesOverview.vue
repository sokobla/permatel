<template>
  <v-card
    variant="flat"
    rounded="lg"
    color="surface-container-lowest"
    class="mt-6"
  >
    <v-card-item>
      <v-card-title class="card-title">
        <v-icon start>mdi-domain</v-icon>
        Supervision des Sites
      </v-card-title>
    </v-card-item>
    <v-table density="compact" class="themed-table">
      <thead>
        <tr>
          <th>Site</th>
          <th class="text-center">Incidents</th>
          <th class="text-center">Couverture</th>
          <th class="text-center">Risque</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="site in sites" :key="site.name">
          <td class="font-fira-code text-caption">{{ site.name }}</td>
          <td class="text-center font-fira-code">{{ site.openIncidents }}</td>
          <td class="text-center">
            <v-chip
              :color="site.coverage === 'OK' ? 'teal' : 'tertiary-container'"
              size="x-small"
              label
              variant="flat"
            >
              {{ site.coverage }}
            </v-chip>
          </td>
          <td class="text-center">
            <v-chip
              :color="riskColor(site.risk)"
              size="x-small"
              label
              variant="tonal"
            >
              {{ site.risk }}
            </v-chip>
          </td>
        </tr>
      </tbody>
    </v-table>
  </v-card>
</template>

<script setup>
defineProps({
  sites: {
    type: Array,
    required: true,
  },
});

const riskColor = (risk) => {
  const colors = {
    Critique: "tertiary-container",
    Élevé: "orange-darken-2",
    Faible: "grey",
  };
  return colors[risk] || "grey";
};
</script>
