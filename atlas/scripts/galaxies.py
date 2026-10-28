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
    "bridgeGroups lists up to three other galaxies that share the most missing theory with this one (data/galaxy-layout.json), or, without a layout, the most recorded roadmap prerequisite links.",
    "Child roadmaps of a collection stay in their parent's galaxy. Parent-child membership is not a prerequisite.",
]


def galaxy_membership(atlas: dict, classification: dict) -> dict:
    """The galaxy of each roadmap: its classification's, or its collection's."""
    records = classification.get("roadmaps", classification)
    galaxy_of = {}
    for roadmap in atlas["roadmaps"]:
        record = records.get(roadmap["id"])
        if not record or not record.get("galaxy"):
            raise ValueError("Every roadmap needs a galaxy; run scripts/classification.py: " + roadmap["id"])
        galaxy_of[roadmap["id"]] = record["galaxy"]
    for roadmap in atlas["roadmaps"]:
        parent = roadmap.get("parentRoadmapId")
        if parent in galaxy_of:
            galaxy_of[roadmap["id"]] = galaxy_of[parent]
    return galaxy_of


def apply_galaxies(atlas: dict, galaxies: list, classification: dict, distances: dict | None = None, layout: dict | None = None,
                   *, fields: list) -> dict:
    """Replace atlas groups with galaxies, move each roadmap, and return the regions record.

    distances (data/roadmap-distances.json) gives each roadmap's distance from
    Mathlib; layout (data/galaxy-layout.json) gives each galaxy's direction and
    the galaxies it shares the most missing theory with.

    Each galaxy is an area of one field (data/galaxies.json), so that labels
    sit at one level of abstraction: the map names fields when zoomed out and
    their areas when zoomed in. An area takes its field's colour, and the only
    area of a field with roadmaps is named after the field.
    """
    known = {galaxy["id"]: galaxy for galaxy in galaxies}
    if len(known) != len(galaxies):
        raise ValueError("Galaxy ids must be unique.")
    field_by_id = {field["id"]: field for field in fields}
    unplaced = sorted(galaxy["id"] for galaxy in galaxies if galaxy.get("field") not in field_by_id)
    if unplaced:
        raise ValueError("Galaxies without a known field: " + ", ".join(unplaced))
    # Each cluster has exactly one default galaxy; galaxies with primaryMsc
    # prefixes take a part of a cluster (see scripts/classification.py).
    clusters = Counter(cluster for galaxy in galaxies if not galaxy.get("primaryMsc") for cluster in galaxy["clusters"])
    if any(count > 1 for count in clusters.values()):
        raise ValueError("A subject cluster has exactly one default galaxy.")
    records = classification.get("roadmaps", {})
    roadmaps = {roadmap["id"]: roadmap for roadmap in atlas["roadmaps"]}
    galaxy_of = galaxy_membership(atlas, classification)
    unknown = sorted({gid for gid in galaxy_of.values() if gid not in known})
    if unknown:
        raise ValueError("Roadmaps are assigned to unknown galaxies: " + ", ".join(unknown))
    for roadmap_id, roadmap in roadmaps.items():
        roadmap["group"] = galaxy_of[roadmap_id]
    measured = (distances or {}).get("roadmaps", {})
    placed = (layout or {}).get("galaxies", {})
    distance_of = {rid: measured.get(rid, {}).get("distance", records[rid]["distance"]) for rid in roadmaps}
    members = defaultdict(list)
    for roadmap_id in sorted(roadmaps):
        members[galaxy_of[roadmap_id]].append(roadmap_id)
    # Listed from nearest to farthest from Mathlib, as the map reads outward.
    distance = {galaxy["id"]: sum(distance_of[r] for r in members[galaxy["id"]]) / len(members[galaxy["id"]])
                for galaxy in galaxies if members[galaxy["id"]]}
    ordered = sorted((galaxy for galaxy in galaxies if members[galaxy["id"]]), key=lambda galaxy: (distance[galaxy["id"]], galaxy["id"]))
    areas_of = defaultdict(list)
    for galaxy in ordered:
        areas_of[galaxy["field"]].append(galaxy["id"])
    groups = []
    for galaxy in ordered:
        field = field_by_id[galaxy["field"]]
        name = field if len(areas_of[field["id"]]) == 1 else galaxy
        groups.append({"id": galaxy["id"], "label": name["label"], "short": name["short"], "caption": name["caption"],
                       "color": field["color"], "field": field["id"],
                       "direction": placed.get(galaxy["id"], {}).get("direction", galaxy.get("direction", 0)),
                       "distance": round(distance[galaxy["id"]], 2),
                       "roadmapIds": members[galaxy["id"]]})
    atlas["groups"] = groups
    atlas["meta"]["groupCount"] = len(atlas["groups"])
    field_roadmaps = {fid: [rid for gid in gids for rid in members[gid]] for fid, gids in areas_of.items()}
    field_distance = {fid: sum(distance_of[rid] for rid in rids) / len(rids) for fid, rids in field_roadmaps.items()}
    atlas["fields"] = [{"id": fid, "label": field_by_id[fid]["label"], "short": field_by_id[fid]["short"], "caption": field_by_id[fid]["caption"],
                        "color": field_by_id[fid]["color"], "groupIds": areas_of[fid], "roadmaps": len(field_roadmaps[fid]),
                        "distance": round(field_distance[fid], 2)}
                       for fid in sorted(areas_of, key=lambda fid: (field_distance[fid], fid))]
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
                                  "bridgeGroups": ([n["galaxy"] for n in placed[galaxy["id"]]["neighbours"] if members[n["galaxy"]]][:3]
                                                   if galaxy["id"] in placed else
                                                   [other for other, _ in sorted(links[galaxy["id"]].items(), key=lambda item: (-item[1], item[0]))[:3]])}
                   for galaxy in ordered},
        "roadmapTags": {roadmap_id: [tag for tag in records[roadmap_id].get("tags", []) if tag != galaxy_of[roadmap_id]]
                        for roadmap_id in sorted(roadmaps) if records[roadmap_id].get("tags")},
        "notes": NOTES,
    }
    regions["roadmapTags"] = {key: value for key, value in regions["roadmapTags"].items() if value}
    return regions
