"""Roadmap prerequisites read from each roadmap's README.

A README names the roadmaps it builds on in its dependency sections ("Dependencies", "Prerequisites",
"Builds on", "Inputs from other roadmaps", "Exact supplier contracts", or a layer's own "Dependencies"
list) and in sentences saying it uses, consumes, needs or builds on another roadmap, or that another
supplies it; a section of what it supplies to others ("Downstream consumers", "Interfaces supplied to
other roadmaps") names roadmaps that build on it. A roadmap is named by a link to its folder, or by its
folder's name (`EllipticCurves`, as Tau Ceti's READMEs write their suppliers): a name of two or more
capitals as a word, and a one-word name (`Chebotarev`) only in code marks.

A README's paragraphs are hard-wrapped, so its lines are joined into paragraphs, and each paragraph is
read clause by clause. The verb nearest a name decides which way the dependency runs: a roadmap named
after "uses", "needs" or "from" is used, one named before "supplies", as its subject, supplies, one
named after "used by" or "supplies" (as its object) uses this one, and one that is the subject of "uses"
uses this one when the clause says so ("EllipticCurves uses this roadmap's divisors"); a clause that says
the roadmap does not need, or avoids, the other is not read. With no verb, the section decides. Each dependency is a prerequisite edge, recorded
with the README line its paragraph starts on.

A pull request's description can say more surely than its README which roadmaps it builds on
(scripts/tauceti_prs.py, stated): follow_pull_requests holds the README links to it.
"""
from __future__ import annotations

import posixpath
import re

REPOSITORY = "TauCetiProject/TauCetiRoadmap"
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
GITHUB = re.compile(r"^https?://(?:github\.com/" + REPOSITORY + r"/(?:blob|tree)/[^/]+|raw\.githubusercontent\.com/" + REPOSITORY + r"/[^/]+)/(.*)$")
# Sections of what the roadmap gives others, and of what it takes from them. A heading that says both is read by
# what it says first ("Boundary and comparison suppliers used by the end theorems" is about suppliers), and a layer's
# own heading ("Layer 6: Exports for Serre and elliptic curves") is no section of consumers: its text mostly cites
# the layer's suppliers.
DOWNSTREAM = re.compile(r"\bdownstream\b|\bconsumers?\b|\bused by\b|\bfeeds\b|\bunlocks\b|\bsuppl(?:ied|ies) to\b|\b(?:to|for) other roadmaps\b"
                        r"|\bexports?\b", re.I)
UPSTREAM = re.compile(r"(?<!in)dependenc|\bdepends\b|prerequisite|builds? on|\bconsum(?:es|ed|ing|ption)?\b|upstream|\brequire[sd]?\b|\brelies\b"
                      r"|\binputs?\b|from other roadmaps|existing foundations|\bsuppl(?:y|ier|iers|ies)\b|\bsupplied\b(?! to\b)", re.I)
