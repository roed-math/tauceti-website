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

Usage: tauceti_progress.py --fetch   download the board's data into data/
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://taucetiproject.github.io/TauCeti/static/progress.json"
PAGE = "https://taucetiproject.github.io/TauCeti/progress/"
REPOSITORY = "https://github.com/TauCetiProject/TauCetiRoadmap/blob/main/"
COPY = ROOT / "data" / "tauceti-progress.json"
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


def tauceti_only(atlas: dict) -> dict:
    """The atlas cut down to the Tau Ceti roadmaps the Progress page reports: the Tau Ceti build.

    Everything the campaign plans (proposed roadmaps, their layers and links,
    blueprints, papers, restructurings, unmapped areas) is left out, and every
    table keyed by a roadmap or layer keeps only the entries that remain."""
    keep = set((atlas.get("taucetiProgress") or {}).get("roadmaps", {}))
    stage_ids = {stage["id"] for stage in atlas["stages"] if stage.get("owner") in keep}
    on_layer = lambda key: key in stage_ids or key.split("::landmark:")[0] in stage_ids
    cut = dict(atlas, variant="tauceti", papers=[], restructurings=[], blueprintLayers=[])
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
