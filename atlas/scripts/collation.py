#!/usr/bin/env python3
"""Which text each paper's findings were read from, and which still need the version of record.

A published paper and its preprint are not the same document. Bhargava–Shankar–
Taniguchi–Thorne–Tsimerman–Zhao's Theorem 1.3(a) carries a factor |Disc(C)|^ε in
the Journal of the AMS that arXiv v1 does not, and a finding written against the
preprint said the published theorem had to be withdrawn. It did not: the
published statement is correct, and the preprint's was the defect.

Nothing in the records said which text had been read, so nothing could catch it.
This reports that, per paper:

    python3 scripts/collation.py             # the exposure, worst first
    python3 scripts/collation.py --write     # also write the worklist and data/collation.json
    python3 scripts/collation.py --resolve   # ask OpenAlex for a copy a worker can fetch

A paper is exposed when a published version exists, the record shows only a
preprint or nothing at all, and some finding quotes a stated result. Those are
the claims that could be about a sentence the published paper no longer contains.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "research" / "blueprint" / "papers"
ERRATA = ROOT / "research" / "blueprint" / "errata"
OUT = ROOT / "research" / "blueprint" / "collation"
DATA = ROOT / "data" / "collation.json"

# Publisher hosts that refuse automated fetches, so a worker cannot collate there and a
# person has to. Checked by hand: each returns 403 to a scripted request.
BLOCKED = ("ams.org", "link.springer.com", "sciencedirect.com", "cambridge.org", "jstor.org",
           "onlinelibrary.wiley.com", "degruyter.com", "tandfonline.com", "academic.oup.com")
PUBLISHER = re.compile(r"(doi\.org/10\.|" + "|".join(host.replace(".", r"\.") for host in BLOCKED) +
                       r"|annals\.math|msp\.org|numdam|projecteuclid|ems\.press|par\.nsf\.gov|pmc\.ncbi)", re.I)
READ_IT = re.compile(r"read|collat|sha-?256|offprint|published (pdf|text|version)", re.I)
PREPRINT = re.compile(r"arxiv|preprint|author copy", re.I)
JOURNAL = re.compile(r"(Ann(als|\.)|Invent|J\.|Journal|Publ|Duke|Compositio|Forum|Bull|Proc|Trans|IH[ÉE]S|"
                     r"Math(ematische|ematics|\.)|Algebra|Geometry|Topology|Crelle|Astérisque)\b.{0,40}\(?(19|20)\d\d", re.I)


def versions(record: dict) -> list:
    """The structured readings a record declares."""
    listed = record.get("sourceVersions") or (record.get("reviewScope") or {}).get("sourceVersions") or []
    return [entry for entry in listed if isinstance(entry, dict)]


def provenance(record: dict) -> str:
    """"published", "preprint" or "unknown": which text this record was read from.

    A declared reading wins. Otherwise the workers' free-text notes are read, and
    only a publisher copy they say they *read* counts -- naming a DOI is not reading it.
    """
    declared = {str(entry.get("kind") or "").lower() for entry in versions(record)}
    if "published" in declared:
        return "published"
    if declared:
        return "preprint"
    notes = " ".join(str(item.get("searched") or "") + " " + str(item.get("known") or "")
                     for item in record.get("sourceIssues") or [] if isinstance(item, dict))
    if PUBLISHER.search(notes) and READ_IT.search(notes):
        return "published"
    if PREPRINT.search(notes):
        return "preprint"
    return "unknown"


def published_exists(paper: dict) -> bool:
    """Whether a version of record exists at all: an arXiv-only paper has none."""
    citation = str(paper.get("citation") or "")
    link = str(paper.get("link") or "")
    if PUBLISHER.search(link):
        return True
    if re.search(r"arxiv", link, re.I) and not JOURNAL.search(citation):
        return False
    return bool(JOURNAL.search(citation))


def stated(record: dict) -> list:
    """The findings that quote a stated result -- the ones a revision can invalidate."""
    return [item for item in record.get("sourceIssues") or []
            if isinstance(item, dict) and item.get("affects") == "a stated result"]


def exposure(records: dict, papers: dict) -> list:
    """Papers whose quoted statements rest on a text that is not the version of record."""
    rows = []
    for name, record in sorted(records.items()):
        paper = papers.get(name) or {}
        quoted = stated(record)
        if not quoted or not published_exists(paper):
            continue
        read = provenance(record)
        if read == "published":
            continue
        rows.append({"paper": name, "provenance": read, "stated": len(quoted),
                     "findings": len(record.get("sourceIssues") or []),
                     "citation": paper.get("citation", ""), "link": paper.get("link", ""),
                     "blocked": any(host in str(paper.get("link") or "") for host in BLOCKED),
                     "locators": [str(item.get("locator") or "") for item in quoted]})
    return sorted(rows, key=lambda row: (-row["stated"], row["paper"]))


def requests_page(rows: list) -> str:
    """The worklist: what a person has to open, and exactly what to look at."""
    lines = ["# Papers needing the published text",
             "",
             "Each of these has findings that quote a stated result, but the record shows only a preprint "
             "or nothing at all. A published version exists, so the quoted sentence may have changed. "
             "Generated by `python3 scripts/collation.py --write`.",
             "",
             "For each, open the link, find the locator, and check the printed sentence against the "
             "finding's `printed` field. Where they differ, the finding belongs to the preprint and the "
             "record should say so.",
             ""]
    for row in rows:
        lines.append(f"## {row['paper']} — {row['stated']} quoted statement(s)")
        lines.append(f"{row['citation']}")
        if row["link"]:
            lines.append(f"Link: {row['link']}" + ("  (publisher blocks automated fetches)" if row["blocked"] else ""))
        lines.append(f"Read from: {row['provenance']}")
        for locator in row["locators"][:12]:
            lines.append(f"- {locator}")
        if len(row["locators"]) > 12:
            lines.append(f"- … and {len(row['locators']) - 12} more")
        lines.append("")
    return "\n".join(lines)


def records() -> dict:
    """Every paper record with findings, by paper id."""
    found = {}
    for path in sorted(list(PAPERS.glob("PAPER-*.result.json")) + list(ERRATA.glob("PAPER-*.json"))):
        data = json.loads(path.read_text())
        items = [item for item in (data.get("sourceIssues") or []) if isinstance(item, dict)]
        if not items:
            continue
        name = data.get("paper") or path.stem.replace(".result", "")
        if name in found:  # an errata pass and an extraction can both carry findings
            found[name] = {**found[name], "sourceIssues": found[name]["sourceIssues"] + items,
                           "sourceVersions": versions(found[name]) + versions(data)}
        else:
            found[name] = data
    return found


def resolve(paper: dict) -> dict:
    """Ask OpenAlex whether a copy exists that a worker could fetch."""
    title = re.search(r'"([^"]+)"', str(paper.get("citation") or ""))
    query = f"https://api.openalex.org/works?filter=title.search:{urllib.request.quote(title.group(1)[:80])}&per_page=1" if title else None
    if not query:
        return {}
    try:
        with urllib.request.urlopen(query, timeout=20) as response:
            results = json.loads(response.read()).get("results") or []
    except Exception as error:  # a lookup is an optimisation; never fail the report
        return {"error": str(error)[:80]}
    if not results:
        return {}
    work = results[0]
    best = work.get("best_oa_location") or {}
    return {"doi": work.get("doi"), "isOA": (work.get("open_access") or {}).get("is_oa"),
            "copy": best.get("pdf_url") or best.get("landing_page_url")}


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--resolve", action="store_true")
    args = parser.parse_args(argv)
    papers = {entry["id"]: entry for entry in json.loads((PAPERS / "papers.json").read_text())["papers"]}
    found = records()
    rows = exposure(found, papers)
    counts = {}
    for name, record in found.items():
        counts[provenance(record)] = counts.get(provenance(record), 0) + 1
    print(f"{len(found)} paper records: " + ", ".join(f"{n} {k}" for k, n in sorted(counts.items())))
    print(f"{len(rows)} paper(s) exposed, holding {sum(row['stated'] for row in rows)} quoted statement(s)")
    for row in rows[:12]:
        print(f"  {row['stated']:3d} statements  {row['paper']} [{row['provenance']}]"
              + ("  publisher blocks fetching" if row["blocked"] else ""))
    if args.resolve:
        for row in rows:
            row["openAlex"] = resolve(papers.get(row["paper"], {}))
        fetchable = [row for row in rows if (row.get("openAlex") or {}).get("copy")]
        print(f"{len(fetchable)} of them have a copy a worker could fetch")
    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "REQUESTS.md").write_text(requests_page(rows))
        DATA.write_text(json.dumps({"purpose": "Which text each paper's findings were read from (scripts/collation.py).",
                                    "provenance": {name: provenance(record) for name, record in sorted(found.items())},
                                    "exposed": rows}, indent=1, ensure_ascii=False) + "\n")
        print(f"written: {(OUT / 'REQUESTS.md').relative_to(ROOT)} and {DATA.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
