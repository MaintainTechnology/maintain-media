# Design

Visual system for **Maintain Media**. The canonical, human-readable spec; the living
reference that renders every asset is [`design-system/index.html`](design-system/index.html).
Source files live in [`media/`](media/). Hex values are the source of truth; OKLCH is
provided for wide-gamut work.

## North Star

Deep near-black teal canvas, vivid purple as the single carrying accent, crisp white type,
and the ascending "M" mountain mark. Tech-forward and precise. The brand lives most
naturally on dark surfaces (see the gradient backgrounds and wireframe graphics), with a
light-background variant provided for documents and print.

## Color

### Core brand (source of truth — do not alter)

| Token | Hex | OKLCH (approx) | RGB | Role |
|-------|-----|----------------|-----|------|
| `--brand-purple` | `#a04dff` | `oklch(0.59 0.25 295)` | `160 77 255` | Primary. Logo mark, accents, links, focus, key CTAs. |
| `--brand-dark` | `#08282d` | `oklch(0.26 0.03 210)` | `8 40 45` | Dark surfaces, text on light, deep backgrounds. |
| `--brand-white` | `#ffffff` | `oklch(1 0 0)` | `255 255 255` | Text on dark, negative space, light surfaces. |

### Extended (derived for UI — not brand colours, use for building interfaces)

Purple ramp (tints/shades of `#a04dff`) and a dark/ink ramp built from `#08282d` toward
near-black. Used by the design-system page itself.

| Token | Hex | Use |
|-------|-----|-----|
| `--purple-300` | `#c79bff` | Hover, lighter accents on dark |
| `--purple-400` | `#b374ff` | Secondary accent |
| `--purple-500` | `#a04dff` | Brand purple |
| `--purple-600` | `#8a34f0` | Pressed / deeper accent |
| `--bg` | `#061518` | Page canvas (near-black, brand-tinted) |
| `--surface` | `#0c2a30` | Cards / panels (brand dark, lifted) |
| `--surface-2` | `#123a42` | Raised panels, hover |
| `--border` | `rgba(255,255,255,.10)` | Hairline dividers on dark |
| `--ink` | `#ffffff` | Headings on dark |
| `--ink-2` | `#cdd9db` | Body on dark (≥ 4.5:1) |
| `--muted` | `#93a7aa` | Labels / captions on dark (large only) |

### Gradient

Signature brand gradient: **purple → deep teal/black**, radial or vertical.
`linear-gradient(180deg, #a04dff 0%, #3a1f6b 45%, #08282d 100%)`. Source raster:
[`media/backgrounds/maintain-media-gradient-bg.png`](media/backgrounds/maintain-media-gradient-bg.png).

## Typography

The brand type library ships three families (in `media/complete-toolkit/.../Typography/`).
Pair on weight, not by mixing the two geometric sans families in body copy.

| Family | Role | Files |
|--------|------|-------|
| **Albert Sans** | Primary — UI, body, most headings. Variable + static 100–900. | `Albert Sans/` |
| **Vela Sans** | Display — large expressive headlines, brand moments. | `Vela Sans/` (Light–ExtraBold) |
| **Aptos** | Documents — Word / PowerPoint / email templates (Office default). | `Microsoft Aptos Fonts/` |

- **Scale:** modular, ≥ 1.25 ratio, fluid `clamp()` for headings. Display ceiling ~ 6rem.
- **Measure:** body 65–75ch.
- **Weights in use:** 800 (display), 700 (h1–h3), 600 (h4 / labels), 500 (emphasis), 400 (body).
- Light type on dark: add 0.05–0.1 line-height.

## Spacing & Layout

- 4px base; steps 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96.
- Section rhythm via `clamp()`; generous separation between sections, tight within groups.
- Responsive grids: `repeat(auto-fit, minmax(min, 1fr))` — no per-breakpoint columns.
- Content max-width ~1200px; icon/asset sheets go wider.

## Radii & Elevation

- Radii: `--r-sm 8px`, `--r-md 14px`, `--r-lg 20px`, `--r-pill 999px`.
- Elevation on dark = lighter surface + hairline border + soft purple-tinted glow for
  interactive/hero elements; avoid heavy drop shadows on dark.

## Motion

- Ease-out (quart/expo). Durations 150–450ms. Staggered reveals per list, not a uniform
  fade on every section. Full `prefers-reduced-motion: reduce` fallback (crossfade/instant).

## Iconography

Two coherent sets, both linked in the living reference:

- **Line icons** (66) — stroke, dark `#08282d`. `media/complete-toolkit/01 Visual Identity/Iconography/`.
- **Colored / filled icons** (16 SVG + duplicates, +12 Canva) — purple `#a04dff`.
  `media/complete-toolkit/01 Visual Identity/icons-colored/` and `04 Canva Assets/Icons/`.

Rule: pick one set per surface; don't mix line and filled in the same context. Line icons on
light surfaces; purple filled icons work on light or dark.

## Logo

Horizontal wordmark = ascending "M" mountain mark + "Maintain Media". Four files in
[`media/logos/`](media/logos/):

| File | Text | Use on |
|------|------|--------|
| `maintain-media-logo-darkbg.svg` | white | dark backgrounds (canonical vector) |
| `maintain-media-logo-lightbg.svg` | dark | light backgrounds (canonical vector) |
| `…-darkbg-canva.svg` / `…-lightbg-canva.svg` | — | heavy raster fallbacks; prefer the vectors |

Clearspace ≥ the height of the "M" mark on all sides. Never recolour the mark off-brand,
stretch, rotate, or place the dark-text logo on a dark background.

## Imagery & Graphics

Gradients (purple→black), the "mountain forms" wireframe landscape, and background textures
live in `media/complete-toolkit/01 Visual Identity/graphics/` and `04 Canva Assets/`. Favor
the brand gradient and wireframe as hero atmosphere; keep photography brand-neutral.

## Accessibility

WCAG 2.1 AA. Verified contrast on every text/background pair. Focus-visible rings in brand
purple. Reduced-motion path for all animation. Swatches and icons always labelled.
