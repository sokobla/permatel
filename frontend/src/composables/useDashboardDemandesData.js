import { ref, computed, onUnmounted, onMounted } from "vue";
import { listDemandes } from "@/services/demandeService";

const OPEN_STATUTS = ["nouvelle", "en_cours", "en_attente"];
const PRIO_ORDER = { urgente: 0, haute: 1, normale: 2, basse: 3 };

function dayKey(isoStr) {
  return isoStr?.slice(0, 10) ?? null;
}

// Mini-graphique 7 jours des cartes KPI : nombre de demandes correspondant
// au prédicat, par jour de `dateField`. Pour les KPI d'état courant
// (ouvertes/urgentes/SLA dépassés/impact sécurité), c'est une APPROXIMATION
// du volume ("combien créées ce jour-là correspondent au critère"), pas un
// relevé historique de l'état réel ce jour-là (on ne conserve pas
// d'historique de statut) — seule la série "résolues" (sur date_resolution)
// est un compte exact.
function buildKpiTrend(demandes, predicate, dateField = "created_at") {
  const today = new Date();
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - (6 - i));
    const key = d.toISOString().slice(0, 10);
    const dayLabel = d.toLocaleDateString("fr-FR", { weekday: "narrow" });
    const count = demandes.filter(
      (x) => predicate(x) && dayKey(x[dateField]) === key,
    ).length;
    return { date: key, dayLabel, count, isToday: i === 6 };
  });
}

function buildTrend(demandes, days) {
  const today = new Date();
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - (days - 1 - i));
    const key = d.toISOString().slice(0, 10);
    const label = d.toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
    });
    return {
      date: key,
      label,
      anomalie: demandes.filter(
        (x) => x.type_demande === "anomalie" && dayKey(x.created_at) === key,
      ).length,
      commande: demandes.filter(
        (x) => x.type_demande === "commande" && dayKey(x.created_at) === key,
      ).length,
      planning: demandes.filter(
        (x) => x.type_demande === "planning" && dayKey(x.created_at) === key,
      ).length,
      admin: demandes.filter(
        (x) => x.type_demande === "admin" && dayKey(x.created_at) === key,
      ).length,
    };
  });
}

