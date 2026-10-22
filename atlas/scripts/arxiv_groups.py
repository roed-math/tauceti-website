"""The published atlas grouped by arXiv subject: one galaxy for each arXiv mathematics category.

Every Tau Ceti roadmap declares its category in its metadata.toml (`topic = "math.NT"`): the Progress
page passes it on for the roadmaps Tau Ceti has accepted, and a pull request's own metadata.toml gives
a proposed roadmap's. A roadmap that declares none takes the category of the nearest folder above it
that declares one; else of most of the roadmaps it is linked to (its prerequisites, the roadmaps that
use it and those its README names), when they clearly agree; else of the subject its title or README
names (data/tauceti-arxiv-areas.json, read backwards); else it waits in a galaxy of its own, "No arXiv
category", until its metadata.toml declares one.

The galaxies go round Mathlib in a fixed order of the categories, so that related subjects are
neighbours (number theory between representation theory and algebraic geometry, analysis beside PDE
and probability), each turned to the middle of a share of the circle that grows with its size.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

# arXiv's mathematics categories, with arXiv's own descriptions, in their order round the map.
CATEGORIES = {
    "math.NT": ("Number Theory", "Prime numbers, diophantine equations, analytic number theory, algebraic number theory, arithmetic geometry, Galois theory."),
    "math.AG": ("Algebraic Geometry", "Algebraic varieties, stacks, sheaves, schemes, moduli spaces, complex geometry, quantum cohomology."),
    "math.AC": ("Commutative Algebra", "Commutative rings, modules, ideals, homological algebra, computational aspects, invariant theory, connections to algebraic geometry and combinatorics."),
    "math.RA": ("Rings and Algebras", "Non-commutative rings and algebras, non-associative algebras, universal algebra and lattice theory, linear algebra, semigroups."),
    "math.KT": ("K-Theory and Homology", "Algebraic and topological K-theory, relations with topology, commutative algebra, and operator algebras."),
    "math.CT": ("Category Theory", "Enriched categories, topoi, abelian categories, monoidal categories, homological algebra."),
    "math.AT": ("Algebraic Topology", "Homotopy theory, homological algebra, algebraic treatments of manifolds."),
    "math.GT": ("Geometric Topology", "Manifolds, orbifolds, polyhedra, cell complexes, foliations, geometric structures."),
    "math.GN": ("General Topology", "Continuum theory, point-set topology, spaces with algebraic structure, foundations, dimension theory, local and global properties."),
    "math.MG": ("Metric Geometry", "Euclidean, hyperbolic, discrete, convex, coarse geometry, comparisons in Riemannian geometry, symmetric spaces."),
    "math.DG": ("Differential Geometry", "Complex, contact, Riemannian, pseudo-Riemannian and Finsler geometry, relativity, gauge theory, global analysis."),
    "math.SG": ("Symplectic Geometry", "Hamiltonian systems, symplectic flows, classical integrable systems."),
    "math.MP": ("Mathematical Physics", "Applications of mathematics to problems in physics, and the mathematical methods those problems need."),
    "math.DS": ("Dynamical Systems", "Dynamics of differential equations and flows, mechanics, classical few-body problems, iterations, complex dynamics, delayed differential equations."),
    "math.AP": ("Analysis of PDEs", "Existence and uniqueness, boundary conditions, linear and non-linear operators, stability, soliton theory, integrable PDE's, conservation laws, qualitative dynamics."),
    "math.CA": ("Classical Analysis and ODEs", "Special functions, orthogonal polynomials, harmonic analysis, ODE's, differential relations, calculus of variations, approximations, expansions, asymptotics."),
    "math.CV": ("Complex Variables", "Holomorphic functions, automorphic group actions and forms, pseudoconvexity, complex geometry, analytic spaces, analytic sheaves."),
    "math.FA": ("Functional Analysis", "Banach spaces, function spaces, real functions, integral transforms, theory of distributions, measure theory."),
    "math.OA": ("Operator Algebras", "Algebras of operators on Hilbert space, C*-algebras, von Neumann algebras, non-commutative geometry."),
    "math.SP": ("Spectral Theory", "Schrödinger operators, operators on manifolds, general differential operators, numerical studies, integral operators, discrete models, resonances, non-self-adjoint operators, random operators and matrices."),
    "math.NA": ("Numerical Analysis", "Numerical algorithms for problems in analysis and algebra, scientific computation."),
    "math.OC": ("Optimization and Control", "Operations research, linear programming, control theory, systems theory, optimal control, game theory."),
    "math.PR": ("Probability", "Theory and applications of probability and stochastic processes: central limit theorems, large deviations, stochastic differential equations, models from statistical mechanics, queuing theory."),
    "math.ST": ("Statistics Theory", "Applied, computational and theoretical statistics: statistical inference, regression, time series, multivariate analysis, data analysis."),
    "math.IT": ("Information Theory", "Theoretical and experimental aspects of information theory and coding."),
    "math.CO": ("Combinatorics", "Discrete mathematics, graph theory, enumeration, combinatorial optimization, Ramsey theory, combinatorial game theory."),
    "math.LO": ("Logic", "Logic, set theory, point-set topology, formal mathematics."),
    "math.GR": ("Group Theory", "Finite groups, topological groups, representation theory, cohomology, classification and structure."),
    "math.QA": ("Quantum Algebra", "Quantum groups, skein theories, operadic and diagrammatic algebra, quantum field theory."),
    "math.RT": ("Representation Theory", "Linear representations of algebras and groups, Lie theory, associative algebras, multilinear algebra."),
    "math.HO": ("History and Overview", "Biographies, philosophy of mathematics, mathematics education, recreational mathematics, communication of mathematics."),
    "math.GM": ("General Mathematics", "Mathematical material of general interest, topics not covered elsewhere."),
}
UNCLASSIFIED = "unclassified"
UNCLASSIFIED_GROUP = ("No arXiv category", "Roadmaps whose metadata.toml declares no arXiv category yet, and that no folder above them, "
                      "no roadmap they are linked to and no subject their title names places.")
ORDER = list(CATEGORIES)
# The colours of the subjects' families, as the atlas used them before.
COLOURS = {"math.NT": "#cfe3fb", "math.AG": "#e0f2e9", "math.KT": "#fce7f3", **dict.fromkeys(("math.AC", "math.RA", "math.GR"), "#dcd4f5"),
           **dict.fromkeys(("math.RT", "math.QA"), "#e7dcfa"), **dict.fromkeys(("math.CT", "math.LO", "math.HO", "math.GM"), "#e2e8f0"),
           **dict.fromkeys(("math.FA", "math.OA", "math.SP", "math.CA", "math.CV", "math.NA", "math.OC", "math.DS", "math.MP", "math.AP"), "#d8eafe"),
           **dict.fromkeys(("math.PR", "math.ST", "math.CO", "math.IT"), "#e6f0ff"),
           **dict.fromkeys(("math.AT", "math.GT", "math.GN", "math.DG", "math.SG", "math.MG"), "#d2f1e7"), UNCLASSIFIED: "#e2e8f0"}
NOTES = [
    "Each galaxy is one arXiv mathematics category. A roadmap sits in the category its metadata.toml declares; one that declares none takes its parent folder's, else that of most of the roadmaps it is linked to, else that of the subject its title names, else waits under \"No arXiv category\".",
    "The galaxies go round Mathlib in a fixed order of the categories, so related subjects are neighbours; a galaxy lies farther out the more theory its roadmaps must build.",
    "bridgeGroups lists up to three other categories joined to this one by the most prerequisite links.",
]


def category(value) -> str | None:
    """An arXiv mathematics category the map knows (`math.NT`; `math-ph` is math.MP), else None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return "math.MP" if value == "math-ph" else value if value in CATEGORIES else None


