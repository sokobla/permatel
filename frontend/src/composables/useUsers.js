/**
 * useUsers — Composable gestion des utilisateurs
 *
 * Fournit :
 *  - Chargement paginé/filtré/trié des utilisateurs (server-side)
 *  - Chargement des rôles et tenants (pour les selects du formulaire)
 *  - Création d'un utilisateur (JSON ou FormData si avatar)
 *  - Suppression d'un utilisateur
 *
 * Aucune valeur métier hardcodée — tout passe par userService
 * qui lit ses endpoints depuis import.meta.env.VITE_*
 */
import { ref, computed } from "vue";
import { userService } from "@/services/userService";

/**
 * Délai de debounce (ms) pour la recherche textuelle.
 * Ajustable ici sans impact sur les composants.
 */
const SEARCH_DEBOUNCE_MS = 350;

export function useUsers() {
  // ─── État liste ─────────────────────────────────────────────────────────────
  const users = ref([]);
  const totalUsers = ref(0);
  const loading = ref(false);
  const listError = ref(null);

  // ─── Paramètres de pagination / filtre / tri ─────────────────────────────────
  const page = ref(1);
  const itemsPerPage = ref(25);
  const searchQuery = ref("");
  const statusFilter = ref("");
  const sortBy = ref("id");
  const sortOrder = ref("asc");

  // ─── Options formulaire ──────────────────────────────────────────────────────
  const roles = ref([]);
  const tenants = ref([]);
  const rolesLoading = ref(false);
  const tenantsLoading = ref(false);

  // ─── État création ────────────────────────────────────────────────────────────
  const submissionLoading = ref(false);
  const submissionError = ref(null);
  const submissionSuccess = ref(false);

  // ─── Calculs dérivés ─────────────────────────────────────────────────────────
  const totalPages = computed(() =>
    itemsPerPage.value > 0
      ? Math.max(1, Math.ceil(totalUsers.value / itemsPerPage.value))
      : 1,
  );

  /**
   * Pages visibles dans la pagination (max 5 boutons centrés sur la page courante).
   */
  const visiblePages = computed(() => {
    const total = totalPages.value;
    const current = page.value;
    const delta = 2;
    const range = [];

    const start = Math.max(1, current - delta);
    const end = Math.min(total, current + delta);

    for (let i = start; i <= end; i++) range.push(i);
    return range;
  });

  // ─── Timer debounce recherche ────────────────────────────────────────────────
  let searchTimer = null;

  // ─── API calls ───────────────────────────────────────────────────────────────

  /**
   * Charge la liste paginée des utilisateurs depuis l'API.
   * Paramètres lus depuis le state local (page, itemsPerPage, searchQuery, etc.)
   */
  async function loadUsers() {
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

      const res = await userService.getUsers(params);

      // Support de plusieurs structures de réponse backend possibles
      const data = res.data;
      users.value = data.users ?? data.items ?? data.data ?? data ?? [];
      totalUsers.value = data.total ?? data.count ?? users.value.length;
    } catch (err) {
      listError.value =
        err.response?.data?.message ??
        err.response?.data?.error ??
        "Erreur lors du chargement des utilisateurs";
      users.value = [];
      totalUsers.value = 0;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Déclenche loadUsers après un délai (debounce) — utilisé pour la recherche.
   */
  function onSearchInput() {
    page.value = 1;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadUsers, SEARCH_DEBOUNCE_MS);
  }

  /**
   * Callback pour v-data-table-server @update:options
   * @param {{ page, itemsPerPage, sortBy: Array }} options
   */
  function onTableOptions(options) {
    page.value = options.page ?? 1;
    itemsPerPage.value = options.itemsPerPage ?? 25;

    if (options.sortBy?.length) {
      sortBy.value = options.sortBy[0].key ?? "id";
      sortOrder.value = options.sortBy[0].order ?? "asc";
    } else {
      sortBy.value = "id";
      sortOrder.value = "asc";
    }
    loadUsers();
  }

  /**
   * Navigation vers une page spécifique.
   */
  function goToPage(p) {
    if (p >= 1 && p <= totalPages.value) {
      page.value = p;
      loadUsers();
    }
  }

  /**
   * Charge les rôles disponibles depuis l'API.
   * Réponse attendue : { roles: [{ value, label }] }
   */
  async function loadRoles() {
    rolesLoading.value = true;
    try {
      const res = await userService.getRoles();
      roles.value = res.data.roles ?? res.data ?? [];
    } catch {
      roles.value = [];
    } finally {
      rolesLoading.value = false;
    }
  }

  /**
   * Charge les tenants disponibles depuis l'API.
   * Réponse attendue : { tenants: [{ id, name }] }
   */
  async function loadTenants() {
    tenantsLoading.value = true;
    try {
      const res = await userService.getTenants();
      tenants.value = res.data.tenants ?? res.data ?? [];
    } catch {
      tenants.value = [];
    } finally {
      tenantsLoading.value = false;
    }
  }

  /**
   * Crée un nouvel utilisateur.
   * Si `avatarFile` est fourni, la requête est envoyée en multipart/form-data.
   *
   * @param {Object} formData  Champs du formulaire
   * @param {File|null} avatarFile  Fichier avatar (optionnel)
   * @returns {boolean} Succès ou échec
   */
  async function createUser(formData, avatarFile = null) {
    submissionLoading.value = true;
    submissionError.value = null;
    submissionSuccess.value = false;

    try {
      // Préparation du payload JSON, commun aux deux cas (avec/sans avatar)
      // 1. Exclure confirmPassword qui n'est jamais envoyé.
      // 2. tenant_ids (tableau) est transmis tel quel (multi-affectation).
      const { confirmPassword, ...rest } = formData;
      const jsonPart = { ...rest };

      // 3. Nettoyer les valeurs nulles ou vides avant l'envoi.
      const cleanedJsonPayload = Object.fromEntries(
        Object.entries(jsonPart).filter(([, v]) => v !== undefined && v !== ""),
      );

      let payload = cleanedJsonPayload;

      if (avatarFile) {
        // Si un avatar est fourni, on utilise FormData.
        // Le backend devra parser le champ 'data' en tant que JSON.
        payload = new FormData();
        payload.append("data", JSON.stringify(cleanedJsonPayload));
        payload.append("avatar", avatarFile);
      }
      console.log("Payload à envoyer pour création :", payload);
      await userService.createUser(payload);
      submissionSuccess.value = true;

      // Rechargement automatique de la liste après création
      page.value = 1;
      await loadUsers();
      return true;
    } catch (err) {
      const data = err.response?.data;
      submissionError.value =
        data?.message ?? data?.error ?? "Erreur lors de la création";
      return false;
    } finally {
      submissionLoading.value = false;
    }
  }

  /**
   * Met à jour un utilisateur existant.
   * Gère le payload JSON et FormData de manière identique à createUser.
   *
   * @param {string|number} userId ID de l'utilisateur à mettre à jour
   * @param {Object} formData Champs du formulaire
   * @param {File|null} avatarFile Fichier avatar (optionnel)
   * @returns {boolean} Succès ou échec
   */
  async function updateUser(userId, formData, avatarFile = null) {
    submissionLoading.value = true;
    submissionError.value = null;
    submissionSuccess.value = false;

    try {
      // Préparation du payload, identique à createUser
      const { confirmPassword, ...rest } = formData;
      const jsonPart = { ...rest };
      // Pour la mise à jour, si le mot de passe est vide, on ne l'envoie pas.
      if (!jsonPart.password) {
        delete jsonPart.password;
      }

      const cleanedJsonPayload = Object.fromEntries(
        Object.entries(jsonPart).filter(([, v]) => v !== undefined && v !== ""),
      );

      let payload = cleanedJsonPayload;

      if (avatarFile) {
        payload = new FormData();
        payload.append("data", JSON.stringify(cleanedJsonPayload));
        payload.append("avatar", avatarFile);
      }

      await userService.updateUser(userId, payload);
      submissionSuccess.value = true;

      await loadUsers();
      return true;
    } catch (err) {
      const data = err.response?.data;
      submissionError.value =
        data?.message ?? data?.error ?? "Erreur lors de la mise à jour";
      return false;
    } finally {
      submissionLoading.value = false;
    }
  }

  async function resetPassword(userId, newPassword) {
    submissionLoading.value = true;
    submissionError.value = null;
    submissionSuccess.value = false;
    try {
      await userService.resetPassword(userId, newPassword);
      submissionSuccess.value = true;
      return true;
    } catch (err) {
      submissionError.value =
        err.response?.data?.message || "Erreur lors de la réinitialisation.";
      return false;
    } finally {
      submissionLoading.value = false;
    }
  }

  /**
   * Supprime un utilisateur par son ID.
   * @param {number|string} userId
   * @returns {boolean} Succès ou échec
   */
  async function deleteUser(userId) {
    try {
      await userService.deleteUser(userId);
      await loadUsers();
      return true;
    } catch (err) {
      listError.value =
        err.response?.data?.message ?? "Erreur lors de la suppression";
      return false;
    }
  }

  /**
   * Réinitialise l'état de création (pour re-ouvrir le formulaire propre).
   */
  function resetSubmissionState() {
    submissionError.value = null;
    submissionSuccess.value = false;
    submissionLoading.value = false;
  }

  // ─── Initialisation ──────────────────────────────────────────────────────────
  /**
   * Initialise le module : charge les utilisateurs + options de formulaire.
   */
  async function init() {
    await Promise.all([loadUsers(), loadRoles(), loadTenants()]);
  }

  return {
    // Liste
    users,
    totalUsers,
    loading,
    listError,
    page,
    itemsPerPage,
    searchQuery,
    statusFilter,
    totalPages,
    visiblePages,

    // Options formulaire
    roles,
    tenants,
    rolesLoading,
    tenantsLoading,

    // Création
    submissionLoading,
    submissionError,
    submissionSuccess,

    // Méthodes
    loadUsers,
    onSearchInput,
    onTableOptions,
    goToPage,
    loadRoles,
    loadTenants,
    createUser,
    updateUser,
    resetPassword,
    deleteUser,
    resetSubmissionState,
    init,
  };
}
