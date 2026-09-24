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


def dependencies(documents: dict, reg: dict) -> dict:
    """Work id -> the roadmaps that cite it."""
    found: dict = {}
    for name, text in documents.items():
        for work in citations(text, reg):
            found.setdefault(work, set()).add(name)
    return {work: sorted(names) for work, names in found.items()}


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


def blocked(deps: dict, reg: dict, kind: str = "") -> list:
    """The cited works a reader cannot get and no free source replaces.

    These are what someone has to buy or borrow for the work to proceed. `kind`
    narrows to "book", "article" or "notes"; empty means all of them.
    """
    index = works(reg)
    wanted = [index[work] for work in deps
              if index[work].get("access") != "free" and not index[work].get("substitute")
              and (not kind or index[work].get("kind", "book") == kind)]
    return sorted(wanted, key=lambda work: (-len(deps[work["id"]]), work["id"]))


def substitutable(deps: dict, reg: dict) -> list:
    """(work, its free substitute) for the restricted works a free source replaces."""
    index = works(reg)
    pairs = [(index[work], index[index[work]["substitute"]]) for work in deps
             if index[work].get("access") != "free" and index[work].get("substitute")]
    return sorted(pairs, key=lambda pair: (-len(deps[pair[0]["id"]]), pair[0]["id"]))


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

    listing("Books to provide -- restricted, and no free source covers the cited material",
            blocked(deps, reg, "book"))
    listing("Articles behind a subscription", blocked(deps, reg, "article"))
    swaps = substitutable(deps, reg)
    lines.append(f"Restricted works a free source already covers ({len(swaps)}):")
    for work, free in swaps:
        lines.append(f"  {work['title']}  ->  {free['title']}")
        lines.append(f"    {len(deps[work['id']])} roadmap(s): {', '.join(deps[work['id']])}")
    free = [index[work] for work in deps if index[work].get("access") == "free"]
    lines.append("")
    lines.append(f"Freely available and already cited: {len(free)} works.")
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


def main(argv: list) -> int:
    reg = register()
    docs = documents()
    deps = dependencies(docs, reg)
    print(report(deps, reg))
    loose = unregistered(docs, reg)
    if loose:
        print(f"\n{len(loose)} link(s) to a publisher that the register does not know:")
        for name, url in loose:
            print(f"  [{name}] {url}")
    if "--write" in argv:
        REPORT.write_text("# Sources the roadmaps depend on\n\n"
                          "Generated by `python3 scripts/sources.py --write`; the decisions live in\n"
                          "`ACCESS.json`, which is the file to edit.\n\n```\n" + report(deps, reg) + "\n```\n")
    if "--check" in argv:
        return 1 if loose else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
