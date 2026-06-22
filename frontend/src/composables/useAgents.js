import { ref, computed } from "vue";
import { agentService } from "@/services/agentService";

const SEARCH_DEBOUNCE_MS = 350;

export function useAgents() {
  // --- État de la liste
  const agents = ref([]);
  const totalAgents = ref(0);
  const loading = ref(false);
  const listError = ref(null);

  // --- Paramètres de la table
  const page = ref(1);
  const itemsPerPage = ref(10);
  const searchQuery = ref("");
  const statusFilter = ref("");
  const typeFilter = ref("");
  const sortBy = ref("nom");
  const sortOrder = ref("asc");

  // --- Options de formulaire
  const prestataires = ref([]);
  const prestatairesLoading = ref(false);

  // --- État de soumission du formulaire
  const submissionLoading = ref(false);
  const submissionError = ref(null);
  const submissionSuccess = ref(false);

  // --- Propriétés calculées
  const totalPages = computed(() =>
    Math.max(1, Math.ceil(totalAgents.value / itemsPerPage.value)),
  );

  let searchTimer = null;

  // --- Méthodes API

  async function loadAgents() {
    loading.value = true;
    listError.value = null;
    try {
      const params = {
        page: page.value,
        per_page: itemsPerPage.value,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
        search: searchQuery.value.trim(),
        status: statusFilter.value,
        type: typeFilter.value,
      };
      const res = await agentService.getAgents(params);
      agents.value = res.data.agents || [];
      totalAgents.value = res.data.total || 0;
    } catch (err) {
      listError.value =
        err.response?.data?.message || "Erreur lors du chargement des agents.";
      agents.value = [];
      totalAgents.value = 0;
    } finally {
      loading.value = false;
    }
  }

  function onSearchInput() {
    page.value = 1;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadAgents, SEARCH_DEBOUNCE_MS);
  }

  function onTableOptions(options) {
    page.value = options.page;
    itemsPerPage.value = options.itemsPerPage;
    if (options.sortBy?.length) {
      sortBy.value = options.sortBy[0].key;
      sortOrder.value = options.sortBy[0].order;
    }
    loadAgents();
  }

  async function loadPrestataires() {
    prestatairesLoading.value = true;
    try {
      const res = await agentService.getPrestataires();
      // On ajoute une option "Agent interne" pour représenter le tenant
      prestataires.value = [
        { id: null, nom: "Agent interne (Tenant)" },
        ...(res.data.prestataires || []),
      ];
    } catch {
      prestataires.value = [{ id: null, nom: "Agent interne (Tenant)" }];
    } finally {
      prestatairesLoading.value = false;
    }
  }

  function _preparePayload(formData, avatarFile) {
    // Nettoyage des données avant envoi
    const cleanedData = Object.fromEntries(
      Object.entries(formData).filter(
        ([, v]) => v !== null && v !== undefined && v !== "",
      ),
    );

    if (avatarFile) {
      const payload = new FormData();
      payload.append("data", JSON.stringify(cleanedData));
      payload.append("avatar", avatarFile);
      return payload;
    }
    return cleanedData;
  }

  async function createAgent(formData, avatarFile = null) {
    submissionLoading.value = true;
    submissionError.value = null;
    submissionSuccess.value = false;
    try {
      const payload = _preparePayload(formData, avatarFile);
      await agentService.createAgent(payload);
      submissionSuccess.value = true;
      await loadAgents(); // Recharger la liste
      return true;
    } catch (err) {
      submissionError.value =
        err.response?.data?.message || "Erreur lors de la création de l'agent.";
      return false;
    } finally {
      submissionLoading.value = false;
    }
  }

  async function updateAgent(agentId, formData, avatarFile = null) {
    submissionLoading.value = true;
    submissionError.value = null;
    submissionSuccess.value = false;
    try {
      const payload = _preparePayload(formData, avatarFile);
      await agentService.updateAgent(agentId, payload);
      submissionSuccess.value = true;
      await loadAgents(); // Recharger la liste
      return true;
    } catch (err) {
      submissionError.value =
        err.response?.data?.message ||
        "Erreur lors de la mise à jour de l'agent.";
      return false;
    } finally {
      submissionLoading.value = false;
    }
  }

  async function deleteAgent(agentId) {
    // On pourrait ajouter un état de chargement spécifique à la suppression
    try {
      await agentService.deleteAgent(agentId);
      await loadAgents();
      return true;
    } catch (err) {
      listError.value =
        err.response?.data?.message ||
        "Erreur lors de la suppression de l'agent.";
      return false;
    }
  }

  function resetSubmissionState() {
    submissionLoading.value = false;
    submissionError.value = null;
    submissionSuccess.value = false;
  }

  async function init() {
    await Promise.all([loadAgents(), loadPrestataires()]);
  }

  return {
    // State
    agents,
    totalAgents,
    loading,
    listError,
    prestataires,
    prestatairesLoading,
    submissionLoading,
    submissionError,
    submissionSuccess,

    // Table options
    page,
    itemsPerPage,
    searchQuery,
    statusFilter,
    typeFilter,
    totalPages,

    // Methods
    init,
    loadAgents,
    onSearchInput,
    onTableOptions,
    createAgent,
    updateAgent,
    deleteAgent,
    resetSubmissionState,
  };
}
