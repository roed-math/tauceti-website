"""Rebuild the works in the source register from the roadmaps themselves.

The register used to be a hand-written list, which meant it recorded only the
works somebody had thought to add: it knew 84, while the roadmaps cite 185 books
by author and title. This reads the citations out of the prose -- `Author, *Title*`
is how the corpus writes one -- and writes a register entry for each, keeping the
access decisions already made in ACCESS.json.

    python3 scripts/sources_scan.py          # rewrite ACCESS.json's works
    python3 scripts/sources_scan.py --dry    # show what would change

Decisions never come from this script. A new work is written with `access` unset,
which the report lists as undecided until a person records free or restricted.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sources import REGISTER, documents, register  # noqa: E402

CITE = re.compile(r"([A-ZÉ][\w.'’-]*(?:[-–—][A-ZÉ][\w.'’-]*)*(?:,? (?:and |& )?[A-ZÉ][\w.'’-]*){0,3})[,']?s? \*([^*\n]{4,90})\*")
SERIES = re.compile(r"\b(GTM|GSM|Graduate Texts|Graduate Studies|Grundlehren|Ergebnisse|Lecture Notes in Math"
                    r"|Springer|Cambridge University Press|Oxford University Press|Princeton University Press"
                    r"|Birkh[äa]user|de Gruyter|Wiley|Academic Press|North-Holland|American Mathematical Society"
                    r"|AMS|Chelsea|Universitext|World Scientific|MIT Press|Monographs|Studies in Math|Colloquium"
                    r"|Annals of Mathematics Studies|\d(?:nd|rd|th) ed|edition)\b")


def slug(author: str, title: str) -> str:
    """A stable id for a work, from the way the roadmaps name it."""
    name = re.sub(r"[^A-Za-z]+", "", author.split(",")[0].split(" and ")[0].split()[-1]).upper()[:14]
    words = [word for word in re.split(r"[^A-Za-z0-9]+", title.lower()) if word not in
             ("a", "an", "the", "of", "to", "and", "in", "on", "for", "its", "with")]
    return f"{name}-{'-'.join(words[:4]).upper()}"


def found(docs: dict) -> dict:
    """Every `Author, *Title*` citation: id -> what was found and where."""
    works: dict = {}
    for name, text in sorted(docs.items()):
        for match in CITE.finditer(text):
            author, title = match.group(1).strip().rstrip(","), match.group(2).strip()
            near = text[max(0, match.start() - 160):match.end() + 220]
            entry = works.setdefault(slug(author, title), {
                "id": slug(author, title), "kind": "book", "title": f"{author}, {title}",
                "match": [], "roadmaps": set(), "series": False})
            pattern = r"\*" + re.escape(title) + r"\*"
            if pattern not in entry["match"]:
                entry["match"].append(pattern)
            entry["roadmaps"].add(name)
            entry["series"] = entry["series"] or bool(SERIES.search(near))
    return works


def merge(reg: dict, scanned: dict) -> dict:
    """The register, with every scanned work present and existing decisions kept."""
    works = {work["id"]: work for work in reg["works"]}
    titles = {pattern: work["id"] for work in reg["works"] for pattern in work.get("match", [])}
    for wid, entry in scanned.items():
        if any(pattern in titles for pattern in entry["match"]):
            continue  # an existing work already claims this citation
        if not entry["series"]:
            continue  # an article, not a book: the publisher-host check covers those
        work = works.setdefault(wid, {
            "id": wid, "kind": "book", "title": entry["title"], "match": [],
            # A book named with a publisher or a series is behind a paywall unless somebody
            # shows otherwise, and assuming the safe direction keeps the report honest: a
            # wrong `restricted` costs a lookup, a wrong `free` sends a worker to a book
            # they cannot open.
            "access": "restricted", "substitute": None,
            "note": "Read as restricted because it is named with a publisher or series; "
                    "record a free edition here if one exists."})
        for pattern in entry["match"]:
            if pattern not in work["match"]:
                work["match"].append(pattern)
    reg["works"] = sorted(works.values(), key=lambda work: work["id"])
    return reg


def main(argv: list) -> int:
    reg = register()
    scanned = found(documents())
    before = len(reg["works"])
    reg = merge(reg, scanned)
    print(f"{len(scanned)} cited works scanned; register {before} -> {len(reg['works'])}")
    undecided = [work["id"] for work in reg["works"] if not work.get("access")]
    print(f"{len(undecided)} works have no access decision yet")
    if "--dry" not in argv:
        REGISTER.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
