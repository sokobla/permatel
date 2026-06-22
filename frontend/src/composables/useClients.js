import { ref, computed } from "vue";
import apiClient from "@/services/http/axios";
import { debounce } from "lodash-es";

export function useClients() {
  const clients = ref([]);
  const totalClients = ref(0);
  const loading = ref(true);
  const submissionLoading = ref(false);
  const submissionError = ref(null);
  const submissionSuccess = ref(false);

  const page = ref(1);
  const itemsPerPage = ref(10);
  const searchQuery = ref("");
  const statusFilter = ref("");
  const sortBy = ref([]);

  const totalPages = computed(() =>
    totalClients.value > 0
      ? Math.ceil(totalClients.value / itemsPerPage.value)
      : 1,
  );

  const loadClients = async () => {
    loading.value = true;
    try {
      const params = {
        page: page.value,
        per_page: itemsPerPage.value,
        search: searchQuery.value,
        status: statusFilter.value,
        sort_by: sortBy.value.length ? sortBy.value[0].key : undefined,
        order: sortBy.value.length ? sortBy.value[0].order : undefined,
      };
      const response = await apiClient.get("/clients", { params });
      clients.value = response.data.clients;
      totalClients.value = response.data.total;
    } catch (error) {
      console.error("Erreur lors du chargement des clients:", error);
      clients.value = [];
      totalClients.value = 0;
    } finally {
      loading.value = false;
    }
  };

  const onSearchInput = debounce(loadClients, 300);

  const onTableOptions = ({
    page: newPage,
    itemsPerPage: newItemsPerPage,
    sortBy: newSortBy,
  }) => {
    page.value = newPage;
    itemsPerPage.value = newItemsPerPage;
    sortBy.value = newSortBy;
    loadClients();
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

  const createClient = async (data, logoFile) => {
    submissionLoading.value = true;
    submissionError.value = null;
    submissionSuccess.value = false;
    try {
      const payload = logoFile ? _buildFormData(data, logoFile) : data;
      const headers = logoFile ? { "Content-Type": "multipart/form-data" } : {};
      await apiClient.post("/clients", payload, { headers });
      submissionSuccess.value = true;
      await loadClients();
      return true;
    } catch (error) {
      submissionError.value =
        error.response?.data?.error || "Une erreur est survenue.";
      return false;
    } finally {
      submissionLoading.value = false;
    }
  };

  const updateClient = async (id, data, logoFile) => {
    submissionLoading.value = true;
    submissionError.value = null;
    submissionSuccess.value = false;
    try {
      const payload = logoFile ? _buildFormData(data, logoFile) : data;
      const headers = logoFile ? { "Content-Type": "multipart/form-data" } : {};
      await apiClient.put(`/clients/${id}`, payload, { headers });
      submissionSuccess.value = true;
      await loadClients();
      return true;
    } catch (error) {
      submissionError.value =
        error.response?.data?.error || "Une erreur est survenue.";
      return false;
    } finally {
      submissionLoading.value = false;
    }
  };

  const deleteClient = async (id) => {
    try {
      await apiClient.delete(`/clients/${id}`);
      await loadClients();
      return true;
    } catch (error) {
      console.error("Erreur lors de la suppression du client:", error);
      return false;
    }
  };

  return {
    clients,
    totalClients,
    loading,
    submissionLoading,
    submissionError,
    submissionSuccess,
    searchQuery,
    statusFilter,
    itemsPerPage,
    page,
    totalPages,
    loadClients,
    onSearchInput,
    onTableOptions,
    createClient,
    updateClient,
    deleteClient,
    resetSubmissionState,
  };
}
