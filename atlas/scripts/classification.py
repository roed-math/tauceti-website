#!/usr/bin/env python3
"""Place every roadmap in a subject galaxy at a distance from Mathlib.

Reads the evidence-based classifications written by the CLASSIFY jobs
(research/blueprint/classify/*.result.json: subject classes of each roadmap's
principal references, looked up in zbMATH, and a 0-10 distance from Mathlib
with its rationale) and the provisional values in
data/classification-estimates.json for roadmaps whose classification has not
finished. A classification result always wins over an estimate. Writes
data/roadmap-classification.json, which the builder uses to group roadmaps
into the galaxies of data/galaxies.json.

Run it whenever new classification results land:

    python3 scripts/classification.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from retirements import apply_retirements  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "research" / "blueprint" / "classify"
PRIVATE = re.compile(r"/(?:Users|home)/[^/\s]+/")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def msc_galaxy(code: str, prefixes: dict) -> str | None:
    """The galaxy whose longest MSC prefix matches the code."""
    best = None
    for prefix, galaxy in prefixes.items():
        if code.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, galaxy)
    return best[1] if best else None


def galaxy_rule(galaxies: list):
    """A function from (cluster, primary MSC) to galaxy id.

    Each cluster has one default galaxy; a galaxy with primaryMsc prefixes takes
    the roadmaps of its clusters whose primary class starts with one of them.
    """
    defaults, splits = {}, {}
    for galaxy in galaxies:
        for cluster in galaxy["clusters"]:
            if galaxy.get("primaryMsc"):
                for prefix in galaxy["primaryMsc"]:
                    splits.setdefault(cluster, []).append((prefix, galaxy["id"]))
            elif cluster in defaults:
                raise SystemExit(f"cluster {cluster!r} has two default galaxies")
            else:
                defaults[cluster] = galaxy["id"]
    missing = set(splits) - set(defaults)
    if missing:
        raise SystemExit("clusters without a default galaxy: " + ", ".join(sorted(missing)))

    def rule(cluster: str, primary: str | None):
        if cluster not in defaults:
            return None
        matches = [(len(prefix), galaxy) for prefix, galaxy in splits.get(cluster, []) if primary and primary.startswith(prefix)]
        return max(matches)[1] if matches else defaults[cluster]
    return rule


def main() -> None:
    galaxies = load(ROOT / "data" / "galaxies.json")["galaxies"]
    galaxy_for = galaxy_rule(galaxies)
    prefixes = {prefix: galaxy["id"] for galaxy in galaxies for prefix in galaxy.get("msc", [])}
    roadmaps = {roadmap["id"]: roadmap for roadmap in apply_retirements(load(ROOT / "data" / "atlas.json"))["roadmaps"]}
    estimates = load(ROOT / "data" / "classification-estimates.json")["estimates"]
    results = {}
    for path in sorted(RESULTS.glob("*.result.json")):
        for entry in load(path):
            if entry.get("assessmentStatus") == "partial" or entry.get("roadmapId") not in roadmaps:
                continue
            results[entry["roadmapId"]] = (path.name.split(".")[0], entry)
    output, missing = {}, []
    for roadmap_id in sorted(roadmaps):
        if roadmap_id in results:
            job, entry = results[roadmap_id]
            record = {"cluster": entry["cluster"], "distance": entry["distance"], "primaryMsc": entry.get("primaryMsc"),
                      "secondaryMsc": entry.get("secondaryMsc") or [], "basis": "classification", "job": job,
                      "rationale": entry.get("distanceRationale", "")}
        elif roadmap_id in estimates:
            entry = estimates[roadmap_id]
            record = {"cluster": entry["cluster"], "distance": entry["distance"], "primaryMsc": entry.get("primaryMsc"),
                      "secondaryMsc": [], "basis": "estimate", "rationale": entry.get("reason", "")}
        else:
            missing.append(roadmap_id)
            continue
        galaxy = galaxy_for(record["cluster"], record["primaryMsc"])
        if galaxy is None:
            raise SystemExit(f"{roadmap_id}: cluster {record['cluster']!r} belongs to no galaxy")
        if not isinstance(record["distance"], (int, float)) or not 0 <= record["distance"] <= 10:
            raise SystemExit(f"{roadmap_id}: distance must lie between 0 and 10")
        if PRIVATE.search(record["rationale"]):
            raise SystemExit(f"{roadmap_id}: the rationale names a private local path")
        record["galaxy"] = galaxy
        tags = []
        for code in record["secondaryMsc"]:
            galaxy = msc_galaxy(code, prefixes)
            if galaxy and galaxy != record["galaxy"] and galaxy not in tags:
                tags.append(galaxy)
        record["tags"] = tags
        output[roadmap_id] = record
    if missing:
        raise SystemExit("No classification or estimate for: " + ", ".join(missing))
    classified = sum(record["basis"] == "classification" for record in output.values())
    document = {
        "version": 2,
        "purpose": "Subject galaxy and distance from Mathlib for every roadmap. Distances run from 0 (the targets can be stated and proved from Mathlib now) to 10 (several research-level theories must be built first). Generated by scripts/classification.py; do not edit by hand.",
        "sources": {
            "classification": "research/blueprint/classify: subject classes of each roadmap's principal references (zbMATH Open API) and a distance judged against the pinned Mathlib and Tau Ceti baseline.",
            "estimate": "data/classification-estimates.json: provisional values for roadmaps whose classification has not finished.",
        },
        "provisional": classified < len(output),
        "counts": {"classified": classified, "estimated": len(output) - classified},
        "roadmaps": output,
    }
    target = ROOT / "data" / "roadmap-classification.json"
    target.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{classified} classified, {len(output) - classified} estimated -> {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
