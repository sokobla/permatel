/**
 * Sanitisation HTML des emails (anti-XSS) via DOMPurify.
 * Autorise une mise en forme courante d'email, neutralise scripts/handlers,
 * force les liens à s'ouvrir en nouvel onglet de façon sûre.
 */
import DOMPurify from "dompurify";

// Liens : target=_blank + rel sécurisé
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer nofollow");
  }
});

export function sanitizeEmailHtml(html) {
  if (!html) return "";
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "a", "b", "strong", "i", "em", "u", "s", "p", "br", "hr", "span", "div",
      "ul", "ol", "li", "blockquote", "pre", "code",
      "h1", "h2", "h3", "h4", "h5", "h6",
      "table", "thead", "tbody", "tr", "td", "th", "img",
    ],
    ALLOWED_ATTR: ["href", "title", "alt", "src", "width", "height", "style", "align"],
    // Bloque les images distantes par défaut ? On les autorise mais sans data exfil via CSS dangereux
    FORBID_TAGS: ["script", "style", "iframe", "object", "embed", "form", "input"],
    FORBID_ATTR: ["onerror", "onload", "onclick"],
    ALLOW_DATA_ATTR: false,
  });
}
