<template>
  <div class="ws-card history-card">
    <!-- En-tête -->
    <div class="card-hdr">
      <h2 class="card-title">Historique Communication</h2>
      <div
        v-if="channelMeta.channel || channelMeta.sessionId"
        class="card-hdr-tags"
      >
        <span v-if="channelMeta.channel" class="mono-tag">
          {{ channelMeta.channel }}
        </span>
        <span v-if="channelMeta.sessionId" class="mono-tag">
          {{ channelMeta.sessionId }}
        </span>
      </div>
    </div>
    <hr class="card-divider" />

    <!-- Barre de chargement -->
    <div v-if="isLoading" class="history-loader">
      <div class="history-loader__bar"></div>
    </div>

    <!-- Timeline scrollable -->
    <div ref="historyBodyRef" class="history-body">
      <template v-if="history.length > 0">
        <!-- Marqueur de début de session -->
        <div class="timeline-marker">
          APPEL DÉMARRÉ À {{ startTime }}
        </div>

        <HistoryMessageBubble
          v-for="msg in history"
          :key="msg.id"
          :message="msg"
        />
      </template>

      <!-- État vide -->
      <div v-else-if="!isLoading" class="history-empty">
        <v-icon size="24" color="#ddd">mdi-message-off-outline</v-icon>
        <p class="history-empty__text">Aucun historique disponible</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import HistoryMessageBubble from './HistoryMessageBubble.vue'

const props = defineProps({
  history:     { type: Array,  default: () => []                        },
  channelMeta: { type: Object, default: () => ({ channel: '', sessionId: '' }) },
  isLoading:   { type: Boolean, default: false                          },
})

const historyBodyRef = ref(null)

const startTime = computed(() =>
  props.history.length > 0 ? props.history[0].time : '—'
)

// Auto-scroll vers le bas à chaque nouveau message
watch(
  () => props.history.length,
  async () => {
    await nextTick()
    if (historyBodyRef.value) {
      historyBodyRef.value.scrollTop = historyBodyRef.value.scrollHeight
    }
  }
)
</script>

<script>
export default { name: 'CommunicationHistoryPanel' }
</script>
