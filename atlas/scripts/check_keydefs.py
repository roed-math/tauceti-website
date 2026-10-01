#!/usr/bin/env python3
"""Check key-definition surveys against research/blueprint/PROTOCOL.md, section 19.

Usage:
  python3 scripts/check_keydefs.py research/blueprint/keydefs/KEYDEF-<area>.json [...]

A survey lists the key definitions of one area: notions that at least two of
the atlas's papers need and the libraries lack, each with the catalogue items
that show the papers need it, its owners, what the libraries have, its
dependencies, its size and a sample API; and it accounts for every item of its
input. Library claims are checked against $TAUCETI_BASELINE/declarations.tsv
when it exists (TAUCETI_BASELINE defaults to the worker baseline directory), and
for form otherwise. Errors make the exit status 1; warnings belong in the report.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_blueprint import load_index  # noqa: E402

API_KINDS = {"example", "counterexample", "theorem", "compatibility"}
API_MIN = 5
SIZES = {"M", "L", "XL"}
EVIDENCE_KINDS = {"definition", "construction"}
REVIEW_STATUSES = {"accepted", "needs_changes", "rejected"}
LIBRARY_REF = re.compile(r"^(mathlib|tauceti):[^\s:][^\s]*$")
TAUCETI_LAYER = re.compile(r"^tauceti:TauCetiRoadmap/[A-Za-z0-9_]+(?:#\S+)?$")
SLUG = re.compile(r"^[a-z0-9]+/[a-z0-9]+(?:-[a-z0-9]+)*$")
DEFINE_WORDS = 20
STATEMENT_WORDS = 6


def text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def words(value) -> int:
    return len(str(value or "").split())


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def catalogue(root: Path) -> dict:
    """{catalogue item id: (paper id, kind)} over data/items/<n>.json."""
    found = {}
    for path in (root / "data" / "items").glob("[0-9]*.json"):
        data = load_json(path)
        for item in data.get("items", []):
            found[item["id"]] = (data.get("paper"), item.get("kind"))
    return found


def layers(root: Path) -> dict:
    """{stage id: owner roadmap} for the layers a key definition may name as an owner."""
    found = {stage["id"]: stage["owner"] for stage in load_json(root / "data" / "atlas.json")["stages"]}
    for folder in (root / "research" / "blueprint" / "roadmaps", root / "data" / "blueprints" / "roadmaps"):
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            roadmap = load_json(path)
            for stage in roadmap.get("stages", []):
                if stage.get("key"):
                    found.setdefault(f"{roadmap['id']}:{stage['key']}", roadmap["id"])
    return found


def surveys(root: Path, job: str) -> list:
    """Every other survey, pending or promoted: [(file, data)]. A promoted copy of this job is not another survey."""
    found = []
    for folder in (root / "research" / "blueprint" / "keydefs", root / "data" / "keydefs"):
        for path in sorted(folder.glob("KEYDEF-*.json")) if folder.is_dir() else []:
            try:
                data = load_json(path)
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("job") != job:
                found.append((str(path.relative_to(root)), data))
    return found


def cycle(graph: dict) -> list:
    """One dependency cycle among the key definitions, or []."""
    state, stack = {}, []

    def visit(node):
        state[node] = 1
        stack.append(node)
        for nxt in graph.get(node, ()):
            if state.get(nxt) == 1:
                return stack[stack.index(nxt):] + [nxt]
            if nxt not in state:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return []

    for node in sorted(graph):
        if node not in state:
            found = visit(node)
            if found:
                return found
    return []


def check(path: Path, root: Path = ROOT, index=None) -> tuple:
    """(errors, warnings) for one survey. index: the declaration names of the pinned libraries, or None."""
    errors, warnings = [], []
    try:
        data = load_json(path)
    except (OSError, ValueError) as exc:
        return [f"cannot read the survey: {exc}"], []
    if not isinstance(data, dict):
        return ["the survey must be a JSON object"], []
    job = Path(path).stem
    if data.get("job") != job:
        errors.append(f"job is {data.get('job')!r}; it must be the file name, {job!r}")
    if data.get("protocol") != "keydef-v1":
        errors.append('protocol must be "keydef-v1"')
    areas = {galaxy["id"] for galaxy in load_json(root / "data" / "galaxies.json")["galaxies"]}
    area = data.get("area")
    if area not in areas:
        errors.append(f"area {area!r} is not an area of data/galaxies.json")
    elif not re.match(rf"^KEYDEF-{re.escape(area)}(?:-[0-9]+)?$", job):
        errors.append(f"a survey of the area {area} is named KEYDEF-{area} or KEYDEF-{area}-<n>")
    status = data.get("status")
    if status not in ("partial", "complete"):
        errors.append('status must be "partial" or "complete"')
    baseline = data.get("baseline")
    if not (isinstance(baseline, dict) and text(baseline.get("tauceti")) and text(baseline.get("mathlib"))):
        errors.append("baseline must record the Tau Ceti and Mathlib commits the library claims were read at")
    if status == "partial" and not (isinstance(data.get("remaining"), list) and data["remaining"]):
        errors.append("a partial survey lists what a continuation must do in `remaining`")

    items = catalogue(root)
    owners_known = layers(root)
    roadmaps_known = set(owners_known.values()) | {roadmap["id"] for roadmap in load_json(root / "data" / "atlas.json").get("roadmaps", [])}
    queue_path = root / "research" / "blueprint" / "queue.json"
    if queue_path.exists():
        roadmaps_known |= {rid for job in load_json(queue_path).get("jobs", []) if job.get("kind") == "design" for rid in job.get("roadmapIds") or []}
    others = surveys(root, job)
    other_ids, other_claims, graph = {}, {}, {}
    for where, survey in others:
        for entry in survey.get("definitions") or []:
            if isinstance(entry, dict) and text(entry.get("id")):
                other_ids.setdefault(entry["id"], where)
                graph.setdefault(entry["id"], [ref for ref in entry.get("dependsOn") or [] if isinstance(ref, str)])
                for paper in entry.get("papers") or []:
                    for item in (paper.get("items") or []) if isinstance(paper, dict) else []:
                        other_claims.setdefault(item, entry["id"])

    def known_items(where, values, field):
        if not isinstance(values, list) or not values:
            errors.append(f"{where}: {field} must be a non-empty list of catalogue item ids")
            return []
        good = []
        for item in values:
            if item in items:
                good.append(item)
            else:
                errors.append(f"{where}: {item!r} is not an item of the paper catalogue (data/items)")
        return good

    definitions = data.get("definitions")
    if not isinstance(definitions, list):
        errors.append("definitions must be a list")
        definitions = []
    ids, accounted = {}, set()
    for n, entry in enumerate(definitions, 1):
        if not isinstance(entry, dict):
            errors.append(f"definition {n}: must be an object")
            continue
        eid = entry.get("id")
        where = f"definition {n} ({eid})" if text(eid) else f"definition {n}"
        if not (isinstance(eid, str) and SLUG.match(eid)):
            errors.append(f"{where}: id must be <area>/<slug>, in lower case with hyphens")
        elif area in areas and not eid.startswith(area + "/"):
            errors.append(f"{where}: id must start with the area, {area}/")
        elif eid in ids:
            errors.append(f"{where}: id used twice in this survey")
        elif eid in other_ids:
            errors.append(f"{where}: id already used in {other_ids[eid]}")
        if text(eid):
            ids[eid] = entry
        if not (text(entry.get("name")) and len(entry["name"]) <= 80):
            errors.append(f"{where}: name must be a noun phrase of at most 80 characters")
        if not (text(entry.get("short")) and len(entry["short"]) <= 60):
            errors.append(f"{where}: short (its planet label) must be at most 60 characters")
        if words(entry.get("define")) < DEFINE_WORDS:
            errors.append(f"{where}: define must say what to define, in at least {DEFINE_WORDS} words")
        library = entry.get("library")
        if not isinstance(library, dict) or not isinstance(library.get("has"), list) or not text(library.get("missing")):
            errors.append(f"{where}: library needs `has` (a list of declarations) and `missing` (what the libraries lack)")
        else:
            for ref in library["has"]:
                if not (isinstance(ref, str) and LIBRARY_REF.match(ref)):
                    errors.append(f"{where}: library reference {ref!r} must be mathlib:<name> or tauceti:<name>")
                elif index is not None and tuple(ref.split(":", 1)) not in index:
                    errors.append(f"{where}: {ref} is not a declaration at the pinned commits")
        papers = entry.get("papers")
        if not isinstance(papers, list) or not papers:
            errors.append(f"{where}: papers must list the papers that need it, with catalogue items")
            papers = []
        distinct = set()
        for paper in papers:
            if not (isinstance(paper, dict) and text(paper.get("paper"))):
                errors.append(f"{where}: each paper is {{\"paper\": \"PAPER-<id>\", \"items\": [...]}}")
                continue
            for item in known_items(where, paper.get("items"), f"the items of {paper['paper']}"):
                owner_paper, kind = items[item]
                if owner_paper != paper["paper"]:
                    errors.append(f"{where}: {item} is an item of {owner_paper}, not of {paper['paper']}")
                elif kind not in EVIDENCE_KINDS:
                    errors.append(f"{where}: {item} is a {kind}; cite the definitions and constructions that are instances")
                else:
                    distinct.add(owner_paper)
                    accounted.add(item)
                    if item in other_claims:
                        warnings.append(f"{where}: {item} is also cited by {other_claims[item]}")
        if len(distinct) < 2:
            errors.append(f"{where}: a key definition is needed by at least two papers; the items cited show {len(distinct)}")
        owners = entry.get("owners")
        if not isinstance(owners, list):
            errors.append(f"{where}: owners must be a list of layer ids (empty when nothing plans it)")
            owners = []
        roadmaps = set()
        for owner in owners:
            if isinstance(owner, str) and owner.startswith("tauceti:"):
                errors.append(f"{where}: {owner} is a Tau Ceti layer; a notion Tau Ceti owns goes under `elsewhere`")
            elif owner not in owners_known:
                errors.append(f"{where}: owner {owner!r} is not a layer of the atlas or of a new roadmap")
            else:
                roadmaps.add(owners_known[owner])
        if not owners:
            warnings.append(f"{where}: nothing plans it yet (a gap)")
        elif len(roadmaps) > 1:
            warnings.append(f"{where}: planned in {len(roadmaps)} roadmaps ({', '.join(sorted(roadmaps))}), a duplication")
        depends = entry.get("dependsOn")
        if not isinstance(depends, list):
            errors.append(f"{where}: dependsOn must be a list")
            depends = []
        if text(eid):
            graph[eid] = [ref for ref in depends if isinstance(ref, str) and not ref.startswith("tauceti:")]
        for ref in depends:
            if not isinstance(ref, str):
                errors.append(f"{where}: dependsOn entries are key definition ids or Tau Ceti layers")
            elif ref.startswith("tauceti:"):
                if not TAUCETI_LAYER.match(ref):
                    errors.append(f"{where}: {ref!r} must be tauceti:TauCetiRoadmap/<roadmap>#<layer>")
            elif ref == eid:
                errors.append(f"{where}: it depends on itself")
        planned_by = entry.get("plannedBy")
        if planned_by is not None:
            if owners:
                errors.append(f"{where}: plannedBy is for a key definition no layer plans; this one has owners")
            elif planned_by not in roadmaps_known:
                errors.append(f"{where}: plannedBy {planned_by!r} is not a roadmap of the atlas, a new roadmap or a queued design")
        if entry.get("size") not in SIZES:
            errors.append(f"{where}: size must be M, L or XL")
        api = entry.get("api")
        if not isinstance(api, list) or len(api) < API_MIN:
            errors.append(f"{where}: the sample API needs at least {API_MIN} statements")
            api = api if isinstance(api, list) else []
        kinds = set()
        for k, item in enumerate(api, 1):
            if not (isinstance(item, dict) and item.get("kind") in API_KINDS and words(item.get("statement")) >= STATEMENT_WORDS):
                errors.append(f"{where}: API statement {k} needs a kind ({', '.join(sorted(API_KINDS))}) and a statement of at least {STATEMENT_WORDS} words")
            else:
                kinds.add(item["kind"])
        for needed in ("example", "counterexample", "theorem"):
            if api and needed not in kinds:
                errors.append(f"{where}: the sample API needs at least one {needed}")
    for eid, entry in ids.items():
        for ref in entry.get("dependsOn") or []:
            if isinstance(ref, str) and not ref.startswith("tauceti:") and ref != eid and ref not in ids and ref not in other_ids:
                errors.append(f"definition {eid}: depends on {ref!r}, which is no key definition of any survey")
    found = cycle({node: [ref for ref in refs if ref in graph] for node, refs in graph.items()})
    if found:
        errors.append("the dependencies form a cycle: " + " -> ".join(found))

    for field in ("elsewhere", "reserve"):
        entries = data.get(field)
        if not isinstance(entries, list):
            errors.append(f"{field} must be a list")
            continue
        for n, entry in enumerate(entries, 1):
            where = f"{field} {n}"
            if not isinstance(entry, dict) or not text(entry.get("name")):
                errors.append(f"{where}: needs a name")
                continue
            accounted.update(known_items(f"{where} ({entry['name']})", entry.get("items"), "items"))
            if field == "elsewhere":
                owner = entry.get("owner")
                if not (isinstance(owner, str) and (owner in other_ids or owner in ids or owner in owners_known or TAUCETI_LAYER.match(owner))):
                    errors.append(f"{where} ({entry['name']}): owner must be a key definition id, an atlas layer or a Tau Ceti layer")
            elif not text(entry.get("reason")):
                errors.append(f"{where} ({entry['name']}): says which criterion it fails, and why")
    routine = data.get("routine")
    if not isinstance(routine, list):
        errors.append("routine must be a list of catalogue item ids")
    else:
        for item in routine:
            if item in items:
                accounted.add(item)
            else:
                errors.append(f"routine: {item!r} is not an item of the paper catalogue (data/items)")

    input_path = root / "research" / "blueprint" / "keydefs" / "inputs" / f"{job}.json"
    if input_path.exists():
        wanted = [item["id"] for item in load_json(input_path).get("items", [])]
        left = [item for item in wanted if item not in accounted]
        if left and status == "complete":
            errors.append(f"{len(left)} of the {len(wanted)} input items are not accounted for, among them " + ", ".join(left[:8]))
        elif left:
            warnings.append(f"{len(left)} of the {len(wanted)} input items are still to account for")
    else:
        errors.append(f"no input for this survey: {input_path.relative_to(root)}")

    review = data.get("review")
    if review is not None:
        if not (isinstance(review, dict) and review.get("status") in REVIEW_STATUSES and text(review.get("reviewer")) and text(review.get("date"))):
            errors.append("review must record status (accepted, needs_changes or rejected), reviewer and date")
    return errors, warnings


def main(argv=None) -> int:
    paths = sys.argv[1:] if argv is None else argv
    if not paths:
        print(__doc__)
        return 2
    base = os.environ.get("TAUCETI_BASELINE", "/tmp/tauceti-workers/baseline")
    names, _ = load_index(str(Path(base) / "declarations.tsv"))
    if names is None:
        print(f"warning: no declaration index at {base}/declarations.tsv; library claims checked for form only", file=sys.stderr)
    status = 0
    for path in paths:
        errors, warnings = check(Path(path), ROOT, names)
        for message in warnings:
            print(f"WARNING {path}: {message}")
        for message in errors:
            print(f"ERROR {path}: {message}")
        print(f"{path}: {len(errors)} error(s), {len(warnings)} warning(s)")
        status = 1 if errors else status
    return status


if __name__ == "__main__":
    sys.exit(main())
