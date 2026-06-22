<template>
  <v-card variant="flat" class="int-card" rounded="lg" border>
    <div class="int-head">
      <div>
        <h2 class="int-title">Intégrations</h2>
        <p class="int-sub">Connectez PERMATEL à vos outils. D'autres intégrations arrivent.</p>
      </div>
    </div>

    <v-divider />

    <div class="int-grid">
      <div v-for="i in INTEGRATIONS" :key="i.key" class="int-item">
        <div class="int-item__icon" :style="{ background: i.tint }">
          <v-icon size="22" :color="i.color">{{ i.icon }}</v-icon>
        </div>
        <div class="int-item__body">
          <div class="int-item__name-row">
            <span class="int-item__name">{{ i.name }}</span>
            <v-chip size="x-small" :color="isActive(i.key) ? '#22c55e' : '#9aa0aa'" variant="tonal">
              {{ isActive(i.key) ? "Disponible" : "Canal désactivé" }}
            </v-chip>
          </div>
          <p class="int-item__desc">{{ i.desc }}</p>
        </div>
        <v-btn variant="outlined" size="small" class="text-none int-item__btn" :disabled="!isActive(i.key)">
          Configurer
        </v-btn>
      </div>
    </div>
  </v-card>
</template>

<script setup>
import { computed } from "vue";
import { integrationList } from "@/config/integrations";
import { useAuthStore } from "@/store/auth";

const INTEGRATIONS = integrationList();
const authStore = useAuthStore();
const availability = computed(() => authStore.featureMap.integrations || {});
const isActive = (key) => availability.value[key] === true;
</script>

<style scoped>
.int-card { font-family: "Fira Sans", sans-serif; }
.int-head { padding: 16px 20px; }
.int-title { font-size: 15px; font-weight: 700; color: #000b23; margin: 0; }
.int-sub { font-size: 12.5px; color: #6b7280; margin: 2px 0 0; }

.int-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
  padding: 18px 20px;
}
.int-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fafafa;
  opacity: 0.92;
}
.int-item__icon {
  width: 44px; height: 44px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.int-item__body { flex: 1; min-width: 0; }
.int-item__name-row { display: flex; align-items: center; gap: 8px; }
.int-item__name { font-size: 14px; font-weight: 700; color: #000b23; }
.int-item__desc { font-size: 12px; color: #6b7280; margin: 4px 0 0; line-height: 1.45; }
.int-item__btn { flex-shrink: 0; }
</style>
