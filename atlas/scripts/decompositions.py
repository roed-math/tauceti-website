"""Validate and merge reviewed mathematical decompositions into an atlas snapshot.

The original data/atlas.json remains the source snapshot. This module adds authored,
source-located refinements at build time and returns the expanded roadmap Markdown
for publication. It never assigns implementation progress to a new target.
"""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
import re


KINDS = {"definition", "construction", "lemma", "theorem", "comparison", "application"}
COVERAGE = {"not_read", "partial", "source_decomposed"}


def require_text(value, context):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing text: {context}")
    return value.strip()


def acyclic(nodes, edges, context):
    adjacency = defaultdict(set)
    indegree = dict.fromkeys(nodes, 0)
    for source, target in edges:
        if source not in indegree or target not in indegree:
            raise ValueError(f"Unknown endpoint in {context}: {source} -> {target}")
        if target not in adjacency[source]:
            adjacency[source].add(target)
            indegree[target] += 1
    pending = deque(node for node, degree in indegree.items() if degree == 0)
    visited = 0
    while pending:
        node = pending.popleft()
        visited += 1
        for target in adjacency[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                pending.append(target)
    if visited != len(indegree):
        remaining = [node for node, degree in indegree.items() if degree]
        raise ValueError(f"Cycle in {context}: {', '.join(remaining[:12])}")


def refinement_owner(node_id, roadmaps):
    """The roadmap a refinement ID belongs to: the longest roadmap ID prefix before ':' or '#'."""
    candidates = [rid for rid in roadmaps if node_id.startswith(rid + ":") or node_id.startswith(rid + "#")]
    return max(candidates, key=len) if candidates and "/" in node_id[len(max(candidates, key=len)):] else None


def pending_refinement(node_id, roadmaps, accepted):
    """True when node_id names a refinement of a roadmap whose packet is not yet accepted."""
    owner = refinement_owner(node_id, roadmaps)
    return bool(owner) and owner not in accepted


def source_citation(reference, sources):
    work = sources[reference["sourceId"]]
    title = work["title"]
    title = f"[{title}]({work['url']})" if work.get("url") else title
    return f"{work['authors']}, *{title}* ({work['edition']}), {reference['locator']}"


def render_node(node, sources):
    lines = [f"### {node['title']}", "", node["statement"].strip(), ""]
    for label, key in [("Hypotheses", "hypotheses"), ("Construction and proof", "proofSteps"),
                       ("Acceptance", "acceptance")]:
        values = node.get(key, [])
        if values:
            lines += [f"#### {label}", ""]
            lines += [f"{index + 1}. {value}" if key == "proofSteps" else f"- {value}"
                      for index, value in enumerate(values)]
            lines.append("")
    lines += ["#### References", ""]
    for reference in node["sources"]:
        lines += [f"- {source_citation(reference, sources)}.",
                  f"  {reference['match']}", ""]
    return "\n".join(lines).rstrip()


def merge_decompositions(snapshot, packets):
    """Return (expanded atlas, changed Markdown files), rejecting invalid packets."""
    atlas = deepcopy(snapshot)
    if not packets:
        return atlas, {}
    roadmaps = {roadmap["id"]: roadmap for roadmap in atlas["roadmaps"]}
    stages = {stage["id"]: stage for stage in atlas["stages"]}
    new_nodes, packet_maps, sources_by_map = {}, set(), {}
    for packet in packets:
        owner = packet["roadmapId"]
        if owner not in roadmaps or owner in packet_maps:
            raise ValueError(f"Unknown or repeated roadmap packet: {owner}")
        packet_maps.add(owner)
        review = packet.get("review", {})
        if review.get("status") != "accepted" or not review.get("notes"):
            raise ValueError(f"Decomposition has not passed independent review: {owner}")
        if packet.get("status") not in {"partial", "source_decomposed"}:
            raise ValueError(f"Invalid decomposition status: {owner}")
        require_text(packet.get("summary"), owner + " summary")
        sources = {}
        for source in packet.get("sources", []):
            for key in ("id", "title", "authors", "edition"):
                require_text(source.get(key), owner + " source " + key)
            if source["id"] in sources:
                raise ValueError(f"Duplicate source ID in {owner}: {source['id']}")
            if source.get("url") and not re.match(r"^https?://", source["url"]):
                raise ValueError("Source URLs must be public HTTP(S) addresses.")
            if source.get("sha256") and not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]):
                raise ValueError("Invalid source SHA-256.")
            if not source.get("readSections"):
                raise ValueError(f"No inspected sections recorded: {source['id']}")
            sources[source["id"]] = source
        sources_by_map[owner] = sources
        for node in packet.get("nodes", []):
            node_id = require_text(node.get("id"), owner + " node ID")
            if not node_id.startswith(owner + ":") or node_id in stages or node_id in new_nodes:
                raise ValueError(f"Invalid or duplicate new node: {node_id}")
            if node.get("kind") not in KINDS:
                raise ValueError(f"Invalid mathematical node kind: {node_id}")
            for key in ("title", "statement", "parentStageId"):
                require_text(node.get(key), node_id + " " + key)
            for key in ("hypotheses", "proofSteps", "acceptance"):
                if not isinstance(node.get(key), list):
                    raise ValueError(f"Missing {key} list: {node_id}")
                for value in node[key]:
                    require_text(value, node_id + " " + key)
            if not node["proofSteps"] or not node["acceptance"] or not node.get("sources"):
                raise ValueError(f"Incomplete source decomposition: {node_id}")
            if node.get("implementationStatus") != "unchecked":
                raise ValueError("Decomposition packets cannot confer implementation status.")
            for reference in node["sources"]:
                if reference.get("sourceId") not in sources:
                    raise ValueError(f"Unknown source for {node_id}")
                for key in ("locator", "excerpt", "match"):
                    require_text(reference.get(key), node_id + " " + key)
            new_nodes[node_id] = (owner, node)
        covered = set()
        for coverage in packet.get("coverage", []):
            stage = stages.get(coverage.get("stageId"))
            if not stage or stage["owner"] != owner or stage["id"] in covered:
                raise ValueError(f"Invalid coverage record in {owner}")
            covered.add(stage["id"])
            if coverage.get("status") not in COVERAGE:
                raise ValueError(f"Invalid source coverage status in {owner}")
            if coverage["status"] == "source_decomposed" and coverage.get("remaining"):
                raise ValueError(f"Source closure claimed with remaining work: {stage['id']}")
        if packet["status"] == "source_decomposed":
            if covered != set(roadmaps[owner]["stages"]) or packet.get("gaps") or any(
                    item["status"] != "source_decomposed" for item in packet["coverage"]):
                raise ValueError(f"Roadmap source closure is not established: {owner}")

    all_owners = {stage_id: stage["owner"] for stage_id, stage in stages.items()}
    all_owners.update({node_id: owner for node_id, (owner, _) in new_nodes.items()})
    hierarchy = [(stage["parentStageId"], stage["id"]) for stage in stages.values()
                 if stage.get("parentStageId")]
    for node_id, (owner, node) in new_nodes.items():
        parent = node["parentStageId"]
        if all_owners.get(parent) != owner:
            raise ValueError(f"Refinement has no parent in its own roadmap: {node_id}")
        hierarchy.append((parent, node_id))
    acyclic(all_owners, hierarchy, "stage hierarchy")

    rendered, expansion = {}, []
    for packet in packets:
        owner = packet["roadmapId"]
        roadmap, sources = roadmaps[owner], sources_by_map[owner]
        text = roadmap["readme"].rstrip() + "\n\n## Detailed mathematical development\n\n"
        text += packet["summary"].strip() + "\n\n"
        for node in packet["nodes"]:
            description = render_node(node, sources)
            line = text.count("\n") + 1
            text += description + "\n\n"
            stage = {
                "id": node["id"], "owner": owner,
                "key": node["id"][len(owner) + 1:], "title": node["title"],
                "description": description, "requires": [], "consumers": [],
                "sourcePath": roadmap["sourcePath"], "sourceLine": line,
                "contextStartLine": line, "contextEndLine": line + description.count("\n"),
                "status": "source_decomposition_recorded", "sourceReviewStatus": "reviewed_expansion",
                "implementationStatus": "unchecked", "origin": roadmap.get("origin", "campaign"),
                "parentStageId": node["parentStageId"], "isLeaf": True,
                "expansion": {"kind": node["kind"], "sources": node["sources"],
                              "packet": owner, "statement": node["statement"],
                              "hypotheses": node["hypotheses"], "proofSteps": node["proofSteps"],
                              "acceptance": node["acceptance"],
                              # A node added during review has not itself been independently
                              # checked; the atlas says so rather than presenting it as reviewed.
                              "addedBy": node.get("addedBy"),
                              "reviewed": not node.get("addedBy")},
            }
            atlas["stages"].append(stage)
            stages[stage["id"]] = stage
            roadmap["stages"].append(stage["id"])
        if packet.get("gaps"):
            text += "## Further source work\n\n"
            for gap in packet["gaps"]:
                text += f"### {gap['title']}\n\n{gap['detail']}\n\n"
        roadmap["readme"] = text.rstrip() + "\n"
        rendered[roadmap["sourcePath"]] = roadmap["readme"]
        review = packet["review"]
        expansion.append({"roadmapId": owner, "status": packet["status"], "summary": packet["summary"].strip(),
                          "nodes": len(packet["nodes"]), "sources": list(sources.values()),
                          "coverage": packet.get("coverage", []), "gaps": packet.get("gaps", []),
                          "review": {"status": review["status"], "reviewer": review.get("reviewer"),
                                     "date": review.get("date"), "notes": review["notes"]}})

    endpoints = set(stages) | {item["id"] for item in atlas.get("external", [])}
    edges = {(edge["source"], edge["target"]): edge for edge in atlas["stageEdges"]}
    accepted = {packet["roadmapId"] for packet in packets}
    for packet in packets:
        sources = sources_by_map[packet["roadmapId"]]
        record = next(item for item in expansion if item["roadmapId"] == packet["roadmapId"])
        for link in packet.get("links", []):
            source, target = link["source"], link["target"]
            require_text(link.get("reason"), f"Dependency {source} -> {target}")
            if not link.get("sources"):
                raise ValueError(f"No source for dependency: {source} -> {target}")
            for reference in link["sources"]:
                if reference.get("sourceId") not in sources:
                    raise ValueError(f"Unknown dependency source: {source} -> {target}")
                require_text(reference.get("locator"), "Dependency locator")
            # A link may name a refinement of a roadmap whose packet is not yet
            # accepted. It is kept aside with its evidence, not silently dropped
            # and not asserted, until that packet is reviewed and promoted.
            missing = [item for item in (source, target) if item not in endpoints]
            if missing and all(pending_refinement(item, roadmaps, accepted) for item in missing):
                record.setdefault("deferredLinks", []).append({"source": source, "target": target,
                                                              "reason": link["reason"], "awaiting": missing})
                continue
            if missing or source == target:
                raise ValueError(f"Invalid dependency: {source} -> {target}")
            edge = edges.setdefault((source, target), {"source": source, "target": target})
            edge.setdefault("evidence", []).append({"reason": link["reason"],
                                                   "sources": link["sources"],
                                                   "packet": packet["roadmapId"]})
    acyclic(endpoints, edges, "mathematical prerequisites")
    atlas["stageEdges"] = list(edges.values())
    for source, target in edges:
        if target in stages and source not in stages[target].setdefault("requires", []):
            stages[target]["requires"].append(source)
        if source in stages and target not in stages[source].setdefault("consumers", []):
            stages[source]["consumers"].append(target)
    parent_ids = {stage.get("parentStageId") for stage in stages.values()}
    for stage in stages.values():
        stage["isLeaf"] = stage["id"] not in parent_ids
    map_edges = {(edge["source"], edge["target"]): edge for edge in atlas["edges"]}
    counts = defaultdict(int)
    for source, target in edges:
        a, b = all_owners.get(source), all_owners.get(target)
        if a and b and a != b:
            counts[a, b] += 1
    for pair, count in counts.items():
        edge = map_edges.setdefault(pair, {"source": pair[0], "target": pair[1], "kind": "stage_supported"})
        edge["stageCount"] = count
    atlas["edges"] = list(map_edges.values())
    for roadmap in roadmaps.values():
        roadmap["prerequisites"] = sorted({source for source, target in map_edges if target == roadmap["id"]})
        roadmap["consumers"] = sorted({target for source, target in map_edges if source == roadmap["id"]})
    atlas["decompositions"] = expansion
    atlas["meta"].update(stageCount=len(stages), stageEdgeCount=len(edges), edgeCount=len(map_edges),
                         sourceExpansionRoadmaps=len(packets), sourceExpansionNodes=len(new_nodes))
    return atlas, rendered


