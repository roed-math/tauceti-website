"""Promoted blueprints in the atlas (research/blueprint/PROTOCOL.md, sections 6, 7, 8 and 14).

scripts/promote.py copies independently reviewed work into data/blueprints/:
packets (a multi-part roadmap has one per part), their roadmap documents, and
the definitions of new roadmaps. The build reads them here:

- a new roadmap enters the atlas with its layers, their links and a place in
  an area (add_new_roadmaps);
- a blueprint replaces the older source decomposition of the layers it covers
  (replaced_layers, trim_decompositions);
- each layer's planets are the nodes its workers marked (at most six a layer),
  linked where one leads to another through the lemmas between them; every
  declaration is listed under its layer, compactly, since the full packets and
  documents are read on demand; and a prerequisite in another roadmap links
  the two layers (merge_blueprints).

The snapshot passed in is never changed.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

PLANET_KINDS = {"definition", "construction", "theorem"}
EVIDENCE_PER_LINK = 2
EXCERPT = 160


def load_promoted(root: Path, folder: Path | None = None) -> tuple:
    """(packets as [(file stem, packet)], documents {file stem: path}, new roadmap definitions).

    folder replaces data/blueprints for tests; the page still reads the files at data/blueprints/."""
    folder = folder or root / "data" / "blueprints"
    packets, documents, definitions = [], {}, []
    if folder.is_dir():
        packets = [(path.stem, json.loads(path.read_text(encoding="utf-8"))) for path in sorted(folder.glob("*.json"))]
        documents = {path.stem: f"data/blueprints/{path.name}" for path in sorted(folder.glob("*.md"))}
        definitions = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((folder / "roadmaps").glob("*.json"))]
    return packets, documents, definitions


def refresh_roadmap_links(atlas: dict) -> None:
    """Roadmap links, and each roadmap's prerequisites and consumers, from the stage links."""
    owner = {stage["id"]: stage["owner"] for stage in atlas["stages"]}
    map_edges = {(edge["source"], edge["target"]): edge for edge in atlas["edges"]}
    counts = Counter()
    for edge in atlas["stageEdges"]:
        a, b = owner.get(edge["source"]), owner.get(edge["target"])
        if a and b and a != b:
            counts[a, b] += 1
    for pair, count in counts.items():
        map_edges.setdefault(pair, {"source": pair[0], "target": pair[1], "kind": "stage_supported"})["stageCount"] = count
    atlas["edges"] = list(map_edges.values())
    for roadmap in atlas["roadmaps"]:
        roadmap["prerequisites"] = sorted({s for s, t in map_edges if t == roadmap["id"]})
        roadmap["consumers"] = sorted({t for s, t in map_edges if s == roadmap["id"]})


def link(stages: dict, source: str, target: str) -> None:
    if source not in stages[target].setdefault("requires", []):
        stages[target]["requires"].append(source)
    if target not in stages[source].setdefault("consumers", []):
        stages[source]["consumers"].append(target)


