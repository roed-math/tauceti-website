#!/usr/bin/env python3
"""Tau Ceti's own progress, as the Progress page of the Tau Ceti site reports it.

The site's Progress board publishes its data as static/progress.json: for every
Tau Ceti roadmap, each layer's state from its latest STATUS.md report (done,
partial, untouched or unassessed), a one-line note of what remains, and its
pull-request activity. This module keeps a copy (data/tauceti-progress.json)
and lays it over the atlas's own snapshot: roadmaps match by name (a roadmap
since moved to Completed/ matches its Completed/ row) and layers by key. An
unassessed layer has no status at all, and a roadmap the board no longer
reports keeps its snapshot.

A roadmap Tau Ceti accepts appears on the board before it appears in the
atlas's snapshot. Its README is kept too (data/tauceti-new-roadmaps.json), and
the build adds it to the map from that README and the board's list of its
layers. It goes in the area a maintainer chose for it
(data/tauceti-placements.json); else in the area or field its title names;
else in the area that holds more of the Tau Ceti roadmaps its README names than
any other; and not at all until one of those says where it belongs. The title
comes before the README because a README also names the roadmaps it builds on,
which often lie in other areas.

Usage: tauceti_progress.py --fetch   download the board's data and new roadmaps' READMEs into data/
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://taucetiproject.github.io/TauCeti/static/progress.json"
PAGE = "https://taucetiproject.github.io/TauCeti/progress/"
REPOSITORY = "https://github.com/TauCetiProject/TauCetiRoadmap/blob/main/"
COPY = ROOT / "data" / "tauceti-progress.json"
READMES = ROOT / "data" / "tauceti-new-roadmaps.json"
PLACEMENTS = ROOT / "data" / "tauceti-placements.json"
RAW = "https://raw.githubusercontent.com/TauCetiProject/TauCetiRoadmap/main/"
STATUS = {"done": "complete", "partial": "in_progress", "untouched": "planned"}


def name(roadmap_id: str) -> str:
    return roadmap_id.replace("tauceti:", "").replace("TauCetiRoadmap/", "")


def field(row: dict, key: str, default):
    """The board stores lists and objects as JSON text; read either form."""
    value = row.get(key)
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return default
    return default if value is None else value


def counts(progress: dict) -> dict:
    """Layers by state over every row of the board, as the Progress page counts them."""
    total = defaultdict(int)
    for row in progress.get("rows", []):
        for state in field(row, "states", []):
            total[state] += 1
    result = {state: total[state] for state in ("done", "partial", "untouched", "unassessed")}
    result["total"] = sum(total.values())
    return result


def matches(atlas: dict, progress: dict) -> dict:
    """Our Tau Ceti roadmap id -> its row on the board."""
    rows = {name(row["id"]): row for row in progress.get("rows", [])}
    found = {}
    for roadmap in atlas["roadmaps"]:
        if roadmap.get("origin") != "tauceti":
            continue
        key = name(roadmap["id"])
        row = rows.get(key) or rows.get("Completed/" + key.split("/")[-1])
        if row:
            found[roadmap["id"]] = row
    return found


def apply(atlas: dict, progress: dict) -> dict:
    """Overlay the board's layer states on atlas["progress"]; keep its notes and activity in atlas["taucetiProgress"]."""
    overlay = atlas.setdefault("progress", {})
    stages_overlay, roadmaps_overlay = overlay.setdefault("stages", {}), overlay.setdefault("roadmaps", {})
    children = defaultdict(list)
    for stage in atlas["stages"]:
        if stage.get("parentStageId") and not stage.get("expansion"):
            children[stage["parentStageId"]].append(stage["id"])

    def leaves(stage_id):
        below = children.get(stage_id)
        return [leaf for child in below for leaf in leaves(child)] if below else [stage_id]

    by_key = defaultdict(list)
    for stage in atlas["stages"]:
        if not stage.get("expansion"):
            by_key[(stage.get("owner"), stage.get("key"))].append(stage)
    date = str(progress.get("exported_at", ""))[:10]
    info = {"exportedAt": progress.get("exported_at"), "page": PAGE, "recentDays": progress.get("recent_days"), "roadmaps": {}, "remaining": {}, "unplaced": [],
            "counts": counts(progress)}
    matched = matches(atlas, progress)
    for roadmap_id, row in matched.items():
        assessment = field(row, "assessment", {}) or {}
        remaining = assessment.get("remaining") or {}
        readme = row.get("readme") if isinstance(row.get("readme"), str) else ""
        status_path = readme[:-len("README.md")] + "STATUS.md" if readme.endswith("README.md") else None
        report = field(row, "status", {}) or {}
        frontier = [item["name"] for item in report.get("frontier", []) if isinstance(item, dict) and item.get("name")]
        basis = f"Tau Ceti Progress page, from the roadmap's latest report (data of {date})."
        if row.get("completed"):
            # Archived as complete by the maintainers: that is final, whatever a report says of a layer.
            done = f"Tau Ceti's maintainers archived this roadmap as complete (Progress page, data of {date})."
            for stage in atlas["stages"]:
                if stage.get("owner") == roadmap_id and not stage.get("expansion") and stage["id"] in leaves(stage["id"]):
                    stages_overlay[stage["id"]] = {"status": "complete", "basis": done, "evidence": [], "snapshotStatus": "reported", "snapshotDate": date}
        for layer, state in zip(field(row, "layer_ids", []), field(row, "states", [])) if not row.get("completed") else ():
            for stage in by_key.get((roadmap_id, layer), []):
                if not stage.get("parentStageId") and remaining.get(layer):
                    info["remaining"][stage["id"]] = remaining[layer]
                for leaf in leaves(stage["id"]):
                    if state in STATUS:
                        stages_overlay[leaf] = {"status": STATUS[state], "basis": basis, "evidence": [], "snapshotStatus": "reported", "snapshotDate": date}
                    else:
                        stages_overlay.pop(leaf, None)
        if row.get("completed"):
            roadmaps_overlay[roadmap_id] = {"status": "complete", "percent": 100, "basis": basis, "evidence": [], "snapshotStatus": "reported", "snapshotDate": date}
        info["roadmaps"][roadmap_id] = {"activity": field(row, "activity", {}) or {}, "assessment": assessment.get("source"),
                                        "status": REPOSITORY + status_path if status_path else None, "completed": bool(row.get("completed")),
                                        "frontier": frontier[:6]}
    # The snapshot's copies of each report are superseded by the live report, linked instead.
    for roadmap in atlas["roadmaps"]:
        if roadmap["id"] in matched:
            roadmap.pop("statusMarkdown", None)
            roadmap.pop("progressMarkdown", None)
    placed = {id(row) for row in matched.values()}
    info["unplaced"] = [{"id": row["id"], "title": row.get("title") or name(row["id"])} for row in progress.get("rows", [])
                        if id(row) not in placed and not row.get("retired")]
    atlas["taucetiProgress"] = info
    return atlas


