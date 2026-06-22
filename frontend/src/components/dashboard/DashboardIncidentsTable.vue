<template>
  <v-card elevation="0" class="fill-height">
    <v-card-title class="card-title">Critical Incidents</v-card-title>
    <v-divider />
    <v-data-table
      :headers="headers"
      :items="incidents"
      density="compact"
      class="incidents-table"
      hide-default-footer
      :items-per-page="-1"
    >
      <template v-slot:[`item.id`]="{ item }">
        <span class="code-font">{{ item.id.toString() }}</span>
      </template>
      <template v-slot:[`item.timestamp`]="{ item }">
        <span class="code-font">{{ new Date(item.timestamp).toLocaleTimeString() }}</span>
      </template>
      <template v-slot:[`item.priority`]="{ item }">
        <v-chip :color="priorityColor(item.priority)" label size="small" class="priority-chip">
          {{ item.priority }}
        </v-chip>
      </template>
      <template v-slot:[`item.actions`]>
        <v-btn variant="text" size="small" icon="mdi-magnify" color="#910807"></v-btn>
      </template>
    </v-data-table>
  </v-card>
</template>

<script setup lang="ts">
import type { Incident } from "@/composables/useMockDashboardData";

defineProps<{
  incidents: Incident[];
}>();

const headers = [
  { title: 'ID', key: 'id', sortable: false, width: '140px' },
  { title: 'Time', key: 'timestamp', sortable: false, width: '100px' },
  { title: 'Description', key: 'description', sortable: false },
  { title: 'Priority', key: 'priority', sortable: false, width: '120px' },
  { title: 'Status', key: 'status', sortable: false, width: '130px' },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center', width: '80px' },
];

const priorityColor = (priority: Incident['priority']) => {
  switch (priority) {
    case 'CRITICAL': return '#E74C3C';
    case 'HIGH': return 'orange';
    case 'MEDIUM': return 'grey-darken-1';
    case 'WARNING': return 'amber';
    default: return 'grey';
  }
};
</script>

<style>
.card-title {
  font-family: 'Fira Sans', sans-serif;
  font-size: 1rem;
  font-weight: 700;
  color: #000B23;
}
.incidents-table {
  font-family: 'Fira Sans', sans-serif;
  background-color: #FFFFFF;
}
.incidents-table .v-data-table-header__content {
  font-weight: 700 !important;
  font-size: 0.75rem !important;
  text-transform: uppercase;
  color: #333;
}
.code-font {
  font-family: 'Fira Code', monospace;
}
.priority-chip {
  font-family: 'Fira Code', monospace;
  font-weight: 700;
}
</style>