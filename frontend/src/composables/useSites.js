import { ref, computed } from "vue";
import apiClient from "@/services/http/axios";
import { debounce } from "lodash-es";

export function useSites() {
  const sites = ref([]);
  const totalSites = ref(0);
  const loading = ref(true);
  const submissionLoading = ref(false);
  const submissionError = ref(null);
  const submissionSuccess = ref(false);

  const page = ref(1);
  const itemsPerPage = ref(10);
  const searchQuery = ref("");
  const statusFilter = ref("");
  const clientFilter = ref("");
  const sortBy = ref([]);

  const totalPages = computed(() =>
    totalSites.value > 0 ? Math.ceil(totalSites.value / itemsPerPage.value) : 1,
  );

  const loadSites = async () => {
    loading.value = true;
    try {
      const params = {
        page: page.value,
        per_page: itemsPerPage.value,
        search: searchQuery.value,
        status: statusFilter.value,
        client_id: clientFilter.value,
        sort_by: sortBy.value.length ? sortBy.value[0].key : undefined,
        order: sortBy.value.length ? sortBy.value[0].order : undefined,
      };
      const response = await apiClient.get("/sites", { params });
      sites.value = response.data.sites;
      totalSites.value = response.data.total;
    } catch (error) {
      console.error("Erreur lors du chargement des sites:", error);
      sites.value = [];
      totalSites.value = 0;
    } finally {
      loading.value = false;
    }
  };

  const onSearchInput = debounce(loadSites, 300);

  const onTableOptions = ({
    page: newPage,
    itemsPerPage: newItemsPerPage,
    sortBy: newSortBy,
  }) => {
    page.value = newPage;
    itemsPerPage.value = newItemsPerPage;
    sortBy.value = newSortBy;
    loadSites();
  };

  const resetSubmissionState = () => {
    submissionLoading.value = false;
    submissionError.value = null;
    submissionSuccess.value = false;
  };

  const _buildFormData = (data, logoFile) => {
    const formData = new FormData();
    formData.append("data", JSON.stringify(data));
    if (logoFile) {
      formData.append("logo", logoFile);
    }
    return formData;
  };

  const createSite = async (data, logoFile) => {
    submissionLoading.value = true;
    submissionError.value = null;
    submissionSuccess.value = false;
    try {
      const payload = logoFile ? _buildFormData(data, logoFile) : data;
      const headers = logoFile ? { "Content-Type": "multipart/form-data" } : {};
      await apiClient.post("/sites", payload, { headers });
      submissionSuccess.value = true;
      await loadSites();
      return true;
    } catch (error) {
      submissionError.value =
        error.response?.data?.error || "Une erreur est survenue.";
      return false;
    } finally {
      submissionLoading.value = false;
    }
  };

  const updateSite = async (id, data, logoFile) => {
    submissionLoading.value = true;
    submissionError.value = null;
    submissionSuccess.value = false;
    try {
      const payload = logoFile ? _buildFormData(data, logoFile) : data;
      const headers = logoFile ? { "Content-Type": "multipart/form-data" } : {};
      await apiClient.put(`/sites/${id}`, payload, { headers });
      submissionSuccess.value = true;
      await loadSites();
      return true;
    } catch (error) {
      submissionError.value =
        error.response?.data?.error || "Une erreur est survenue.";
      return false;
    } finally {
      submissionLoading.value = false;
    }
  };

  const deleteSite = async (id) => {
    // La logique de suppression pour les sites est une désactivation (soft delete)
    // qui est gérée par un endpoint DELETE qui change is_active à false.
    try {
      await apiClient.delete(`/sites/${id}`);
      await loadSites(); // Recharger pour refléter le changement de statut
      return true;
    } catch (error) {
      console.error("Erreur lors de la désactivation du site:", error);
      return false;
    }
  };

  return {
    sites,
    totalSites,
    loading,
    submissionLoading,
    submissionError,
    submissionSuccess,
    searchQuery,
    statusFilter,
    clientFilter,
    itemsPerPage,
    page,
    totalPages,
    loadSites,
    onSearchInput,
    onTableOptions,
    createSite,
    updateSite,
    deleteSite,
    resetSubmissionState,
  };
}
