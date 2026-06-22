import { ref, reactive, onUnmounted, readonly } from "vue";

// --- MOCK DATA GENERATION ---

const createInitialKpis = () => ({
  totalCalls: { label: "TOTAL CALLS", value: 1256, change: 0.1 },
  waitingCalls: { label: "CALLS IN QUEUE", value: 8 },
  sla: {
    label: "GLOBAL SLA",
    value: 92.5,
    unit: "%",
    threshold: { value: 90, direction: "down" },
  },
  aht: {
    label: "AVERAGE HANDLE TIME",
    value: 185,
    unit: "s",
    threshold: { value: 200, direction: "up" },
  },
  agentsConnected: { label: "AGENTS CONNECTED", value: 48 },
  agentsOnCall: { label: "AGENTS ON CALL", value: 35 },
  agentsOnBreak: { label: "AGENTS ON BREAK", value: 5 },
  pickupRate: { label: "PICKUP RATE", value: 98.1, unit: "%" },
  abandons: {
    label: "ABANDONED",
    value: 26,
    threshold: { value: 30, direction: "up" },
  },
});

const agentStatuses = ["EN APPEL", "DISPONIBLE", "PAUSE", "OFFLINE"];
const createInitialAgents = () => [
  {
    id: "AGT-007",
    name: "Alice Martin",
    team: "Support N1",
    status: "EN APPEL",
    timeInStatus: 123,
  },
  {
    id: "AGT-012",
    name: "Bob Dupont",
    team: "Support N1",
    status: "DISPONIBLE",
    timeInStatus: 45,
  },
  {
    id: "AGT-003",
    name: "Charlie Durand",
    team: "Commercial",
    status: "PAUSE",
    timeInStatus: 302,
  },
  {
    id: "AGT-021",
    name: "David Petit",
    team: "Support N2",
    status: "EN APPEL",
    timeInStatus: 560,
  },
  {
    id: "AGT-035",
    name: "Eve Dubois",
    team: "Commercial",
    status: "OFFLINE",
    timeInStatus: 86400,
  },
  {
    id: "AGT-042",
    name: "Frank Moreau",
    team: "Support N2",
    status: "DISPONIBLE",
    timeInStatus: 18,
  },
];

const incidentPriorities = ["CRITICAL", "HIGH", "MEDIUM", "WARNING"];
const incidentStatuses = ["En cours", "Investigating", "Bloqué", "Acknowledge"];
const createInitialIncidents = () => [
  {
    id: "ERR-402-SIP",
    timestamp: new Date(Date.now() - 5 * 60000),
    description: "SIP Trunk Capacity Reached",
    priority: "CRITICAL",
    status: "Investigating",
  },
  {
    id: "WRN-881-API",
    timestamp: new Date(Date.now() - 15 * 60000),
    description: "API Latency > 500ms",
    priority: "HIGH",
    status: "En cours",
  },
  {
    id: "SYS-101-DB",
    timestamp: new Date(Date.now() - 120 * 60000),
    description: "Database connection pool saturation",
    priority: "MEDIUM",
    status: "Acknowledge",
  },
];

const createInitialTeams = () => [
  { name: "Support N1", calls: 890, sla: 91.2, aht: 170, pickupRate: 99.1 },
  { name: "Support N2", calls: 150, sla: 95.8, aht: 320, pickupRate: 97.5 },
  { name: "Commercial", calls: 216, sla: 88.5, aht: 155, pickupRate: 96.8 },
];

const createRealtimeSeries = () => {
  return Array.from({ length: 20 }, () => Math.floor(Math.random() * 50 + 10));
};

// --- COMPOSABLE LOGIC ---

let fastIntervalId;
let slowIntervalId;

const kpis = reactive(createInitialKpis());
const agents = ref(createInitialAgents());
const incidents = ref(createInitialIncidents());
const teams = ref(createInitialTeams());
const realtimeSeries = ref(createRealtimeSeries());

const random = (min, max) => Math.random() * (max - min) + min;

