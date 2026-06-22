<template>
  <div class="ch-tabs-bar" role="tablist" aria-label="Canaux de communication">
    <template v-for="(tab, index) in tabs" :key="tab.key">
      <span v-if="index > 0" class="ch-sep" aria-hidden="true"></span>
      <button
        class="ch-tab"
        :class="{ 'ch-tab--active': selectedChannel === tab.key }"
        role="tab"
        :aria-selected="selectedChannel === tab.key"
        @click="emit('change', tab.key)"
      >
        <v-icon size="14">{{ tab.icon }}</v-icon>
        {{ tab.label }}

        <!-- Indicateur d'état du canal (lié à Slack / SMTP) -->
        <v-icon
          v-if="states[tab.key] === 'locked'"
          size="11"
          class="ch-state ch-state--locked"
          title="Indisponible — intégration requise"
        >mdi-lock-outline</v-icon>
        <span
          v-else-if="states[tab.key] === 'warn'"
          class="ch-state ch-state--warn"
          title="Configuration requise"
        ></span>
        <span
          v-else-if="tab.key === 'workspace' && selectedChannel === 'workspace'"
          class="ch-status-dot"
          aria-hidden="true"
        ></span>
      </button>
    </template>
  </div>
</template>

<script setup>
defineProps({
  selectedChannel: { type: String, default: 'workspace' },
  // Onglets visibles : [{ key, label, icon }] (dérivés des canaux du tenant)
  tabs: { type: Array, default: () => [] },
  // map clé canal -> 'locked' | 'warn' | 'ok' (optionnel)
  states: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['change'])
</script>

<script>
export default { name: 'ChannelTabs' }
</script>

<style scoped>
.ch-state { margin-left: 2px; }
.ch-state--locked { color: #9aa0aa; }
.ch-state--warn {
  width: 7px; height: 7px; border-radius: 50%;
  background: #f39c12; display: inline-block; margin-left: 4px;
}
</style>
