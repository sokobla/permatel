<template>
  <div class="msg-bubble" :class="`msg-bubble--${message.role}`">
    <div class="msg-bubble__inner">
      <div class="msg-bubble__header">
        <v-icon
          size="13"
          :color="message.role === 'agent' ? '#00a8a8' : '#aaa'"
        >
          {{ message.role === 'agent' ? 'mdi-headset' : 'mdi-account-outline' }}
        </v-icon>
        <span class="msg-bubble__role-label">
          {{ message.role === 'agent' ? 'AGENT' : 'CLIENT' }}
        </span>
      </div>
      <p class="msg-bubble__text">{{ message.text }}</p>
      <div class="msg-bubble__meta">
        <span class="msg-bubble__time">{{ message.time }}</span>
        <span class="msg-bubble__type-tag">[{{ message.type }}]</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: Object,
    required: true,
    // Shape : { id, role: 'client'|'agent', text, time, type: 'TRANSCRIPTION'|'AUDIO'|'CHAT' }
  },
})
</script>

<script>
export default { name: 'HistoryMessageBubble' }
</script>
