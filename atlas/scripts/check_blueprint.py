#!/usr/bin/env python3
"""Check blueprint packets against research/blueprint/PROTOCOL.md.

Usage:
  python3 scripts/check_blueprint.py research/blueprint/packets/X.json [...] [--index PATH] [--json]

Errors make the exit status 1; warnings do not. The declaration index defaults to
$TAUCETI_BASELINE/declarations.tsv (TAUCETI_BASELINE defaults to the worker
baseline directory); without it, baseline references are checked for form only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from source_issues import check_issues  # noqa: E402
KINDS = {"definition", "construction", "lemma", "theorem", "comparison", "application"}
COVERAGE = {"not_read", "partial", "source_decomposed", "closed"}
ROLES = {"constructor", "data", "projection", "extensionality", "characterisation", "simp", "instance",
         "structure", "functoriality", "universal-property", "compatibility", "equivalence", "coercion",
         "relation", "example", "other"}
BASE_REF = re.compile(r"^(mathlib|tauceti):(\S+)$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
PRIVATE = re.compile(r"/Users/|/private/|/Volumes/|file://|C:\\\\Users")
LEAN_CODE = re.compile(r"```\s*lean|\bsorry\b")


def text(value):
    return isinstance(value, str) and value.strip() != ""


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_index(path):
    names, suffixes = {}, defaultdict(set)
    if not path or not Path(path).exists():
        return None, None
    with open(path, encoding="utf-8") as handle:
        next(handle, None)
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            library, name = parts[0], parts[1]
            names.setdefault((library, name), (parts[2], parts[3], parts[4]))
            pieces = name.split(".")
            for i in range(1, len(pieces)):
                suffixes[(library, ".".join(pieces[i:]))].add(name)
    return names, suffixes


RETIRED_STAGES = set()
# Layers an accepted restructuring proposal drops (PROTOCOL.md section 15): closed without nodes,
# since the layers the proposal names supply them.
DROPPED_STAGES = set()


def world():
    """Ids a prerequisite may resolve to, outside the packet being checked."""
    atlas = load_json(ROOT / "data" / "atlas.json")
    stages = {s["id"]: s["owner"] for s in atlas["stages"]}
    retired_path = ROOT / "data" / "roadmap-retirements.json"
    retired = set(load_json(retired_path)["roadmaps"]) if retired_path.exists() else set()
    RETIRED_STAGES.clear()
    RETIRED_STAGES.update(sid for sid, owner in stages.items() if owner in retired)
    roadmaps = {r["id"] for r in atlas["roadmaps"]}
    nodes = {}
    for path in sorted((ROOT / "data" / "decompositions").glob("*.json")):
        packet = load_json(path)
        for node in packet.get("nodes", []):
            nodes[node["id"]] = ("integrated", packet["roadmapId"], path.name)
    blueprints = {}
    for path in sorted((ROOT / "research" / "blueprint" / "packets").glob("*.json")):
        try:
            packet = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        blueprints[path.resolve()] = packet
        for node in packet.get("nodes", []):
            nodes.setdefault(node.get("id"), ("blueprint", packet.get("roadmapId"), path.name))
    for path in sorted((ROOT / "research" / "blueprint" / "roadmaps").glob("*.json")):
        try:
            roadmap = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        roadmaps.add(roadmap.get("id"))
        for stage in roadmap.get("stages", []):
            stages[f"{roadmap.get('id')}:{stage.get('key')}"] = roadmap.get("id")
    reserved_path = ROOT / "research" / "blueprint" / "reserved-ids.json"
    reserved = load_json(reserved_path) if reserved_path.exists() else {}
    DROPPED_STAGES.clear()
    for path in sorted((ROOT / "research" / "blueprint" / "restructure").glob("RS-*.result.json")):
        try:
            proposal = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if (proposal.get("review") or {}).get("status") == "accepted":
            DROPPED_STAGES.update(sid for sid, layer in (proposal.get("layers") or {}).items() if layer.get("action") == "drop")
    return atlas, stages, roadmaps, nodes, blueprints, reserved


def layer_of(node, own, own_stages):
    """The layer a node belongs to, following sub-structure up to a stage."""
    parent, seen = node.get("parentStageId"), set()
    while parent in own and parent not in seen:
        seen.add(parent)
        parent = own[parent].get("parentStageId")
    return parent if parent in own_stages else (node.get("realises") or [None])[0]


def check(path, index, context):
    atlas, stages, roadmaps, nodes, blueprints, reserved = context
    errors, warnings = [], []
    raw = Path(path).read_text(encoding="utf-8")
    if PRIVATE.search(raw):
        errors.append("private filesystem path in packet")
    try:
        packet = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"], [], {}
    if LEAN_CODE.search(raw):
        errors.append("Lean code block or `sorry` in packet text")
    rid = packet.get("roadmapId")
    if rid not in roadmaps:
        errors.append(f"unknown roadmap {rid!r}")
    if packet.get("protocol") != "blueprint-v1":
        errors.append("protocol must be 'blueprint-v1'")
    if packet.get("status") not in ("partial", "closed"):
        errors.append("status must be 'partial' or 'closed'")
    if not text(packet.get("summary")):
        errors.append("missing summary")
    own_stages = {sid for sid, owner in stages.items() if owner == rid}
    scope = packet.get("scope") or sorted(own_stages)
    for sid in scope:
        if sid not in own_stages:
            errors.append(f"scope names a stage outside the roadmap: {sid}")

    baseline = packet.get("baseline") or {}
    for key in ("tauceti", "mathlib"):
        if not HEX40.match(str(baseline.get(key, ""))):
            errors.append(f"baseline.{key} must be a 40-hex commit")
    names, suffixes = index if index else (None, None)
    declared = {}
    for item in baseline.get("declarations", []):
        ref = item.get("ref", "")
        m = BASE_REF.match(ref)
        if not m:
            errors.append(f"malformed baseline reference {ref!r}")
            continue
        for key in ("module", "provides"):
            if not text(item.get(key)):
                errors.append(f"baseline {ref}: missing {key}")
        declared[ref] = item
        if names is not None:
            library, name = m.group(1), m.group(2)
            if (library, name) not in names:
                hits = suffixes.get((library, name), set())
                if hits:
                    warnings.append(f"baseline {ref} found only as {sorted(hits)[:3]} in the index; use the full name")
                else:
                    errors.append(f"baseline {ref} not found in the pinned {library} index")

    sources = {}
    for source in packet.get("sources", []):
        sid = source.get("id")
        for key in ("id", "title", "authors", "edition"):
            if not text(source.get(key)):
                errors.append(f"source {sid}: missing {key}")
        if source.get("url") and not re.match(r"^https?://", source["url"]):
            errors.append(f"source {sid}: url must be http(s)")
        if source.get("sha256") and not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]):
            errors.append(f"source {sid}: sha256 must be 64 lowercase hex characters")
        if not source.get("readSections"):
            errors.append(f"source {sid}: no readSections")
        if sid in sources:
            errors.append(f"duplicate source id {sid}")
        sources[sid] = source

    own = {}
    for node in packet.get("nodes", []):
        nid = node.get("id")
        if not text(nid) or not nid.startswith(f"{rid}:"):
            errors.append(f"node id {nid!r} must start with '{rid}:'")
            continue
        if nid in own:
            errors.append(f"duplicate node {nid}")
        other = nodes.get(nid)
        if other and other[0] == "blueprint" and other[2] != Path(path).name and other[1] == rid:
            errors.append(f"node {nid} also appears in {other[2]}")
        if nid in stages:
            errors.append(f"node {nid} reuses an atlas stage id")
        own[nid] = node
    edges = []
    counts = Counter()
    api_items = 0
    unit_tests = 0
    planets = Counter()
    resolved = Counter()
    for nid, node in own.items():
        kind = node.get("kind")
        counts[kind] += 1
        if kind not in KINDS:
            errors.append(f"{nid}: invalid kind {kind!r}")
        for key in ("title", "statement", "parentStageId"):
            if not text(node.get(key)):
                errors.append(f"{nid}: missing {key}")
        parent = node.get("parentStageId")
        if parent and parent not in own_stages and parent not in own and not (
                parent in nodes and nodes[parent][1] == rid):
            errors.append(f"{nid}: parent {parent} is not a stage or node of {rid}")
        for key in ("hypotheses", "proofSteps", "acceptance", "prerequisites"):
            if not isinstance(node.get(key), list):
                errors.append(f"{nid}: {key} must be a list")
        if not node.get("proofSteps"):
            errors.append(f"{nid}: proofSteps is empty")
        if not node.get("acceptance"):
            errors.append(f"{nid}: acceptance is empty")
        if node.get("implementationStatus") != "unchecked":
            errors.append(f"{nid}: implementationStatus must be 'unchecked'")
        for real in node.get("realises", []) or []:
            if real not in own_stages:
                errors.append(f"{nid}: realises unknown stage {real}")
        if not node.get("sources"):
            errors.append(f"{nid}: no sources")
        for ref in node.get("sources", []) or []:
            if ref.get("sourceId") not in sources:
                errors.append(f"{nid}: unknown sourceId {ref.get('sourceId')!r}")
            for key in ("locator", "excerpt", "match"):
                if not text(ref.get(key)):
                    errors.append(f"{nid}: source reference missing {key}")
            if len(ref.get("excerpt") or "") > 400:
                warnings.append(f"{nid}: excerpt longer than 400 characters")
        if kind in ("definition", "construction"):
            api = node.get("api") or []
            if not api:
                errors.append(f"{nid}: a {kind} needs an api outline")
            elif len(api) < 3:
                warnings.append(f"{nid}: api outline has only {len(api)} item(s)")
            for item in api:
                api_items += 1
                if not text(item.get("name")) or not text(item.get("statement")):
                    errors.append(f"{nid}: api item needs name and statement")
                if item.get("role") not in ROLES:
                    errors.append(f"{nid}: api item {item.get('name')!r} has unknown role {item.get('role')!r}")
            # The API is derived from use: where and how the object is used.
            uses = node.get("uses") or []
            if not uses:
                errors.append(f"{nid}: a {kind} needs its uses (where and how it is used)")
            elif any(not text(use.get("where")) or not text(use.get("how")) for use in uses):
                errors.append(f"{nid}: each use needs 'where' and 'how'")
            # Unit tests pin the definition down: a wrong definition fails one of them.
            tests = node.get("tests") or []
            if len(tests) < 3:
                errors.append(f"{nid}: a {kind} needs at least 3 unit tests")
            for item in tests:
                unit_tests += 1
                if not text(item.get("name")) or not text(item.get("statement")):
                    errors.append(f"{nid}: unit test {item.get('name')!r} needs a name and a statement")
        # Planets are what the atlas shows inside a layer: key definitions,
        # central constructions and named theorems, with short names.
        planet = node.get("planet")
        if planet is not None:
            if kind not in ("definition", "construction", "theorem"):
                errors.append(f"{nid}: only definitions, constructions and theorems can be planets")
            name = planet.get("name") if isinstance(planet, dict) else None
            if not text(name) or len(name) > 60:
                errors.append(f"{nid}: a planet needs a name of at most 60 characters")
            planets[layer_of(node, own, own_stages)] += 1
        for pre in node.get("prerequisites", []) or []:
            if pre in own:
                edges.append((pre, nid)); resolved["node (this packet)"] += 1
            elif BASE_REF.match(str(pre)):
                resolved["baseline"] += 1
                if pre not in declared:
                    errors.append(f"{nid}: baseline prerequisite {pre} is not listed in baseline.declarations")
            elif pre in nodes:
                resolved[f"node ({nodes[pre][0]})"] += 1
            elif pre in stages:
                resolved["stage"] += 1
                if pre in RETIRED_STAGES:
                    warnings.append(f"{nid}: {pre} belongs to a retired roadmap (data/roadmap-retirements.json); cite the library or a covering roadmap instead")
                if stages[pre] != rid and not any(r.get("supplier") == pre for r in packet.get("requests", [])):
                    warnings.append(f"{nid}: uses another roadmap's stage {pre} without a request entry")
                if packet.get("status") == "closed":
                    errors.append(f"{nid}: a closed packet cannot rest on stage {pre}")
            elif pre in reserved:
                resolved["reserved"] += 1
                warnings.append(f"{nid}: prerequisite {pre} is reserved for {reserved[pre].get('job')} and not yet written")
            else:
                errors.append(f"{nid}: unresolved prerequisite {pre!r}")
    for layer, count in sorted(planets.items(), key=lambda kv: str(kv[0])):
        if count > 6:
            errors.append(f"{layer}: {count} planets; a layer shows at most 6")
    # acyclicity within the packet
    graph = defaultdict(list)
    for a, b in edges:
        graph[a].append(b)
    state = {}
    def visit(v, trail):
        state[v] = 1
        for w in graph[v]:
            if state.get(w) == 1:
                errors.append("prerequisite cycle: " + " -> ".join(trail + [w]))
                return
            if not state.get(w):
                visit(w, trail + [w])
        state[v] = 2
    sys.setrecursionlimit(100000)
    for v in list(own):
        if not state.get(v):
            visit(v, [v])
    realised = {real for node in own.values() for real in (node.get("realises") or [])}
    covered = {}
    for record in packet.get("coverage", []):
        sid = record.get("stageId")
        if sid not in scope:
            errors.append(f"coverage record for {sid} outside scope")
            continue
        if sid in covered:
            errors.append(f"duplicate coverage record for {sid}")
        covered[sid] = record
        if record.get("status") not in COVERAGE:
            errors.append(f"coverage {sid}: invalid status {record.get('status')!r}")
        if record.get("status") in ("closed", "source_decomposed") and record.get("remaining"):
            errors.append(f"coverage {sid}: {record.get('status')} with remaining work")
        if record.get("status") == "closed" and sid not in realised and sid not in DROPPED_STAGES:
            errors.append(f"coverage {sid}: closed but no node realises it")
    for sid in scope:
        if sid not in covered:
            errors.append(f"no coverage record for stage {sid}")
    errors += check_issues(packet.get("sourceIssues"), str(rid))
    for gap in packet.get("gaps", []):
        if not text(gap.get("title")) or not text(gap.get("detail")):
            errors.append("gap needs title and detail")
    for request in packet.get("requests", []):
        if request.get("supplier") not in stages and request.get("supplier") not in nodes:
            errors.append(f"request names unknown supplier {request.get('supplier')!r}")
        if not text(request.get("need")):
            errors.append("request needs a precise 'need'")
    if packet.get("status") == "closed":
        if packet.get("gaps") or packet.get("requests"):
            errors.append("closed packet has gaps or requests")
        if any(covered.get(s, {}).get("status") != "closed" for s in scope):
            errors.append("closed packet has stages that are not closed")
    summary = {"packet": str(path), "roadmap": rid, "status": packet.get("status"), "nodes": len(own),
               "kinds": dict(counts), "apiItems": api_items, "unitTests": unit_tests, "planets": sum(planets.values()),
               "baselineDeclarations": len(declared),
               "prerequisites": dict(resolved), "gaps": len(packet.get("gaps", [])),
               "requests": len(packet.get("requests", [])), "stagesInScope": len(scope),
               "stagesClosed": sum(1 for s in scope if covered.get(s, {}).get("status") == "closed")}
    return errors, warnings, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("packets", nargs="+")
    default_base = os.environ.get("TAUCETI_BASELINE", "/tmp/tauceti-workers/baseline")
    parser.add_argument("--index", default=str(Path(default_base) / "declarations.tsv"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    index = load_index(args.index)
    if index[0] is None:
        print(f"warning: no declaration index at {args.index}; baseline references checked for form only", file=sys.stderr)
        index = None
    context = world()
    failed = False
    reports = []
    for path in args.packets:
        errors, warnings, summary = check(path, index, context)
        failed |= bool(errors)
        reports.append({"summary": summary, "errors": errors, "warnings": warnings})
        if not args.json:
            print(f"== {path}")
            print(json.dumps(summary, ensure_ascii=False))
            for e in errors[:200]:
                print("ERROR  ", e)
            if len(errors) > 200:
                print(f"ERROR   ... {len(errors) - 200} more")
            for w in warnings[:80]:
                print("warning", w)
            print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=1))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
