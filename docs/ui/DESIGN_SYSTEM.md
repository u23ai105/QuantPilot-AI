# Design System: Quiet Institutional

## 1. Core Philosophy
"Quiet Institutional" is a design language tailored for modern quantitative research. It relies on typography, precise spacing, and restrained colors to build trust and surface high-density information clearly. 

**Anti-Patterns (Do NOT use):**
- Neon gradients or glowing effects.
- Excessive cards or visually noisy dashboards.
- Glassmorphism.
- Giant shadows (use flat surfaces with restrained borders).
- Decorative AI graphics or "neon purple/blue AI styling".
- Excessive rounded containers (stick to subtle `md` radii).

## 2. Color Palette (Semantic)
The palette is muted and intentional. We avoid pure blacks and pure whites in dark mode to reduce eye strain.

**Dark Mode (Primary Theme):**
- **Background:** `#0a0a0a` (Deep Charcoal)
- **Surface (Cards/Panels):** `#141414`
- **Surface Hover/Active:** `#1f1f1f`
- **Border:** `#27272a` (Subtle separator)
- **Text Primary:** `#f4f4f5` (High contrast, slightly softened white)
- **Text Secondary:** `#a1a1aa` (Muted gray for metadata)

**Financial Semantics:**
- **Positive (Profit, Growth):** `#10b981` (Emerald, slightly desaturated)
- **Negative (Loss, Drawdown):** `#ef4444` (Rose/Red, slightly desaturated)
- **Neutral (Info, Processing):** `#3b82f6` (Muted Blue)

**AI Semantics:**
- **AI Accent:** `#8b5cf6` (Subtle purple/violet, used extremely sparingly for AI agent identity or tool calls, avoiding glowing shadows).

## 3. Typography
**Primary Font:** Inter (or similar highly legible geometric sans-serif).
**Monospace Font:** JetBrains Mono (or Roboto Mono).

**Scale:**
- **H1 (Page Title):** 24px, Semi-bold, tracking-tight.
- **H2 (Section Header):** 18px, Medium.
- **H3 (Card Header):** 14px, Medium, uppercase tracking-wide (optional).
- **Body:** 14px, Regular (Standard reading size).
- **Small/Metadata:** 12px, Regular, Text Secondary.
- **Monospace Values:** 13px, Medium (For financial numbers, tickers).

## 4. Spacing & Grid
- **Base Unit:** 4px (Tailwind standard).
- **Padding/Margins:** Favor generous padding in open areas (p-6 or p-8) and tight clustering for related financial data (gap-1 or gap-2).
- **Layout Max-Width:** Fluid up to large 4K screens. No boxed max-width unless it's a specific reading pane (like the AI chat).

## 5. UI Elements
- **Borders & Radii:** 
  - Standard Radius: `0.375rem` (rounded-md). Avoid excessively pill-shaped buttons.
  - Borders: 1px solid, `#27272a`.
- **Shadows:** Minimal. Shadows are only used to elevate floating elements (modals, dropdowns). Cards sit flat with a border.
- **Buttons:**
  - *Primary:* Solid surface color slightly lighter than background, bordered, with white text. (No bright blue primary buttons).
  - *Ghost:* Transparent background, changes to subtle gray on hover.
- **Inputs:**
  - Flat background (`#141414`), subtle border. Focus states use a clean, thin white or AI Accent ring.
- **Tables:**
  - Borderless rows. 
  - Monospace numeric columns right-aligned. 
  - Text columns left-aligned.
  - Hover states on rows are subtle (`bg-white/5`).
- **Badges / Status Indicators:**
  - Small (text-xs), rounded-sm, 1px border. 
  - Colors are muted (e.g., bg-green-500/10 text-green-400 border-green-500/20).

## 6. Motion & Transitions
- **Speed:** Fast (`150ms` or `200ms`).
- **Timing Function:** Ease-in-out.
- **Usage:** Hover states, modal fade-ins. No bouncy or spring animations. The interface must feel immediate.
