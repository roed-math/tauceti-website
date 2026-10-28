"""Retired roadmaps (data/roadmap-retirements.json), removed wherever the atlas is read.

The snapshot in data/atlas.json stays unchanged. A retired roadmap disappears
with its layers, and every roadmap-level and layer-level link through it is
dropped rather than rerouted: which of the covering roadmaps a consumer really
needs is decided by the reviewed link maps, not guessed here.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_retirements(root: Path = ROOT) -> dict:
    path = root / "data" / "roadmap-retirements.json"
    return json.loads(path.read_text(encoding="utf-8"))["roadmaps"] if path.exists() else {}


def retired_stage_ids(atlas: dict, retired: dict) -> set:
    return {stage["id"] for stage in atlas["stages"] if stage.get("owner") in retired}


def apply_retirements(atlas: dict, retired: dict | None = None) -> dict:
    """Remove retired roadmaps from an atlas dictionary, in place, and return it."""
    retired = load_retirements() if retired is None else retired
    if not retired:
        return atlas
    known = {roadmap["id"] for roadmap in atlas["roadmaps"]}
    unknown = sorted(set(retired) - known)
    if unknown:
        raise ValueError("Retired roadmaps not in the atlas: " + ", ".join(unknown))
    gone = retired_stage_ids(atlas, retired)
    atlas["roadmaps"] = [roadmap for roadmap in atlas["roadmaps"] if roadmap["id"] not in retired]
    for roadmap in atlas["roadmaps"]:
        for key in ("prerequisites", "consumers"):
            if isinstance(roadmap.get(key), list):
                roadmap[key] = [item for item in roadmap[key]
                                if (item.get("id") if isinstance(item, dict) else item) not in retired]
        if roadmap.get("parentRoadmapId") in retired:
            roadmap["parentRoadmapId"] = None
    atlas["stages"] = [stage for stage in atlas["stages"] if stage["id"] not in gone]
    for stage in atlas["stages"]:
        for key in ("requires", "consumers"):
            if isinstance(stage.get(key), list):
                stage[key] = [item for item in stage[key] if item not in gone]
    atlas["edges"] = [edge for edge in atlas["edges"] if edge["source"] not in retired and edge["target"] not in retired]
    atlas["stageEdges"] = [edge for edge in atlas["stageEdges"] if edge["source"] not in gone and edge["target"] not in gone]
    for group in atlas.get("groups", []):
        group["roadmapIds"] = [rid for rid in group.get("roadmapIds", []) if rid not in retired]
    meta = atlas.setdefault("meta", {})
    meta["retiredRoadmaps"] = sorted(retired)
    meta["roadmapCount"] = len(atlas["roadmaps"])
    meta["stageCount"] = len(atlas["stages"])
    return atlas
