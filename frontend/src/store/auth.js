/**
 * Store d'authentification PERMATEL - Pinia
 *
 * Etat persiste (localStorage via pinia-plugin-persistedstate) :
 *   user, accessToken, refreshToken, activeTenantId, tenants
 *
 * Etat non persiste :
 *   returnUrl - destination memorisee avant redirection vers /login
 *
 * Actions :
 *   login(username, password)  - authentification complete
 *   logout()                   - deconnexion avec appel API + reset
 *   logoutSilent()             - reset local seul (utilise par l'intercepteur
 *                                quand le refresh token est invalide)
 *   setAccessToken(token)      - mise a jour access token apres refresh
 *                                (utilise exclusivement par l'intercepteur)
 *   selectTenant(tenantId)     - selection du tenant actif (tache 2.5)
 */
import { defineStore } from "pinia";
import { authService } from "@/services/authService";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    // Donnees utilisateur
    user: null,

    // Tokens JWT
    accessToken: null,
    refreshToken: null,

    // Multi-tenant - liste des tenants accessibles, renseignee apres login
    tenants: [],
    // Tenant actif (UUID string) - propage dans le claim `tid` du JWT
    activeTenantId: null,
    // Vrai si l'utilisateur est super-admin global (accès à tous les tenants)
    isGlobalAdmin: false,
    // Vrai si l'utilisateur administre le tenant ACTIF (super-admin, ou membership_role=admin)
    isTenantAdmin: false,
    // Disponibilités fonctionnelles du tenant actif (source : backend, jamais recalculées ici)
    features: null,

    // Navigation - non persiste (ne doit pas survivre a un rechargement)
    returnUrl: null,
  }),

  getters: {
    /** Vrai si un access token est present en memoire. */
    isAuthenticated: (state) => !!state.accessToken,

    /**
     * Vrai si l'utilisateur doit encore choisir un tenant actif.
     * - standard : seulement s'il a ≥2 tenants (1 seul ⇒ auto-sélectionné, écran bypassé) ;
     * - super-admin : toujours tant qu'aucun tenant n'est actif (doit choisir son contexte).
     */
    needsTenantSelection: (state) => {
      if (state.activeTenantId) return false;
      if (state.isGlobalAdmin) return state.tenants.length >= 1;
      return state.tenants.length > 1;
    },

    /** Rôle courant ('ADMIN' | 'MANAGER' | 'PERMANENCIER') ou null. */
    role: (state) => state.user?.role ?? null,

    isAdmin: (state) => state.user?.role === "ADMIN",
    isManager: (state) => state.user?.role === "MANAGER",
    isPermanencier: (state) => state.user?.role === "PERMANENCIER",

    /** Capacité d'administration du tenant actif (membres ET configuration). */
    canManageMembers: (state) => state.isGlobalAdmin || state.isTenantAdmin,
    canManageSettings: (state) => state.isGlobalAdmin || state.isTenantAdmin,

    /** Map des disponibilités fonctionnelles (dégradation sûre si non chargé). */
    featureMap: (state) =>
      state.features ?? {
        channels: {},
        config_state: {},
        workspace_tabs: {},
        settings_sections: {},
        integrations: {},
      },

    /**
     * Capacité de suppression (RBAC).
     * ADMIN et MANAGER : lecture/écriture/suppression.
     * PERMANENCIER : pas de droit de suppression.
     */
    canDelete: (state) =>
      state.user?.role === "ADMIN" || state.user?.role === "MANAGER",

    /**
     * Vérifie si le rôle courant fait partie de la liste autorisée.
     * `roles` falsy (null/undefined) ⇒ accès à tous.
     * @returns {(roles?: string[]) => boolean}
     */
    hasAnyRole: (state) => (roles) =>
      !roles || roles.length === 0 || roles.includes(state.user?.role),

    /** Route d'accueil selon le rôle : permanencier → workspace, autres → dashboard. */
    homeRoute: (state) => {
      if (!state.user) return "/login";
      return state.user.role === "PERMANENCIER" ? "/workspace" : "/dashboard";
    },
  },

  actions: {
    /**
     * Authentifie l'utilisateur.
     * Si un seul tenant est assigne, le tenant actif est defini automatiquement.
     * Si plusieurs tenants, l'appelant doit gerer la selection (tache 2.5).
     *
     * @returns {{ success: boolean, returnUrl?: string, error?: string }}
     */
    async login(username, password) {
      try {
        const response = await authService.login(username, password);
        const {
          user,
          access_token,
          refresh_token,
          tenants,
          active_tenant_id,
          is_global_admin,
          is_tenant_admin,
        } = response.data;
        this.user = user;
        this.accessToken = access_token;
        this.refreshToken = refresh_token;
        this.tenants = tenants ?? [];
        this.activeTenantId = active_tenant_id ?? null;
        this.isGlobalAdmin = !!is_global_admin;
        this.isTenantAdmin = !!is_tenant_admin;
        this.features = response.data.features ?? null;

        const destination = this.returnUrl || this.homeRoute;
        this.returnUrl = null; // Consommer l'URL memorisee

        return { success: true, returnUrl: destination };
      } catch (error) {
        this.$reset();
        return {
          success: false,
          error: error.response?.data?.error || "Erreur de connexion.",
        };
      }
    },

    /**
     * Deconnexion complete : revoque les tokens cote API puis vide l'etat.
     * L'echec de l'appel API n'empeche pas le reset local.
     */
    async logout() {
      // IMPORTANT : attendre la fin de l'appel API AVANT de réinitialiser le
      // store. Sinon $reset() efface l'access token avant que l'intercepteur
      // ne l'attache à la requête → 401 → la session n'est jamais révoquée.
      try {
        await authService.logout();
      } catch (err) {
        console.error(
          "[AuthStore] Appel logout API echoue, nettoyage local quand meme.",
          err,
        );
      } finally {
        this.$reset();
      }
    },

    /**
     * Deconnexion silencieuse - utilisee par l'intercepteur HTTP quand
     * le refresh token est expire ou revoque.
     * N'appelle pas l'API (le token est deja invalide cote serveur).
     */
    logoutSilent() {
      this.$reset();
    },

    /**
     * Met a jour l'access token apres un renouvellement reussi.
     * Appele exclusivement par l'intercepteur HTTP (interceptor.js).
     *
     * @param {string} token - Nouvel access token JWT
     */
    setAccessToken(token) {
      this.accessToken = token;
    },

    /**
     * Selectionne le tenant actif (flow multi-tenant - tache 2.5).
     * Appelle /api/auth/select-tenant et met a jour les tokens.
     *
     * @param {string} tenantId - UUID du tenant a activer
     * @returns {{ success: boolean, error?: string }}
     */
    async selectTenant(tenantId) {
      try {
        const response = await authService.selectTenant(tenantId);
        const { access_token, refresh_token, active_tenant_id, is_tenant_admin } =
          response.data;

        this.accessToken = access_token;
        this.refreshToken = refresh_token;
        this.activeTenantId = active_tenant_id;
        this.isTenantAdmin = !!is_tenant_admin;
        this.features = response.data.features ?? null;

        return { success: true };
      } catch (error) {
        return {
          success: false,
          error:
            error.response?.data?.error || "Echec de la selection du tenant.",
        };
      }
    },

    /**
     * Rafraichit la liste des tenants accessibles depuis l'API
     * (utile pour le super-admin et le selecteur de l'app-bar).
     */
    async fetchTenants() {
      try {
        const { data } = await authService.getTenants();
        this.tenants = data.tenants ?? [];
        this.isGlobalAdmin = !!data.is_global_admin;
        return { success: true };
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.error || "Echec du chargement des tenants.",
        };
      }
    },

    /** Recharge les disponibilités fonctionnelles du tenant actif. */
    async fetchFeatures() {
      try {
        const { data } = await authService.getFeatures();
        this.features = data;
        return { success: true };
      } catch {
        return { success: false };
      }
    },

    /**
     * Change le tenant actif en cours de session puis recharge l'application
     * pour repartir d'un etat propre (aucune donnee de l'ancien tenant residuelle).
     *
     * @param {string} tenantId - UUID du tenant cible
     * @param {string} [redirectTo] - route de destination apres rechargement
     */
    async switchTenant(tenantId, redirectTo) {
      if (tenantId === this.activeTenantId) return { success: true };
      const res = await this.selectTenant(tenantId);
      if (!res.success) return res;
      // Rechargement complet : garantit le reset de tous les stores/caches
      // (les vues refetchent au montage avec le nouveau contexte tenant).
      const target = redirectTo || this.homeRoute;
      window.location.assign(target);
      return { success: true };
    },
  },

  // returnUrl est volontairement exclu : ne doit pas survivre a un rechargement.
  persist: {
    paths: [
      "user",
      "accessToken",
      "refreshToken",
      "tenants",
      "activeTenantId",
      "isGlobalAdmin",
      "isTenantAdmin",
      "features",
    ],
  },
});
