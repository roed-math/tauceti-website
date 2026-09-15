#!/usr/bin/env python3
"""Build an offline, self-contained atlas using Python's standard library."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def safe_script(text: str) -> str:
    return re.sub(r"</script", r"<\\/script", text, flags=re.IGNORECASE)


def comment_text(text: str) -> str:
    return text.replace("--", "—")


def build(output: Path) -> dict:
    atlas = json.loads(read_text("data/atlas.json"))
    atlas["progress"] = json.loads(read_text("data/status.json"))
    atlas["regions"] = json.loads(read_text("data/regions.json"))
    atlas["opportunities"] = json.loads(read_text("data/opportunities.json"))
    atlas["stagePresentation"] = json.loads(read_text("data/stage-presentation.json"))
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
    assets = {
        "D3": "vendor/d3.v5.15.0.min.js",
        "KATEX": "vendor/katex.v0.16.28.min.js",
        "MARKDOWN": "src/markdown.js",
        "GRAPH": "src/graph.js",
        "CAMERA": "src/camera.js",
        "PROGRESS": "src/progress.js",
        "LANDMARKS": "src/landmarks.js",
        "PRESENTATION": "src/presentation.js",
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
    parent_ids = {stage.get("parentStageId") for stage in atlas["stages"] if stage.get("parentStageId")}
    source_paths = ["src/shell.html", *style_paths, *assets.values(), "data/atlas.json", "data/status.json", "data/regions.json", "data/opportunities.json", "data/stage-presentation.json", "NOTICE", "LICENSE", "vendor/D3-LICENSE.txt", "vendor/KaTeX-LICENSE.txt"]
    report = {
        "roadmaps": len(atlas["roadmaps"]),
        "stages": len(atlas["stages"]),
        "terminalTargets": sum(stage["id"] not in parent_ids for stage in atlas["stages"]),
        "groups": len(atlas["groups"]),
        "unmappedAreas": len(atlas["opportunities"]["areas"]),
        "additionalRegions": len(atlas["opportunities"]["groups"]),
        "mathematicalSummaries": len(atlas["roadmaps"]),
        "curatedStagePresentations": len(atlas["stagePresentation"]),
        "administrativeStages": sum(bool(item.get("hidden")) for item in atlas["stagePresentation"].values()),
        "mathematicalStars": sum(not atlas["stagePresentation"].get(stage["id"], {}).get("hidden") for stage in atlas["stages"]),
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
