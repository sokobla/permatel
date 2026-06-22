<template>
  <div class="ws-card">
    <!-- En-tête -->
    <div class="card-hdr">
      <h2 class="card-title">Recherche Contact</h2>
    </div>
    <hr class="card-divider" />

    <!-- Corps -->
    <div class="card-body">
      <!-- Champ Nom / Prénom -->
      <div class="form-group">
        <label class="form-label" for="ws-search-name">NOM / PRÉNOM</label>
        <input
          id="ws-search-name"
          v-model="localName"
          class="form-input"
          placeholder="Ex: Dupont Jean"
          autocomplete="off"
          @keyup.enter="emitSearch"
        />
      </div>

      <!-- Champ Téléphone + bouton recherche -->
      <div class="form-group">
        <label class="form-label" for="ws-search-phone">TÉLÉPHONE</label>
        <div class="search-phone-row">
          <input
            id="ws-search-phone"
            v-model="localPhone"
            class="form-input"
            placeholder="+33 6..."
            inputmode="tel"
            autocomplete="off"
            @keyup.enter="emitSearch"
          />
          <button
            class="btn-search-icon"
            :disabled="isSearching"
            aria-label="Rechercher un contact"
            title="Rechercher"
            @click="emitSearch"
          >
            <span
              v-if="isSearching"
              class="btn-submit__spinner"
              style="width: 12px; height: 12px; border-width: 1.5px"
            ></span>
            <v-icon v-else size="14" color="white">mdi-magnify</v-icon>
          </button>
        </div>
      </div>

      <!-- Bandeau erreur -->
      <div v-if="searchError" class="list-error">
        <v-icon size="13" color="#E74C3C">mdi-alert-circle-outline</v-icon>
        {{ searchError }}
      </div>

      <!-- Tableau résultats (visible après première recherche) -->
      <ContactResultsTable
        v-if="hasSearched"
        :contacts="contacts"
        :selected-contact-id="selectedContactId"
        :is-loading="isSearching"
        @select="(c) => emit('contact-selected', c)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import ContactResultsTable from "./ContactResultsTable.vue";

const props = defineProps({
  contacts: { type: Array, default: () => [] },
  isSearching: { type: Boolean, default: false },
  searchError: { type: String, default: "" },
  selectedContactId: { type: [Number, null], default: null },
  hasSearched: { type: Boolean, default: false },
});

const emit = defineEmits(["search", "contact-selected"]);

const localName = ref("");
const localPhone = ref("");

function emitSearch() {
  const name = localName.value.trim();
  const phone = localPhone.value.trim();
  if (!name && !phone) return;
  emit("search", { name, phone });
}
</script>

<script>
export default { name: "ContactSearchPanel" };
</script>