LAYER_HEADING = re.compile(r"^\s*(?:Layer|Stage|Milestone|Part|Step)\b|^\s*§|^\s*[A-Z]{0,4}[.\d]*\d[\w.–-]*[.:)]?\s", re.I)
NEGATED = re.compile(r"\bnot\b|n't\b|\bindependent(?:ly)?\b|\bwithout\b|\binstead of\b|\brather than\b|\bavoids?\b|\bno longer\b|\bnothing\b", re.I)
# A clause: a sentence, a table cell, a dash aside, or one of two clauses joined by ", and".
CLAUSE = re.compile(r"(?<=[.;!?])\s+(?=[A-Z*`(\[§])|\s+\|\s+|\s+[—–]\s+|,\s+and\s+(?=[A-Z*`\[])")
# A roadmap's folder name as a word: two or more capitals (EllipticCurves, GL2ModularityLifting), or any name in
# code marks; a path names its last folder.
NAMED = re.compile(r"`([A-Za-z0-9]+(?:/[A-Za-z0-9]+)*)`|(?<![A-Za-z0-9/])((?:[A-Z][A-Za-z0-9]*/)*[A-Z][a-z0-9]*[A-Z][A-Za-z0-9]*)(?![A-Za-z0-9])")
DOWNSTREAM_WORDS = re.compile(r"\bdownstream\b|\bconsumers?\b", re.I)
# The verbs: what a roadmap named after one, as its object, is; and what one named before it, as its subject, is.
VERBS = [
    (re.compile(r"\b(?:supplied|provided|given|delivered|proved|proven|constructed|defined|built) (?:by|from)\b", re.I), "up", None),
    (re.compile(r"\b(?:consumed|used|needed|required|imported|cited) by\b", re.I), "down", None),
    # A roadmap named after "supplies" or "gives" is, in these READMEs, mostly a source cited for what is supplied
    # ("... gives #H¹(K_v, M) = ... (ClassFieldTheory Layer 5)"), not its receiver.
    (re.compile(r"\b(?:supplies|supply|provides|provide|gives|give|delivers)\b", re.I), None, "up"),
    (re.compile(r"\b(?:exports|feeds|unlocks)\b", re.I), "down", "up"),
    (re.compile(r"\b(?:consum(?:e|es|ing)|uses?|using|needs?|requires?|requiring|builds? on|built on|depends? on|dependent on|relies on"
                r"|relying on|imports?|reuses?|invokes?|draws? on|applies|apply|cites?)\b", re.I), "up", "self"),
    (re.compile(r"\bfrom\b", re.I), "up", None),
]
# What may stand between a roadmap's name and a verb it is the subject of: its layers or sections, a parenthesis, a
# link, or more names ("EllipticCurves Layer 4 supplies", "A, B and C consume"). A name further from its verb, as in
# "the Amice transform of PadicMeasures ... that the constructions use", is not the verb's subject. Likewise a
# roadmap that receives what this one exports must follow the verb ("used by the HamiltonianReduction roadmap"): in
# "the PL tools used by PlanarTopology" the tools are not this roadmap's.
_BETWEEN = (r"\s|,|\band\b|\bor\b|\balso\b|\broadmaps?\b|\b[Ll]ayers?\b|['’]s\b|§+[^\s,;]*|\b[A-Z]{0,3}\d[^\s,;]*|\([^)]*\)|`[^`]*`"
            r"|\[[^\]]*\]\([^)]*\)|[*_]+|\b[A-Z][a-z0-9]*[A-Z][A-Za-z0-9]*(?:/[A-Za-z0-9]+)*\b")
SUBJECT = re.compile(f"(?:{_BETWEEN})*")
OBJECT = re.compile(f"(?:{_BETWEEN}|\\b[Tt]he\\b)*")
# A roadmap named as the subject of "uses" uses this one only when the clause says what of this one it uses.
SELF = re.compile(r"\bthis (?:roadmap|layer|section)\b|\bhere\b|\bours?\b|\bwe\b", re.I)


def target_folder(href: str, folder: str) -> str | None:
    """The repository path a README link points to, read from the README's folder; None outside the repository."""
    href = href.split("#")[0].split("?")[0]
    if not href:
        return None
    absolute = GITHUB.match(href)
    if absolute:
        return posixpath.normpath(absolute.group(1))
    if re.match(r"^[a-z]+:", href) or href.startswith("//"):
        return None
    path = posixpath.normpath(href.lstrip("/") if href.startswith("/") else posixpath.join(folder, href))
    return None if path.startswith("..") else path


def roadmap_at(path: str, folders: dict) -> str | None:
    """The roadmap whose folder holds path: the longest folder that contains it."""
    parts = path.split("/")
    for end in range(len(parts), 0, -1):
        found = folders.get("/".join(parts[:end]))
        if found:
            return found
    return None


def by_name(folders: dict, folder: str) -> dict:
    """Roadmap ids by folder name. A name two folders share means the one beside the README's own."""
    names = {}
    for path, roadmap_id in sorted(folders.items()):
        names.setdefault(path.split("/")[-1], []).append((path, roadmap_id))
    parent = folder.rsplit("/", 1)[0]
    return {name: next((rid for path, rid in options if path.rsplit("/", 1)[0] == parent), options[0][1]) if len(options) > 1 else options[0][1]
            for name, options in names.items()}