def add_new_roadmaps(snapshot: dict, definitions: list, records: dict, clusters: dict) -> tuple:
    """(atlas, classification records) with each promoted new roadmap (PROTOCOL.md section 7) added.

    Its area is the one it names (as "area", or as its "group" when that is an
    area id), else its base roadmap's (a Part II's "parent"), else the area
    where most roadmaps of its group are, else the area most of its
    prerequisites are in. clusters maps area ids to their cluster.
    """
    atlas, records = deepcopy(snapshot), deepcopy(records)
    if not definitions:
        return atlas, records
    usual = defaultdict(Counter)
    for roadmap in atlas["roadmaps"]:
        if roadmap.get("group") and roadmap["id"] in records:
            usual[roadmap["group"]][records[roadmap["id"]]["galaxy"]] += 1
    stages = {stage["id"]: stage for stage in atlas["stages"]}
    edges = {(edge["source"], edge["target"]) for edge in atlas["stageEdges"]}
    for definition in definitions:
        rid = definition["id"]
        if any(roadmap["id"] == rid for roadmap in atlas["roadmaps"]):
            raise ValueError(f"A new roadmap already in the atlas: {rid}")
        path = f"data/blueprints/{rid}.md"
        ids = [f"{rid}:{item['key']}" for item in definition.get("stages", [])]
        roadmap = {"id": rid, "title": definition["title"], "summary": definition.get("summary", ""), "readme": definition.get("readme", ""),
                   "origin": "campaign", "lifecycle": "proposed", "group": definition.get("group"), "parentRoadmapId": None,
                   "sourcePath": path, "stages": ids, "prerequisites": [], "consumers": [], "pendingLinks": []}
        atlas["roadmaps"].append(roadmap)
        for sid, item in zip(ids, definition.get("stages", [])):
            stage = {"id": sid, "owner": rid, "key": item["key"], "title": item.get("title", item["key"]), "description": item.get("description", ""),
                     "requires": [], "consumers": [], "sourcePath": path, "sourceLine": 1, "contextStartLine": 1, "contextEndLine": 1,
                     "depth": 0, "firstAction": "", "status": "needs_source_decomposition", "implementationStatus": "unchecked",
                     "signatureMatchStatus": "unchecked", "sourceReviewStatus": "reviewed_blueprint", "origin": "campaign",
                     "parentStageId": None, "isLeaf": True}
            atlas["stages"].append(stage)
            stages[sid] = stage
        suppliers = Counter(p for p in definition.get("prerequisites", []) if p in records)
        for sid, item in zip(ids, definition.get("stages", [])):
            for source in item.get("requires", []):
                if source not in stages or source == sid:
                    roadmap["pendingLinks"].append([source, sid])
                    continue
                if (source, sid) not in edges:
                    edges.add((source, sid))
                    # The roadmap's own plan, drawn like any roadmap's declared prerequisites.
                    atlas["stageEdges"].append({"source": source, "target": sid, "kind": "declared"})
                link(stages, source, sid)
                if stages[source]["owner"] != rid and stages[source]["owner"] in records:
                    suppliers[stages[source]["owner"]] += 1
        for prerequisite in definition.get("prerequisites", []):
            if any(r["id"] == prerequisite for r in atlas["roadmaps"]):
                atlas["edges"].append({"source": prerequisite, "target": rid, "kind": "declared"})
        area, how = definition.get("area"), "the area it names"
        if area not in clusters:
            area = definition.get("group")
        if area not in clusters:
            area, how = records.get(definition.get("parent"), {}).get("galaxy"), f"the area of {definition.get('parent')}, its base"
        if area not in clusters and usual.get(definition.get("group")):
            counts = usual[definition["group"]]
            area, how = min(counts, key=lambda gid: (-counts[gid], gid)), f"the area where most {definition['group']} roadmaps are"
        if area not in clusters:
            by_area = Counter()
            for supplier, count in suppliers.items():
                by_area[records[supplier]["galaxy"]] += count
            area = min(by_area, key=lambda gid: (-by_area[gid], gid)) if by_area else None
            how = "the area most of its prerequisites are in"
        if area not in clusters:
            raise ValueError(f"Cannot place the new roadmap {rid}: name its area (PROTOCOL.md section 7)")
        near = [records[s]["distance"] for s in suppliers if isinstance(records[s].get("distance"), (int, float))]
        records[rid] = {"galaxy": area, "cluster": clusters[area], "distance": min(10, max(near) + 1) if near else 5,
                        "primaryMsc": None, "secondaryMsc": [], "basis": "blueprint",
                        "rationale": f"A new roadmap from a reviewed blueprint, placed in {how}."}
    refresh_roadmap_links(atlas)
    return atlas, records


def layer_of(node: dict, nodes: dict, stages: dict, rid: str):
    """The layer of the roadmap a node belongs to, through any parent nodes."""
    seen, parent = set(), node.get("parentStageId")
    while parent in nodes and parent not in seen:
        seen.add(parent)
        parent = nodes[parent].get("parentStageId")
    if parent in stages and stages[parent]["owner"] == rid and not stages[parent].get("expansion"):
        return parent
    realised = [sid for sid in node.get("realises") or [] if sid in stages and stages[sid]["owner"] == rid]
    return realised[0] if realised else None


