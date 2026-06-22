<template>
  <v-row>
    <v-col v-for="kpi in kpis" :key="kpi.title" cols="12" sm="6" md="4" lg="2">
      <v-card class="kpi-card" variant="outlined" rounded="lg">
        <v-card-text>
          <div class="d-flex align-center">
            <v-icon
              :icon="kpi.icon"
              size="small"
              class="mr-2"
              color="on-surface"
            />
            <div class="kpi-title">{{ kpi.title }}</div>
          </div>
          <div class="kpi-value font-fira-code">{{ kpi.value }}</div>
          <div v-if="kpi.subtitle" class="kpi-subtitle">
            {{ kpi.subtitle }}
          </div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  data: {
    type: Object,
    required: true,
  },
});

const kpis = computed(() => [
  {
    title: "Appels Total",
    value: props.data.totalCalls,
    icon: "mdi-phone-in-talk-outline",
  },
  {
    title: "Appels en Attente",
    value: props.data.pendingCalls,
    icon: "mdi-phone-hangup-outline",
  },
  {
    title: "SLA",
    value: `${props.data.sla.toFixed(1)}%`,
    icon: "mdi-chart-timeline-variant",
  },
  {
    title: "Tps. Traitement Moyen",
    value: `${props.data.avgHandlingTime}s`,
    icon: "mdi-timer-sand",
  },
  {
    title: "Agents Actifs",
    value: props.data.activeAgents,
    icon: "mdi-account-group-outline",
  },
  {
    title: "Incidents Critiques",
    value: props.data.criticalIncidents,
    icon: "mdi-alert-octagon-outline",
  },
]);
</script>

<style scoped>
.kpi-card {
  border-color: rgba(var(--v-border-color), 0.15);
  background-color: var(--surface-container-lowest);
}
.kpi-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.75rem;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--on-surface);
  opacity: 0.7;
}
.kpi-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: var(--primary);
  line-height: 1.2;
  margin-top: 4px;
}
.kpi-subtitle {
  font-size: 0.75rem;
  color: var(--on-surface);
  opacity: 0.6;
}
</style>