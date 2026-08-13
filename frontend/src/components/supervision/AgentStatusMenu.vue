<template>
  <v-menu location="bottom end">
    <template #activator="{ props }">
      <v-btn
        v-bind="props"
        variant="text"
        color="#000b23"
        size="small"
        class="asm-btn"
      >
        <span class="asm-dot" :class="`asm-dot--${statusColor}`"></span>
        {{ statusLabel }}
        <v-icon size="16" class="ml-1">mdi-chevron-down</v-icon>
      </v-btn>
    </template>
    <v-list density="compact" min-width="220">
      <v-list-item @click="setStatus('Available')">
        <template #prepend
          ><span class="asm-dot asm-dot--online"></span
        ></template>
        <v-list-item-title>Disponible</v-list-item-title>
      </v-list-item>

      <v-list-item
        :active="pauseSubmenuOpen"
        @click.stop="pauseSubmenuOpen = !pauseSubmenuOpen"
      >
        <template #prepend
          ><span class="asm-dot asm-dot--away"></span
        ></template>
        <v-list-item-title>En pause</v-list-item-title>
        <template #append>
          <v-icon size="16">{{
            pauseSubmenuOpen ? "mdi-chevron-up" : "mdi-chevron-down"
          }}</v-icon>
        </template>
      </v-list-item>
      <template v-if="pauseSubmenuOpen">
        <v-list-item
          v-for="code in pauseCodes"
          :key="code.id"
          class="asm-pause-code"
          @click="setStatus('On Break', code.digit)"
        >
          <v-list-item-title
            >{{ code.label }} ({{ code.digit }})</v-list-item-title
          >
        </v-list-item>
        <v-list-item v-if="!pauseCodes.length" disabled>
          <v-list-item-title class="text-caption"
            >Aucun code configuré</v-list-item-title
          >
        </v-list-item>
      </template>

      <v-list-item @click="setStatus('Logged Out')">
        <template #prepend
          ><span class="asm-dot asm-dot--offline"></span
        ></template>
        <v-list-item-title>Déconnecté</v-list-item-title>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { telephonyService } from "@/services/telephonyService";

const pauseCodes = ref([]);
const pauseSubmenuOpen = ref(false);
const currentStatus = ref(null); // dernier statut demandé localement — pas de confirmation temps réel (cf. plan 13/08)

const statusLabel = computed(() => {
  if (currentStatus.value === "Available") return "Disponible";
  if (currentStatus.value === "On Break") return "En pause";
  if (currentStatus.value === "Logged Out") return "Déconnecté";
  return "Statut";
});

const statusColor = computed(() => {
  if (currentStatus.value === "Available") return "online";
  if (currentStatus.value === "On Break") return "away";
  if (currentStatus.value === "Logged Out") return "offline";
  return "unknown";
});

async function loadPauseCodes() {
  try {
    const { data } = await telephonyService.getPauseCodes();
    pauseCodes.value = data;
  } catch {
    pauseCodes.value = [];
  }
}

async function setStatus(status, pauseCode) {
  pauseSubmenuOpen.value = false;
  try {
    await telephonyService.setMyStatus(
      status === "On Break" ? { status, pause_code: pauseCode } : { status },
    );
    currentStatus.value = status;
  } catch {
    // Best-effort : job perdu silencieusement (Redis/connecteur indisponible,
    // cf. backend/app/routes/telephony.py::_dispatch_pbx_job) — pas de retry
    // dédié, l'utilisateur peut relancer l'action.
  }
}

onMounted(loadPauseCodes);
</script>

<style scoped>
.asm-btn {
  text-transform: none;
  font-weight: 500;
}
.asm-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}
.asm-dot--online {
  background: #16a34a;
}
.asm-dot--away {
  background: #f59e0b;
}
.asm-dot--offline {
  background: #9aa0aa;
}
.asm-dot--unknown {
  background: #cbd0d6;
}
.asm-pause-code {
  padding-left: 32px !important;
}
</style>
