<template>
  <div class="akpi">
    <div v-if="loading" class="akpi-loading">
      <v-progress-circular indeterminate size="20" color="#00a8a8" />
      <span>Chargement des KPI…</span>
    </div>

    <template v-else-if="kpis">
      <div class="akpi-grid">
        <!-- Score -->
        <div class="akpi-card akpi-card--score">
          <div class="akpi-card__top">
            <span class="akpi-card__label">Score agent</span>
            <v-tooltip text="100 − 5 points par incident discriminant sur la période. Borné 0–100.">
              <template #activator="{ props }"><v-icon v-bind="props" size="13" color="#9aa0aa">mdi-information-outline</v-icon></template>
            </v-tooltip>
          </div>
          <div class="akpi-card__value" :style="{ color: scoreColor }">{{ kpis.score }}<small>/100</small></div>
        </div>

        <!-- Incidents agent (discriminants) -->
        <div class="akpi-card akpi-card--incident">
          <div class="akpi-card__top">
            <span class="akpi-card__label">Incidents agent</span>
            <v-tooltip text="Anomalies discriminantes (natures pénalisantes ou impact sécurité). Impactent le score.">
              <template #activator="{ props }"><v-icon v-bind="props" size="13" color="#9aa0aa">mdi-information-outline</v-icon></template>
            </v-tooltip>
          </div>
          <div class="akpi-card__value akpi-card__value--red">{{ kpis.incidents }}</div>
        </div>

        <!-- Anomalies (toutes) -->
        <div class="akpi-card">
          <div class="akpi-card__top">
            <span class="akpi-card__label">Anomalies</span>
            <v-tooltip text="Toutes les anomalies impliquant l'agent (incidents inclus). N'impactent pas directement le score.">
              <template #activator="{ props }"><v-icon v-bind="props" size="13" color="#9aa0aa">mdi-information-outline</v-icon></template>
            </v-tooltip>
          </div>
          <div class="akpi-card__value">{{ kpis.anomalies }}</div>
        </div>
      </div>

      <p class="akpi-relation">
        {{ kpis.incidents }} incident(s) discriminant(s) sur {{ kpis.anomalies }} anomalie(s).
      </p>
    </template>

    <div v-else class="akpi-empty">Aucune donnée KPI.</div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  kpis: { type: Object, default: null },
  loading: { type: Boolean, default: false },
});

const scoreColor = computed(() => {
  const s = props.kpis?.score ?? 100;
  if (s >= 80) return "#22c55e";
  if (s >= 50) return "#f39c12";
  return "#e74c3c";
});
</script>

<style scoped>
.akpi { font-family: "Fira Sans", sans-serif; }
.akpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.akpi-card {
  border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 14px; background: #fafafa;
}
.akpi-card--score { background: #f7fdfd; }
.akpi-card--incident { background: #fdf6f6; }
.akpi-card__top { display: flex; align-items: center; gap: 4px; }
.akpi-card__label { font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; }
.akpi-card__value { font-size: 24px; font-weight: 800; color: #000b23; line-height: 1.2; }
.akpi-card__value small { font-size: 12px; font-weight: 600; color: #9aa0aa; }
.akpi-card__value--red { color: #e74c3c; }
.akpi-relation { font-size: 11.5px; color: #6b7280; margin: 8px 0 0; }
.akpi-loading, .akpi-empty { display: flex; align-items: center; gap: 8px; color: #9aa0aa; font-size: 12.5px; padding: 8px 0; }
</style>
