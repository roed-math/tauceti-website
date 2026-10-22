"""Each roadmap's distance from Mathlib on the published pages.

scripts/measure_distances.py measures the roadmaps of the explorer's own snapshot: w_T ln(1 + T) + w_D D
over the prerequisite closure of a roadmap's layers, T the targets still missing from Mathlib and Tau
Ceti and D the longest chain of layers still to be built, with weights fitted to the swarm's pairwise
judgements and placed on a 0-10 scale. The published pages draw roadmaps it never saw: those Tau Ceti
has accepted since, and those open pull requests propose. This module applies the same function, with
the same weights and on the same scale, to every roadmap on the page, over the page's own prerequisite
graph, so that a roadmap's place on the map says how much theory it still needs.

A roadmap added from its README has no layer links to other roadmaps, only the prerequisites its
README names (scripts/roadmap_dependencies.py); each counts as its first layers needing all of the
roadmap it builds on. A roadmap the swarm judged keeps its judged distance.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict

from library_coverage import already_available
from theory_graph import TheoryGraph


def raw_measurement(structure: dict, weights: dict) -> float:
    return weights["lnMissingTargets"] * math.log1p(structure["missingTargets"]) + weights["depth"] * structure["depth"]


def scale_factor(recorded: dict) -> float:
    """measure_distances.py's factor from its log-odds scale to the atlas's 0-10 scale, read back from its roadmaps."""
    weights = recorded["pairwise"]["weights"]
    ratios = [entry["measurement"] / raw for entry in recorded.get("roadmaps", {}).values()
              if entry.get("structure") and entry.get("measurement") and (raw := raw_measurement(entry["structure"], weights)) > .5]
    return statistics.median(ratios) if ratios else 1.0


def readme_links(atlas: dict) -> list:
    """Layer links standing for the roadmap prerequisites no layer link records: the prerequisite's last layers
    before the dependent's first ones."""
    owner = {stage["id"]: stage["owner"] for stage in atlas["stages"] if not stage.get("expansion")}
    inside, linked = defaultdict(set), set()
    for edge in atlas.get("stageEdges", []):
        a, b = owner.get(edge["source"]), owner.get(edge["target"])
        if a and b and a == b:
            inside[a].add((edge["source"], edge["target"]))
        elif a and b:
            linked.add((a, b))
    layers = defaultdict(list)
    for sid, rid in owner.items():
        layers[rid].append(sid)
    first = {rid: [sid for sid in sids if not any(target == sid for _, target in inside[rid])] for rid, sids in layers.items()}
    last = {rid: [sid for sid in sids if not any(source == sid for source, _ in inside[rid])] for rid, sids in layers.items()}
    links = []
    for edge in atlas.get("edges", []):
        source, target = edge["source"], edge["target"]
        if source == target or (source, target) in linked or not layers.get(source) or not layers.get(target):
            continue
        links += [{"source": a, "target": b} for a in sorted(last[source]) for b in sorted(first[target])]
    return links


def measure(atlas: dict, recorded: dict, coverage: dict) -> dict:
    """roadmap id -> its distance record, as data/roadmap-distances.json keeps one: judged ones as recorded."""
    weights, factor = recorded["pairwise"]["weights"], scale_factor(recorded)
    statuses = {sid: entry.get("status") for sid, entry in atlas.get("progress", {}).get("stages", {}).items()}
    hidden = {sid for sid, item in atlas.get("stagePresentation", {}).items() if isinstance(item, dict) and item.get("hidden")}
    hidden |= set(already_available(coverage, atlas))
    graph = TheoryGraph({"stages": atlas["stages"], "stageEdges": atlas.get("stageEdges", []) + readme_links(atlas)}, statuses, hidden, coverage=coverage)
    members = defaultdict(list)
    for roadmap in atlas["roadmaps"]:
        members[roadmap["id"]].append(roadmap["id"])
        if roadmap.get("parentRoadmapId"):
            members[roadmap["parentRoadmapId"]].append(roadmap["id"])
    out = {}
    for roadmap in atlas["roadmaps"]:
        rid = roadmap["id"]
        known = recorded.get("roadmaps", {}).get(rid)
        if known and known.get("basis") == "judged":
            out[rid] = known
            continue
        layers = [sid for member in members[rid] for sid in graph.by_owner.get(member, ())]
        needed = set().union(*(graph.roadmap_closure(member) for member in members[rid]))
        structure = {"layers": sum(1 for sid in layers if sid not in graph.aggregate), "missingOwn": round(graph.missing(layers), 1),
                     "missingLayers": round(graph.missing(needed), 1), "missingTargets": round(graph.missing_targets(needed), 1),
                     "depth": max((graph.depth(sid) for sid in layers), default=0),
                     "suppliers": len({graph.owner[sid] for sid in needed if graph.weight[sid] > 0} - set(members[rid]))}
        built = not structure["missingLayers"] and not structure["missingTargets"]
        distance = 0.0 if built else round(max(0.0, min(10.0, raw_measurement(structure, weights) * factor)), 2)
        out[rid] = {"structure": structure, "measurement": distance, "distance": distance, "judgements": 0, "basis": "built" if built else "measured"}
    return out
