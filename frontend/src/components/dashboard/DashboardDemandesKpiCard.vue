<template>
  <v-card elevation="0" :class="['ddkc-card', isAlert ? 'ddkc-card--alert' : '']">
    <v-card-text class="ddkc-body">
      <div class="ddkc-top">
        <v-icon :color="isAlert ? '#e74c3c' : '#00a8a8'" size="16">{{ kpi.icon }}</v-icon>
        <span class="ddkc-label">{{ kpi.label }}</span>
      </div>
      <div :class="['ddkc-value', isAlert ? 'ddkc-value--alert' : '']">
        {{ kpi.value }}
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  kpi: { type: Object, required: true },
});

const isAlert = computed(() => {
  if (!props.kpi.threshold) return false;
  const { value, threshold } = props.kpi;
  if (threshold.direction === "up"   && value > threshold.value) return true;
  if (threshold.direction === "down" && value < threshold.value) return true;
  return false;
});
</script>

<script>
export default { name: "DashboardDemandesKpiCard" };
</script>

<style scoped>
.ddkc-card {
  border: 1px solid rgba(197, 198, 206, 0.15) !important;
  border-left: 3px solid #00a8a8 !important;
  height: 100%;
}

.ddkc-card--alert {
  border-left-color: #e74c3c !important;
}

.ddkc-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 14px 12px !important;
}

.ddkc-top {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ddkc-label {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.7rem;
  font-weight: 700;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  line-height: 1.2;
}

.ddkc-value {
  font-family: "Fira Code", monospace;
  font-size: 2.25rem;
  line-height: 1;
  font-weight: 500;
  color: #000b23;
}

.ddkc-value--alert {
  color: #e74c3c;
}
</style>
