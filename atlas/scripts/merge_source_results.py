#!/usr/bin/env python3
"""Turn accepted source jobs into the access register.

Each SRC job moves a roadmap's citations off books a reader cannot get, and
records in its result the free works it cited and the citations it had to keep.
Workers do not edit research/blueprint/sources/ACCESS.json themselves -- fifty
jobs writing one file would collide -- so this merges the accepted ones.

    python3 scripts/merge_source_results.py            # what would change
    python3 scripts/merge_source_results.py --apply    # write it

A result counts only when its reviewer, on another account, opened the sources
and wrote `Verdict: accepted` on the first line of the review. Anything else,
including a review that reads well but never says, merges nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "research" / "blueprint" / "sources" / "results"
REVIEWS = ROOT / "research" / "blueprint" / "reviews"
REGISTER = ROOT / "research" / "blueprint" / "sources" / "ACCESS.json"
VERDICT = re.compile(r"^\s*Verdict:\s*accepted\s*$", re.I)


def accepted(results: Path = RESULTS, reviews: Path = REVIEWS) -> list:
    """The results whose review accepted them."""
    found = []
    for path in sorted(Path(results).glob("SRC-*.json")):
        review = Path(reviews) / f"REV-{path.stem}.md"
        if not review.exists():
            continue
        first = review.read_text().splitlines()[:1]
        if first and VERDICT.match(first[0]):
            found.append(json.loads(path.read_text()))
    return found


def apply_edits(results: list, root: Path = ROOT) -> tuple:
    """Move the citations in the roadmap documents. Returns (applied, refused).

    Each edit names the line as the worker read it. If the document has moved on
    since -- another job, a rewrite, a rebased branch -- the line no longer matches
    and the edit is refused rather than guessed at, and no edit of that file is
    applied: a half-applied result is worse than none, because the result and the
    document then disagree about what was done.
    """
    applied, refused = [], []
    by_file: dict = {}
    for result in results:
        for edit in result.get("edits", []):
            by_file.setdefault(edit["file"], []).append((result["roadmap"], edit))
    for name, edits in sorted(by_file.items()):
        path = Path(root) / name
        if not path.exists():
            refused += [f"{roadmap}: {name} does not exist" for roadmap, _ in edits]
            continue
        lines = path.read_text().splitlines()
        wrong = [f"{roadmap}: {name} line {edit['line']} is not what the job read"
                 for roadmap, edit in edits
                 if not (1 <= edit["line"] <= len(lines) and lines[edit["line"] - 1].rstrip() == edit["old"].rstrip())]
        if wrong:
            refused += wrong
            continue
        for roadmap, edit in edits:
            lines[edit["line"] - 1] = edit["new"]
            applied.append(f"{roadmap}: {name} line {edit['line']}")
        path.write_text("\n".join(lines) + "\n")
    return applied, refused


def merge(reg: dict, results: list) -> tuple:
    """The register with the accepted work folded in, and the notes for a person.

    Raises when a result tries to call a work free that the register has already
    decided is restricted: a job may add a free source, never reclassify a book.
    """
    works = {work["id"]: work for work in reg["works"]}
    notes = []
    for result in results:
        for entry in result.get("register", []):
            known = works.get(entry["id"])
            if known and known.get("access") == "restricted" and entry.get("access") == "free":
                raise ValueError(f"{result['roadmap']}: {entry['id']} is registered as restricted; "
                                 "a source job may not reclassify it")
            if known:
                known["urls"] = sorted(set(known.get("urls", []) + entry.get("urls", [])))
                known["match"] = sorted(set(known.get("match", []) + entry.get("match", [])))
                continue
            works[entry["id"]] = {"id": entry["id"], "kind": entry.get("kind", "notes"),
                                  "access": entry.get("access", "free"), "title": entry["title"],
                                  "match": entry.get("match", []), "urls": entry.get("urls", []),
                                  "note": entry.get("note", "")}
        for citation in result.get("citations", []):
            book = works.get(citation.get("book"))
            if not book:
                continue
            if citation.get("outcome") == "replaced" and citation.get("source"):
                book.setdefault("substitute", None)
                book["substitute"] = book["substitute"] or citation["source"]
            elif citation.get("outcome") == "kept":
                notes.append(f"{result['roadmap']}: still needs {book['title']} -- {citation.get('reason', 'no reason given')}")
    reg["works"] = sorted(works.values(), key=lambda work: work["id"])
    return reg, notes


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    results = accepted()
    reg = json.loads(REGISTER.read_text())
    before = len(reg["works"])
    reg, notes = merge(reg, results)
    print(f"{len(results)} accepted result(s); register {before} -> {len(reg['works'])} works")
    for note in notes:
        print(" ", note)
    edits = sum(len(result.get("edits", [])) for result in results)
    print(f"{edits} citation(s) to move")
    if args.apply:
        applied, refused = apply_edits(results)
        for line in applied:
            print("  moved", line)
        for line in refused:
            print("  REFUSED", line)
        REGISTER.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
        print("written; now run python3 scripts/sources.py --write --check")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
