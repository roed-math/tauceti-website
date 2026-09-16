#!/usr/bin/env python3
"""Build an offline, self-contained atlas using Python's standard library."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from decompositions import merge_decompositions  # noqa: E402


def load_decompositions() -> list:
    """Reviewed source decompositions promoted under data/decompositions/, in name order."""
    folder = ROOT / "data" / "decompositions"
    if not folder.is_dir():
        return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def safe_script(text: str) -> str:
    return re.sub(r"</script", r"<\\/script", text, flags=re.IGNORECASE)


def comment_text(text: str) -> str:
    return text.replace("--", "—")


def build(output: Path) -> dict:
    atlas = json.loads(read_text("data/atlas.json"))
    # The snapshot stays immutable; reviewed decompositions refine it at build
    # time, so nothing is appended twice and the originals remain the record.
    decompositions = load_decompositions()
    original_stage_count = len(atlas["stages"])
    atlas, _expanded_documents = merge_decompositions(atlas, decompositions)
    atlas.setdefault("decompositions", [])
    atlas["meta"]["originalStageCount"] = original_stage_count
    atlas["progress"] = json.loads(read_text("data/status.json"))
    # Stage statuses mapped from the maintained reports (scripts/merge_stage_status.py)
    # sit on top of the imported snapshot; each carries its quoted evidence.
    mapped_path = ROOT / "data/stage-status-reports.json"
    atlas["mappedStageStatuses"] = json.loads(mapped_path.read_text(encoding="utf-8")) if mapped_path.exists() else {}
    for stage_id, entry in atlas["mappedStageStatuses"].items():
        if entry.get("status") not in ("planned", "in_progress", "complete") or not entry.get("evidence"):
            raise ValueError("Mapped stage status needs a known status and evidence: " + stage_id)
    atlas["progress"]["stages"].update(atlas["mappedStageStatuses"])
    atlas["regions"] = json.loads(read_text("data/regions.json"))
    atlas["opportunities"] = json.loads(read_text("data/opportunities.json"))
    # Areas without a roadmap are not drawn: the atlas maps roadmaps that exist.
    atlas["opportunities"]["areas"] = []
    atlas["stagePresentation"] = json.loads(read_text("data/stage-presentation.json"))
    atlas["landmarkLabels"] = json.loads(read_text("data/landmark-labels.json"))
    atlas["landmarkHidden"] = json.loads(read_text("data/landmark-hidden.json"))
    # Edited overview summaries: mathematical prose for readers, keyed by roadmap id.
    atlas["roadmapSummaries"] = json.loads(read_text("data/roadmap-summaries.json"))
    roadmap_ids = {roadmap["id"] for roadmap in atlas["roadmaps"]}
    for roadmap_id, summary in atlas["roadmapSummaries"].items():
        if roadmap_id not in roadmap_ids:
            raise ValueError("Roadmap summary refers to an unknown roadmap: " + roadmap_id)
        if not isinstance(summary, str) or len(summary.split()) < 40:
            raise ValueError("Roadmap summaries are at least forty words of prose: " + roadmap_id)
    for roadmap in atlas["roadmaps"]:
        if roadmap["id"] in atlas["roadmapSummaries"]:
            roadmap["summary"] = atlas["roadmapSummaries"][roadmap["id"]]
    atlas["bibliography"] = json.loads(read_text("data/bibliography.json"))
    stage_ids = {stage["id"] for stage in atlas["stages"]}
    if set(atlas["stagePresentation"]) - stage_ids:
        raise ValueError("Stage presentation contains an unknown stage ID.")
    for stage_id, item in atlas["stagePresentation"].items():
        if not isinstance(item.get("summary"), str) or not item["summary"].strip():
            raise ValueError("Missing mathematical presentation summary: " + stage_id)
        if "hidden" in item and not isinstance(item["hidden"], bool):
            raise ValueError("Stage visibility must be a boolean: " + stage_id)
        if "title" in item and (not isinstance(item["title"], str) or not item["title"].strip()):
            raise ValueError("Empty mathematical presentation title: " + stage_id)
    for landmark_id, reason in atlas["landmarkHidden"].items():
        if "::landmark:" not in landmark_id or landmark_id.split("::landmark:")[0] not in stage_ids:
            raise ValueError("Hidden planet refers to an unknown stage ID: " + landmark_id)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Every hidden planet needs a recorded reason: " + landmark_id)
        if landmark_id in atlas["landmarkLabels"]:
            raise ValueError("A planet cannot be both named and hidden: " + landmark_id)
    for landmark_id, label in atlas["landmarkLabels"].items():
        if "::landmark:" not in landmark_id or landmark_id.split("::landmark:")[0] not in stage_ids:
            raise ValueError("Planet label contains an unknown stage ID: " + landmark_id)
        if not isinstance(label, str) or not label.strip() or len(label) > 72 or re.search(r"[\\${}^]", label):
            raise ValueError("Planet labels must be short plain text: " + landmark_id)
    for work in atlas["bibliography"]["works"]:
        if not work.get("title") or not isinstance(work.get("aliases"), list):
            raise ValueError("Bibliographic records need a title and aliases.")
        if work.get("url") and not re.match(r"^https?://", work["url"]):
            raise ValueError("Bibliographic links must be public web addresses.")
    assets = {
        "D3": "vendor/d3.v5.15.0.min.js",
        "KATEX": "vendor/katex.v0.16.28.min.js",
        "MARKDOWN": "src/markdown.js",
        "UNIVERSE": "src/universe.js",
        "GRAPH": "src/graph.js",
        "CAMERA": "src/camera.js",
        "PROGRESS": "src/progress.js",
        "LANDMARKS": "src/landmarks.js",
        "PRESENTATION": "src/presentation.js",
        "REFERENCES": "src/references.js",
        "APP": "src/app.js",
    }
    style_paths = ["src/style.css"]
    if (ROOT / "src/voyager.css").exists():
        style_paths.append("src/voyager.css")
    page = read_text("src/shell.html")
    styles = "\n".join(read_text(path) for path in style_paths)
    if re.search(r"</style", styles, re.IGNORECASE):
        raise ValueError("Stylesheets must not contain a closing HTML style tag.")
    page = page.replace("/*__STYLE__*/", styles)
    for tag, path in assets.items():
        marker = "/*__" + tag + "__*/"
        if marker not in page:
            raise ValueError("Missing template marker: " + marker)
        page = page.replace(marker, safe_script(read_text(path)))
    payload = json.dumps(atlas, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    if "/*__DATA__*/" not in page:
        raise ValueError("Missing data template marker.")
    page = page.replace("/*__DATA__*/", payload)
    if re.search(r"/\*__[A-Z_]+__\*/", page):
        raise ValueError("An unresolved build marker remains in the page.")
    # Set initial counters too, so they agree with the data before app startup.
    for element_id, count in (("roadmap-total", len(atlas["roadmaps"])), ("stage-total", len(atlas["stages"]))):
        page = re.sub(r'(<b id="' + element_id + r'">)[^<]*(</b>)', lambda match: match[1] + f"{count:,}" + match[2], page)
    notices = "\n\n".join(read_text(path) for path in ("NOTICE", "LICENSE", "vendor/D3-LICENSE.txt", "vendor/KaTeX-LICENSE.txt"))
    page = page.replace("</head>", "<!--\n" + comment_text(notices) + "\n-->\n</head>", 1)
    if re.search(r"<(?:script|link)\b[^>]*(?:src|href)\s*=\s*['\"]https?://", page, re.IGNORECASE):
        raise ValueError("An external runtime asset would prevent a self-contained build.")
    if re.search(r"/(?:Users|home)/[^/\s]+/", page):
        raise ValueError("An absolute home directory remains in the public atlas.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    # Refinements are planning detail under their parent layer: they are not
    # progress targets, so the parent stays terminal for progress accounting.
    refinements = [stage for stage in atlas["stages"] if stage.get("expansion")]
    parent_ids = {stage.get("parentStageId") for stage in atlas["stages"] if stage.get("parentStageId") and not stage.get("expansion")}
    source_paths = ["src/shell.html", *style_paths, *assets.values(), "data/atlas.json", "data/status.json", "data/regions.json", "data/opportunities.json", "data/stage-presentation.json", "data/landmark-labels.json", "data/landmark-hidden.json", "data/roadmap-summaries.json", "data/bibliography.json", "NOTICE", "LICENSE", "vendor/D3-LICENSE.txt", "vendor/KaTeX-LICENSE.txt"]
    source_paths += [str(path.relative_to(ROOT)) for path in sorted((ROOT / "data" / "decompositions").glob("*.json"))] if (ROOT / "data" / "decompositions").is_dir() else []
    report = {
        "roadmaps": len(atlas["roadmaps"]),
        "stages": len(atlas["stages"]),
        "originalStages": original_stage_count,
        "sourceRefinements": len(refinements),
        "reviewedDecompositions": [{"roadmap": item["roadmapId"], "status": item["status"], "nodes": item["nodes"],
                                    "review": item["review"]["status"], "deferredLinks": len(item.get("deferredLinks", []))}
                                   for item in atlas["decompositions"]],
        "terminalTargets": sum(stage["id"] not in parent_ids and not stage.get("expansion") for stage in atlas["stages"]),
        "groups": len(atlas["groups"]),
        "unmappedAreas": len(atlas["opportunities"]["areas"]),
        "areasWithRoadmaps": sum(1 for group in atlas["groups"] + atlas["opportunities"]["groups"] if any(roadmap.get("group") == group["id"] for roadmap in atlas["roadmaps"])),
        "additionalRegions": len(atlas["opportunities"]["groups"]),
        "mathematicalSummaries": len(atlas["roadmaps"]),
        "editedRoadmapSummaries": len(atlas["roadmapSummaries"]),
        "curatedStagePresentations": len(atlas["stagePresentation"]),
        "administrativeStages": sum(bool(item.get("hidden")) for item in atlas["stagePresentation"].values()),
        "mathematicalStars": sum(not atlas["stagePresentation"].get(stage["id"], {}).get("hidden") for stage in atlas["stages"]),
        "plainTextPlanetLabels": len(atlas["landmarkLabels"]),
        "hiddenPlanets": len(atlas["landmarkHidden"]),
        "mappedStageStatuses": len(atlas["mappedStageStatuses"]),
        "bibliographicSources": len(atlas["bibliography"]["works"]),
        "roadmapEdges": len(atlas["edges"]),
        "stageEdges": len(atlas["stageEdges"]),
        "sourceDocuments": sum(1 for _ in (ROOT / "content").rglob("*.md")),
        "htmlBytes": output.stat().st_size,
        "htmlSha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "networkDependencies": 0,
        "localProgressOverridesIncluded": False,
        "assets": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
    }
    (ROOT / "BUILD.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "index.html", help="HTML output path; defaults to the repository's index.html")
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