def area_categories(areas: dict) -> dict:
    """The arXiv category of each of the atlas's old subject areas: the category whose default it is, else the first
    that allows it (data/tauceti-arxiv-areas.json, read backwards)."""
    found = {}
    for code, entry in areas.items():
        if entry.get("default"):
            found.setdefault(entry["default"], code)
    for code, entry in areas.items():
        for area in entry.get("areas", []):
            found.setdefault(area, code)
    return found


def categories_of(atlas: dict, declared: dict, areas: dict | None = None) -> dict:
    """Each roadmap's (category, basis): "declared" in its metadata.toml; "parent" from the nearest folder above it
    that declares one (declared may name folders that are not on the map); "links" from a clear lead among the
    roadmaps it is linked to; "area" from the subject area its title or README named (areas maps an area to
    its category); or "none"."""
    ids = [roadmap["id"] for roadmap in atlas["roadmaps"]]
    found = {rid: (code, "declared") for rid in ids if (code := category(declared.get(rid)))}
    for rid in ids:
        if rid in found:
            continue
        parts = rid.split("/")
        for end in range(len(parts) - 1, 0, -1):
            above = category(declared.get("/".join(parts[:end])))
            if above:
                found[rid] = (above, "parent")
                break
    neighbours = defaultdict(list)
    for key in ("edges", "roadmapLinks"):
        for link in atlas.get(key, []):
            if link.get("source") != link.get("target"):
                neighbours[link.get("source")].append(link.get("target"))
                neighbours[link.get("target")].append(link.get("source"))

    def by_links(trusted):
        """Place each roadmap still unplaced whose linked roadmaps, among those placed on a trusted basis, clearly agree."""
        placed = {}
        for rid in ids:
            if rid not in found:
                ranked = Counter(found[other][0] for other in neighbours[rid] if other in found and found[other][1] in trusted).most_common(2)
                if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
                    placed[rid] = (ranked[0][0], "links")
        found.update(placed)
        return placed

    by_links({"declared", "parent"})
    for roadmap in atlas["roadmaps"]:
        code = (areas or {}).get(roadmap.get("group"))
        if roadmap["id"] not in found and code in CATEGORIES:
            found[roadmap["id"]] = (code, "area")
    # Roadmaps placed so far place their neighbours in turn: sub-roadmaps of an undeclared collection settle together.
    while by_links({"declared", "parent", "links", "area"}):
        pass
    return {rid: found.get(rid, (UNCLASSIFIED, "none")) for rid in ids}