def placed(clause: str, folder: str, folders: dict, names: dict) -> set:
    """(roadmap, start, end) for each roadmap a clause names: by a link to its folder, or by its folder's name."""
    found = {}
    for match in LINK.finditer(clause):
        path = target_folder(match.group(1), folder)
        other = roadmap_at(path, folders) if path else None
        if other:
            found.setdefault(other, match.span())
    plain = LINK.sub(lambda match: " " * len(match.group(0)), clause)
    for match in NAMED.finditer(plain):
        other = names.get((match.group(1) or match.group(2)).split("/")[-1])
        if other:
            found.setdefault(other, match.span())
    return {(other, start, end) for other, (start, end) in found.items()}


def direction(clause: str, at: int, end: int | None = None):
    """Whether a roadmap named from position `at` to `end` of a clause is a prerequisite of the README's roadmap ("up"),
    one that builds on it ("down"), or neither, by the verb nearest it. Named before its verb, it must be the verb's
    subject."""
    if DOWNSTREAM_WORDS.search(clause):
        return "down"
    end = at if end is None else end
    nearest = None
    for pattern, after, before in VERBS:
        for match in pattern.finditer(clause):
            gap = at - match.end() if match.end() <= at else match.start() - at
            if gap >= 0 and (nearest is None or gap < nearest[0]):
                nearest = (gap, match.end() <= at, after, before, match.span())
    if nearest is None:
        return None
    _, named_after, after, before, (verb, verb_end) = nearest
    if named_after:
        return None if after == "down" and not OBJECT.fullmatch(clause[verb_end:at]) else after
    if not SUBJECT.fullmatch(clause[end:verb]):
        return None
    if before == "self":
        return "down" if SELF.search(clause) else None
    return before


def heading_way(title: str):
    """Whether a heading opens a section of the roadmaps this one gives to ("down"), of those it takes from ("up"),
    or neither."""
    down = None if LAYER_HEADING.search(title) else DOWNSTREAM.search(title)
    up = UPSTREAM.search(title)
    if down and up:
        return "down" if down.start() < up.start() else "up"
    return "down" if down else "up" if up else None


def paragraphs(text: str):
    """(first line number, paragraph, headings above it) for each paragraph, list item or table row of a README,
    outside code blocks."""
    headings, fenced, current, start = [], False, [], 0
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        fence = stripped.startswith("```")
        heading = None if fenced or fence else HEADING.match(line)
        # A paragraph ends at a blank line, a heading, a fence, a table row or a new list item.
        if fenced or fence or heading or not stripped or stripped.startswith(("|", "- ", "* ", "+ ", ">")) or re.match(r"\d+[.)]\s", stripped):
            if current:
                yield start, " ".join(current), list(headings)
            current = []
        if fence:
            fenced = not fenced
            continue
        if heading:
            level = len(heading.group(1))
            headings = [h for h in headings if h[0] < level] + [(level, heading.group(2))]
            continue
        if fenced or not stripped:
            continue
        if stripped.startswith("|"):
            yield number, stripped, list(headings)
            continue
        if not current:
            start = number
        current.append(stripped)
    if current:
        yield start, " ".join(current), list(headings)


def dependencies(text: str, folder: str, folders: dict) -> list:
    """(prerequisite folder's roadmap, dependent roadmap, line number, heading) for each dependency the README states.

    folder is the README's own folder (TauCetiRoadmap/<Name> or Completed/<Name>); folders maps every
    known roadmap folder to its roadmap id."""
    own, names = folders.get(folder), by_name(folders, folder)
    found = []
    for number, paragraph, headings in paragraphs(text):
        titles = [title for _, title in headings]
        section = next((title for title in reversed(titles) if heading_way(title)), None)
        downstream = section is not None and heading_way(section) == "down"
        for clause in CLAUSE.split(paragraph):
            if NEGATED.search(clause):
                continue
            for other, at, end in sorted(placed(clause, folder, folders, names)):
                if other == own:
                    continue
                way = direction(clause, at, end)
                if way is None and section:
                    way = "down" if downstream else "up"
                if way == "up":
                    found.append((other, own, number, section or ""))
                elif way == "down":
                    found.append((own, other, number, section or ""))
    return found


# How much a README's saying a dependency counts: its dependent's README says it more surely than its supplier's, and
# a dependency section more surely than a verb; one README counts at most MOST. A link the snapshot declares counts
# DECLARED.
WEIGHT = {(True, True): 3, (True, False): 2, (False, True): 2, (False, False): 1}
MOST, DECLARED = 9, 6
# A link a pull request's description states counts more than the READMEs can say against it (two, at MOST each).
STATED = 100


