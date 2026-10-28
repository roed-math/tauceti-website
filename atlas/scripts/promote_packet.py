#!/usr/bin/env python3
"""Promote an independently reviewed decomposition packet into data/decompositions/.

Promotion is deliberate: the packet must carry an accepted independent review,
must merge cleanly with the current snapshot together with every packet already
promoted, and is copied unchanged. Nothing here edits application code, the
original snapshot or the roadmap sources.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from decompositions import merge_decompositions  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path, help="Reviewed packet JSON, usually under research/expansion/drafts/")
    parser.add_argument("--dry-run", action="store_true", help="Validate the merge without copying the packet")
    arguments = parser.parse_args()
    packet = json.loads(arguments.packet.read_text(encoding="utf-8"))
    review = packet.get("review") or {}
    if review.get("status") != "accepted" or not review.get("reviewer") or not review.get("notes"):
        raise SystemExit("The packet has no accepted independent review; promotion refused.")
    folder = ROOT / "data" / "decompositions"
    promoted = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))] if folder.is_dir() else []
    promoted = [item for item in promoted if item["roadmapId"] != packet["roadmapId"]] + [packet]
    atlas = json.loads((ROOT / "data" / "atlas.json").read_text(encoding="utf-8"))
    expanded, _documents = merge_decompositions(atlas, promoted)
    record = next(item for item in expanded["decompositions"] if item["roadmapId"] == packet["roadmapId"])
    added = [stage for stage in expanded["stages"] if stage.get("expansion", {}).get("packet") == packet["roadmapId"]]
    unreviewed = [stage["id"] for stage in added if not stage["expansion"]["reviewed"]]
    print(json.dumps({
        "roadmap": packet["roadmapId"], "status": packet["status"], "review": review["status"],
        "reviewer": review.get("reviewer"), "refinements": len(added), "addedDuringReview": unreviewed,
        "deferredLinks": record.get("deferredLinks", []), "gaps": [gap["title"] for gap in packet.get("gaps", [])],
        "stages": len(expanded["stages"]), "stageEdges": len(expanded["stageEdges"]),
    }, indent=2, ensure_ascii=False))
    if arguments.dry_run:
        return
    folder.mkdir(parents=True, exist_ok=True)
    name = packet["roadmapId"].replace(":", "_").replace("/", "_") + ".json"
    (folder / name).write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Promoted to", (folder / name).relative_to(ROOT))


if __name__ == "__main__":
    main()
