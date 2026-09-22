#!/usr/bin/env python3
"""Check paper extractions against research/blueprint/PROTOCOL.md, section 16.

Usage:
  python3 scripts/check_paper.py research/blueprint/papers/PAPER-XYZ.result.json [...]

A paper extraction lists every definition, construction and key theorem a
paper uses or proves, says for each whether the libraries have it, a layer of
the atlas plans it, or it is missing, and routes what is missing: as a source
of an existing roadmap's layers, as a Part II of an existing roadmap, or as a
new roadmap. Errors make the exit status 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from source_issues import check_issues  # noqa: E402
KINDS = {"definition", "construction", "theorem"}
STATUSES = {"library", "planned", "missing"}
ROUTES = {"source", "part-ii", "new"}
BRIEF_WORDS = 60


def text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def check(data, name: str, roadmaps: dict, stages: dict) -> list:
    """Errors in an extraction. roadmaps: id -> {origin, title}; stages: layer id -> owning roadmap."""
    if not isinstance(data, dict):
        return ["the extraction is not a JSON object"]
    errors = []
    if data.get("paper") != name:
        errors.append(f"paper must be {name}")
    if data.get("protocol") != "paper-v1":
        errors.append("protocol must be paper-v1")
    if data.get("status") not in ("partial", "complete"):
        errors.append("status must be 'partial' or 'complete'")
    source = data.get("source") or {}
    if not text(source.get("title")) or not text(source.get("authors")) or not any(text(source.get(k)) for k in ("doi", "arxiv", "url")):
        errors.append("source needs its title, authors and a doi, arxiv id or url")
    if not text(data.get("summary")):
        errors.append("a summary of what the paper proves and needs")
    items = {}
    for item in data.get("items") or []:
        iid = item.get("id")
        if not text(iid) or not iid.startswith(name + "/"):
            errors.append(f"item id {iid!r} must start with {name}/")
            continue
        if iid in items:
            errors.append(f"{iid} appears twice")
        items[iid] = item
        if item.get("kind") not in KINDS:
            errors.append(f"{iid}: kind is one of {', '.join(sorted(KINDS))}")
        for field in ("name", "statement", "locator"):
            if not text(item.get(field)):
                errors.append(f"{iid}: needs its {field}")
        status = item.get("status")
        if status not in STATUSES:
            errors.append(f"{iid}: status is one of {', '.join(sorted(STATUSES))}")
        elif status == "library":
            refs = item.get("library") or []
            if not refs or not all(isinstance(r, str) and r.split(":")[0] in ("mathlib", "tauceti") for r in refs):
                errors.append(f"{iid}: a library item cites its declarations (mathlib:… or tauceti:…)")
        elif status == "planned":
            planned = item.get("planned") or []
            if not planned:
                errors.append(f"{iid}: a planned item names the layers that plan it")
            errors += [f"{iid}: {sid} is not a layer of the atlas" for sid in planned if sid not in stages]
    if not items:
        errors.append("no items: list every definition, construction and key theorem the paper uses or proves")
    taken = {}
    for number, route in enumerate(data.get("routes") or [], 1):
        where = f"route {number}"
        kind = route.get("route")
        if kind not in ROUTES:
            errors.append(f"{where}: route is one of {', '.join(sorted(ROUTES))}")
            continue
        if not text(route.get("reason")):
            errors.append(f"{where}: needs a reason")
        chosen = route.get("items") or []
        if not chosen:
            errors.append(f"{where}: names the items it takes")
        for iid in chosen:
            if iid not in items:
                errors.append(f"{where}: unknown item {iid}")
                continue
            taken[iid] = taken.get(iid, 0) + 1
            if kind != "source" and items[iid].get("status") != "missing":
                errors.append(f"{where}: {iid} is not missing, so it needs no new roadmap")
        if kind == "source":
            rid = route.get("roadmap")
            if rid not in roadmaps:
                errors.append(f"{where}: unknown roadmap {rid}")
            elif roadmaps[rid].get("origin") == "tauceti":
                errors.append(f"a source route cannot re-plan the Tau Ceti roadmap {rid}; propose a Part II")
            layers = route.get("stages") or []
            if not layers:
                errors.append(f"{where}: names the layers the paper serves")
            errors += [f"{where}: {sid} is not a layer of {rid}" for sid in layers if stages.get(sid) != rid]
            continue
        rid = route.get("roadmap")
        if not text(rid) or not rid.replace("_", "").isalnum():
            errors.append(f"{where}: a new roadmap id in CamelCase")
        elif rid in roadmaps:
            errors.append(f"{where}: {rid} already exists; extend it instead")
        if not text(route.get("title")):
            errors.append(f"{where}: needs a title")
        if not text(route.get("area")):
            errors.append(f"{where}: needs an area (a galaxy id in data/galaxies.json)")
        if len(str(route.get("brief") or "").split()) < BRIEF_WORDS:
            errors.append(f"{where}: a brief of at least {BRIEF_WORDS} words (final theorems, what to cover, what to import)")
        if kind == "part-ii":
            parent = route.get("parent")
            if parent not in roadmaps:
                errors.append(f"{where}: unknown parent roadmap {parent}")
            if "Part II" not in str(route.get("title") or ""):
                errors.append(f"{where}: a Part II is titled '<parent title>, Part II: <topic>'")
    if data.get("status") == "complete":
        for iid, item in items.items():
            if item.get("status") == "missing" and not taken.get(iid):
                errors.append(f"{iid} is missing but no route takes it")
    errors += [f"{iid} is taken by {count} routes" for iid, count in taken.items() if count > 1 and items[iid].get("status") == "missing"]
    errors += check_issues(data.get("sourceIssues"), name)
    return errors


def known() -> tuple:
    """Roadmaps and layers: the atlas's, and the new roadmaps' in research/blueprint/roadmaps/."""
    atlas = json.loads((ROOT / "data" / "atlas.json").read_text(encoding="utf-8"))
    roadmaps = {r["id"]: {"origin": r.get("origin"), "title": r.get("title", "")} for r in atlas["roadmaps"]}
    stages = {s["id"]: s["owner"] for s in atlas["stages"]}
    for path in sorted((ROOT / "research" / "blueprint" / "roadmaps").glob("*.json")):
        try:
            roadmap = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        roadmaps.setdefault(roadmap.get("id"), {"origin": "proposed", "title": roadmap.get("title", "")})
        for stage in roadmap.get("stages", []):
            stages.setdefault(f"{roadmap.get('id')}:{stage.get('key')}", roadmap.get("id"))
    return roadmaps, stages


def main(paths) -> int:
    roadmaps, stages = known()
    failed = False
    for path in map(Path, paths):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"{path}: {exc}")
            failed = True
            continue
        found = check(data, path.name.split(".")[0], roadmaps, stages)
        print(f"{path}: {'ok' if not found else str(len(found)) + ' error(s)'}")
        for error in found:
            print(f"  ERROR {error}")
        failed |= bool(found)
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
