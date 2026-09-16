#!/usr/bin/env python3
"""Check link packets (research/blueprint/PROTOCOL.md section 10).

Usage: python3 scripts/check_links.py research/blueprint/links/X.json [...]
Errors make the exit status 1.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = re.compile(r"/Users/|/private/|/Volumes/|file://")


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def load_world():
    atlas = json.loads((ROOT / "data" / "atlas.json").read_text(encoding="utf-8"))
    stages = {s["id"]: s for s in atlas["stages"]}
    readmes = {r["id"]: norm(r.get("readme")) for r in atlas["roadmaps"]}
    for path in sorted((ROOT / "research" / "blueprint" / "roadmaps").glob("*.json")):
        try:
            roadmap = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        readmes[roadmap["id"]] = norm(roadmap.get("readme"))
        for stage in roadmap.get("stages", []):
            sid = f"{roadmap['id']}:{stage['key']}"
            stages[sid] = {"id": sid, "owner": roadmap["id"], "description": stage.get("description", ""),
                           "title": stage.get("title", "")}
    edges = defaultdict(set)
    for edge in atlas["stageEdges"]:
        edges[edge["source"]].add(edge["target"])
    return stages, readmes, edges


def reaches(edges, start, goal):
    seen, todo = {start}, [start]
    while todo:
        v = todo.pop()
        if v == goal:
            return True
        for w in edges.get(v, ()):
            if w not in seen:
                seen.add(w); todo.append(w)
    return False


def check(path, world, others):
    stages, readmes, base_edges = world
    errors, warnings = [], []
    raw = Path(path).read_text(encoding="utf-8")
    if PRIVATE.search(raw):
        errors.append("private filesystem path in packet")
    packet = json.loads(raw)
    rid = packet.get("roadmapId")
    if rid not in readmes:
        errors.append(f"unknown roadmap {rid!r}")
    if packet.get("protocol") != "links-v1":
        errors.append("protocol must be 'links-v1'")
    if packet.get("status") not in ("partial", "complete"):
        warnings.append("status should be 'partial' or 'complete' (a missing status counts as partial)")
    edges = defaultdict(set, {k: set(v) for k, v in base_edges.items()})
    for other in others:
        for link in other.get("links", []):
            edges[link.get("source")].add(link.get("target"))
    seen = set()
    for link in packet.get("links", []):
        s, t = link.get("source"), link.get("target")
        label = f"{s} -> {t}"
        if s not in stages or t not in stages:
            errors.append(f"{label}: unknown endpoint")
            continue
        if s == t:
            errors.append(f"{label}: self link")
        if stages[s]["owner"] == stages[t]["owner"]:
            warnings.append(f"{label}: both stages belong to {stages[s]['owner']}")
        if rid not in (stages[s]["owner"], stages[t]["owner"]):
            errors.append(f"{label}: neither endpoint belongs to {rid}")
        if (s, t) in seen:
            errors.append(f"{label}: duplicate")
        seen.add((s, t))
        if t in base_edges.get(s, set()):
            warnings.append(f"{label}: already recorded in the atlas")
        if link.get("confidence") not in ("explicit", "inferred"):
            errors.append(f"{label}: confidence must be explicit or inferred")
        if not (link.get("reason") or "").strip():
            errors.append(f"{label}: missing reason")
        evidence = link.get("evidence") or []
        sides = {e.get("stageId") for e in evidence}
        if s not in sides or t not in sides:
            errors.append(f"{label}: evidence must quote both the source and the target stage")
        for item in evidence:
            sid, quote = item.get("stageId"), norm(item.get("quote"))
            if sid not in stages or len(quote) < 12:
                errors.append(f"{label}: evidence needs a known stage and a quote of at least 12 characters")
                continue
            owner = stages[sid]["owner"]
            if quote not in norm(stages[sid].get("description")) and quote not in readmes.get(owner, ""):
                errors.append(f"{label}: quote not found verbatim in {sid} or its roadmap document: {quote[:80]!r}")
        if reaches(edges, t, s):
            errors.append(f"{label}: would create a cycle with recorded stage links")
        edges[s].add(t)
    for overlap in packet.get("overlaps", []):
        ids = overlap.get("stages") or []
        if len(ids) < 2 or any(i not in stages for i in ids):
            errors.append(f"overlap {ids}: needs at least two known stages")
        if overlap.get("recommendation") not in ("merge", "rescope", "keep"):
            errors.append(f"overlap {ids}: recommendation must be merge, rescope or keep")
        if not (overlap.get("detail") or "").strip():
            errors.append(f"overlap {ids}: missing detail")
    if not packet.get("examined"):
        errors.append("examined list is empty")
    summary = {"packet": str(path), "roadmap": rid, "status": packet.get("status", "partial"), "links": len(packet.get("links", [])),
               "overlaps": len(packet.get("overlaps", [])), "examined": len(packet.get("examined", []))}
    return errors, warnings, summary


def main():
    paths = [p for p in sys.argv[1:] if not p.startswith("--")]
    world = load_world()
    folder = ROOT / "research" / "blueprint" / "links"
    failed = False
    for path in paths:
        others = []
        for other in sorted(folder.glob("*.json")):
            if other.resolve() != Path(path).resolve():
                try:
                    others.append(json.loads(other.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    pass
        errors, warnings, summary = check(path, world, others)
        failed |= bool(errors)
        print(f"== {path}\n{json.dumps(summary)}")
        for e in errors[:200]:
            print("ERROR  ", e)
        for w in warnings[:80]:
            print("warning", w)
        print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
