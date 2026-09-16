"""The atlas's theory graph, and how much of it is still to be built.

Nodes are the roadmap layers (stages) of data/atlas.json, joined by their
prerequisite links (stageEdges). A parent layer is the sum of its sub-layers,
so it requires them and carries no weight of its own; administrative layers
(hidden in data/stage-presentation.json) carry no weight either but keep their
links. A layer recorded as complete (data/status.json and
data/stage-status-reports.json) is library material: it costs nothing and
ends every chain through it. A layer in progress counts half.

Where layers have been decomposed into single declarations (the reviewed
decompositions in data/decompositions and the blueprint packets in
research/blueprint/packets), the declaration graph gives a finer count, its
depth, and the source pages it covers.
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIGHT = {"complete": 0.0, "in_progress": 0.5}
PAGES = re.compile(r"\b(?:pp?\.|pages?)\s*(\d+)(?:\s*[–—-]\s*(\d+))?", re.IGNORECASE)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def stage_statuses(root: Path = ROOT) -> dict:
    """Recorded status per stage: the snapshot's, then the mapped reports on top."""
    statuses = {sid: entry.get("status") for sid, entry in load(root / "data" / "status.json")["stages"].items()}
    mapped = root / "data" / "stage-status-reports.json"
    if mapped.exists():
        statuses.update({sid: entry.get("status") for sid, entry in load(mapped).items()})
    # Layers the reviewed library audit finds already built (scripts/library_coverage.py).
    from library_coverage import coverage_statuses, load_coverage
    implied = coverage_statuses(load_coverage(root), statuses, set(statuses) | set(load_coverage(root).get("layers", {})))
    statuses.update({sid: entry["status"] for sid, entry in implied.items()})
    return statuses


class TheoryGraph:
    """Layers, their prerequisites and their weights (1 when still to be built)."""

    def __init__(self, atlas: dict, statuses: dict, hidden: set):
        self.owner = {stage["id"]: stage["owner"] for stage in atlas["stages"] if not stage.get("expansion")}
        ids = set(self.owner)
        self.prereqs = defaultdict(set)
        for edge in atlas["stageEdges"]:
            if edge["source"] in ids and edge["target"] in ids and edge["source"] != edge["target"]:
                self.prereqs[edge["target"]].add(edge["source"])
        children = defaultdict(set)
        for stage in atlas["stages"]:
            parent = stage.get("parentStageId")
            if parent in ids and stage["id"] in ids:
                children[parent].add(stage["id"])
        for parent, kids in children.items():
            for kid in kids:
                # A sub-layer that names its own parent means "the earlier parts
                # of it"; keep that link and do not add the reverse one.
                if parent not in self.prereqs[kid]:
                    self.prereqs[parent].add(kid)
        self.aggregate = {sid for sid in ids if children.get(sid)} | (hidden & ids)
        self.weight = {}
        for sid in ids:
            self.weight[sid] = 0.0 if sid in self.aggregate else WEIGHT.get(statuses.get(sid), 1.0)
        self.built = {sid for sid in ids if statuses.get(sid) == "complete"}
        self.by_owner = defaultdict(list)
        for sid, owner in sorted(self.owner.items()):
            self.by_owner[owner].append(sid)
        self._depth = {}
        self._closure = {}

    def depth(self, sid: str, visiting=None) -> int:
        """Longest chain of layers still to be built that ends at this layer."""
        if sid in self._depth:
            return self._depth[sid]
        if sid in self.built:
            self._depth[sid] = 0
            return 0
        visiting = visiting if visiting is not None else set()
        visiting.add(sid)
        below = 0
        for pre in sorted(self.prereqs.get(sid, ())):
            if pre in visiting:
                continue  # a cycle through aggregate links: ignore the back edge
            below = max(below, self.depth(pre, visiting))
        visiting.discard(sid)
        own = 1 if self.weight[sid] > 0 else 0
        self._depth[sid] = below + own
        return self._depth[sid]

    def closure(self, sid: str) -> frozenset:
        """Every layer this layer needs, itself included; built layers end the search."""
        if sid in self._closure:
            return self._closure[sid]
        seen, stack = set(), [sid]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            if node in self.built:
                continue
            stack.extend(self.prereqs.get(node, ()))
        result = frozenset(seen)
        self._closure[sid] = result
        return result

    def related(self, sid: str) -> set:
        """Every layer this layer builds on, built or not: what its subject rests on."""
        seen, stack = set(), [sid]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(self.prereqs.get(node, ()))
        return seen

    def relatedness_weight(self, sid: str) -> float:
        """Layers still to be built count fully and built ones half; aggregates not at all."""
        if sid in self.aggregate:
            return 0.0
        return 0.5 if sid in self.built else 1.0

    def roadmap_closure(self, roadmap_id: str) -> set:
        needed = set()
        for sid in self.by_owner.get(roadmap_id, ()):
            needed |= self.closure(sid)
        return needed

    def missing(self, stages) -> float:
        return sum(self.weight[sid] for sid in stages)


