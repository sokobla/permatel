import { ref, computed } from "vue";
import { partnerService } from "@/services/partnerService";

const SEARCH_DEBOUNCE_MS = 350;

export function usePartners() {
  // --- État liste ---
  const partners = ref([]);
  const totalPartners = ref(0);
  const loading = ref(false);
  const listError = ref(null);

  // --- Paramètres de pagination / filtre / tri ---
  const page = ref(1);
  const itemsPerPage = ref(25);
  const searchQuery = ref("");
  const statusFilter = ref("");
  const sortBy = ref("nom"); // Tri par défaut par nom
  const sortOrder = ref("asc");

  // --- État soumission formulaire ---
  const submissionLoading = ref(false);
  const submissionError = ref(null);
  const submissionSuccess = ref(false);

  // --- Calculs dérivés ---
  const totalPages = computed(() =>
    itemsPerPage.value > 0
      ? Math.max(1, Math.ceil(totalPartners.value / itemsPerPage.value))
      : 1,
  );

  let searchTimer = null;

  // --- API calls ---
  async function loadPartners() {
    loading.value = true;
    listError.value = null;
    try {
      const params = {
        page: page.value,
        per_page: itemsPerPage.value,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
      };
      if (searchQuery.value?.trim()) params.search = searchQuery.value.trim();
      if (statusFilter.value) params.status = statusFilter.value;

      const res = await partnerService.getPartners(params);
      partners.value =
        res.data.prestataires ?? res.data.partners ?? res.data ?? [];
      totalPartners.value = res.data.total ?? partners.value.length;
    } catch (err) {
      listError.value =
        err.response?.data?.message ??
        "Erreur lors du chargement des prestataires.";
      partners.value = [];
      totalPartners.value = 0;
    } finally {
      loading.value = false;
    }
  }

  function onSearchInput() {
    page.value = 1;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadPartners, SEARCH_DEBOUNCE_MS);
  }

  function onTableOptions(options) {
    page.value = options.page ?? 1;
    itemsPerPage.value = options.itemsPerPage ?? 25;
    if (options.sortBy?.length) {
      sortBy.value = options.sortBy[0].key ?? "nom";
      sortOrder.value = options.sortBy[0].order ?? "asc";
    }
    loadPartners();
  }

  function resetSubmissionState() {
    submissionError.value = null;
    submissionSuccess.value = false;
    submissionLoading.value = false;
  }

  async function _submit(apiCall) {
    submissionLoading.value = true;
    submissionError.value = null;
    submissionSuccess.value = false;
    try {
      await apiCall();
      submissionSuccess.value = true;
      await loadPartners();
      return true;
    } catch (err) {
      submissionError.value =
        err.response?.data?.message ?? "Une erreur est survenue.";
      return false;
    } finally {
      submissionLoading.value = false;
    }
  }

  async function createPartner(formData) {
    return _submit(() => partnerService.createPartner(formData));
  }

  async function updatePartner(id, formData) {
    return _submit(() => partnerService.updatePartner(id, formData));
  }

  async function deactivatePartner(id) {
    // La suppression est un soft-delete via PATCH status
    try {
      await partnerService.deactivatePartner(id);
      await loadPartners();
      return true;
    } catch (err) {
      listError.value =
        err.response?.data?.message ?? "Erreur lors de la désactivation.";
      return false;
    }
  }

  async function init() {
    await loadPartners();
  }

  return {
    partners,
    totalPartners,
    loading,
    listError,
    page,
    itemsPerPage,
    searchQuery,
    statusFilter,
    totalPages,
    submissionLoading,
    submissionError,
    submissionSuccess,
    loadPartners,
    onSearchInput,
    onTableOptions,
    createPartner,
    updatePartner,
    deactivatePartner,
    resetSubmissionState,
    init,
  };
}
