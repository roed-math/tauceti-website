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
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (file, nav label). Order is the nav order. A directory (trailing slash) is one of the two apps
# built separately into the site, the Atlas and Tau Ceti Review, which have no page in src/pages.
PAGES = [
    ("index.html", "Home"),
    ("contents.html", "What’s inside"),
    ("atlas/", "Atlas"),
    ("review/", "Review"),
    ("contribute.html", "Contribute"),
    ("growth.html", "Growth"),
    ("structure.html", "Roadmaps"),
    ("people.html", "People"),
    ("acknowledgments.html", "Acknowledgments"),
    ("health.html", "Health"),
]

# Tau Ceti Review's data is built and published by the review data repository. Until that repository's
# Pages are up, the review's existing site serves the same data/.
REVIEW_DATA = "https://cbirkbeck.github.io/tauceti-reviewed-by-test/data/"

HEADER = re.compile(r"\A\s*<!--\s*(\{.*?\})\s*-->\s*", re.S)


def review_app(out: Path, data_url: str) -> None:
    """The review app from review/web/, reading its data/ from data_url (review/web/data.js)."""
    shutil.copytree(ROOT / "review" / "web", out)
    index = out / "index.html"
    page = index.read_text()
    meta = f'<meta name="tau-review-data" content="{html.escape(data_url.rstrip("/") + "/")}">'
    assert "<head>" in page, "review/web/index.html has no <head>"
    index.write_text(page.replace("<head>", "<head>\n  " + meta, 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "_site")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--atlas", type=Path, help="the Atlas as scripts/build_atlas.sh built it, copied to atlas/")
    ap.add_argument("--review-data", default=os.environ.get("REVIEW_DATA_URL") or REVIEW_DATA,
                    help="where Tau Ceti Review's built data/ is published (default $REVIEW_DATA_URL, else %(default)s)")
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
    if args.atlas:
        shutil.copytree(args.atlas, args.out / "atlas")
    review_app(args.out / "review", args.review_data)

    for file, _ in PAGES:
        if file.endswith("/"):
            continue
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
    print(f"built {sum(not f.endswith('/') for f, _ in PAGES)} pages into {args.out}")


if __name__ == "__main__":
    main()
