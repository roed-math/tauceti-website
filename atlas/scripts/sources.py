"""Where the roadmaps' mathematics comes from, and whether a reader can get it.

A roadmap stage is only checkable by someone who can read its source. Cite a book
behind a paywall and the stage is unreadable to most readers, and to every worker,
so the work stalls on an acquisition nobody can make. This keeps a register of the
works the roadmaps cite, `research/blueprint/sources/ACCESS.json`, records for each
whether it is freely available, and names the free substitute where one exists.

    python3 scripts/sources.py            # the report
    python3 scripts/sources.py --check    # exit 1 on a citation the register does not know

The check is the part that matters: a link to a publisher is fine when the register
says which work it is and what a reader without a subscription should do instead. A
link the register has never seen is a new dependency that nobody has decided about.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "research" / "blueprint" / "sources" / "ACCESS.json"
REPORT = ROOT / "research" / "blueprint" / "sources" / "REPORT.md"
ROADMAPS = ROOT / "research" / "blueprint" / "atlas" / "roadmaps"
CONTENT = ROOT / "content"

URL = re.compile(r'https?://[^\s<>()\[\]"\'`]+')

# What separates a source from a mention. A roadmap that names a book in a reading list
# has not made it a dependency; one that pins a chapter, a theorem or an extraction point
# has, because a worker has to open that page to do the stage.
LOCATOR = re.compile(r"(?:Ch(?:apter|apters|\.|s\.)?|§{1,2}|Theorem|Thm\.?|Prop(?:osition)?|Lemma|Cor(?:ollary)?"
                     r"|Appendix|pp?\.)\s*[IVXL\d]", re.I)
MARKER = re.compile(r"\bextract\b|reference for|source for|primary source|source route"
                    r"|principal (?:construction )?reference", re.I)


def register(path: Path = REGISTER) -> dict:
    """The access register."""
    return json.loads(Path(path).read_text())


def works(reg: dict) -> dict:
    """The register's works by id."""
    return {work["id"]: work for work in reg["works"]}


def citations(text: str, reg: dict) -> set:
    """The ids of the registered works this text cites.

    Patterns are written to match a citation and not a passing mention: `Shimura,`
    is the book, `Shimura variety` is not.
    """
    found = set()
    for work in reg["works"]:
        patterns = work.get("match", []) + [re.escape(url) for url in work.get("urls", [])]
        if any(re.search(pattern, text) for pattern in patterns):
            found.add(work["id"])
    return found


def citation_role(text: str, work: dict, window: int = 80) -> str:
    """Whether this document depends on the work, or merely names it.

    "source" when some citation of it is pinned -- a chapter, a theorem, an
    extraction point -- and "background" when every mention is a bare reference.
    The distinction is the difference between a book somebody has to obtain and a
    book somebody listed as further reading.
    """
    patterns = work.get("match", []) + [re.escape(url) for url in work.get("urls", [])]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            near = text[max(0, match.start() - window):match.end() + window]
            if LOCATOR.search(near) or MARKER.search(near):
                return "source"
    return "background"


def dependencies(documents: dict, reg: dict, role: str = "") -> dict:
    """Work id -> the roadmaps that cite it, optionally only those depending on it.

    `role` is "source" for the roadmaps whose mathematics rests on the work, or
    "background" for those that only name it. Empty counts every citation.
    """
    index = works(reg)
    found: dict = {}
    for name, text in documents.items():
        for wid in citations(text, reg):
            if role and citation_role(text, index[wid]) != role:
                continue
            found.setdefault(wid, set()).add(name)
    return {wid: sorted(names) for wid, names in found.items()}


def unregistered(documents: dict, reg: dict) -> list:
    """(roadmap, url) for every link to a publisher the register does not account for."""
    known = {url for work in reg["works"] for url in work.get("urls", [])}
    hosts = {host.lower() for host in reg["checkHosts"]}
    found = []
    for name in sorted(documents):
        for url in URL.findall(documents[name]):
            url = url.rstrip(".,;:)")
            if urlparse(url).netloc.lower() in hosts and url not in known:
                found.append((name, url))
    return found


def unlawful(documents: dict, reg: dict) -> list:
    """(where, url) for every link to a site that hosts copies without permission.

    These are not free sources, whatever they cost: citing one puts an unlicensed
    copy into the record and leaves the claim resting on a text nobody may legally
    read. A hit is a failure, not a warning -- replace the citation with the work
    itself, and re-read the passage in a copy that may be read.
    """
    hosts = [host.lower() for host in reg.get("blockedHosts", [])]
    found = []
    for name in sorted(documents):
        for url in URL.findall(documents[name]):
            url = url.rstrip(".,;:)")
            host = urlparse(url).netloc.lower()
            if any(host == bad or host.endswith("." + bad) for bad in hosts):
                found.append((name, url))
    return found


