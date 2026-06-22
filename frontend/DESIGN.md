# Design System Document: Operational Precision & Editorial Authority

## 1. Overview & Creative North Star
### The Creative North Star: "The Digital Architect"
This design system moves away from the generic "SaaS dashboard" aesthetic. Instead, it adopts the persona of **"The Digital Architect"**—a style that balances the raw, technical precision of monospace data with the sophisticated authority of high-end editorial layouts. 

While the user requirements specify an operational, border-focused dashboard, we achieve "high-end" status by treating borders not as dividers, but as architectural lines. We prioritize **intentional asymmetry** and **tonal depth** to ensure that data-dense screens feel organized and intentional rather than cluttered.

---

## 2. Colors: Tonal Logic & The "No-Line" Rule
The color palette uses a high-contrast foundation of deep navy and crisp off-whites, punctuated by technical teal and urgent red.

### Surface Hierarchy & Nesting
To prevent the UI from looking like a flat spreadsheet, we utilize **Tonal Layering**.
- **Surface (Base):** `#F2F2F2` (Background). Use this for the furthest back layer.
- **Surface-Container-Lowest:** `#FFFFFF`. Use this for the primary content cards.
- **Surface-Container-High:** `#EEEEEE`. Use this for nested technical regions within cards (e.g., a "Properties" panel inside a data view).

### The "No-Line" Rule & Signature Textures
- **Prohibit 1px solid borders for sectioning:** Avoid using lines to separate large layout blocks. Instead, use a background shift from `Surface` to `Surface-Container-Low`.
- **The "Ghost Border" Fallback:** Where containment is critical for operational clarity, use the `outline_variant` (#C5C6CE) at 15% opacity. It should feel like a suggestion of a boundary, not a hard cage.
- **Signature Gradients:** For primary CTAs and the Sidebar, use a subtle 45-degree gradient from `Primary` (#000B23) to `Primary_Container` (#15223A). This adds a "lithic" depth that solid hex codes lack.

---

## 3. Typography: Technical Editorial
We juxtapose the human-centric **Fira Sans** with the machine-precise **Fira Code** to create a "Technical Editorial" feel.

| Role | Token | Font Family | Size | Intent |
| :--- | :--- | :--- | :--- | :--- |
| **Display** | `display-lg` | Fira Code | 3.5rem | High-impact data metrics. |
| **Headline** | `headline-md` | Fira Code | 1.75rem | Major section headers. |
| **Title** | `title-sm` | Fira Sans | 1.0rem | Card titles, Semi-bold (600). |
| **Body** | `body-md` | Fira Sans | 0.875rem | Standard operational data. |
| **Label** | `label-sm` | Fira Code | 0.6875rem | Monospace metadata, IDs, timestamps. |

**Editorial Note:** Always use Fira Code for numeric data. The tabular spacing of a monospace font ensures that columns of numbers align perfectly, reinforcing the "Operational" brand pillar.

---

## 4. Elevation & Depth: Tonal Layering
In this system, depth is a product of color contrast, not drop shadows.

- **The Layering Principle:** A `Surface-Container-Lowest` (#FFFFFF) card sitting on a `Surface` (#F2F2F2) background provides sufficient natural "lift."
- **Ambient Shadows:** Shadows are strictly reserved for temporary floating elements (Modals, Tooltips). Use `on_surface` color at 4% opacity with a 20px blur. It should be felt, not seen.
- **Glassmorphism:** For top navigation bars or floating action panels, use `Surface` (#FFFFFF) at 85% opacity with a `12px backdrop-blur`. This allows the "data" underneath to subtly bleed through, maintaining the operational context.

---

## 5. Components: Operational Sophistication

### Buttons: High-Contrast Actions
*   **Primary:** Background `Primary` (#15223A), Text `On_Primary` (#FFFFFF). 8px radius.
*   **Accent/CTA:** Background `Tertiary_Container` (#E74C3C), Text `White`. Use sparingly for "destructive" or "critical path" actions.
*   **Tactile Feedback:** On hover, shift the background color to the next-darker tier; do not use shadows.

### Inputs: The Technical Frame
*   **Structure:** Outlined, 8px radius, compact density.
*   **Focus State:** A 2px solid stroke of `Tertiary_Fixed_Variant` (#910807). This "Red Focus" is our signature—it signals high-priority attention to the active field.
*   **Typography:** Use Fira Code for input text to emphasize data entry precision.

### Sidebar: The Anchor
*   **Base:** `Primary_Container` (#15223A).
*   **Active Item:** This is a high-contrast "cut-out." The active item should be `Surface-Container-Lowest` (#FFFFFF) with text in `On_Tertiary_Container` (#E74C3C). This "White on Dark" inversion provides an unmistakable visual anchor for navigation.

### Cards & Data Tables
*   **Forbid Dividers:** Do not use horizontal lines between rows. Use a subtle alternating background color (`Surface` vs `Surface-Container-Low`) or 12px of vertical white space.
*   **Header:** Card headers should use a 4px left-border accent of `Secondary` (#00A8A8) to categorize information types.

---

## 6. Do’s and Don’ts

### Do
*   **DO** use monospace (Fira Code) for all numerical values, IDs, and status codes.
*   **DO** use white space as your primary divider. If you think you need a line, try adding 8px of padding first.
*   **DO** nest containers to show relationship. A teal `Secondary` chip inside a white card communicates "active status" within a "data object."

### Don’t
*   **DON’T** use standard grey shadows. They muddy the "Architectural" cleanliness of the operational dashboard.
*   **DON’T** use 100% opaque borders for decorative purposes. Borders must serve a containment function or be "Ghost" style.
*   **DON’T** use Fira Sans for data points. Sans-serif is for reading; Monospace is for analyzing.