export function useDashboardDemandesData() {
  const demandes = ref([]);
  const loading = ref(false);
  const refreshing = ref(false);
  const loadError = ref("");

  const ouvertes = computed(() =>
    demandes.value.filter((d) => OPEN_STATUTS.includes(d.statut)),
  );

  const kpis = computed(() => {
    const all = demandes.value;
    const now = new Date();
    const today = now.toISOString().slice(0, 10);
    const ouv = ouvertes.value;

    const urgentesValue = ouv.filter((d) => d.priorite === "urgente").length;
    const slaValue = ouv.filter(
      (d) => d.sla_deadline && new Date(d.sla_deadline) < now,
    ).length;
    const impactValue = ouv.filter(
      (d) => d.type_demande === "anomalie" && d.impact_securite,
    ).length;

    return {
      ouvertes: {
        label: "DEMANDES OUVERTES",
        value: ouv.length,
        icon: "mdi-text-box-outline",
        subtitle: "Nouvelle · En cours · En attente",
        trend: buildKpiTrend(all, (d) => OPEN_STATUTS.includes(d.statut)),
      },
      urgentes: {
        label: "URGENCES ACTIVES",
        value: urgentesValue,
        icon: "mdi-alert-octagon-outline",
        threshold: { value: 0, direction: "up" },
        subtitle:
          urgentesValue > 0
            ? "À traiter en priorité"
            : "Aucune urgence en cours",
        trend: buildKpiTrend(all, (d) => d.priorite === "urgente"),
      },
      slaDepassement: {
        label: "SLA DÉPASSÉS",
        value: slaValue,
        icon: "mdi-timer-alert-outline",
        threshold: { value: 0, direction: "up" },
        subtitle: slaValue > 0 ? "Dépassement à traiter" : "Aucun dépassement",
        trend: buildKpiTrend(
          all,
          (d) => d.sla_deadline && new Date(d.sla_deadline) < now,
        ),
      },
      impactSecurite: {
        label: "IMPACT SÉCURITÉ",
        value: impactValue,
        icon: "mdi-shield-alert-outline",
        threshold: { value: 0, direction: "up" },
        subtitle:
          impactValue > 0
            ? "Anomalies à impact sécurité"
            : "Aucun impact sécurité signalé",
        trend: buildKpiTrend(
          all,
          (d) => d.type_demande === "anomalie" && d.impact_securite,
        ),
      },
      nouvelles: {
        label: "NOUVELLES / JOUR",
        value: all.filter((d) => dayKey(d.created_at) === today).length,
        icon: "mdi-plus-circle-outline",
        subtitle: "Créées aujourd'hui",
        trend: buildKpiTrend(all, () => true, "created_at"),
      },
      resolues: {
        label: "RÉSOLUES / JOUR",
        value: all.filter((d) => dayKey(d.date_resolution) === today).length,
        icon: "mdi-check-circle-outline",
        subtitle: "Résolues aujourd'hui",
        trend: buildKpiTrend(all, () => true, "date_resolution"),
      },
    };
  });

  const byType = computed(() => {
    const ouv = ouvertes.value;
    const total = ouv.length || 1;
    return [
      { key: "anomalie", label: "Anomalie", color: "#e74c3c" },
      { key: "commande", label: "Commande", color: "#00a8a8" },
      { key: "planning", label: "Planning", color: "#3498db" },
      { key: "admin", label: "Administratif", color: "#8e44ad" },
    ].map((t) => {
      const count = ouv.filter((d) => d.type_demande === t.key).length;
      return { ...t, count, pct: Math.round((count / total) * 100) };
    });
  });

  const byStatut = computed(() => {
    const all = demandes.value;
    const total = all.length || 1;
    return [
      { key: "nouvelle", label: "Nouvelle", color: "#3498db" },
      { key: "en_cours", label: "En cours", color: "#00a8a8" },
      { key: "en_attente", label: "En attente", color: "#f39c12" },
      { key: "resolue", label: "Résolue", color: "#27ae60" },
      { key: "cloturee", label: "Clôturée", color: "#888888" },
      { key: "annulee", label: "Annulée", color: "#e74c3c" },
    ].map((s) => {
      const count = all.filter((d) => d.statut === s.key).length;
      return { ...s, count, pct: Math.round((count / total) * 100) };
    });
  });

  const trendData = computed(() => buildTrend(demandes.value, 30));

  const critiques = computed(() => {
    const now = new Date();
    const seen = new Set();
    return ouvertes.value
      .filter(
        (d) =>
          d.priorite === "urgente" ||
          (d.sla_deadline && new Date(d.sla_deadline) < now),
      )
      .sort(
        (a, b) => (PRIO_ORDER[a.priorite] ?? 9) - (PRIO_ORDER[b.priorite] ?? 9),
      )
      .filter((d) => {
        if (seen.has(d.id)) return false;
        seen.add(d.id);
        return true;
      })
      .slice(0, 10);
  });

  async function load() {
    if (loading.value || refreshing.value) return;

    const isInitial = demandes.value.length === 0;
    if (isInitial) loading.value = true;
    else refreshing.value = true;

    loadError.value = "";
    try {
      demandes.value = await listDemandes();
    } catch {
      loadError.value = "Impossible de charger les données de demandes.";
    } finally {
      loading.value = false;
      refreshing.value = false;
    }
  }

  function startAutoRefresh(interval = 30000) {
    load();

    let id = setInterval(load, interval);

    const onVisibility = () => {
      if (document.hidden) {
        clearInterval(id);
      } else {
        load();
        id = setInterval(load, interval);
      }
    };

    document.addEventListener("visibilitychange", onVisibility);

    onUnmounted(() => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVisibility);
    });
  }

  return {
    loading,
    refreshing,
    loadError,
    kpis,
    byType,
    byStatut,
    trendData,
    critiques,
    load,
    startAutoRefresh,
  };
}
