<template>
  <v-card elevation="0" class="ddb-card">
    <v-card-title class="card-title">RÉPARTITION DES DEMANDES OUVERTES</v-card-title>
    <v-divider />
    <v-card-text class="ddb-body">

      <div v-if="loading" class="ddb-skeleton">
        <div v-for="n in 8" :key="n" class="ddb-sk-row">
          <div class="ddb-sk ddb-sk--label"></div>
          <div class="ddb-sk ddb-sk--bar"></div>
          <div class="ddb-sk ddb-sk--count"></div>
        </div>
      </div>

      <div v-else class="ddb-cols">

        <!-- ─ Par type ─ -->
        <div class="ddb-col">
          <div class="ddb-col-hdr">PAR TYPE</div>
          <div class="ddb-rows">
            <div v-for="t in byType" :key="t.key" class="ddb-row">
              <span class="ddb-row-label">{{ t.label }}</span>
              <div class="ddb-bar-track">
                <div
                  class="ddb-bar-fill"
                  :style="{ width: `${t.pct}%`, background: t.color }"
                ></div>
              </div>
              <span class="ddb-row-count">{{ t.count }}</span>
            </div>
          </div>
        </div>

        <div class="ddb-sep"></div>

        <!-- ─ Par statut ─ -->
        <div class="ddb-col">
          <div class="ddb-col-hdr">PAR STATUT</div>
          <div class="ddb-rows">
            <div v-for="s in byStatut" :key="s.key" class="ddb-row">
              <span class="ddb-row-label">{{ s.label }}</span>
              <div class="ddb-bar-track">
                <div
                  class="ddb-bar-fill"
                  :style="{ width: `${s.pct}%`, background: s.color }"
                ></div>
              </div>
              <span class="ddb-row-count">{{ s.count }}</span>
            </div>
          </div>
        </div>

      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
defineProps({
  byType:   { type: Array, default: () => [] },
  byStatut: { type: Array, default: () => [] },
  loading:  { type: Boolean, default: false },
});
</script>

<script>
export default { name: "DashboardDemandesBreakdown" };
</script>

<style scoped>
.ddb-card {
  border: 1px solid rgba(197, 198, 206, 0.15) !important;
  height: 100%;
}

.ddb-body {
  padding: 12px 16px 16px !important;
}

/* ── Layout ──────────────────────────────────────────────────── */

.ddb-cols {
  display: flex;
  gap: 0;
}

.ddb-col {
  flex: 1;
  min-width: 0;
}

.ddb-sep {
  width: 1px;
  background: rgba(0, 0, 0, 0.06);
  margin: 0 16px;
  flex-shrink: 0;
}

.ddb-col-hdr {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #aaa;
  text-transform: uppercase;
  margin-bottom: 10px;
}

/* ── Rows ────────────────────────────────────────────────────── */

.ddb-rows {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.ddb-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ddb-row-label {
  font-family: "Fira Sans", sans-serif;
  font-size: 0.7rem;
  font-weight: 600;
  color: #444;
  width: 76px;
  flex-shrink: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ddb-bar-track {
  flex: 1;
  height: 6px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 3px;
  overflow: hidden;
}

.ddb-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
  min-width: 2px;
}

.ddb-row-count {
  font-family: "Fira Code", monospace;
  font-size: 0.75rem;
  font-weight: 700;
  color: #000b23;
  width: 24px;
  text-align: right;
  flex-shrink: 0;
}

/* ── Skeleton ──────────────────────────────────────────────── */

.ddb-skeleton {
  display: flex;
  flex-direction: column;
  gap: 9px;
  animation: ddb-pulse 1.4s ease-in-out infinite;
}

@keyframes ddb-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.35; }
}

.ddb-sk-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ddb-sk {
  background: #e8e8e8;
  border-radius: 3px;
}

.ddb-sk--label { width: 76px; height: 10px; flex-shrink: 0; }
.ddb-sk--bar   { flex: 1; height: 6px; }
.ddb-sk--count { width: 24px; height: 10px; flex-shrink: 0; }
</style>
