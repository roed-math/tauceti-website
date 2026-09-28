"""Papers as artefacts on the atlas.

Each paper routed into the atlas (research/blueprint/papers/papers.json) is drawn
beside the roadmap most of its items go to, and unlocks once every layer it needs
is formalised. What it needs comes from the routes its review accepted
(PROTOCOL.md section 16): the layers a source route names, the whole of the
roadmap a Part II extends, and any Part II or new roadmap it calls for, which
keeps it locked until that roadmap is in the atlas.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def accepted_routes(folder: Path, pid: str) -> list:
    """The routes of an extraction that its review accepted, read as research/blueprint/make_queue.py reads them."""
    try:
        result = json.loads((folder / f"{pid}.result.json").read_text(encoding="utf-8"))
        review = json.loads((folder / f"{pid}.review.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if review.get("verdict") != "accept":
        return []
    accepted = {entry.get("route") for entry in review.get("routes", []) if entry.get("verdict") == "accept"}
    return [route for number, route in enumerate(result.get("routes", []), 1) if number in accepted]


def paper_artefacts(atlas: dict, folder: Path) -> list:
    """One artefact for each routed paper that has a place in the atlas."""
    try:
        registry = json.loads((folder / "papers.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    roadmaps = {roadmap["id"] for roadmap in atlas["roadmaps"]}
    stages = {stage["id"] for stage in atlas["stages"]}
    artefacts = []
    for paper in registry.get("papers", []):
        weight, needs, whole, pending = Counter(), set(), set(), set()
        for route in accepted_routes(folder, paper["id"]):
            items = len(route.get("items") or []) or 1
            if route.get("route") == "source":
                needs.update(stage for stage in route.get("stages", []) if stage in stages)
                if route.get("roadmap") in roadmaps:
                    weight[route["roadmap"]] += items
            elif route.get("route") == "part-ii" and route.get("parent") in roadmaps:
                whole.add(route["parent"])
                weight[route["parent"]] += items
            if route.get("route") in ("part-ii", "new") and route.get("roadmap"):
                (whole if route["roadmap"] in roadmaps else pending).add(route["roadmap"])
        if not weight:
            continue
        short = paper.get("short") or paper["citation"]
        artefacts.append({
            "id": "paper:" + paper["id"], "label": short.split(":")[0].strip(), "citation": paper.get("citation") or short,
            "link": paper.get("link", ""), "home": max(sorted(weight), key=weight.get),
            "needs": sorted(needs), "roadmaps": sorted(whole), "pending": sorted(pending),
        })
    return artefacts
