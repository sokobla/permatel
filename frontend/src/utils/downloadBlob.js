/**
 * downloadBlob — déclenche le téléchargement d'un Blob côté navigateur.
 * Extrait du motif éprouvé dans ReportCdr.vue (export CSV/ZIP Téléphonie).
 */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Parse le message d'erreur d'une réponse Axios en `responseType: "blob"`. */
export async function blobErrorMessage(err, fallback) {
  const blob = err?.response?.data;
  if (blob instanceof Blob) {
    try {
      const text = await blob.text();
      const parsed = JSON.parse(text);
      if (parsed?.error) return parsed.error;
    } catch {
      /* corps non-JSON, on garde le message par défaut */
    }
  }
  return err?.response?.data?.error || fallback;
}

/** Génère et télécharge un CSV depuis un tableau déjà en mémoire (pas de round-trip backend). */
export function arrayToCsv(header, rows, filename) {
  const escape = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [header, ...rows].map((row) => row.map(escape).join(","));
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  downloadBlob(blob, filename);
}
