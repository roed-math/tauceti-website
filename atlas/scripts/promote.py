#!/usr/bin/env python3
"""Promote independently reviewed work into the atlas (research/blueprint/PROTOCOL.md, section 8).

Usage:
  python3 scripts/promote.py [--dry-run]

A blueprint packet or a link map goes live when its review object says
"accepted" and names, as "independent-review-<job>", a review job that is
finished in the queue and reviews a job that wrote the file. It goes live as it
stood when that review accepted it: the file is copied into data/, the only
place the atlas reads worker output from, and later edits wait for the next
accepted review. A blueprint takes its roadmap document with it, and a packet
for a new roadmap its definition.

Every candidate is tried in the atlas build before it is kept; one that breaks
the build is refused, rolled back and recorded with the reason, so that one bad
file never stops the rest. data/promotions.json records what went live, from
which review, and what was refused. The exit status is 0 in every such case.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = "data/promotions.json"
PURPOSE = ("Work promoted into the atlas by scripts/promote.py: each source file, the data files it became, and the review "
           "that accepted it; and work refused, with the reason. A file goes live again only after a new accepted review.")


def signature(review) -> str:
    """One review, identified by everything it says."""
    return hashlib.sha256(json.dumps(review, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def review_job(review):
    reviewer = str(review.get("reviewer") or "")
    return reviewer[len("independent-review-"):] if reviewer.startswith("independent-review-") else None


def decide(path: str, data: dict, jobs: list, record: dict) -> tuple:
    """("promote" | "skip" | "refuse", reason) for one candidate file."""
    review = data.get("review") if isinstance(data, dict) else None
    if not isinstance(review, dict) or review.get("status") != "accepted":
        return "skip", "no accepted review"
    mark = signature(review)
    if any((record.get(kind) or {}).get(path, {}).get("review") == mark for kind in ("promoted", "refused")):
        return "skip", "this review was acted on already"
    job_id = review_job(review)
    if not job_id:
        return "refuse", "the review names no review job: reviewer must be independent-review-<job>"
    by_id = {job["id"]: job for job in jobs}
    job = by_id.get(job_id)
    if job is None:
        return "refuse", f"{job_id} is not a job of the queue"
    writers = {j["id"] for j in jobs if path in (j.get("outputs") or [])}
    if not writers & set(job.get("after") or []):
        return "refuse", f"{job_id} does not review a job that wrote {path}"
    if job.get("state") != "done":
        return "skip", f"{job_id} is not finished"
    return "promote", f"accepted by {job_id}"


def destinations(root: Path, path: str, data: dict, atlas_roadmaps: set) -> tuple:
    """(files to copy as (source, destination), problem or None)."""
    name = Path(path).name
    if path.startswith("research/blueprint/links/"):
        return [(path, f"data/links/{name}")], None
    if path.startswith("research/blueprint/restructure/"):
        report = path.replace(".result.json", ".md")
        return [(path, f"data/restructure/{name}")] + ([(report, f"data/restructure/{Path(report).name}")] if (root / report).exists() else []), None
    files = [(path, f"data/blueprints/{name}")]
    document = f"research/blueprint/readmes/{Path(name).stem}.md"
    if (root / document).exists():
        files.append((document, f"data/blueprints/{Path(name).stem}.md"))
    roadmap = data.get("roadmapId")
    if roadmap not in atlas_roadmaps:
        definition = f"research/blueprint/roadmaps/{roadmap}.json"
        if not (root / definition).exists():
            return [], f"{roadmap} is a new roadmap, but {definition} is missing"
        files.append((definition, f"data/blueprints/roadmaps/{roadmap}.json"))
    return files, None


def candidates(root: Path) -> list:
    bp = root / "research" / "blueprint"
    found = [str(p.relative_to(root)) for folder in ("packets", "links") for p in sorted((bp / folder).glob("*.json"))]
    return found + [str(p.relative_to(root)) for p in sorted((bp / "restructure").glob("RS-*.result.json"))]


def promote(root: Path = ROOT, validate=None, now=None, dry_run=False) -> dict:
    """Promote every candidate whose review allows it. validate() builds the atlas and raises on a problem."""
    now = now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    jobs = json.loads((root / "research" / "blueprint" / "queue.json").read_text(encoding="utf-8"))["jobs"]
    record_path = root / RECORD
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {}
    record.setdefault("purpose", PURPOSE)
    record.setdefault("promoted", {})
    record.setdefault("refused", {})
    atlas_roadmaps = {r["id"] for r in json.loads((root / "data" / "atlas.json").read_text(encoding="utf-8"))["roadmaps"]}
    summary = {"promoted": [], "refused": [], "waiting": []}
    if validate and not dry_run:
        # The atlas must build as it is before any candidate is blamed for breaking it.
        validate()
    for path in candidates(root):
        try:
            data = json.loads((root / path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        verdict, reason = decide(path, data, jobs, record)
        if verdict == "skip":
            if reason.endswith("not finished"):
                summary["waiting"].append((path, reason))
            continue
        files, problem = destinations(root, path, data, atlas_roadmaps) if verdict == "promote" else ([], reason)
        if problem is None:
            problem = stage(root, files, validate) if not dry_run else None
        review = signature(data["review"])
        if problem:
            summary["refused"].append((path, problem))
            if not dry_run:
                record["refused"][path] = {"review": review, "reason": problem, "at": now}
            continue
        summary["promoted"].append(path)
        if not dry_run:
            record["refused"].pop(path, None)
            record["promoted"][path] = {"to": [dest for _, dest in files], "review": review,
                                        "reviewer": data["review"].get("reviewer"), "reviewDate": data["review"].get("date"),
                                        "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(), "promotedAt": now}
    if not dry_run and (summary["promoted"] or summary["refused"]):
        record_path.write_text(json.dumps(record, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return summary


SITE = "https://cbirkbeck.github.io/tauceti-explorer/"


def notices(root: Path, summary: dict, jobs: list) -> list:
    """(issue number, comment) for the workers: on the issue of each job that wrote promoted or refused work."""
    mapping_path = root / "research" / "blueprint" / "issues.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}
    said = []
    for path, problem in [(path, None) for path in summary["promoted"]] + list(summary["refused"]):
        try:
            roadmap = json.loads((root / path).read_text(encoding="utf-8")).get("roadmapId", "")
        except (OSError, ValueError):
            roadmap = ""
        for job in jobs:
            if path in (job.get("outputs") or []) and job["id"] in mapping:
                if problem is None:
                    body = (f"`{path}` is now in the atlas, as its independent review accepted it: "
                            f"{SITE}#view=roadmap&id={roadmap}. Later changes go live after their own accepted review.")
                else:
                    body = (f"The atlas could not take in `{path}` after its accepted review: {problem}. "
                            "Fix the file in a new pull request; it goes live after its next accepted review.")
                said.append((mapping[job["id"]], body))
    return said


def stage(root: Path, files: list, validate) -> str | None:
    """Copy the files into place and try the build; on failure restore what was there. Returns the problem, if any."""
    saved = {}
    for source, dest in files:
        target = root / dest
        saved[dest] = target.read_bytes() if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / source, target)
    try:
        if validate:
            validate()
    except Exception as exc:  # the build's own error says what is wrong
        for dest, content in saved.items():
            if content is None:
                (root / dest).unlink(missing_ok=True)
            else:
                (root / dest).write_bytes(content)
        return str(exc) or exc.__class__.__name__
    return None


def build_check():
    sys.path.insert(0, str(ROOT / "scripts"))
    from build import assemble
    assemble(require_distances=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="say what would be promoted, change nothing")
    parser.add_argument("--comment", action="store_true", help="tell the workers on the issues of the jobs that wrote the work")
    args = parser.parse_args()
    summary = promote(ROOT, validate=build_check, dry_run=args.dry_run)
    if args.comment and not args.dry_run:
        import subprocess
        jobs = json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text(encoding="utf-8"))["jobs"]
        for number, body in notices(ROOT, summary, jobs):
            subprocess.run(["gh", "issue", "comment", str(number), "--body", body], cwd=ROOT, check=False, capture_output=True)
    for path in summary["promoted"]:
        print("promoted", path)
    for path, reason in summary["refused"]:
        print("refused", path, "-", reason)
    for path, reason in summary["waiting"]:
        print("waiting", path, "-", reason)
    if not any(summary.values()):
        print("nothing to promote")
    return 0


if __name__ == "__main__":
    sys.exit(main())
