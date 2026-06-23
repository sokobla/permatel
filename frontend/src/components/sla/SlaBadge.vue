<template>
  <span v-if="meta" class="sla-badge" :style="{ background: meta.tint, color: meta.color }" :title="title">
    <span class="sla-dot" :style="{ background: meta.color }"></span>
    {{ meta.label }}<template v-if="timeText"> · {{ timeText }}</template>
  </span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  // Une "horloge" SLA telle que renvoyée par le backend :
  // { status, deadline?, remaining_seconds?, overdue_seconds? }
  state: { type: Object, default: null },
});

const META = {
  on_time:  { label: "Dans les délais", color: "#16a34a", tint: "rgba(22,163,74,0.10)" },
  at_risk:  { label: "À risque",        color: "#f39c12", tint: "rgba(243,156,18,0.12)" },
  breached: { label: "Hors délai",      color: "#e74c3c", tint: "rgba(231,76,60,0.12)" },
  met:      { label: "Respecté",        color: "#16a34a", tint: "rgba(22,163,74,0.10)" },
  missed:   { label: "Non respecté",    color: "#e74c3c", tint: "rgba(231,76,60,0.12)" },
  paused:   { label: "En pause",        color: "#6b7280", tint: "rgba(107,114,128,0.12)" },
};

const meta = computed(() => META[props.state?.status] || null); // n/a → rien

function humanize(sec) {
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h >= 24) return `${Math.floor(h / 24)} j ${h % 24} h`;
  if (h > 0) return `${h} h ${m.toString().padStart(2, "0")}`;
  return `${m} min`;
}

const timeText = computed(() => {
  const s = props.state;
  if (!s) return "";
  if (s.status === "breached" && s.overdue_seconds != null) return `retard ${humanize(s.overdue_seconds)}`;
  if ((s.status === "on_time" || s.status === "at_risk") && s.remaining_seconds != null)
    return `reste ${humanize(s.remaining_seconds)}`;
  return "";
});

const title = computed(() =>
  props.state?.deadline ? `Échéance : ${new Date(props.state.deadline).toLocaleString("fr-FR")}` : "",
);
</script>

<style scoped>
.sla-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border-radius: 999px;
  font-family: "Fira Sans", sans-serif;
  font-size: 11.5px;
  font-weight: 600;
  white-space: nowrap;
}
.sla-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
