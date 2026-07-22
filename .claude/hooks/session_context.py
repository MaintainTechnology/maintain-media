#!/usr/bin/env python3
"""SessionStart hook for the Maintain Media asset library.

Injects the naming convention + brand colors as context and flags any media files
that don't follow the convention. Runs from the project root (cwd). Always exits 0
so it can never block a session; requires only the Python standard library.

Wired in .claude/settings.json under hooks.SessionStart.
"""
import json
import re
import sys
from pathlib import Path

MEDIA_EXTS = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"}
CONVENTION = re.compile(r"^maintain-media-[a-z0-9-]+\.[a-z0-9]+$")


def main() -> None:
    root = Path(__file__).resolve().parents[2]  # .claude/hooks/ -> repo root
    media = root / "media"

    assets, strays = [], []
    if media.is_dir():
        for p in sorted(media.rglob("*")):
            if p.is_file() and p.suffix.lower() in MEDIA_EXTS:
                rel = p.relative_to(media).as_posix()
                assets.append(rel)
                if not CONVENTION.match(p.name):
                    strays.append(rel)

    ctx = [
        "Maintain Media brand-asset repo. Naming: maintain-media-<role>[-variant].<ext> "
        "(lowercase, hyphen-separated, no spaces, no '(1)'/Untitled/screencapture noise).",
        "Brand colors: purple #a04dff, dark #08282d, white #ffffff.",
        "Folders: media/logos, media/backgrounds, media/brand. Prefer vector (.svg) over "
        "raster; never rename or delete the canonical logo files without asking.",
    ]
    if assets:
        ctx.append(f"Current assets ({len(assets)}): " + ", ".join(assets))
    if strays:
        ctx.append("Filenames NOT matching the convention (fix via /asset-audit): "
                   + ", ".join(strays))

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(ctx),
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never block a session on a hook error
    sys.exit(0)
