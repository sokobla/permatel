<template>
  <div class="contact-table-wrapper">
    <!-- Barre de chargement -->
    <div v-if="isLoading" class="history-loader">
      <div class="history-loader__bar"></div>
    </div>

    <table
      class="contact-results-table"
      role="grid"
      aria-label="Résultats de recherche contact"
    >
      <thead>
        <tr>
          <th scope="col">NOM</th>
          <th scope="col">TÉLÉPHONE</th>
          <th scope="col">STAT</th>
        </tr>
      </thead>
      <tbody>
        <template v-if="contacts.length > 0">
          <tr
            v-for="contact in contacts"
            :key="contact.id"
            :class="{ 'row--selected': selectedContactId === contact.id }"
            :aria-selected="selectedContactId === contact.id"
            tabindex="0"
            @click="emit('select', contact)"
            @keyup.enter="emit('select', contact)"
            @keyup.space.prevent="emit('select', contact)"
          >
            <td class="mono-text">{{ contact.name }}</td>
            <td class="mono-text">{{ contact.phone }}</td>
            <td>
              <span
                class="contact-stat-dot"
                :class="`contact-stat-dot--${contact.status}`"
                :title="contact.status === 'active' ? 'Actif' : 'Inactif'"
                :aria-label="contact.status === 'active' ? 'Actif' : 'Inactif'"
              ></span>
            </td>
          </tr>
        </template>

        <tr v-else-if="!isLoading" class="contact-table-empty">
          <td colspan="3">AUCUN RÉSULTAT TROUVÉ</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({
  contacts:          { type: Array,          default: () => [] },
  selectedContactId: { type: [Number, null], default: null    },
  isLoading:         { type: Boolean,        default: false   },
})

const emit = defineEmits(['select'])
</script>

<script>
export default { name: 'ContactResultsTable' }
</script>
