#!/usr/bin/env python3
"""Give the built Atlas a link back to the site at the start of its own header: it is a full-screen map
with no room for the site's bar. Run by scripts/build_atlas.sh on its output; safe to run twice.

Usage: python3 scripts/atlas_back.py ATLAS_DIR
"""
from __future__ import annotations

import sys
from pathlib import Path

ATLAS_HEADER = '<header class="app-header"><a class="brand"'
ATLAS_BACK_STYLE = ("<style>.site-back{font-size:13px;color:var(--muted,#8b939b);text-decoration:none;white-space:nowrap;"
                    "padding-right:10px;margin-right:10px;border-right:1px solid var(--line,#2a3440)}"
                    ".site-back:hover{color:var(--ink,#e7ebef)}</style>")


def atlas_back(atlas: Path) -> None:
    """A link back to the site at the start of the Atlas's own header: it is a full-screen map with no room
    for the site's bar."""
    for page, home in ((atlas / "index.html", "../"), (atlas / "tauceti" / "index.html", "../../")):
        if not page.exists():
            continue
        text = page.read_text(encoding="utf-8")
        if 'class="site-back"' in text:
            continue
        if ATLAS_HEADER not in text:
            print(f"warning: no Atlas header in {page}; left without a link back")
            continue
        text = text.replace(ATLAS_HEADER, f'<header class="app-header"><a class="site-back" href="{home}">← Tau Ceti</a><a class="brand"', 1)
        page.write_text(text.replace("</head>", ATLAS_BACK_STYLE + "</head>", 1), encoding="utf-8")


if __name__ == "__main__":
    atlas_back(Path(sys.argv[1]))
