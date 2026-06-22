<template>
  <header class="header">
    <div class="header__brand">
      <router-link to="/dashboard">Permatel</router-link>
    </div>
    <div class="header__user-menu">
      <!-- Ces données viendront du store (Pinia/Vuex) -->
      <span>Bonjour, {{ user.prenom || "Utilisateur" }}</span>
      <button @click="logout">Déconnexion</button>
    </div>
  </header>
</template>

<script>
export default {
  name: "AppHeader",
  props: {
    user: {
      type: Object,
      default: () => ({ prenom: "Alice" }), // Données factices pour l'exemple
    },
  },
  methods: {
    logout() {
      console.log("Déconnexion en cours...");
      // Ici, il faudra appeler le service d'authentification
      // et rediriger vers la page de login.
      // this.$router.push('/login');
    },
  },
};
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background-color: #ffffff;
  border-bottom: 1px solid #dee2e6;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
}
.header__brand a {
  font-weight: bold;
  text-decoration: none;
  color: #333;
  font-size: 1.5rem;
}
.header__user-menu span {
  margin-right: 1rem;
}
</style>
