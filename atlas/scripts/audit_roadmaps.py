#!/usr/bin/env python3
"""Audit the roadmaps: how far along, how well planned, how well sourced.

    python3 scripts/audit_roadmaps.py            # print the report
    python3 scripts/audit_roadmaps.py --write    # also write ROADMAP_AUDIT.md and data/roadmap-audit.json

A roadmap can be wrong in ways the graph cannot show: a layer that names no
source for what it asks, so nobody can check it or credit whoever proved it; a
roadmap with no sources section at all; a plan that leans on one book; a plan
pinned to a book nobody can open; finished work that no review can promote; a
whole area of mathematics that no roadmap owns. This gathers those into one
place, per roadmap, so the gaps can be turned into jobs.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sources import blocked, dependencies, documents, leaning, register  # noqa: E402

REPORT = ROOT / "research" / "blueprint" / "audit" / "ROADMAP_AUDIT.md"
DATA = ROOT / "data" / "roadmap-audit.json"

# What a citation looks like in this corpus: a source line, a bracketed key, an author-year,
# a theorem or section number, an arXiv id or a link. A layer with none of these asks for
# mathematics without saying whose.
CITATION = re.compile(r"\*\*Source[^*]*\*\*|\*Source[^*]*\*|Source route|\[[A-Z][A-Za-z\-]+\d{2}\]"
                      r"|\b[A-Z][a-zA-Z]+(?:[–-][A-Z][a-zA-Z]+)*\s*\(\d{4}\)|Theorem \d|§\s*\d|arXiv|https?://", re.I)
SOURCES_SECTION = re.compile(r"^#+\s*(sources?|references?|bibliograph)", re.I | re.M)


def cites(text: str) -> bool:
    """Whether a layer's text names a source for what it asks."""
    return bool(CITATION.search(text or ""))


def citation_gaps(stages: list) -> dict:
    """Roadmap id -> (layers without a citation, layers), for every roadmap with layers."""
    counts: dict = collections.defaultdict(lambda: [0, 0])
    for stage in stages:
        counts[stage["owner"]][1] += 1
        if not cites(stage.get("description")):
            counts[stage["owner"]][0] += 1
    return {owner: tuple(pair) for owner, pair in counts.items()}


def sourceless(roadmaps: dict) -> list:
    """Roadmaps whose document has no sources or references section."""
    return sorted(rid for rid, roadmap in roadmaps.items() if not SOURCES_SECTION.search(roadmap.get("readme") or ""))


def blueprint_paths(roadmaps: dict, jobs: list, promoted: set) -> dict:
    """Roadmap id -> "promoted", "pending", "excluded" (upstream roadmaps are linked, not
    blueprinted) or "none"."""
    pending = {rid for job in jobs if job["kind"] == "blueprint" and job.get("state") in ("pending", "external")
               for rid in job.get("roadmapIds") or []}
    found = {}
    for rid in roadmaps:
        if rid in promoted:
            found[rid] = "promoted"
        elif rid in pending:
            found[rid] = "pending"
        elif rid.startswith("tauceti:"):
            found[rid] = "excluded"
        else:
            found[rid] = "none"
    return found


def unreviewed_done(jobs: list, kinds=("blueprint", "design", "link")) -> list:
    """Finished jobs that no review job exists for: work that can never be promoted."""
    ids = {job["id"] for job in jobs}
    return sorted(job["id"] for job in jobs
                  if job["kind"] in kinds and job.get("state") == "done" and "REV-" + job["id"][3:] not in ids
                  and "REV-" + job["id"] not in ids)


def verification(roadmaps: dict, jobs: list) -> dict:
    """Roadmap id -> the kinds of finished checking it has had."""
    done: dict = collections.defaultdict(set)
    for job in jobs:
        if job.get("state") == "done":
            for rid in job.get("roadmapIds") or []:
                done[rid].add(job["kind"])
    return {rid: sorted(done[rid] & {"audit", "redteam", "compare", "review"}) for rid in roadmaps}


def progress(stages: list, reports: dict) -> dict:
    """Roadmap id -> counts of complete, in progress, planned and unknown layers."""
    status = {}
    records = reports.get("stages") if isinstance(reports.get("stages"), dict) else reports
    for sid, record in (records or {}).items():
        status[sid] = record.get("status") if isinstance(record, dict) else record
    found: dict = collections.defaultdict(lambda: collections.Counter())
    for stage in stages:
        found[stage["owner"]][status.get(stage["id"], "unknown")] += 1
    return {rid: dict(counter) for rid, counter in found.items()}