def unplaced(atlas: dict, progress: dict) -> list:
    """The rows of the board that no roadmap of the atlas matches."""
    placed = {id(row) for row in matches(atlas, progress).values()}
    return [row for row in progress.get("rows", []) if id(row) not in placed and not row.get("retired")]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def short_name(roadmap_id: str) -> str:
    return name(roadmap_id).split("/")[-1]


def load_placements(path: Path = PLACEMENTS) -> dict:
    """The areas maintainers chose for new Tau Ceti roadmaps, by board id (data/tauceti-placements.json)."""
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("placements", {})
    except (OSError, ValueError):
        return {}


def area_for(text: str, title: str, atlas: dict, own: str, chosen: str | None = None) -> tuple:
    """(area, Tau Ceti roadmaps the README names, basis), on the most direct evidence there is:
    - "chosen": the area a maintainer chose (data/tauceti-placements.json);
    - "title": the area or field the title names, the earliest in the title, an area before a
      field at the same place (a field means its largest area);
    - "readme": the area that holds more of the Tau Ceti roadmaps the README names than any other.
    A README also names the roadmaps a roadmap builds on, often in other areas, so it decides only
    on a clear lead, never by a tie-break. Failing all three, the area is None."""
    known = {}
    for roadmap in atlas["roadmaps"]:
        if roadmap.get("origin") == "tauceti" and short_name(roadmap["id"]) != own and roadmap.get("group"):
            known.setdefault(short_name(roadmap["id"]), roadmap)
    linked = re.findall(r"\]\((?:\.\./|/?TauCetiRoadmap/|https://github\.com/TauCetiProject/TauCetiRoadmap/(?:blob|tree)/main/TauCetiRoadmap/)([A-Za-z0-9]+)", text)
    names = sorted({n for n in linked if n in known}) or sorted(n for n in known if re.search(r"\b" + re.escape(n) + r"\b", text))
    named = [known[n]["id"] for n in names]
    groups = {group["id"] for group in atlas.get("groups", [])}
    if chosen in groups:
        return chosen, named, "chosen"
    words = title.lower()
    size = Counter(roadmap.get("group") for roadmap in atlas["roadmaps"])
    candidates = []
    for group in atlas.get("groups", []):
        found = re.search(r"\b" + re.escape(group["label"].lower()) + r"\b", words)
        if found:
            candidates.append((found.start(), 0, group["id"]))
    for field_ in atlas.get("fields", []):
        members = [g for g in field_.get("groupIds", []) if g in groups]
        found = re.search(r"\b" + re.escape(field_["label"].lower()) + r"\b", words)
        if members and found:
            candidates.append((found.start(), 1, max(sorted(members), key=lambda g: size[g])))
    if candidates:
        return min(candidates)[2], named, "title"
    ranked = Counter(known[n]["group"] for n in names).most_common()
    if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
        return ranked[0][0], named, "readme"
    return None, named, None