def add_dependencies(atlas: dict, readmes: dict) -> int:
    """Add the prerequisite edges the READMEs state between roadmaps on the map; returns how many were added.

    readmes maps a roadmap id to (README text, its folder, the README's address). An edge the atlas
    already records, in either form, is kept as it is. Each new edge has a weight: how surely the READMEs say it."""
    ids = {roadmap["id"] for roadmap in atlas["roadmaps"]}
    folders = {roadmap_id.split(":", 1)[1]: roadmap_id for roadmap_id in ids if roadmap_id.startswith("tauceti:")}
    known = {(edge["source"], edge["target"]) for edge in atlas.get("edges", [])}
    added = {}
    for roadmap_id in sorted(readmes):
        text, folder, address = readmes[roadmap_id]
        if roadmap_id not in ids or not text:
            continue
        said = {}
        for source, target, line, section in dependencies(text, folder, folders):
            if source == target or (source, target) in known:
                continue
            edge = added.setdefault((source, target), {"source": source, "target": target, "kind": "readme", "stageCount": 0, "weight": 0, "evidence": []})
            said[(source, target)] = said.get((source, target), 0) + WEIGHT[(target == roadmap_id, bool(section))]
            if len(edge["evidence"]) < 3:
                edge["evidence"].append({"readme": address, "line": line, "section": section, "roadmap": roadmap_id})
        for key, weight in said.items():
            added[key]["weight"] += min(weight, MOST)
    atlas.setdefault("edges", []).extend(added[key] for key in sorted(added))
    return len(added)


def follow_pull_requests(atlas: dict, pulls: list) -> dict:
    """Hold the README prerequisites of the proposed roadmaps to what their pull requests state; returns the counts.

    A roadmap on main rests on no roadmap still in an open pull request: Tau Ceti merges a roadmap after what it
    needs, so a README link from a proposed roadmap to one on main is set aside. A pull request with a merge-order
    block (its `stated` entry in data/tauceti-prs.json) lists every open pull request that must merge before it, and
    says that the other roadmaps its README names consume it: its roadmaps rest on no other proposed roadmap, and a
    README link from one is set aside. The pull requests it says add roadmaps its README cites become links of kind
    "pull"; a README link between the same two roadmaps becomes one, keeping its README lines."""
    pull_of = {roadmap["id"]: roadmap["pull"]["number"] for roadmap in atlas["roadmaps"] if roadmap.get("origin") == "proposed" and roadmap.get("pull")}
    adds = {}
    for roadmap_id, number in sorted(pull_of.items()):
        adds.setdefault(number, []).append(roadmap_id)
    said = {pull["number"]: pull for pull in pulls if pull.get("stated") and pull["number"] in adds}
    counts = {"pulls": len(said), "onMain": 0, "outsideMergeOrder": 0, "confirmed": 0, "added": 0}
    kept = []
    for edge in atlas.get("edges", []):
        source, target = pull_of.get(edge["source"]), pull_of.get(edge["target"])
        if edge.get("kind") == "readme" and source and not target:
            counts["onMain"] += 1
            continue
        if edge.get("kind") == "readme" and source and target in said and source != target \
                and source not in said[target]["stated"]["before"] + said[target]["stated"]["prerequisites"]:
            counts["outsideMergeOrder"] += 1
            continue
        kept.append(edge)
    links = {(edge["source"], edge["target"]): edge for edge in kept}
    for number, pull in sorted(said.items()):
        for target in adds[number]:
            for source in (rid for other in pull["stated"]["prerequisites"] if other != number for rid in adds.get(other, [])):
                edge = links.get((source, target))
                if edge is None:
                    edge = links[(source, target)] = {"source": source, "target": target, "kind": "pull", "stageCount": 0, "evidence": []}
                    kept.append(edge)
                    counts["added"] += 1
                elif edge.get("kind") == "readme":
                    counts["confirmed"] += 1
                else:
                    continue
                edge.update(kind="pull", pull=number, url=pull.get("url"))
    atlas["edges"] = kept
    return counts
