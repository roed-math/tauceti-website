"""Regroup the snapshot's roadmaps into the subject galaxies of data/galaxies.json.

The snapshot records an older, hand-made area for each roadmap. The atlas
instead places every roadmap in the galaxy of its subject cluster, read from
data/roadmap-classification.json (see scripts/classification.py). Child
roadmaps of a collection stay in their parent's galaxy, so a collection is
never split across the map.
"""
from __future__ import annotations

from collections import Counter, defaultdict

NOTES = [
    "Each roadmap has one galaxy, chosen from the subject classes of its principal references; secondary tags come from their other subject classes. Tags are not dependency edges or completion claims.",
    "A galaxy lies farther from Mathlib at the centre the more theory its roadmaps must build before their targets can be stated and proved; the distance is the mean over its roadmaps, and neighbouring galaxies hold related subjects.",
    "bridgeGroups lists up to three other galaxies with the most recorded roadmap prerequisite links, counting both directions. It describes connections in this snapshot, not mathematical similarity.",
    "Child roadmaps of a collection stay in their parent's galaxy. Parent-child membership is not a prerequisite.",
]


def apply_galaxies(atlas: dict, galaxies: list, classification: dict) -> dict:
    """Replace atlas groups with galaxies, move each roadmap, and return the regions record."""
    known = {galaxy["id"]: galaxy for galaxy in galaxies}
    if len(known) != len(galaxies):
        raise ValueError("Galaxy ids must be unique.")
    clusters = Counter(cluster for galaxy in galaxies for cluster in galaxy["clusters"])
    if any(count > 1 for count in clusters.values()):
        raise ValueError("A subject cluster belongs to exactly one galaxy.")
    records = classification.get("roadmaps", {})
    roadmaps = {roadmap["id"]: roadmap for roadmap in atlas["roadmaps"]}
    galaxy_of = {}
    for roadmap_id in roadmaps:
        record = records.get(roadmap_id)
        if not record or record.get("galaxy") not in known:
            raise ValueError("Every roadmap needs a galaxy; run scripts/classification.py: " + roadmap_id)
        galaxy_of[roadmap_id] = record["galaxy"]
    for roadmap_id, roadmap in roadmaps.items():
        parent = roadmap.get("parentRoadmapId")
        if parent in galaxy_of:
            galaxy_of[roadmap_id] = galaxy_of[parent]
        roadmap["group"] = galaxy_of[roadmap_id]
    members = defaultdict(list)
    for roadmap_id in sorted(roadmaps):
        members[galaxy_of[roadmap_id]].append(roadmap_id)
    # Listed from nearest to farthest from Mathlib, as the map reads outward.
    distance = {galaxy["id"]: sum(records[r]["distance"] for r in members[galaxy["id"]]) / len(members[galaxy["id"]])
                for galaxy in galaxies if members[galaxy["id"]]}
    ordered = sorted((galaxy for galaxy in galaxies if members[galaxy["id"]]), key=lambda galaxy: (distance[galaxy["id"]], galaxy["id"]))
    atlas["groups"] = [{"id": galaxy["id"], "label": galaxy["label"], "short": galaxy["short"], "caption": galaxy["caption"],
                        "color": galaxy["color"], "direction": galaxy["direction"], "distance": round(distance[galaxy["id"]], 2),
                        "roadmapIds": members[galaxy["id"]]}
                       for galaxy in ordered]
    atlas["meta"]["groupCount"] = len(atlas["groups"])
    links = defaultdict(Counter)
    for edge in atlas["edges"]:
        a, b = galaxy_of.get(edge["source"]), galaxy_of.get(edge["target"])
        if a and b and a != b:
            links[a][b] += 1
            links[b][a] += 1
    regions = {
        "version": 2,
        "purpose": "Subject galaxies: descriptions, topics and the galaxies each is most connected to.",
        "groups": {galaxy["id"]: {"description": galaxy["description"], "topics": galaxy["topics"],
                                  "bridgeGroups": [other for other, _ in sorted(links[galaxy["id"]].items(), key=lambda item: (-item[1], item[0]))[:3]]}
                   for galaxy in ordered},
        "roadmapTags": {roadmap_id: [tag for tag in records[roadmap_id].get("tags", []) if tag != galaxy_of[roadmap_id]]
                        for roadmap_id in sorted(roadmaps) if records[roadmap_id].get("tags")},
        "notes": NOTES,
    }
    regions["roadmapTags"] = {key: value for key, value in regions["roadmapTags"].items() if value}
    return regions