def distance_of(atlas: dict, roadmap_id: str) -> float:
    """A roadmap's distance from Mathlib as the page reads it: measured, else classified, else 5."""
    measured = atlas.get("roadmapDistances", {}).get("roadmaps", {}).get(roadmap_id, {}).get("distance")
    classified = atlas.get("roadmapClassification", {}).get("roadmaps", {}).get(roadmap_id, {}).get("distance")
    return next((value for value in (measured, classified) if isinstance(value, (int, float))), 5)


def group_by_arxiv(atlas: dict, declared: dict, areas: dict | None = None) -> dict:
    """Replace the atlas's subject galaxies with one per arXiv category and move every roadmap into its own.

    declared maps a roadmap id, or the id a folder off the map would have, to the category its metadata.toml
    declares; areas is data/tauceti-arxiv-areas.json's categories. Returns {category: roadmaps}."""
    chosen = categories_of(atlas, declared, area_categories(areas or {}))
    names = {**{code: name for code, (name, _) in CATEGORIES.items()}, UNCLASSIFIED: UNCLASSIFIED_GROUP[0]}
    descriptions = {**{code: text for code, (_, text) in CATEGORIES.items()}, UNCLASSIFIED: UNCLASSIFIED_GROUP[1]}
    members = defaultdict(list)
    for roadmap in atlas["roadmaps"]:
        code, basis = chosen[roadmap["id"]]
        roadmap["group"], roadmap["arxiv"] = code, code if code in CATEGORIES else None
        members[code].append(roadmap["id"])
        name = names[code]
        rationale = {"declared": f"In {name} ({code}), the arXiv category its metadata.toml declares.",
                     "parent": f"In {name} ({code}), the arXiv category of the folder above it: it declares none of its own.",
                     "links": f"In {name} ({code}), the arXiv category of most of the roadmaps it is linked to: it declares none of its own.",
                     "area": f"In {name} ({code}), the arXiv category of the subject its title or README names: it declares none of its own.",
                     "none": "It declares no arXiv category in a metadata.toml, and neither the folder above it, the roadmaps it is "
                             "linked to nor its title settle one."}[basis]
        record = atlas.setdefault("roadmapClassification", {}).setdefault("roadmaps", {}).setdefault(roadmap["id"], {})
        record.update(arxiv=code, arxivBasis=basis, rationale=rationale)
    present = [code for code in [*ORDER, UNCLASSIFIED] if members[code]]
    # Each galaxy is turned to the middle of its share of the circle; a share grows as the galaxy does.
    weights = {code: 1 + math.sqrt(len(members[code])) for code in present}
    total, start, direction = sum(weights.values()), 90.0, {}
    for code in present:
        share = 360 * weights[code] / total
        direction[code] = round((start + share / 2) % 360, 1)
        start += share
    group_of = {rid: code for code, rids in members.items() for rid in rids}
    links = defaultdict(Counter)
    for edge in atlas.get("edges", []):
        a, b = group_of.get(edge["source"]), group_of.get(edge["target"])
        if a and b and a != b:
            links[a][b] += 1
            links[b][a] += 1
    atlas["groups"] = [{"id": code, "label": names[code] if code == UNCLASSIFIED else f"{names[code]} ({code})", "short": names[code],
                        "caption": ["No arXiv", "category yet"] if code == UNCLASSIFIED else [names[code], code],
                        "color": COLOURS[code], "arxiv": code if code in CATEGORIES else None, "direction": direction[code],
                        "distance": round(sum(distance_of(atlas, rid) for rid in members[code]) / len(members[code]), 2),
                        "roadmapIds": sorted(members[code])} for code in present]
    atlas["meta"]["groupCount"] = len(atlas["groups"])
    atlas["fields"] = []
    atlas["regions"] = {
        "version": 3,
        "purpose": "arXiv subject galaxies: arXiv's description of each category and the categories it is most connected to.",
        "groups": {code: {"description": descriptions[code], "topics": [],
                          "bridgeGroups": [other for other, _ in sorted(links[code].items(), key=lambda item: (-item[1], item[0]))[:3]]}
                   for code in present},
        "roadmapTags": {},
        "notes": NOTES,
    }
    # The measured distances name the old galaxies: what uses a roadmap is counted again by arXiv category.
    distances = atlas.get("roadmapDistances", {})
    distances["galaxies"] = {}
    for rid, entry in distances.get("roadmaps", {}).items():
        if "usedBy" in entry and rid in group_of:
            users = Counter(group_of[edge["target"]] for edge in atlas.get("edges", [])
                            if edge["source"] == rid and edge["target"] in group_of and group_of[edge["target"]] != group_of[rid])
            entry["usedBy"] = [{"galaxy": code, "roadmaps": count} for code, count in sorted(users.items(), key=lambda item: (-item[1], item[0]))]
    return {code: len(members[code]) for code in present}