const updateFastData = () => {
  kpis.totalCalls.value += Math.floor(random(0, 4));
  kpis.totalCalls.change = random(-0.5, 0.5);
  kpis.waitingCalls.value = Math.max(
    0,
    kpis.waitingCalls.value + Math.round(random(-2, 2)),
  );
  kpis.abandons.value += random(0, 1) > 0.8 ? 1 : 0;
  kpis.sla.value = Math.max(
    85,
    Math.min(100, kpis.sla.value + random(-0.1, 0.1)),
  );
  kpis.aht.value = Math.max(
    150,
    Math.min(220, kpis.aht.value + random(-0.5, 0.5)),
  );
  kpis.pickupRate.value = Math.max(
    90,
    Math.min(100, kpis.pickupRate.value + random(-0.2, 0.2)),
  );

  let onCallCount = 0;
  let onBreakCount = 0;
  agents.value.forEach((agent) => {
    agent.timeInStatus += 5;
    if (random(0, 1) > 0.97 && agent.status !== "OFFLINE") {
      const newStatus =
        agentStatuses[Math.floor(random(0, agentStatuses.length - 1))];
      if (agent.status !== newStatus) {
        agent.status = newStatus;
        agent.timeInStatus = 0;
      }
    }
    if (agent.status === "EN APPEL") onCallCount++;
    if (agent.status === "PAUSE") onBreakCount++;
  });
  kpis.agentsOnCall.value = onCallCount;
  kpis.agentsOnBreak.value = onBreakCount;
  kpis.agentsConnected.value = agents.value.filter(
    (a) => a.status !== "OFFLINE",
  ).length;

  const newSeries = [...realtimeSeries.value];
  newSeries.shift();
  newSeries.push(Math.floor(random(10, 60)));
  realtimeSeries.value = newSeries;
};

const updateSlowData = () => {
  teams.value.forEach((team) => {
    team.calls += Math.floor(random(10, 50));
    team.sla = Math.max(80, Math.min(100, team.sla + random(-0.5, 0.5)));
    team.aht = Math.max(150, Math.min(350, team.aht + random(-2, 2)));
    team.pickupRate = Math.max(
      90,
      Math.min(100, team.pickupRate + random(-0.3, 0.3)),
    );
  });

  if (random(0, 1) > 0.8) {
    const newId = `EVT-${Math.floor(random(100, 999))}`;
    if (!incidents.value.find((i) => i.id === newId)) {
      incidents.value.unshift({
        id: newId,
        timestamp: new Date(),
        description: "New automatic system warning",
        priority:
          incidentPriorities[Math.floor(random(0, incidentPriorities.length))],
        status: "En cours",
      });
      if (incidents.value.length > 10) incidents.value.pop();
    }
  }

  if (random(0, 1) > 0.7 && incidents.value.length > 0) {
    const incidentToUpdate =
      incidents.value[Math.floor(random(0, incidents.value.length))];
    if (incidentToUpdate.status !== "Acknowledge") {
      incidentToUpdate.status =
        incidentStatuses[Math.floor(random(0, incidentStatuses.length))];
    }
  }
};

export function useMockDashboardData() {
  const startAutoRefresh = (fastInterval = 5000, slowInterval = 20000) => {
    stopAutoRefresh();
    fastIntervalId = window.setInterval(updateFastData, fastInterval);
    slowIntervalId = window.setInterval(updateSlowData, slowInterval);
  };

  const stopAutoRefresh = () => {
    if (fastIntervalId) clearInterval(fastIntervalId);
    if (slowIntervalId) clearInterval(slowIntervalId);
    fastIntervalId = undefined;
    slowIntervalId = undefined;
  };

  onUnmounted(stopAutoRefresh);

  return {
    kpis: readonly(kpis),
    agents: readonly(agents),
    incidents: readonly(incidents),
    teams: readonly(teams),
    realtimeSeries: readonly(realtimeSeries),
    startAutoRefresh,
    stopAutoRefresh,
  };
}
