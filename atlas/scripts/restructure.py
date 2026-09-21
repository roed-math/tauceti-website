"""Accepted restructuring proposals in the atlas (research/blueprint/PROTOCOL.md, section 15).

scripts/promote.py copies a proposal into data/restructure/ once its independent
review accepts it. The build applies it here: an extended roadmap takes its new
title ("<base>, Part II: ...") and builds on its base; a narrowed layer plans
only what it keeps, and says who supplies the rest; a dropped layer leaves the
map, naming its suppliers; and the proposal's links join the atlas. Tau Ceti
roadmaps never change. Links whose ends are not in the atlas, or that would
close a cycle, are left out and recorded. The snapshot passed in is never changed.
"""
from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from blueprints import link, refresh_roadmap_links


def load_accepted(root: Path) -> list:
    folder = root / "data" / "restructure"
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("RS-*.result.json"))] if folder.is_dir() else []


def apply_restructurings(snapshot: dict, proposals: list) -> tuple:
    """(atlas, presentation overrides for dropped layers)."""
    atlas = deepcopy(snapshot)
    atlas["restructurings"] = []
    hidden = {}
    if not proposals:
        return atlas, hidden
    roadmaps = {roadmap["id"]: roadmap for roadmap in atlas["roadmaps"]}
    stages = {stage["id"]: stage for stage in atlas["stages"]}
    edges = {(edge["source"], edge["target"]): edge for edge in atlas["stageEdges"]}
    following = defaultdict(set)
    for source, target in edges:
        following[source].add(target)

    def reaches(start, goal):
        seen, stack = set(), [start]
        while stack:
            item = stack.pop()
            if item == goal:
                return True
            if item not in seen:
                seen.add(item)
                stack.extend(following[item])
        return False

    upstream = lambda rid: rid.startswith("tauceti:") or roadmaps.get(rid, {}).get("origin") == "tauceti"
    for proposal in proposals:
        rs = proposal.get("family", "")
        record = {"proposal": rs, "roadmaps": {}, "layers": {}, "links": 0, "skippedLinks": [], "unchanged": []}
        for rid, entry in (proposal.get("roadmaps") or {}).items():
            roadmap = roadmaps.get(rid)
            if roadmap is None or upstream(rid):
                record["unchanged"].append(rid)
                continue
            action = entry.get("action", "keep")
            record["roadmaps"][rid] = action
            if entry.get("title"):
                roadmap["title"] = entry["title"]
            if action == "extend" and entry.get("extends") in roadmaps:
                roadmap["extends"] = entry["extends"]
                pair = {"source": entry["extends"], "target": rid, "kind": "declared"}
                if pair not in atlas["edges"]:
                    atlas["edges"].append(pair)
            roadmap["restructuredBy"] = rs
        for sid, entry in (proposal.get("layers") or {}).items():
            stage = stages.get(sid)
            action = entry.get("action", "keep")
            if stage is None or upstream(stage["owner"]):
                record["unchanged"].append(sid)
                continue
            if action not in ("narrow", "drop"):
                continue
            record["layers"][sid] = action
            suppliers = [s for s in entry.get("suppliedBy") or [] if isinstance(s, str)]
            stage["restructured"] = {"proposal": rs, "action": action, **({"keeps": entry["keeps"]} if action == "narrow" else {}),
                                     "suppliedBy": suppliers, "reason": entry.get("reason", "")}
            if action == "narrow" and entry.get("keeps"):
                supplied = f" The rest is supplied by {', '.join(suppliers)}." if suppliers else ""
                stage["description"] = f"{entry['keeps']}\n\n*Narrowed by the restructuring {rs}.{supplied}*"
            if action == "drop":
                hidden[sid] = {"hidden": True, "summary": f"Dropped by the restructuring {rs}; "
                                                          f"{', '.join(suppliers) or 'other layers'} supply it. {entry.get('reason', '')}".strip()}
        for item in proposal.get("links") or []:
            source, target = item.get("source"), item.get("target")
            if source not in stages or target not in stages or source == target:
                record["skippedLinks"].append([source, target])
                continue
            evidence = {"proposal": rs, "reason": item.get("reason", "")}
            edge = edges.get((source, target))
            if edge is None:
                if reaches(target, source):
                    record["skippedLinks"].append([source, target])
                    continue
                edge = edges[source, target] = {"source": source, "target": target, "kind": "restructure", "evidence": []}
                following[source].add(target)
                link(stages, source, target)
                record["links"] += 1
            edge.setdefault("evidence", []).append(evidence)
        atlas["restructurings"].append(record)
    atlas["stageEdges"] = list(edges.values())
    refresh_roadmap_links(atlas)
    return atlas, hidden