def replaced_layers(packets: list, stages_of: dict | None = None) -> set:
    """The layers promoted blueprints cover: each packet's scope, else its coverage and nodes, else its whole roadmap."""
    covered = set()
    for _, packet in packets:
        if packet.get("scope"):
            covered |= set(packet["scope"])
            continue
        found = {entry.get("stageId") for entry in packet.get("coverage", [])}
        found |= {node.get("parentStageId") for node in packet.get("nodes", []) if ":" in str(node.get("parentStageId")) and "/" not in str(node.get("parentStageId"))}
        covered |= found or set((stages_of or {}).get(packet["roadmapId"], []))
    covered.discard(None)
    return covered


def trim_decompositions(decompositions: list, covered: set) -> list:
    """Older decompositions without the layers a blueprint now covers."""
    kept = []
    for packet in decompositions:
        nodes = {node["id"]: node for node in packet.get("nodes", [])}

        def layer(node):
            seen, parent = set(), node.get("parentStageId")
            while parent in nodes and parent not in seen:
                seen.add(parent)
                parent = nodes[parent].get("parentStageId")
            return parent
        dropped = {nid for nid, node in nodes.items() if layer(node) in covered}
        if not dropped and not any(entry.get("stageId") in covered for entry in packet.get("coverage", [])):
            kept.append(packet)
            continue
        trimmed = dict(packet)
        trimmed["nodes"] = [node for node in packet.get("nodes", []) if node["id"] not in dropped]
        trimmed["coverage"] = [entry for entry in packet.get("coverage", []) if entry.get("stageId") not in covered]
        trimmed["links"] = [item for item in packet.get("links", []) if item.get("source") not in dropped and item.get("target") not in dropped]
        if "deferredLinks" in packet:
            trimmed["deferredLinks"] = [item for item in packet["deferredLinks"]
                                        if item.get("source") not in dropped and item.get("target") not in dropped]
        if not trimmed["nodes"] and not trimmed["coverage"]:
            continue
        if trimmed.get("status") == "source_decomposed":
            trimmed["status"] = "partial"
        kept.append(trimmed)
    return kept


def excerpt(text: str) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= EXCERPT else text[:EXCERPT].rsplit(" ", 1)[0] + " …"


def planet_name(node: dict):
    planet = node.get("planet")
    if node.get("kind") in PLANET_KINDS and isinstance(planet, dict) and isinstance(planet.get("name"), str) and planet["name"].strip():
        return planet["name"].strip()
    return None