def blocked(deps: dict, reg: dict, kind: str = "") -> list:
    """The cited works a reader cannot get and no free source replaces.

    These are what someone has to buy or borrow for the work to proceed. A work the maintainer has
    provided (`provided`) is no longer one of them. `kind`
    narrows to "book", "article" or "notes"; empty means all of them.
    """
    index = works(reg)
    wanted = [index[work] for work in deps
              if index[work].get("access") != "free" and not index[work].get("substitute") and not index[work].get("provided")
              and (not kind or index[work].get("kind", "book") == kind)]
    return sorted(wanted, key=lambda work: (-len(deps[work["id"]]), work["id"]))


def substitutable(deps: dict, reg: dict) -> list:
    """(work, its free substitute) for the restricted works a free source replaces."""
    index = works(reg)
    pairs = [(index[work], index[index[work]["substitute"]]) for work in deps
             if index[work].get("access") != "free" and index[work].get("substitute")]
    return sorted(pairs, key=lambda pair: (-len(deps[pair[0]["id"]]), pair[0]["id"]))


def leaning(documents: dict, reg: dict, share: float = 0.7, least: int = 3) -> list:
    """Roadmaps whose citations nearly all point at one work.

    A roadmap built from a single book inherits that book's arrangement, which is
    both a mathematical weakness -- one author's choices, one route through the
    material -- and, where the book is not free, a dependency that cannot be met.
    `share` is how much of the citation traffic the leading work has to carry, and
    `least` how many times it must be named before the count means anything.
    """
    index = works(reg)
    found = []
    for name in sorted(documents):
        text = documents[name]
        counts = {}
        for wid in citations(text, reg):
            patterns = index[wid].get("match", []) + [re.escape(url) for url in index[wid].get("urls", [])]
            counts[wid] = sum(len(re.findall(pattern, text)) for pattern in patterns)
        total = sum(counts.values())
        if not total:
            continue
        top, hits = max(counts.items(), key=lambda kv: kv[1])
        if hits >= least and hits / total >= share:
            found.append({"roadmap": name, "work": top, "title": index[top]["title"],
                          "share": hits / total, "hits": hits, "works": len(counts),
                          "access": index[top].get("access", "restricted"),
                          "substitute": index[top].get("substitute")})
    return sorted(found, key=lambda row: (-row["share"], -row["hits"], row["roadmap"]))


def only(deps: dict, reg: dict) -> dict:
    """Roadmap -> the books to provide that nothing else cites.

    Most of the list is here: a book two roadmaps need is a shared dependency worth
    buying, while a book one roadmap alone names is that roadmap's own debt, and
    whoever writes it can often reach the same mathematics another way.
    """
    grouped: dict = {}
    for work in blocked(deps, reg, "book"):
        names = deps[work["id"]]
        if len(names) == 1:
            grouped.setdefault(names[0], []).append(work["title"])
    return {name: sorted(titles) for name, titles in sorted(grouped.items(),
            key=lambda item: (-len(item[1]), item[0]))}


def report(deps: dict, reg: dict) -> str:
    """The report: what must be provided, what can be swapped, and what is already free."""
    index = works(reg)
    lines = []

    def listing(title, wanted):
        lines.append(f"{title} ({len(wanted)}):")
        for work in wanted:
            names = deps[work["id"]]
            lines.append(f"  {work['title']}")
            lines.append(f"    {len(names)} roadmap(s): {', '.join(names)}")
            if work.get("note"):
                lines.append(f"    {work['note']}")
        lines.append("")

    listing("Books to provide -- restricted, no free source covers them, and a stage pins a "
            "chapter or theorem to them", blocked(deps, reg, "book"))
    listing("Articles behind a subscription", blocked(deps, reg, "article"))
    swaps = substitutable(deps, reg)
    lines.append(f"Restricted works a free source already covers ({len(swaps)}):")
    for work, free in swaps:
        lines.append(f"  {work['title']}  ->  {free['title']}")
        lines.append(f"    {len(deps[work['id']])} roadmap(s): {', '.join(deps[work['id']])}")
    alone = only(deps, reg)
    lines.append(f"Of those books, the ones a single roadmap cites "
                 f"({sum(len(t) for t in alone.values())} across {len(alone)} roadmaps):")
    for name, titles in alone.items():
        lines.append(f"  {name} ({len(titles)})")
        for title in titles:
            lines.append(f"    {title}")
    lines.append("")
    free = [index[work] for work in deps if index[work].get("access") == "free"]
    lines.append(f"Freely available and already cited: {len(free)} works.")
    return "\n".join(lines)


