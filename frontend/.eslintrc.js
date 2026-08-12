module.exports = {
  root: true,
  env: {
    node: true,
  },
  extends: [
    "plugin:vue/vue3-essential",
    "eslint:recommended",
    "plugin:prettier/recommended",
  ],
  // Certains composants (ex. frontend/src/views/DashboardView.vue,
  // components/dashboard/*.vue) utilisent `<script setup lang="ts">` sans
  // qu'aucun parser TS ne soit jamais configuré ici — ESLint échouait
  // silencieusement à les analyser (erreurs de parsing), les rendant
  // invisibles au lint. `parserOptions.parser` délègue le contenu des
  // balises <script> au parser TypeScript ; `vue-eslint-parser` (déjà
  // présent en dépendance transitive d'eslint-plugin-vue) reste le parser
  // de premier niveau pour la structure des fichiers .vue eux-mêmes.
  parser: "vue-eslint-parser",
  parserOptions: {
    parser: "@typescript-eslint/parser",
    ecmaVersion: "latest",
    sourceType: "module",
  },
  rules: {
    "prettier/prettier": ["error", { endOfLine: "auto" }],
    "no-console": process.env.NODE_ENV === "production" ? "warn" : "off",
    "no-debugger": process.env.NODE_ENV === "production" ? "warn" : "off",
  },
};