def page_spans(locators) -> dict:
    """Pages cited per source, as sorted disjoint intervals."""
    spans = defaultdict(list)
    for source_id, locator in locators:
        for match in PAGES.finditer(locator or ""):
            first = int(match.group(1))
            last = int(match.group(2)) if match.group(2) else first
            if last < first or last - first > 200:
                last = first
            spans[source_id].append((first, last))
    merged = {}
    for source_id, intervals in spans.items():
        intervals.sort()
        out = []
        for first, last in intervals:
            if out and first <= out[-1][1] + 1:
                out[-1] = (out[-1][0], max(out[-1][1], last))
            else:
                out.append((first, last))
        merged[source_id] = out
    return merged


def declaration_graphs(root: Path = ROOT) -> dict:
    """Declaration-level nodes per roadmap; a blueprint packet replaces a decomposition."""
    graphs = {}
    folder = root / "data" / "decompositions"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        packet = load(path)
        nodes = {node["id"]: node for node in packet.get("nodes", [])}
        edges = defaultdict(set)
        locators = []
        for link in packet.get("links", []):
            if link.get("source") in nodes and link.get("target") in nodes:
                edges[link["target"]].add(link["source"])
            locators += [(s.get("sourceId"), s.get("locator")) for s in link.get("sources", [])]
        for node in nodes.values():
            locators += [(s.get("sourceId"), s.get("locator")) for s in node.get("sources", [])]
        review = (packet.get("review") or {}).get("status", "")
        graphs[packet["roadmapId"]] = {"kind": "decomposition", "nodes": nodes, "edges": edges, "locators": locators,
                                       "reviewed": review.startswith("accepted") or review == "passed"}
    folder = root / "research" / "blueprint" / "packets"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        packet = load(path)
        nodes = {node["id"]: node for node in packet.get("nodes", [])}
        edges = defaultdict(set)
        locators = []
        for node in nodes.values():
            for pre in node.get("prerequisites", []):
                if pre in nodes:
                    edges[node["id"]].add(pre)
            locators += [(s.get("sourceId"), s.get("locator")) for s in node.get("sources", [])]
        # The independent reviewer records its verdict in the packet itself.
        accepted = (packet.get("review") or {}).get("status") == "accepted"
        roadmap_id = packet["roadmapId"]
        if roadmap_id in graphs and graphs[roadmap_id]["kind"] == "blueprint":
            # A multi-part roadmap: its part packets form one graph.
            merged = graphs[roadmap_id]
            merged["nodes"].update(nodes)
            for key, value in edges.items():
                merged["edges"][key] |= value
            merged["locators"] += locators
            merged["reviewed"] = merged["reviewed"] and accepted
        else:
            graphs[roadmap_id] = {"kind": "blueprint", "nodes": nodes, "edges": edges, "locators": locators, "reviewed": accepted}
    return graphs