def leaning_report(rows: list) -> str:
    """The roadmaps that lean on one work, worst first."""
    lines = [f"Roadmaps whose citations nearly all point at one work ({len(rows)}):"]
    for row in rows:
        lines.append(f"  {row['share']:.0%} of {row['hits']} citations  {row['roadmap']}")
        standing = row["access"] + (f", free substitute {row['substitute']}" if row.get("substitute") else "")
        lines.append(f"    {row['title']} [{standing}]")
    return "\n".join(lines)


def roadmap_name(stem: str) -> str:
    """One name per roadmap, whatever file it came from.

    The atlas files carry the qualified ids (`tauceti_TauCetiRoadmap_AlgebraicCurves`)
    while the prose sits under the bare name, and a report that lists both as separate
    roadmaps overstates how many depend on a source.
    """
    for prefix in ("tauceti_TauCetiRoadmap_", "tauceti_Completed_", "tauceti_"):
        if stem.startswith(prefix):
            return stem[len(prefix):]
    return stem


def documents(content: Path = CONTENT, roadmaps: Path = ROADMAPS) -> dict:
    """Every roadmap document, by roadmap name: the prose a worker reads.

    A roadmap's prose is spread over its campaign README, its Tau Ceti README and
    the stage descriptions in its atlas JSON. All of them are joined under the one
    name rather than one replacing another, or the citations in whichever was read
    first would vanish from the report.
    """
    found: dict = {}

    def add(name, text):
        name = roadmap_name(name)
        found[name] = found[name] + "\n" + text if name in found else text

    for path in sorted(Path(content).rglob("*.md")):
        # content/<section>/<roadmap>/<file>.md belongs to the roadmap; a file directly
        # inside a section (a guide, say) stands for itself.
        section = path.relative_to(content).parts[:-1]
        add(path.parent.name if len(section) > 1 else path.stem, path.read_text())
    for path in sorted(Path(roadmaps).glob("*.json")):
        roadmap = json.loads(path.read_text())
        text = [roadmap.get("summary") or ""]
        text += [(stage.get("description") or "") for stage in roadmap.get("stages", [])]
        add(path.stem, "\n".join(text))
    return found


def everything(roots=(CONTENT, ROOT / "research")) -> dict:
    """Every text file under the roadmap and research trees, by repository path.

    The roadmap documents are what the citation report is about, but an unlawful
    copy can be cited anywhere -- the one this check was written for sat in an
    errata review -- so the sweep for those reads the lot.
    """
    found = {}
    for root in roots:
        for path in sorted(Path(root).rglob("*")):
            if path.suffix in (".md", ".json") and path.is_file():
                found[str(path.relative_to(ROOT))] = path.read_text(errors="ignore")
    return found


def main(argv: list) -> int:
    reg = register()
    docs = documents()
    deps = dependencies(docs, reg, role="source")
    mentions = dependencies(docs, reg, role="background")
    rows = leaning(docs, reg)
    print(report(deps, reg))
    spare = sorted({work for work in mentions} - set(deps))
    index = works(reg)
    named = [index[work]["title"] for work in spare
             if index[work].get("kind", "book") == "book" and index[work].get("access") != "free"
             and not index[work].get("substitute") and not index[work].get("provided")]
    print(f"\nNamed in a reading list but nothing is pinned to them ({len(named)}) -- "
          f"no one has to obtain these:")
    for title in sorted(named):
        print(f"  {title}")
    print()
    print(leaning_report(rows))
    banned = unlawful(everything(), reg)
    if banned:
        print(f"\n{len(banned)} link(s) to a site that hosts copies without permission:")
        for name, url in banned:
            print(f"  [{name}] {url}")
    loose = unregistered(docs, reg)
    if loose:
        print(f"\n{len(loose)} link(s) to a publisher that the register does not know:")
        for name, url in loose:
            print(f"  [{name}] {url}")
    if "--write" in argv:
        REPORT.write_text("# Sources the roadmaps depend on\n\n"
                          "Generated by `python3 scripts/sources.py --write`; the decisions live in\n"
                          "`ACCESS.json`, which is the file to edit.\n\n```\n" + report(deps, reg)
                          + "\n\n" + leaning_report(rows) + "\n```\n")
    if "--check" in argv:
        return 1 if loose or banned else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
