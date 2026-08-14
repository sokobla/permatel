/**
 * countryFlag — code pays ISO 3166-1 alpha-2 -> emoji drapeau (14/08).
 * Symboles Unicode "regional indicator" : aucune dépendance/asset image.
 * Purement décoratif — jamais utilisé côté export (cf. backend, country_code
 * volontairement absent des CSV).
 */
export function countryFlag(code) {
  if (!code || code.length !== 2) return "";
  const upper = code.toUpperCase();
  const base = 0x1f1e6; // 🇦
  const chars = [...upper].map((c) => base + (c.charCodeAt(0) - 65));
  if (chars.some((c) => c < base || c > base + 25)) return "";
  return String.fromCodePoint(...chars);
}
