<template>
  <v-card variant="outlined" rounded="lg" class="fill-height">
    <v-card-item>
      <v-card-title class="card-title">Activité Temps Réel</v-card-title>
    </v-card-item>
    <v-row no-gutters class="px-4 pb-4">
      <v-col cols="12" md="7">
        <apexchart
          type="area"
          height="280"
          :options="chartOptions"
          :series="series"
        ></apexchart>
      </v-col>
      <v-col cols="12" md="5" class="pl-md-4">
        <DashboardAgentsStatus :agents="agents" />
      </v-col>
    </v-row>
  </v-card>
</template>

<script setup>
import { computed } from "vue";
import Apexchart from "vue3-apexcharts";
import DashboardAgentsStatus from "./DashboardAgentsStatus.vue";

defineProps({
  series: {
    type: Array,
    required: true,
  },
  agents: {
    type: Array,
    required: true,
  },
});

const chartOptions = computed(() => ({
  chart: {
    toolbar: { show: false },
    sparkline: { enabled: false },
    animations: {
      enabled: true,
      easing: "linear",
      dynamicAnimation: { speed: 1000 },
    },
    background: "transparent",
  },
  colors: ["#00A8A8"],
  stroke: { curve: "smooth", width: 2 },
  fill: {
    type: "gradient",
    gradient: {
      shade: "dark",
      type: "vertical",
      opacityFrom: 0.6,
      opacityTo: 0.1,
      stops: [0, 100],
    },
  },
  dataLabels: { enabled: false },
  xaxis: { labels: { show: false }, axisBorder: { show: false }, axisTicks: { show: false } },
  yaxis: { labels: { show: false } },
  grid: { show: false },
  tooltip: { enabled: false },
  theme: { mode: "light" },
}));
</script>