def audit() -> dict:
    atlas = json.loads((ROOT / "data" / "atlas.json").read_text())
    roadmaps = {r["id"]: r for r in atlas["roadmaps"]}
    stages = atlas["stages"]
    jobs = json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]
    promoted = {json.loads(p.read_text()).get("roadmapId") or p.stem for p in (ROOT / "data" / "blueprints").glob("*.json")}
    reports = json.loads((ROOT / "data" / "stage-status-reports.json").read_text())
    areas = json.loads((ROOT / "data" / "opportunities.json").read_text()).get("areas", [])
    reg = register()
    docs = documents()
    src = dependencies(docs, reg, role="source")
    restricted: dict = collections.defaultdict(list)
    for work in blocked(src, reg, "book"):
        for rid in src[work["id"]]:
            restricted[rid].append(work["title"])
    lean = {row["roadmap"]: row for row in leaning(docs, reg)}

    gaps = citation_gaps(stages)
    paths = blueprint_paths(roadmaps, jobs, promoted)
    prog = progress(stages, reports)
    checks = verification(roadmaps, jobs)
    no_sources = set(sourceless(roadmaps))
    per_roadmap = {}
    for rid, roadmap in roadmaps.items():
        uncited, total = gaps.get(rid, (0, 0))
        short = rid.split("/")[-1]
        per_roadmap[rid] = {
            "title": roadmap["title"], "origin": roadmap.get("origin"), "lifecycle": roadmap.get("lifecycle"),
            "layers": total, "uncited": uncited, "sourcesSection": rid not in no_sources,
            "blueprint": paths[rid], "checked": checks[rid], "progress": prog.get(rid, {}),
            "restrictedBooks": restricted.get(rid, []) or restricted.get(short, []),
            "leansOn": (lean.get(short) or {}).get("title"),
        }
    done_unreviewed = unreviewed_done(jobs)
    return {"purpose": "Per-roadmap audit of progress, planning and sourcing (scripts/audit_roadmaps.py).",
            "roadmaps": per_roadmap, "areasWithoutRoadmap": [a.get("title") for a in areas],
            "unreviewedDone": done_unreviewed,
            "totals": {"roadmaps": len(roadmaps), "layers": len(stages),
                       "uncitedLayers": sum(u for u, _ in gaps.values()),
                       "fullyUncitedRoadmaps": sum(1 for u, n in gaps.values() if n and u == n),
                       "noSourcesSection": len(no_sources),
                       "blueprint": dict(collections.Counter(paths.values())),
                       "restrictedBookRoadmaps": len(restricted), "leaningRoadmaps": len(lean),
                       "layersComplete": sum(p.get("complete", 0) for p in prog.values()),
                       "layersInProgress": sum(p.get("in_progress", 0) for p in prog.values()),
                       "untouchedRoadmaps": sum(1 for p in prog.values() if not p.get("complete") and not p.get("in_progress"))}}


def report(found: dict) -> str:
    t = found["totals"]
    lines = ["# Roadmap audit", "",
             "Generated by `python3 scripts/audit_roadmaps.py --write`. Progress, planning and sourcing, per roadmap.", "",
             f"**{t['roadmaps']} roadmaps, {t['layers']} layers.** {t['layersComplete']} layers complete, "
             f"{t['layersInProgress']} under way; {t['untouchedRoadmaps']} roadmaps with nothing complete or under way.", "",
             f"**Sourcing.** {t['uncitedLayers']} layers name no source for what they ask; {t['fullyUncitedRoadmaps']} roadmaps "
             f"have no cited layer at all; {t['noSourcesSection']} documents have no sources section. "
             f"{t['restrictedBookRoadmaps']} roadmaps pin a statement to a book with no free substitute; "
             f"{t['leaningRoadmaps']} lean on a single work.", "",
             f"**Planning.** Blueprints: {t['blueprint']}. Areas with no roadmap: {len(found['areasWithoutRoadmap'])}. "
             f"Finished work with no review job: {len(found['unreviewedDone'])}.", ""]
    lines += ["## Layers that name no source, by roadmap", ""]
    rows = sorted(found["roadmaps"].items(), key=lambda kv: -kv[1]["uncited"])
    for rid, r in rows:
        if r["uncited"]:
            lines.append(f"- {rid} — {r['uncited']} of {r['layers']}" + ("" if r["sourcesSection"] else " · no sources section")
                         + (f" · leans on {r['leansOn']}" if r["leansOn"] else ""))
    lines += ["", "## Finished work that no review can promote", ""] + [f"- {j}" for j in found["unreviewedDone"]]
    lines += ["", "## Areas with no dedicated roadmap", ""] + [f"- {a}" for a in found["areasWithoutRoadmap"]]
    return "\n".join(lines) + "\n"


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    found = audit()
    text = report(found)
    print("\n".join(text.splitlines()[:12]))
    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(text)
        DATA.write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n")
        print(f"written: {REPORT.relative_to(ROOT)}, {DATA.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
