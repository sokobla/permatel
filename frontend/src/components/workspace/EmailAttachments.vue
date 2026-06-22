<template>
  <div class="ea-root">
    <div class="ea-bar">
      <button type="button" class="ea-add" @click="picker?.click()">
        <v-icon size="15">mdi-paperclip</v-icon>
        Joindre un fichier
      </button>
      <span v-if="modelValue.length" class="ea-count">{{ modelValue.length }} fichier(s)</span>
      <input
        ref="picker" type="file" multiple class="ea-hidden"
        :accept="ACCEPT" @change="onPick"
      />
    </div>

    <p v-if="error" class="ea-error">{{ error }}</p>

    <ul v-if="modelValue.length" class="ea-list">
      <li v-for="(f, i) in modelValue" :key="i" class="ea-item">
        <v-icon size="16" :color="iconColor(f)">{{ iconFor(f) }}</v-icon>
        <span class="ea-item__name">{{ f.name }}</span>
        <span class="ea-item__meta">{{ humanSize(f.size) }}</span>
        <button type="button" class="ea-remove" title="Retirer" @click="remove(i)">
          <v-icon size="14">mdi-close</v-icon>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
  modelValue: { type: Array, default: () => [] }, // File[]
  maxSizeMb: { type: Number, default: 10 },
});
const emit = defineEmits(["update:modelValue"]);

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,.gif,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip";
const ALLOWED = new Set(ACCEPT.split(","));

const picker = ref(null);
const error = ref("");

function ext(name) {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}
function onPick(e) {
  error.value = "";
  const incoming = Array.from(e.target.files || []);
  const current = [...props.modelValue];
  for (const f of incoming) {
    if (!ALLOWED.has(ext(f.name))) { error.value = `Type non autorisé : ${f.name}`; continue; }
    if (f.size > props.maxSizeMb * 1024 * 1024) { error.value = `Trop volumineux (max ${props.maxSizeMb} Mo) : ${f.name}`; continue; }
    if (current.some((c) => c.name === f.name && c.size === f.size)) continue; // doublon
    current.push(f);
  }
  emit("update:modelValue", current);
  if (picker.value) picker.value.value = "";
}
function remove(i) {
  const next = [...props.modelValue];
  next.splice(i, 1);
  emit("update:modelValue", next);
}
function humanSize(b) {
  if (b < 1024) return `${b} o`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} Ko`;
  return `${(b / 1024 / 1024).toFixed(1)} Mo`;
}
function iconFor(f) {
  const e = ext(f.name);
  if (e === ".pdf") return "mdi-file-pdf-box";
  if ([".png", ".jpg", ".jpeg", ".webp", ".gif"].includes(e)) return "mdi-file-image-outline";
  if ([".xls", ".xlsx", ".csv"].includes(e)) return "mdi-file-excel-outline";
  if ([".doc", ".docx"].includes(e)) return "mdi-file-word-outline";
  if (e === ".zip") return "mdi-folder-zip-outline";
  return "mdi-file-outline";
}
function iconColor(f) {
  const e = ext(f.name);
  if (e === ".pdf") return "#e74c3c";
  if ([".xls", ".xlsx", ".csv"].includes(e)) return "#16a085";
  if ([".doc", ".docx"].includes(e)) return "#2980b9";
  return "#6b7280";
}
</script>

<style scoped>
.ea-root { font-family: "Fira Sans", sans-serif; }
.ea-bar { display: flex; align-items: center; gap: 10px; }
.ea-add {
  display: inline-flex; align-items: center; gap: 6px;
  height: 30px; padding: 0 12px; border: 1px dashed #c4c9d0; border-radius: 6px;
  background: #fff; font-size: 12px; font-weight: 600; color: #15223a; cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.ea-add:hover { border-color: #00a8a8; color: #00a8a8; }
.ea-count { font-size: 11px; color: #6b7280; }
.ea-hidden { display: none; }
.ea-error { font-size: 12px; color: #e74c3c; margin: 6px 0 0; }
.ea-list { list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.ea-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border: 1px solid #e5e7eb; border-radius: 6px; background: #fafbfc;
}
.ea-item__name { flex: 1; min-width: 0; font-size: 12.5px; color: #15223a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ea-item__meta { font-size: 11px; color: #9aa0aa; font-family: "Fira Code", monospace; }
.ea-remove { border: none; background: none; cursor: pointer; color: #9aa0aa; display: flex; }
.ea-remove:hover { color: #e74c3c; }
</style>
