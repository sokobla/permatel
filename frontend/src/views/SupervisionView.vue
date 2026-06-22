<template>
  <div class="sv-page">

    <!-- En-tête : titre + tenant actif (toujours spécifié) -->
    <header class="sv-head">
      <div>
        <h1 class="sv-title">SUPERVISION</h1>
        <p class="sv-sub">Surveillance opérationnelle en temps réel</p>
      </div>
      <div class="sv-tenant">
        <span class="sv-tenant__label">TENANT ACTIF</span>
        <span class="sv-tenant__value">
          <span class="sv-tenant__dot"></span>
          {{ activeTenantName }}
        </span>
      </div>
    </header>

    <!-- Avertissement si aucun tenant actif -->
    <div v-if="!activeTenantId" class="sv-warn">
      Aucun tenant actif sélectionné — la supervision nécessite un tenant.
    </div>

    <!-- Monitoring des sessions -->
    <SessionMonitoring v-else />

  </div>
</template>

<script setup>
// === IMPORTS ===
import { computed } from "vue";
import SessionMonitoring from "@/components/supervision/SessionMonitoring.vue";
import { useAuthStore } from "@/store/auth";

// === STATE ===
const authStore = useAuthStore();

// === COMPUTED ===
const activeTenantId = computed(() => authStore.activeTenantId);
const activeTenantName = computed(() => {
  const t = authStore.tenants?.find((x) => x.id === authStore.activeTenantId);
  return t?.nom || t?.code || "—";
});
</script>

<style scoped>
.sv-page {
  font-family: "Fira Sans", sans-serif;
  background: #f2f2f2;
  min-height: 100%;
  padding: 24px;
  box-sizing: border-box;
}

.sv-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.sv-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #000b23;
  margin: 0;
}
.sv-sub {
  font-size: 12px;
  color: #6b7280;
  margin: 2px 0 0;
}

.sv-tenant {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
}
.sv-tenant__label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #6b7280;
}
.sv-tenant__value {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 700;
  color: #000b23;
}
.sv-tenant__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
}

.sv-warn {
  padding: 14px 16px;
  border-radius: 8px;
  background: rgba(243, 156, 18, 0.1);
  border: 1px solid rgba(243, 156, 18, 0.3);
  color: #b7770d;
  font-size: 13px;
}
</style>