def merge_links(snapshot, packets):
    """Merge independently reviewed link packets (research/blueprint/PROTOCOL.md section 10).

    Each accepted link becomes a stage dependency with its quoted evidence; roadmap
    links are recomputed by merge_decompositions. A link that duplicates a recorded
    one adds its evidence; a link that would create a cycle is refused. A link to a
    layer not in the atlas (a roadmap still to be promoted) waits in deferredLinks.
    """
    atlas = deepcopy(snapshot)
    stages = {stage["id"]: stage for stage in atlas["stages"]}
    edges = {(edge["source"], edge["target"]): edge for edge in atlas["stageEdges"]}
    merged = 0
    for packet in packets:
        review = packet.get("review") or {}
        if review.get("status") != "accepted" or not review.get("reviewer"):
            raise ValueError(f"Link packet without an accepted review: {packet.get('roadmapId')}")
        for link in packet.get("links", []):
            source, target = link["source"], link["target"]
            if source == target:
                raise ValueError(f"Invalid reviewed link: {source} -> {target}")
            missing = [end for end in (source, target) if end not in stages]
            if missing:
                atlas.setdefault("deferredLinks", []).append({"source": source, "target": target,
                                                              "packet": packet["roadmapId"], "awaiting": missing})
                continue
            require_text(link.get("reason"), f"Link {source} -> {target}")
            evidence = link.get("evidence") or []
            if len({item.get("stageId") for item in evidence} & {source, target}) < 2:
                raise ValueError(f"Link without two-sided evidence: {source} -> {target}")
            edge = edges.setdefault((source, target), {"source": source, "target": target, "kind": "reviewed_link"})
            edge.setdefault("evidence", []).append({"reason": link["reason"], "confidence": link.get("confidence"),
                                                   "quotes": evidence, "packet": packet["roadmapId"],
                                                   "reviewer": review.get("reviewer")})
            merged += 1
    acyclic(set(stages) | {item["id"] for item in atlas.get("external", [])}, edges, "reviewed roadmap links")
    atlas["stageEdges"] = list(edges.values())
    for source, target in edges:
        if target in stages and source not in stages[target].setdefault("requires", []):
            stages[target]["requires"].append(source)
        if source in stages and target not in stages[source].setdefault("consumers", []):
            stages[source]["consumers"].append(target)
    atlas.setdefault("meta", {})["reviewedLinks"] = merged
    return atlas