def declaration_metrics(graph: dict, own_layers: list) -> dict:
    nodes, edges = graph["nodes"], graph["edges"]
    depth = {}

    def walk(node_id, visiting):
        if node_id in depth:
            return depth[node_id]
        visiting.add(node_id)
        below = max((walk(pre, visiting) for pre in sorted(edges.get(node_id, ())) if pre not in visiting), default=0)
        visiting.discard(node_id)
        built = nodes[node_id].get("implementationStatus") in ("implemented", "complete")
        depth[node_id] = below + (0 if built else 1)
        return depth[node_id]

    for node_id in sorted(nodes):
        walk(node_id, set())
    covered = {node.get("parentStageId") for node in nodes.values()} & set(own_layers)
    spans = page_spans(graph["locators"])
    return {
        "source": graph["kind"],
        "reviewed": graph["reviewed"],
        "declarations": len(nodes),
        "missingDeclarations": sum(1 for n in nodes.values() if n.get("implementationStatus") not in ("implemented", "complete")),
        "depth": max(depth.values(), default=0),
        "layersCovered": len(covered),
        "layers": len(own_layers),
        "sourcePages": sum(last - first + 1 for intervals in spans.values() for first, last in intervals),
    }


def structure(atlas: dict, root: Path = ROOT) -> tuple:
    """Per-roadmap structural measures, and the graph they came from."""
    presentation = load(root / "data" / "stage-presentation.json")
    hidden = {sid for sid, item in presentation.items() if isinstance(item, dict) and item.get("hidden")}
    graph = TheoryGraph(atlas, stage_statuses(root), hidden)
    declarations = declaration_graphs(root)
    # A collection roadmap is measured by its child roadmaps together.
    members = defaultdict(lambda: [])
    for roadmap in atlas["roadmaps"]:
        members[roadmap["id"]].append(roadmap["id"])
        if roadmap.get("parentRoadmapId"):
            members[roadmap["parentRoadmapId"]].append(roadmap["id"])
    out = {}
    for roadmap in atlas["roadmaps"]:
        rid = roadmap["id"]
        layers = [sid for member in members[rid] for sid in graph.by_owner.get(member, ())]
        own = [sid for sid in layers if sid not in graph.aggregate]
        needed = set().union(*(graph.roadmap_closure(member) for member in members[rid]))
        entry = {
            "layers": len(own),
            "missingOwn": round(graph.missing(own), 1),
            "missingLayers": round(graph.missing(needed), 1),
            "depth": max((graph.depth(sid) for sid in layers), default=0),
            "suppliers": len({graph.owner[sid] for sid in needed if graph.weight[sid] > 0} - set(members[rid])),
        }
        if rid in declarations:
            entry["declarationLevel"] = declaration_metrics(declarations[rid], own)
        out[rid] = entry
    return out, graph


def tfidf_similarity(sets: dict, weights: dict) -> dict:
    """Cosine similarity of weighted indicator vectors, each item weighted by its rarity."""
    count = defaultdict(int)
    for items in sets.values():
        for item in items:
            count[item] += 1
    total = len(sets)
    vectors = {key: {item: weights.get(item, 1.0) * math.log((1 + total) / (1 + count[item])) for item in items if weights.get(item, 1.0) > 0}
               for key, items in sets.items()}
    norms = {key: math.sqrt(sum(v * v for v in vec.values())) for key, vec in vectors.items()}
    keys = sorted(sets)
    sim = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if not norms[a] or not norms[b]:
                value = 0.0
            else:
                small, large = (vectors[a], vectors[b]) if len(vectors[a]) <= len(vectors[b]) else (vectors[b], vectors[a])
                value = sum(w * large.get(item, 0.0) for item, w in small.items()) / (norms[a] * norms[b])
            sim[(a, b)] = sim[(b, a)] = value
    return sim
