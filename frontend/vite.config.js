import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vuetify from "vite-plugin-vuetify";
import { resolve } from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // https://github.com/vuetifyjs/vuetify-loader/tree/next/packages/vite-plugin
    vuetify({
      autoImport: true,
    }),
  ],
  resolve: {
    alias: {
      // Set up the '@' alias to point to the 'src' directory
      "@": resolve(__dirname, "./src"),
    },
  },
});
