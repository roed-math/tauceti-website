#!/usr/bin/env python3
"""Assemble the static site into _site/: each src/pages/*.html inside src/layout.html,
plus static/ and the generated data/.

A page begins with a JSON comment giving its title, description and page scripts:

  <!-- {"title": "Growth", "description": "...", "scripts": ["growth.js"]} -->

Usage: python3 scripts/build_site.py [--out _site] [--data data]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (file, nav label). Order is the nav order.
PAGES = [
    ("index.html", "Home"),
    ("contents.html", "What’s inside"),
    ("contribute.html", "Contribute"),
    ("growth.html", "Growth"),
    ("structure.html", "Roadmaps"),
    ("people.html", "People"),
    ("acknowledgments.html", "Acknowledgments"),
    ("health.html", "Health"),
]

HEADER = re.compile(r"\A\s*<!--\s*(\{.*?\})\s*-->\s*", re.S)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "_site")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    args = ap.parse_args()

    layout = (ROOT / "src/layout.html").read_text()
    now = dt.datetime.now(dt.timezone.utc)
    version = now.strftime("%Y%m%d%H%M%S")
    built_at = now.strftime("%Y-%m-%d %H:%M UTC")

    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    shutil.copytree(ROOT / "static", args.out / "static")
    if args.data.exists():
        shutil.copytree(args.data, args.out / "data", ignore=shutil.ignore_patterns("cache"))
    (args.out / ".nojekyll").write_text("")

    for file, _ in PAGES:
        src = (ROOT / "src/pages" / file).read_text()
        m = HEADER.match(src)
        meta = json.loads(m.group(1)) if m else {}
        body = src[m.end():] if m else src
        nav = "\n".join(
            f'        <a href="{"./" if f == "index.html" else f}"'
            + (' aria-current="page"' if f == file else "")
            + f">{html.escape(label)}</a>"
            for f, label in PAGES)
        scripts = "\n".join(f'  <script src="static/js/{s}?v={version}" defer></script>'
                            for s in meta.get("scripts", []))
        title = meta.get("title", "Tau Ceti")
        page = (layout
                .replace("{{title}}", html.escape(title if title == "Tau Ceti" else f"{title} — Tau Ceti"))
                .replace("{{description}}", html.escape(meta.get("description", "")))
                .replace("{{scripts}}", scripts)
                .replace("{{nav}}", nav)
                .replace("{{page}}", file.removesuffix(".html"))
                .replace("{{version}}", version)
                .replace("{{built_at}}", built_at)
                .replace("{{content}}", body))
        (args.out / file).write_text(page)
    print(f"built {len(PAGES)} pages into {args.out}")


if __name__ == "__main__":
    main()
