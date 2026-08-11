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
        <v-btn
          variant="outlined"
          size="small"
          class="text-none int-item__btn"
          :disabled="!isActive(i.key)"
          @click="configure(i.key)"
        >
          Configurer
        </v-btn>
      </div>
    </div>

    <!-- Panneau de configuration Téléphonie (connecteurs PBX, domaines, événements ESL). -->
    <v-dialog v-model="telephonyDialog" max-width="960" scrollable>
      <v-card rounded="lg">
        <div class="tel-dlg-head">
          <span class="tel-dlg-head__title">Configuration — Téléphonie</span>
          <v-btn icon="mdi-close" variant="text" size="small" @click="telephonyDialog = false" />
        </div>
        <v-divider />
        <v-card-text class="tel-dlg-body">
          <SettingsTelephony />
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { computed, ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { integrationList } from "@/config/integrations";
import { useAuthStore } from "@/store/auth";
import SettingsTelephony from "@/components/settings/SettingsTelephony.vue";

const INTEGRATIONS = integrationList();
const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();
const availability = computed(() => authStore.featureMap.integrations || {});
const isActive = (key) => availability.value[key] === true;

// Seule la Téléphonie a un panneau de configuration dédié pour l'instant
// (Slack n'est pas encore implémenté côté backend). Le panneau s'ouvre en
// dialog inline, plus en tant qu'onglet Paramètres autonome (relocalisé
// depuis SettingsView.vue).
const telephonyDialog = ref(false);
function configure(key) {
  if (key === "telephony") telephonyDialog.value = true;
}

// Lien profond conservé pour les anciens signets (/pbx-connectors) : ouvre
// directement le panneau si le canal est actif.
onMounted(() => {
  if (route.query.configure === "telephony" && isActive("telephony")) {
    telephonyDialog.value = true;
    router.replace({ query: { ...route.query, configure: undefined } });
  }
});
</script>

<style scoped>
.int-card { font-family: "Fira Sans", sans-serif; }
.int-head { padding: 16px 20px; }
.int-title { font-size: 17px; font-weight: 700; color: #000b23; margin: 0; }
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
.int-item__name { font-size: 16px; font-weight: 700; color: #000b23; }
.int-item__desc { font-size: 14px; color: #6b7280; margin: 4px 0 0; line-height: 1.45; }
.int-item__btn { flex-shrink: 0; }

.tel-dlg-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px;
}
.tel-dlg-head__title { font-size: 17px; font-weight: 700; color: #000b23; }
.tel-dlg-body { padding: 0 !important; background: #f2f2f2; }
</style>
