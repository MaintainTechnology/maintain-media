---
description: Audit all media assets for naming, placement, and README consistency
---

Audit the `media/` folder and report issues (do not fix without confirmation):

1. **Naming** — every media file matches `maintain-media-<role>[-variant].<ext>`
   (lowercase, hyphens, no spaces, no `(1)` / "Untitled" / "screencapture").
2. **Placement** — logos in `logos/`, textures/heroes in `backgrounds/`, references in
   `brand/`.
3. **Duplicates / bloat** — redundant raster copies of vector logos; oversized PNGs.
4. **README drift** — `media/README.md` lists every file, and nothing stale.

Output a table of `file | issue | fix`, then ask whether to apply the fixes.
