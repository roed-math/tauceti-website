"""Roadmap prerequisites read from each roadmap's README.

A README names the roadmaps it builds on in its dependency sections ("Dependencies", "Prerequisites",
"Builds on", "Inputs from other roadmaps", or a layer's own "Dependencies" list) and on lines that say
it consumes, builds on or depends on another roadmap; a "Downstream consumers" section names the roadmaps
that build on it. Each such link to another roadmap's folder is a prerequisite edge, recorded with the
README line that states it. A link anywhere else is only a reference (roadmapLinks), and a line that
says the roadmap does not need, or avoids, the other is not read as a dependency.
"""
from __future__ import annotations

import posixpath
import re

REPOSITORY = "TauCetiProject/TauCetiRoadmap"
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
GITHUB = re.compile(r"^https?://(?:github\.com/" + REPOSITORY + r"/(?:blob|tree)/[^/]+|raw\.githubusercontent\.com/" + REPOSITORY + r"/[^/]+)/(.*)$")
DOWNSTREAM = re.compile(r"downstream|consumers|\bused by\b|\bfeeds\b|\bunlocks\b", re.I)
UPSTREAM = re.compile(r"dependenc|\bdepends\b|prerequisite|builds? on|\bconsum|upstream|\brequires?\b|\brelies\b|\binputs?\b"
                      r"|from other roadmaps|existing foundations", re.I)
CONSUMED_BY = re.compile(r"\b(?:consumed|used|needed|required) by\b|\bfeeds (?:into )?\[|\bunlocks\b|\bdownstream\b", re.I)
CONSUMES = re.compile(r"\bconsum(?:e|es|ing)\b|\bbuilds? on\b|\bbuilt on\b|\bdepends? on\b|\bdependent on\b|\brequires?\b|\brelies on\b"
                      r"|\bprerequisites?\b|\bimports?\b|\breuses?\b|\binput from\b|\btakes? as input\b", re.I)
NEGATED = re.compile(r"\bnot\b|n't\b|\bindependent(?:ly)?\b|\bwithout\b|\binstead of\b|\brather than\b|\bavoids?\b|\bno longer\b", re.I)


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


def dependencies(text: str, folder: str, folders: dict) -> list:
    """(prerequisite folder's roadmap, dependent roadmap, line number, heading) for each dependency the README states.

    folder is the README's own folder (TauCetiRoadmap/<Name> or Completed/<Name>); folders maps every
    known roadmap folder to its roadmap id."""
    own = folders.get(folder)
    found, headings, fenced = [], [], False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        heading = None if fenced else HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            headings = [h for h in headings if h[0] < level] + [(level, heading.group(2))]
            continue
        if fenced:
            continue
        for href in LINK.findall(line):
            path = target_folder(href, folder)
            other = roadmap_at(path, folders) if path else None
            if not other or other == own:
                continue
            titles = [title for _, title in headings]
            section = next((title for title in reversed(titles) if DOWNSTREAM.search(title) or UPSTREAM.search(title)), None)
            if NEGATED.search(line):
                continue
            if section and DOWNSTREAM.search(section) or CONSUMED_BY.search(line):
                found.append((own, other, number, section or ""))
            elif section or CONSUMES.search(line):
                found.append((other, own, number, section or ""))
    return found


def add_dependencies(atlas: dict, readmes: dict) -> int:
    """Add the prerequisite edges the READMEs state between roadmaps on the map; returns how many were added.

    readmes maps a roadmap id to (README text, its folder, the README's address). An edge the atlas
    already records, in either form, is kept as it is."""
    ids = {roadmap["id"] for roadmap in atlas["roadmaps"]}
    folders = {roadmap_id.split(":", 1)[1]: roadmap_id for roadmap_id in ids if roadmap_id.startswith("tauceti:")}
    known = {(edge["source"], edge["target"]) for edge in atlas.get("edges", [])}
    added = {}
    for roadmap_id in sorted(readmes):
        text, folder, address = readmes[roadmap_id]
        if roadmap_id not in ids or not text:
            continue
        for source, target, line, section in dependencies(text, folder, folders):
            if source == target or (source, target) in known:
                continue
            edge = added.setdefault((source, target), {"source": source, "target": target, "kind": "readme", "stageCount": 0, "evidence": []})
            if len(edge["evidence"]) < 3:
                edge["evidence"].append({"readme": address, "line": line, "section": section, "roadmap": roadmap_id})
    atlas.setdefault("edges", []).extend(added[key] for key in sorted(added))
    return len(added)
