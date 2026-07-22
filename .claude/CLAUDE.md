# Maintain Media — Project Guide for Claude

This repository is the **Maintain Media brand-asset library**. It stores the company's
logos, backgrounds, and brand references — it is not application code.

## Design system — the primary reference

The canonical brand reference is **`design-system/index.html`** — it renders every asset and
links to the files in `media/`. The written specs are **`DESIGN.md`** (visual system) and
**`PRODUCT.md`** (brand strategy). When building or reviewing **any** Maintain Media visual,
treat the design system as the source of truth for colours, type, logos, and iconography.
Regenerate it with `python design-system/generate.py` after assets change.

## What lives here

```
media/
├── logos/          Logo files (vector preferred)
├── backgrounds/    Background textures / hero images
├── brand/          Brand references (color kits, guideline screenshots)
└── README.md       Human-readable asset index
```

## Naming convention

`maintain-media-<role>[-variant].<ext>`

- lowercase, hyphen-separated, **no spaces**, no `(1)` / "Untitled" / "screencapture" noise
- `<role>`: `logo`, `gradient-bg`, `brandkit-colors`, …
- `<variant>`: e.g. `darkbg` (white text, for dark backgrounds), `lightbg` (dark text,
  for light backgrounds), `canva` (heavy raster export / fallback)

Examples: `maintain-media-logo-darkbg.svg`, `maintain-media-gradient-bg.png`.

## Brand colors

| Color  | Hex       | Use                        |
|--------|-----------|----------------------------|
| Purple | `#a04dff` | Primary / logo mark        |
| Dark   | `#08282d` | Text on light backgrounds  |
| White  | `#ffffff` | Text on dark backgrounds   |

## Rules

- **Prefer vector (`.svg`) over raster.** The clean ~4 KB logo vectors are canonical; the
  `-canva` raster-in-SVG exports are redundant fallbacks.
- **Never rename** `maintain-media-logo-darkbg.svg` / `maintain-media-logo-lightbg.svg` —
  outside references may depend on them.
- **Never delete** an asset without asking — files here are not reproducible from code.
- After adding or moving assets, **update `media/README.md`**.

## Toolbox (`.claude/`)

- **Skill** `asset-intake` — classify, rename, and file a new asset.
- **Commands** `/new-asset <path>`, `/asset-audit`.
- **Agent** `brand-asset-reviewer` — audits naming, placement, duplicates, and README drift.
- **Hook** `hooks/session_context.py` (SessionStart) — injects these conventions and flags
  any stray filenames at the start of each session.
