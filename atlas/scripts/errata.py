#!/usr/bin/env python3
"""The register of mistakes found in published sources (research/blueprint/PROTOCOL.md, section 18).

  python3 scripts/errata.py

Collects every finding recorded under `sourceIssues` in the paper extractions
(research/blueprint/papers/PAPER-*.result.json) and the blueprint packets
(research/blueprint/packets/*.json) and writes research/errata/REGISTER.md,
for readers, and data/source-issues.json. A finding is confirmed (or rejected)
only by a verdict from a finished review job that reviews a job which wrote
the file it is recorded in; any other verdict leaves it awaiting review. New
confirmed mistakes come first, then new ones awaiting review, then those
already corrected in print. The intake runs this after every merge.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIND = {"misprint": "Misprint", "error": "Error", "gap": "Gap"}


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def valid_reviews(path: str, jobs: list) -> set:
    """The finished review jobs that review a job which wrote the file."""
    writers = {job["id"] for job in jobs if path in (job.get("outputs") or [])}
    return {job["id"] for job in jobs if job["kind"] == "review" and job.get("state") == "done" and writers & set(job.get("after") or [])}


def collect(root: Path = ROOT, jobs: list | None = None) -> dict:
    if jobs is None:
        jobs = (load(root / "research" / "blueprint" / "queue.json") or {"jobs": []})["jobs"]
    papers = {entry["id"]: entry for entry in (load(root / "research" / "blueprint" / "papers" / "papers.json") or {}).get("papers", [])}
    issues, unchecked, older = [], [], []
    files = [(p, "paper") for p in sorted((root / "research" / "blueprint" / "papers").glob("PAPER-*.result.json"))]
    files += [(p, "packet") for p in sorted((root / "research" / "blueprint" / "packets").glob("*.json"))]
    # Files of the errata jobs, which record what work finished earlier found (PROTOCOL.md section 18).
    errata = [(p, "errata") for p in sorted((root / "research" / "blueprint" / "errata").glob("*.json"))]
    checked_by_errata = set()
    for path, _ in errata:
        data = load(path)
        if isinstance(data, dict) and isinstance(data.get("sourceIssues"), list):
            checked_by_errata.add(data.get("paper") or data.get("roadmapId") or path.stem)
    files += errata
    for path, kind in files:
        data = load(path)
        if not isinstance(data, dict):
            continue
        relative = str(path.relative_to(root))
        if kind in ("paper", "errata") and (data.get("paper") or kind == "paper"):
            owner = data.get("paper") or path.name.split(".")[0]
            source = data.get("source") or {}
            default = papers.get(owner, {}).get("citation") or ", ".join(x for x in (source.get("authors"), source.get("title")) if x)
            sources = {}
        else:
            owner = data.get("roadmapId") or path.stem
            default = f"Sources of the blueprint of {owner}"
            # An errata file for a blueprint cites the sources listed in its packet.
            listing = data if kind == "packet" else (load(root / "research" / "blueprint" / "packets" / f"{owner}.json") or {})
            sources = {s.get("id"): ", ".join(x for x in (s.get("authors"), s.get("title"), s.get("edition")) if x) for s in listing.get("sources") or []}
        listed = data.get("sourceIssues")
        if not isinstance(listed, list) or any(not isinstance(item, dict) or "kind" not in item for item in listed):
            # Not yet checked, or recorded in an older form that its errata job converts;
            # older-form findings are shown apart meanwhile, as recorded.
            for item in listed if isinstance(listed, list) else []:
                if isinstance(item, dict) and "kind" not in item and owner not in checked_by_errata:
                    older.append({"owner": owner, "citation": default, "file": relative, "id": item.get("id"),
                                  "locator": item.get("locator"), "finding": item.get("finding"), "resolution": item.get("resolution"),
                                  "classification": item.get("classification")})
            if kind != "errata" and owner not in checked_by_errata:
                unchecked.append(owner)
            continue
        reviewers = valid_reviews(relative, jobs)
        for item in data.get("sourceIssues") or []:
            if not isinstance(item, dict):
                continue
            review = item.get("review") if isinstance(item.get("review"), dict) else {}
            valid = review.get("by") in reviewers and review.get("verdict") in ("confirmed", "rejected")
            issues.append({**{k: item.get(k) for k in ("id", "kind", "locator", "printed", "correction", "reason", "affects", "known", "searched")},
                           "owner": owner, "file": relative, "citation": sources.get(item.get("source")) or default,
                           "status": review["verdict"] if valid else "awaiting review",
                           "reviewedBy": review.get("by") if valid else None, "reviewReason": review.get("reason") if valid else None})
    return {"purpose": "Mistakes found in published sources by the atlas's workers (research/blueprint/PROTOCOL.md section 18).",
            "issues": issues, "older": older, "unchecked": sorted(unchecked)}


def code(value) -> str:
    return "`" + " ".join(str(value or "").replace("`", "'").split()) + "`"


def entry(item: dict, confirmed: bool) -> str:
    reach = {"nothing": "", "the proof": " (it affects the proof)", "a stated result": " (it affects a stated result)"}.get(item["affects"], "")
    line = (f"- **{KIND.get(item['kind'], item['kind'])}** at {item['locator']}{reach}. The source says {code(item['printed'])}; "
            f"it should be {code(item['correction'])}. {item['reason']}")
    line += f" Confirmed by `{item['reviewedBy']}`." if confirmed else ""
    line += f" Recorded as `{item['id']}`; looked for an existing correction in: {'; '.join(item['searched'] or [])}."
    return line


def register(data: dict) -> str:
    issues = data["issues"]
    new = [i for i in issues if str(i["known"]).strip().lower() == "new"]
    confirmed = [i for i in new if i["status"] == "confirmed"]
    waiting = [i for i in new if i["status"] == "awaiting review"]
    printed = [i for i in issues if str(i["known"]).strip().lower() != "new" and i["status"] != "rejected"]
    rejected = [i for i in issues if i["status"] == "rejected"]
    out = ["# Mistakes found in published sources", "",
           "The atlas's workers read papers and books line by line to extract and plan their mathematics, and they record every "
           "mistake they find in them: misprints (slips whose intended meaning is clear), errors (false statements or steps that "
           "fail) and gaps (steps asserted without an adequate proof). A finding counts as confirmed once an independent reviewer "
           "has checked it at its locator. Each finding says where its worker looked for an existing correction; a new one is "
           "not corrected in any erratum or later version they found. Nothing here has been sent to the authors.",
           "", "Collected by `scripts/errata.py` from the paper extractions and blueprint packets (research/blueprint/PROTOCOL.md, "
           "section 18); the data is in `data/source-issues.json`.", "",
           f"{len(confirmed)} new mistakes confirmed · {len(waiting)} awaiting review · {len(printed)} already corrected in print · "
           f"{len(rejected)} rejected on review · {len(data['unchecked'])} extractions and packets not yet checked.", ""]

    def grouped(items, confirmed_list):
        by_source = defaultdict(list)
        for item in items:
            by_source[(item["citation"], item["owner"])].append(item)
        lines = []
        for (citation, owner), group in sorted(by_source.items(), key=lambda kv: kv[0][1]):
            lines += [f"### {citation} (`{owner}`)", ""] + [entry(item, confirmed_list) for item in sorted(group, key=lambda i: i["id"])] + [""]
        return lines or ["None yet.", ""]
    out += ["## New mistakes, confirmed", ""] + grouped(confirmed, True)
    out += ["## New mistakes awaiting review", ""] + grouped(waiting, False)
    out += ["## Already corrected in print", ""]
    out += [f"- {item['citation']} (`{item['owner']}`), {item['locator']}: corrected in {item['known']}." for item in sorted(printed, key=lambda i: i["id"])] or ["None yet."]
    out += ["", "## Rejected on review", "", f"{len(rejected)} findings were rejected by their reviewers; they are kept in `data/source-issues.json`.", ""]
    out += ["## Recorded in an older form", "",
            "Found before these findings had a standard form, and not yet reviewed: each is being restated and checked by its "
            "paper's errata job. Shown as their workers recorded them.", ""]
    by_source = defaultdict(list)
    for item in data.get("older", []):
        by_source[(item["citation"], item["owner"])].append(item)
    for (citation, owner), group in sorted(by_source.items(), key=lambda kv: kv[0][1]):
        out += [f"### {citation} (`{owner}`)", ""]
        out += [f"- **{item['id']}** at {item['locator']}" + (f" ({item['classification']})" if item.get("classification") else "")
                + f". {item['finding']} *Resolution recorded:* {item['resolution']}" for item in group] + [""]
    if not by_source:
        out += ["None.", ""]
    out += ["## Not yet checked", "", "These extractions and packets were written before mistakes were recorded, and are being checked: "
            + (", ".join(f"`{owner}`" for owner in data["unchecked"]) or "none") + ".", ""]
    return "\n".join(out)


def main() -> int:
    data = collect(ROOT)
    (ROOT / "research" / "errata").mkdir(parents=True, exist_ok=True)
    (ROOT / "research" / "errata" / "REGISTER.md").write_text(register(data), encoding="utf-8")
    (ROOT / "data" / "source-issues.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    statuses = defaultdict(int)
    for item in data["issues"]:
        statuses[item["status"]] += 1
    print(f"{len(data['issues'])} findings {dict(statuses)}; {len(data['unchecked'])} not yet checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