def merge_blueprints(snapshot: dict, packets: list, documents: dict) -> dict:
    """The atlas with each promoted blueprint's planets, declarations and links. packets: [(file stem, packet)]."""
    atlas = deepcopy(snapshot)
    atlas["blueprintLayers"] = []
    if not packets:
        return atlas
    roadmaps = {roadmap["id"]: roadmap for roadmap in atlas["roadmaps"]}
    stages = {stage["id"]: stage for stage in atlas["stages"]}
    parts = defaultdict(list)
    for stem, packet in packets:
        if packet.get("roadmapId") not in roadmaps:
            raise ValueError(f"A promoted blueprint for a roadmap that is not in the atlas: {packet.get('roadmapId')}")
        parts[packet["roadmapId"]].append((stem, packet))
    nodes_of, layer = {}, {}
    for rid, items in parts.items():
        nodes = {}
        for index, (_, packet) in enumerate(items):
            for node in packet.get("nodes", []):
                nodes[node["id"]] = (index, node)
        plain = {nid: node for nid, (_, node) in nodes.items()}
        for nid, (_, node) in nodes.items():
            found = layer_of(node, plain, stages, rid)
            if found is None:
                raise ValueError(f"{nid}: its layer is not a layer of {rid}")
            layer[nid] = found
        nodes_of[rid] = nodes

    def atlas_layer(ref):
        if ref in layer:
            return layer[ref]
        stage = stages.get(ref)
        while stage and stage.get("expansion") and stage.get("parentStageId") in stages:
            stage = stages[stage["parentStageId"]]
        return stage["id"] if stage else None

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

    def add_edge(source, target, evidence):
        edge = edges.get((source, target))
        if edge is None:
            edge = edges[source, target] = {"source": source, "target": target, "kind": "blueprint", "evidence": []}
            following[source].add(target)
            link(stages, source, target)
        if evidence and edge.get("kind") == "blueprint":
            # How many declarations use the link: the map draws a layer's most used links.
            edge["uses"] = edge.get("uses", 0) + 1
        if evidence and len(edge.setdefault("evidence", [])) < EVIDENCE_PER_LINK:
            edge["evidence"].append(evidence)

    with_planets = set()
    for rid, items in parts.items():
        roadmap, nodes = roadmaps[rid], nodes_of[rid]
        listing, planets, skipped = defaultdict(list), [], []
        for nid, (index, node) in nodes.items():
            listing[layer[nid]].append([nid[len(rid) + 1:] if nid.startswith(rid + ":") else nid, node.get("kind"), node.get("title", ""), index])
            name = planet_name(node)
            if not name:
                continue
            if nid in stages:
                raise ValueError(f"A planet with the id of an existing layer or refinement: {nid}")
            stage = {"id": nid, "owner": rid, "key": nid[len(rid) + 1:], "title": name, "description": excerpt(node.get("statement", "")),
                     "requires": [], "consumers": [], "sourcePath": roadmap.get("sourcePath"), "sourceLine": 1,
                     "contextStartLine": 1, "contextEndLine": 1, "status": "source_decomposition_recorded",
                     "sourceReviewStatus": "reviewed_blueprint", "implementationStatus": "unchecked",
                     "origin": roadmap.get("origin", "campaign"), "parentStageId": layer[nid], "isLeaf": True,
                     "expansion": {"kind": node["kind"], "packet": rid, "blueprint": True, "file": index, "title": node.get("title", ""),
                                   "statement": node.get("statement", ""), "hypotheses": node.get("hypotheses", []), "planet": name,
                                   "addedBy": node.get("addedBy"), "reviewed": not node.get("addedBy")}}
            atlas["stages"].append(stage)
            stages[nid] = stage
            roadmap["stages"].append(nid)
            planets.append(nid)
            with_planets.add(layer[nid])
        # A planet leads to another of its layer when a chain of prerequisites
        # joins them through declarations that are not planets.
        chosen = set(planets)
        for target in planets:
            stack, seen = list(nodes[target][1].get("prerequisites", [])), set()
            while stack:
                ref = stack.pop()
                if ref in seen or ref not in nodes:
                    continue
                seen.add(ref)
                if ref in chosen:
                    if ref != target and layer[ref] == layer[target] and not reaches(target, ref):
                        add_edge(ref, target, None)
                    continue
                stack.extend(nodes[ref][1].get("prerequisites", []))
        # A prerequisite in another roadmap links the two layers.
        for nid, (_, node) in nodes.items():
            for ref in node.get("prerequisites", []):
                if ref in nodes:
                    continue
                supplier = atlas_layer(ref)
                if supplier is None or stages[supplier]["owner"] == rid:
                    continue
                target = layer[nid]
                evidence = {"packet": rid, "reason": f"{node.get('title', nid)} uses {ref}"}
                if (supplier, target) in edges:
                    add_edge(supplier, target, evidence)
                elif reaches(target, supplier):
                    if [supplier, target] not in skipped:
                        skipped.append([supplier, target])
                else:
                    add_edge(supplier, target, evidence)
        kinds = Counter(node.get("kind") for _, node in nodes.values())
        roadmap["blueprint"] = {
            "files": [stem for stem, _ in items],
            "documents": [documents[stem] for stem, _ in items if stem in documents],
            "declarations": len(nodes), "planets": len(planets), "kinds": dict(sorted(kinds.items())),
            "layers": dict(listing),
            "parts": [{"part": packet.get("part"), "status": packet.get("status"), "summary": packet.get("summary", ""),
                       "reviewer": (packet.get("review") or {}).get("reviewer"), "reviewDate": (packet.get("review") or {}).get("date"),
                       "gaps": len(packet.get("gaps") or [])} for _, packet in items],
            "skippedLinks": skipped,
        }
    atlas["stageEdges"] = list(edges.values())
    atlas["blueprintLayers"] = sorted(with_planets)
    parent_ids = {stage.get("parentStageId") for stage in atlas["stages"]}
    for stage in atlas["stages"]:
        stage["isLeaf"] = stage["id"] not in parent_ids
    refresh_roadmap_links(atlas)
    return atlas