def summary(text: str, least: int = 40, most: int = 150) -> str:
    """A README's opening prose, as the atlas summarises a roadmap: from the first paragraph
    saying what "this roadmap" does (Tau Ceti's READMEs often open with what Mathlib already
    has), whole paragraphs until there are at least `least` words, cut at a sentence by `most`
    words; no headings, tables, lists, quotations or code, and links reduced to their text."""
    blocks, fenced = [], False
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if "```" in block:
            # An odd number of fences opens or closes a code block; a whole one inside the paragraph changes nothing.
            if block.count("```") % 2:
                fenced = not fenced
            continue
        if fenced or not block or block.startswith(("#", "|", ">", "<!--")) or re.match(r"^([-*+]|\d+\.)\s", block):
            continue
        blocks.append(re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", " ".join(block.split())))
    start = next((i for i, block in enumerate(blocks[:6]) if block.startswith("This roadmap")), 0)
    kept, words = [], 0
    for block in blocks[start:]:
        kept.append(block)
        words += len(block.split())
        if words >= least:
            break
    joined = " ".join(kept).split()
    if len(joined) <= most:
        return " ".join(joined)
    cut = " ".join(joined[:most])
    end = cut.rfind(". ")
    return cut[:end + 1] if end >= 0 and len(cut[:end + 1].split()) >= least else cut + " …"


def add_new_roadmaps(atlas: dict, progress: dict, readmes: dict, placements: dict | None = None) -> list:
    """Add the roadmaps the board reports and the atlas lacks, built from their READMEs; the ids added."""
    placements = load_placements() if placements is None else placements
    added = []
    for row in unplaced(atlas, progress):
        text = readmes.get(row["id"])
        if not text:
            continue
        roadmap_id = "tauceti:" + row["id"]
        heading = re.search(r"^#\s+(.+)$", text, re.M)
        title = re.sub(r"^Roadmap:\s*", "", heading.group(1).strip()) if heading else (row.get("title") or short_name(roadmap_id))
        title = title[:1].upper() + title[1:]
        choice = placements.get(row["id"]) or {}
        group, named, basis = area_for(text, title, atlas, short_name(roadmap_id), choice.get("galaxy"))
        if not group:
            continue
        lines = text.splitlines()

        def section(label):
            for number, line in enumerate(lines):
                found = re.match(r"^(#{1,6})\s+(.*)$", line)
                if found and found.group(2).strip().lower().startswith(label.lower()):
                    body = []
                    for later in lines[number + 1:]:
                        deeper = re.match(r"^(#{1,6})\s", later)
                        if deeper and len(deeper.group(1)) <= len(found.group(1)):
                            break
                        body.append(later)
                    return number + 1, "\n".join(body).strip()
            return 1, ""

        headings = field(row, "layers", [])
        stages, edges = [], []
        # Layers in the order the README lists them, each after the one before it.
        for index, layer in enumerate(field(row, "layer_ids", [])):
            label = headings[index] if index < len(headings) else layer
            short = label[len(layer):].lstrip(" :.—–-").strip() if label.startswith(layer) else label
            line, body = section(label)
            stage = {"id": f"{roadmap_id}#{slug(label)}", "owner": roadmap_id, "key": layer, "title": short or layer, "description": body[:4000],
                     "requires": [stages[-1]["id"]] if stages else [], "consumers": [], "sourcePath": row.get("readme"), "repositoryPath": row.get("readme"),
                     "sourceLine": line, "contextStartLine": line, "contextEndLine": line, "depth": index, "firstAction": "", "status": "unknown",
                     "origin": "tauceti", "parentStageId": None, "isLeaf": True, "headingLevel": 2, "sectionKind": "layer", "anchor": slug(label)}
            if stages:
                stages[-1]["consumers"].append(stage["id"])
                edges.append({"source": stages[-1]["id"], "target": stage["id"], "origin": "tauceti", "evidence": {"sourcePath": row.get("readme"), "basis": "README order"}})
            stages.append(stage)
        if not stages:
            continue
        atlas["roadmaps"].append({"id": roadmap_id, "title": title, "summary": summary(text), "readme": text, "origin": "tauceti", "lifecycle": "active",
                                  "group": group, "parentRoadmapId": ("tauceti:" + row["parent_id"]) if row.get("parent_id") else None,
                                  "sourcePath": row.get("readme"), "repositoryPath": row.get("readme"), "stages": [stage["id"] for stage in stages],
                                  "prerequisites": [], "consumers": [], "sections": []})
        atlas["stages"] += stages
        atlas.setdefault("stageEdges", []).extend(edges)
        atlas.setdefault("roadmapLinks", []).extend({"source": roadmap_id, "target": other, "kind": "reference", "label": short_name(other), "anchor": ""} for other in named)
        # "provisional": joined from its README since the snapshot, until a classification job classifies it.
        reason = {"chosen": f"Placed where the maintainers chose: {choice.get('reason', '').strip()}",
                  "title": "Placed provisionally in the area its title names.",
                  "readme": f"Placed provisionally with most of the Tau Ceti roadmaps its README names ({', '.join(short_name(n) for n in named)})."}[basis]
        atlas.setdefault("roadmapClassification", {}).setdefault("roadmaps", {})[roadmap_id] = {"basis": "provisional", "rationale": reason}
        added.append(roadmap_id)
    return added


def fetch_readmes(progress: dict, snapshot: Path = ROOT / "data" / "atlas.json", copy: Path = READMES) -> dict:
    """The READMEs of the roadmaps the board reports and the atlas's snapshot lacks."""
    readmes = {}
    for row in unplaced(json.loads(snapshot.read_text(encoding="utf-8")), progress):
        if isinstance(row.get("readme"), str):
            with urllib.request.urlopen(RAW + row["readme"], timeout=60) as response:
                readmes[row["id"]] = response.read().decode("utf-8")
    copy.write_text(json.dumps(readmes, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return readmes


def load_readmes(copy: Path = READMES) -> dict:
    return json.loads(copy.read_text(encoding="utf-8")) if copy.exists() else {}


def tauceti_only(atlas: dict) -> dict:
    """The atlas cut down to the Tau Ceti roadmaps the Progress page reports: the Tau Ceti build.

    Everything the campaign plans (proposed roadmaps, their layers and links,
    blueprints, papers, restructurings, unmapped areas) is left out, and every
    table keyed by a roadmap or layer keeps only the entries that remain."""
    keep = set((atlas.get("taucetiProgress") or {}).get("roadmaps", {}))
    stage_ids = {stage["id"] for stage in atlas["stages"] if stage.get("owner") in keep}
    on_layer = lambda key: key in stage_ids or key.split("::landmark:")[0] in stage_ids
    cut = dict(atlas, variant="tauceti", papers=[], restructurings=[], blueprintLayers=[], packages={})
    cut["roadmaps"] = [roadmap for roadmap in atlas["roadmaps"] if roadmap["id"] in keep]
    cut["stages"] = [stage for stage in atlas["stages"] if stage["id"] in stage_ids]
    cut["stageEdges"] = [edge for edge in atlas.get("stageEdges", []) if edge["source"] in stage_ids and edge["target"] in stage_ids]
    for key in ("edges", "roadmapLinks"):
        cut[key] = [edge for edge in atlas.get(key, []) if edge.get("source") in keep and edge.get("target") in keep]
    cut["decompositions"] = [item for item in atlas.get("decompositions", []) if item.get("roadmapId") in keep]
    cut["deferredLinks"] = [link for link in atlas.get("deferredLinks", []) if link.get("source") in stage_ids and link.get("target") in stage_ids]
    cut["opportunities"] = dict(atlas.get("opportunities", {}), areas=[], groups=[])
    for key in ("stagePresentation", "mappedStageStatuses", "libraryStatuses", "landmarkHidden", "landmarkLabels"):
        cut[key] = {k: v for k, v in atlas.get(key, {}).items() if on_layer(k)}
    cut["roadmapSummaries"] = {k: v for k, v in atlas.get("roadmapSummaries", {}).items() if k in keep}
    for key in ("roadmapClassification", "roadmapDistances"):
        if key in atlas:
            cut[key] = dict(atlas[key], roadmaps={k: v for k, v in atlas[key].get("roadmaps", {}).items() if k in keep})
    if "libraryCoverage" in atlas:
        cut["libraryCoverage"] = dict(atlas["libraryCoverage"], layers={k: v for k, v in atlas["libraryCoverage"].get("layers", {}).items() if k in stage_ids})
    progress = atlas.get("progress", {})
    cut["progress"] = dict(progress, stages={k: v for k, v in progress.get("stages", {}).items() if k in stage_ids},
                           roadmaps={k: v for k, v in progress.get("roadmaps", {}).items() if k in keep})
    return cut


def fetch(url: str = URL, copy: Path = COPY) -> dict:
    with urllib.request.urlopen(url, timeout=60) as response:
        progress = json.loads(response.read().decode("utf-8"))
    if not isinstance(progress.get("rows"), list) or not progress["rows"]:
        raise ValueError("The Progress page's data has no roadmaps.")
    copy.write_text(json.dumps(progress, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return progress


def load(copy: Path = COPY) -> dict | None:
    return json.loads(copy.read_text(encoding="utf-8")) if copy.exists() else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fetch", action="store_true", help="download the Progress page's data")
    args = parser.parse_args()
    if args.fetch:
        progress = fetch()
        print(f"{len(progress['rows'])} roadmaps, exported {progress.get('exported_at')}: {counts(progress)}")
        readmes = fetch_readmes(progress)
        print(f"{len(readmes)} roadmap(s) newer than the atlas's snapshot: {', '.join(sorted(readmes)) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
