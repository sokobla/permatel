<template>
  <v-card
    elevation="0"
    class="kpi-card"
  >
    <v-card-text>
      <div class="kpi-label">{{ kpi.label }}</div>
      <div class="d-flex align-end mt-2">
        <div class="kpi-value" :class="valueColor">{{ kpi.value.toFixed(kpi.unit === '%' ? 1 : 0) }}<span v-if="kpi.unit" class="kpi-unit">{{ kpi.unit }}</span></div>
        <div v-if="kpi.change" class="kpi-change ml-2" :class="kpi.change > 0 ? 'text-success' : 'text-error'">
          <v-icon size="small">{{ kpi.change > 0 ? 'mdi-arrow-up' : 'mdi-arrow-down' }}</v-icon>
          {{ Math.abs(kpi.change).toFixed(1) }}%
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { Kpi } from "@/composables/useMockDashboardData";

const props = defineProps<{
  kpi: Kpi;
}>();

const valueColor = computed(() => {
  if (!props.kpi.threshold) return 'text-navy-darken-1';

  const { value, threshold } = props.kpi;
  if (threshold.direction === 'down' && value < threshold.value) {
    return 'text-red-accent-3';
  }
  if (threshold.direction === 'up' && value > threshold.value) {
    return 'text-red-accent-3';
  }
  return 'text-navy-darken-1';
});
</script>

<style scoped>
.kpi-card {
  border: 1px solid rgba(197, 198, 206, 0.15) !important;
}
.kpi-label {
  font-family: 'Fira Sans', sans-serif;
  font-size: 0.8rem;
  font-weight: 500;
  color: #555;
  text-transform: uppercase;
}
.kpi-value {
  font-family: 'Fira Code', monospace;
  font-size: 2.25rem;
  line-height: 1;
  font-weight: 500;
}
.kpi-unit {
  font-family: 'Fira Sans', sans-serif;
  font-size: 1.25rem;
  margin-left: 4px;
  color: #777;
}
.kpi-change {
  font-family: 'Fira Code', monospace;
  font-weight: 500;
}
</style>