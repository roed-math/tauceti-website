#!/usr/bin/env python3
"""Check restructuring proposals against research/blueprint/PROTOCOL.md, section 15.

Usage:
  python3 scripts/check_restructure.py research/blueprint/restructure/RS-NN.result.json [...]

Errors make the exit status 1. The family file (research/blueprint/restructure/RS-NN.json)
names the members and anchors; data/atlas.json and the new roadmaps defined in
research/blueprint/roadmaps/ give the known roadmaps and layers. An id starting "UPSTREAM:"
stands for the libraries or an upstream source, as in the atlas's own links: it may supply
or own mathematics, but it is not a layer to change. Tau Ceti roadmaps never change. A
retired roadmap must say where each of its layers goes; the layers of a merged roadmap that
the proposal does not list move into the roadmap it names.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP_ACTIONS = {"keep", "extend", "merge", "retire"}
LAYER_ACTIONS = {"keep", "narrow", "move", "drop"}


def text(value):
    return isinstance(value, str) and value.strip() != ""


def supplies(ref, stages):
    """A layer of the atlas, or the libraries and upstream sources."""
    return ref in stages or (isinstance(ref, str) and ref.startswith("UPSTREAM:"))


def check(data, family, roadmaps, stages):
    """Errors in a proposal. roadmaps: id -> origin; stages: layer id -> owning roadmap."""
    if not isinstance(data, dict):
        return ["the proposal is not a JSON object"]
    errors = []
    if data.get("family") != family["id"]:
        errors.append(f"family must be {family['id']}")
    decisions = data.get("roadmaps") or {}
    layers = data.get("layers") or {}
    for member in (m["id"] for m in family["members"]):
        if member not in decisions:
            errors.append(f"no decision for member roadmap {member}")
    for rid, decision in decisions.items():
        decision = decision or {}
        if rid not in roadmaps:
            errors.append(f"unknown roadmap {rid}")
            continue
        if roadmaps[rid] == "tauceti":
            if decision.get("action") != "keep":
                errors.append(f"{rid} is a Tau Ceti roadmap and never changes")
            continue
        action = decision.get("action")
        if action not in ROADMAP_ACTIONS:
            errors.append(f"{rid}: unknown action {action!r}")
            continue
        if action != "keep" and not text(decision.get("reason")):
            errors.append(f"{rid}: a {action} needs a reason")
        if action == "extend" and decision.get("extends") not in roadmaps:
            errors.append(f"{rid}: an extension names the roadmap it extends")
        if action == "merge" and decision.get("into") not in roadmaps:
            errors.append(f"{rid}: a merge names the roadmap it merges into")
        if "title" in decision and not text(decision.get("title")):
            errors.append(f"{rid}: an empty title")
        if action == "retire":
            for sid, owner in sorted(stages.items()):
                if owner == rid and (layers.get(sid) or {}).get("action") not in ("move", "drop"):
                    errors.append(f"{rid} is retired but its layer {sid} is neither moved nor dropped")
    for sid, change in layers.items():
        change = change or {}
        if sid not in stages:
            errors.append(f"unknown layer {sid}")
            continue
        if roadmaps.get(stages[sid]) == "tauceti":
            errors.append(f"{sid} belongs to a Tau Ceti roadmap and never changes")
            continue
        action = change.get("action")
        if action not in LAYER_ACTIONS:
            errors.append(f"{sid}: unknown action {action!r}")
            continue
        if action != "keep" and not text(change.get("reason")):
            errors.append(f"{sid}: a {action} needs a reason")
        if action == "narrow" and not text(change.get("keeps")):
            errors.append(f"{sid}: a narrowed layer says exactly what it keeps")
        if action == "move" and change.get("moveTo") not in roadmaps:
            errors.append(f"{sid}: a moved layer names the roadmap it moves to")
        suppliers = change.get("suppliedBy") or []
        if action == "drop" and not suppliers:
            errors.append(f"{sid}: a dropped layer names the layers that supply it (suppliedBy)")
        for supplier in suppliers:
            if supplier == sid:
                errors.append(f"{sid} cannot supply itself")
            elif not supplies(supplier, stages):
                errors.append(f"{sid}: supplier {supplier} is not a layer of the atlas")
    for link in data.get("links") or []:
        for end in ("source", "target"):
            if not supplies(link.get(end), stages):
                errors.append(f"link {end} {link.get(end)} is not a layer of the atlas")
        if not text(link.get("reason")):
            errors.append(f"link {link.get('source')} -> {link.get('target')} needs a reason")
    for owner in data.get("owners") or []:
        if not text(owner.get("target")):
            errors.append("an owners entry needs its target")
        if not supplies(owner.get("owner"), stages):
            errors.append(f"owner {owner.get('owner')} is not a layer of the atlas")
        for former in owner.get("formerly") or []:
            if former not in stages:
                errors.append(f"former owner {former} is not a layer of the atlas")
    return errors


def main(paths):
    atlas = json.loads((ROOT / "data" / "atlas.json").read_text(encoding="utf-8"))
    roadmaps = {r["id"]: r.get("origin") for r in atlas["roadmaps"]}
    stages = {s["id"]: s["owner"] for s in atlas["stages"]}
    # New roadmaps from design and plan jobs, not yet in the atlas.
    for path in sorted((ROOT / "research" / "blueprint" / "roadmaps").glob("*.json")):
        try:
            roadmap = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        roadmaps.setdefault(roadmap.get("id"), "proposed")
        for stage in roadmap.get("stages", []):
            stages.setdefault(f"{roadmap.get('id')}:{stage.get('key')}", roadmap.get("id"))
    failed = False
    for path in paths:
        path = Path(path)
        family_path = path.with_name(path.name.split(".")[0] + ".json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            family = json.loads(family_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"{path}: {exc}")
            failed = True
            continue
        found = check(data, family, roadmaps, stages)
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
