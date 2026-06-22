<template>
  <v-card elevation="0" class="ddt-card">
    <div class="ddt-header">
      <span class="ddt-title">TENDANCE — 30 DERNIERS JOURS</span>
      <div class="ddt-legend">
        <span v-for="s in SERIES_META" :key="s.key" class="ddt-legend-item">
          <span class="ddt-legend-dot" :style="{ background: s.color }"></span>
          {{ s.label }}
        </span>
      </div>
    </div>
    <v-divider />
    <v-card-text class="ddt-body">
      <div v-if="loading" class="ddt-skeleton">
        <div v-for="n in 5" :key="n" class="ddt-sk-bar" :style="{ height: `${30 + n * 15}%` }"></div>
      </div>
      <ApexChart
        v-else
        type="area"
        height="240"
        :options="chartOptions"
        :series="series"
      />
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from "vue";
import ApexChart from "vue3-apexcharts";

const props = defineProps({
  trendData: { type: Array, default: () => [] },
  loading:   { type: Boolean, default: false },
});

const SERIES_META = [
  { key: "anomalie", label: "Anomalie",      color: "#e74c3c" },
  { key: "commande", label: "Commande",      color: "#00a8a8" },
  { key: "planning", label: "Planning",      color: "#3498db" },
  { key: "admin",    label: "Administratif", color: "#8e44ad" },
];

const series = computed(() =>
  SERIES_META.map((s) => ({
    name: s.label,
    data: props.trendData.map((d) => d[s.key] ?? 0),
  }))
);

const categories = computed(() => props.trendData.map((d) => d.label ?? d.date));

const chartOptions = computed(() => ({
  chart: {
    type: "area",
    toolbar: { show: false },
    animations: { enabled: true, speed: 600 },
    background: "transparent",
  },
  colors: SERIES_META.map((s) => s.color),
  fill: {
    type: "gradient",
    gradient: {
      type: "vertical",
      shadeIntensity: 0.4,
      opacityFrom: 0.35,
      opacityTo: 0.03,
    },
  },
  stroke: {
    curve: "smooth",
    width: 2,
  },
  xaxis: {
    categories: categories.value,
    labels: {
      rotate: 0,
      style: { fontFamily: "Fira Code, monospace", fontSize: "9px", colors: "#aaa" },
      formatter: (val, idx) => (idx % 5 === 0 ? val : ""),
    },
    axisBorder: { show: false },
    axisTicks: { show: false },
  },
  yaxis: {
    labels: {
      style: { fontFamily: "Fira Code, monospace", fontSize: "9px", colors: "#aaa" },
      formatter: (v) => Math.round(v),
    },
    min: 0,
  },
  grid: {
    borderColor: "rgba(0,0,0,0.05)",
    strokeDashArray: 4,
    padding: { left: 0, right: 0 },
  },
  legend: { show: false },
  tooltip: {
    theme: "light",
    style: { fontFamily: "Fira Sans, sans-serif", fontSize: "11px" },
    x: { show: true },
  },
  dataLabels: { enabled: false },
}));
</script>

<script>
export default { name: "DashboardDemandeTrend" };
</script>

<style scoped>
.ddt-card {
  border: 1px solid rgba(197, 198, 206, 0.15) !important;
  height: 100%;
}

.ddt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
  flex-wrap: wrap;
  gap: 8px;
}

.ddt-title {
  font-family: "Fira Sans", sans-serif;
  font-size: 1rem;
  font-weight: 700;
  color: #000b23;
}

.ddt-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.ddt-legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: "Fira Sans", sans-serif;
  font-size: 0.7rem;
  font-weight: 600;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.ddt-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

.ddt-body {
  padding: 4px 8px 8px !important;
}

/* ── Skeleton ──────────────────────────────────────────────── */

.ddt-skeleton {
  height: 240px;
  display: flex;
  align-items: flex-end;
  gap: 4px;
  padding: 0 12px;
  animation: ddt-pulse 1.4s ease-in-out infinite;
}

@keyframes ddt-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.35; }
}

.ddt-sk-bar {
  flex: 1;
  background: #e8e8e8;
  border-radius: 2px 2px 0 0;
}
</style>
