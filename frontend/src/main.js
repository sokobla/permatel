import { createApp } from "vue";
import { createPinia } from "pinia";
import piniaPluginPersistedstate from "pinia-plugin-persistedstate";
import App from "./App.vue";
import router from "./router";
import vuetify from "./plugins/vuetify";
import { loadFonts } from "./plugins/webfontloader";
import { setupInterceptors } from "@/services/http/interceptor";

// Titre de l'onglet = nom réel de l'application (configurable via VITE_APP_NAME)
document.title = import.meta.env.VITE_APP_NAME || "PERMATEL";

loadFonts();

const app = createApp(App);

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);

app.use(pinia);
app.use(router);
app.use(vuetify);

setupInterceptors(); // Doit être appelé après l'installation de Pinia

app.mount("#app");
