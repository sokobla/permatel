<template>
  <v-card elevation="0" :class="['ddkc-card', isAlert ? 'ddkc-card--alert' : '']">
    <v-card-text class="ddkc-body">
      <div class="ddkc-top">
        <span class="ddkc-icon-bubble" :class="isAlert ? 'ddkc-icon-bubble--alert' : ''">
          <v-icon :color="isAlert ? '#e74c3c' : '#00a8a8'" size="15">{{ kpi.icon }}</v-icon>
        </span>
        <span class="ddkc-label">{{ kpi.label }}</span>
      </div>

      <div class="ddkc-main">
        <div class="ddkc-value-block">
          <div :class="['ddkc-value', isAlert ? 'ddkc-value--alert' : '']">{{ kpi.value }}</div>
          <div v-if="kpi.subtitle" :class="['ddkc-subtitle', isAlert ? 'ddkc-subtitle--alert' : '']">
            {{ kpi.subtitle }}
          </div>
        </div>

        <div v-if="kpi.trend?.length" class="ddkc-week">
          <div v-for="d in kpi.trend" :key="d.date" class="ddkc-week__col">
            <div class="ddkc-week__track">
              <div
                class="ddkc-week__fill"
                :class="d.isToday ? 'ddkc-week__fill--today' : (isAlert ? 'ddkc-week__fill--alert' : '')"
                :style="{ height: barHeight(d.count) + '%' }"
              ></div>
            </div>
            <span :class="['ddkc-week__day', d.isToday ? 'ddkc-week__day--today' : '']">{{ d.dayLabel }}</span>
          </div>
        </div>
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

// Hauteur relative des barres du mini-graphique 7 jours (min 8% pour rester
// visible/cliquable même à 0, max normalisé sur le jour le plus chargé).
const maxTrendCount = computed(() =>
  Math.max(1, ...(props.kpi.trend || []).map((d) => d.count)),
);
function barHeight(count) {
  if (!count) return 8;
  return Math.round((count / maxTrendCount.value) * 100);
}
</script>

<script>
export default { name: "DashboardDemandesKpiCard" };
</script>

<style scoped>
.ddkc-card {
  border: 1px solid rgba(197, 198, 206, 0.15) !important;
  height: 100%;
}

.ddkc-card--alert {
  border-color: rgba(231, 76, 60, 0.35) !important;
}

.ddkc-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px 14px !important;
}

.ddkc-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ddkc-icon-bubble {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: rgba(0, 168, 168, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ddkc-icon-bubble--alert {
  background: rgba(231, 76, 60, 0.12);
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

.ddkc-main {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10px;
}

.ddkc-value-block { min-width: 0; }

.ddkc-value {
  font-family: "Fira Code", monospace;
  font-size: 2.1rem;
  line-height: 1;
  font-weight: 500;
  color: #000b23;
}

.ddkc-value--alert {
  color: #e74c3c;
}

.ddkc-subtitle {
  font-family: "Fira Sans", sans-serif;
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}
.ddkc-subtitle--alert {
  color: #e74c3c;
}

/* Mini-graphique 7 jours */
.ddkc-week {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  flex-shrink: 0;
}
.ddkc-week__col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  width: 10px;
}
.ddkc-week__track {
  width: 5px;
  height: 26px;
  border-radius: 3px;
  background: rgba(0, 11, 35, 0.06);
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}
.ddkc-week__fill {
  width: 100%;
  border-radius: 3px 3px 0 0;
  background: #00a8a8;
  opacity: 0.55;
}
.ddkc-week__fill--today {
  background: #000b23;
  opacity: 1;
}
.ddkc-week__fill--alert {
  background: #e74c3c;
  opacity: 0.55;
}
.ddkc-week__day {
  font-size: 7.5px;
  font-weight: 600;
  color: #9aa0aa;
}
.ddkc-week__day--today {
  color: #000b23;
}
</style>
