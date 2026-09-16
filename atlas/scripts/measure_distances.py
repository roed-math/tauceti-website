#!/usr/bin/env python3
"""Measure each roadmap's distance from Mathlib and lay out the subject galaxies.

Three measures are combined:

- structure (scripts/theory_graph.py): how much of each roadmap's prerequisite
  closure is still to be built, and how deep the chain of missing layers is;
  declaration counts and source pages where layers have been decomposed;
- pairwise judgements (research/blueprint/compare/*.result.json), fitted with a
  Bradley–Terry model (scripts/bradley_terry.py) and placed on the 0-10 scale
  by a least-squares fit to the classification scores;
- the classification's own 0-10 score (data/roadmap-classification.json).

A roadmap's distance comes from its pairwise score once it has at least
MIN_JUDGEMENTS judgements, and from the classification score before that.
Once a roadmap's layers are all decomposed into reviewed declarations, and
enough roadmaps have both declaration counts and pairwise scores to calibrate
them, the log of its missing declarations takes over.

Galaxy directions come from how related the galaxies are (scripts/radial_layout.py).
Writes data/roadmap-distances.json and data/galaxy-layout.json.

    python3 scripts/measure_distances.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bradley_terry import bootstrap, fit, outcomes, quantile  # noqa: E402
from galaxies import galaxy_membership  # noqa: E402
from radial_layout import layout, rank_normalise  # noqa: E402
from theory_graph import structure, tfidf_similarity  # noqa: E402

MIN_JUDGEMENTS = 4
LAYER_SHARE = 0.6
MIN_CALIBRATION = 8
COMPARE = ROOT / "research" / "blueprint" / "compare"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    return round(cov / math.sqrt(va * vb), 3) if va and vb else None


def least_squares(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    return my - slope * mx, slope


def clamp(value):
    return max(0.0, min(10.0, value))


def judgements_by_job():
    jobs = {}
    for path in sorted(COMPARE.glob("COMPARE-*.result.json")) if COMPARE.is_dir() else []:
        try:
            data = load(path)
        except ValueError:
            continue
        items = data.get("judgements", []) if isinstance(data, dict) else data
        jobs[path.name.split(".")[0]] = [item for item in items if isinstance(item, dict)]
    return jobs


def pairwise_scores(roadmap_ids, classification):
    jobs = judgements_by_job()
    judgements = [item for items in jobs.values() for item in items
                  if item.get("a") in roadmap_ids and item.get("b") in roadmap_ids]
    if not judgements:
        return {}, {"judgements": 0, "jobs": 0}
    ids = sorted(roadmap_ids)
    scores = fit(ids, outcomes(judgements))
    counts = defaultdict(int)
    for item in judgements:
        counts[item["a"]] += 1
        counts[item["b"]] += 1
    judged = [rid for rid in ids if counts[rid] >= MIN_JUDGEMENTS]
    intercept, slope = least_squares([scores[r] for r in judged], [classification[r]["distance"] for r in judged]) if len(judged) >= 3 else (5.0, 1.0)
    draws = bootstrap(ids, judgements)
    out = {}
    for rid in ids:
        if not counts[rid]:
            continue
        out[rid] = {"score": round(scores[rid], 3), "judgements": counts[rid],
                    "distance": round(clamp(intercept + slope * scores[rid]), 2),
                    "low": round(clamp(intercept + slope * quantile(draws[rid], .16)), 2),
                    "high": round(clamp(intercept + slope * quantile(draws[rid], .84)), 2)}
    # Split-half reliability: fit the odd and even jobs separately and compare.
    halves = [[], []]
    for index, name in enumerate(sorted(jobs)):
        halves[index % 2] += [item for item in jobs[name] if item.get("a") in roadmap_ids and item.get("b") in roadmap_ids]
    reliability = None
    if halves[0] and halves[1]:
        first, second = fit(ids, outcomes(halves[0])), fit(ids, outcomes(halves[1]))
        both = [rid for rid in ids if rid in first and rid in second]
        reliability = spearman([first[r] for r in both], [second[r] for r in both])
    summary = {"judgements": len(judgements), "jobs": len(jobs), "calibration": {"intercept": round(intercept, 4), "slope": round(slope, 4)},
               "roadmapsWithEnough": len(judged), "splitHalfSpearman": reliability}
    return out, summary


def main() -> None:
    atlas = load(ROOT / "data" / "atlas.json")
    classification = load(ROOT / "data" / "roadmap-classification.json")["roadmaps"]
    galaxies = load(ROOT / "data" / "galaxies.json")["galaxies"]
    roadmap_ids = {roadmap["id"] for roadmap in atlas["roadmaps"]}
    measured, graph = structure(atlas)
    pairwise, pairwise_summary = pairwise_scores(roadmap_ids, classification)

    # Declaration counts take over only where they are complete and reviewed,
    # and only once enough roadmaps calibrate them against pairwise scores.
    complete = {rid: m["declarationLevel"] for rid, m in measured.items()
                if m.get("declarationLevel") and m["declarationLevel"]["reviewed"]
                and m["declarationLevel"]["layersCovered"] == m["declarationLevel"]["layers"] > 0}
    calibrated = [rid for rid in complete if rid in pairwise and pairwise[rid]["judgements"] >= MIN_JUDGEMENTS]
    declaration_fit = None
    if len(calibrated) >= MIN_CALIBRATION:
        declaration_fit = least_squares([math.log1p(complete[r]["missingDeclarations"]) for r in calibrated],
                                        [pairwise[r]["distance"] for r in calibrated])

    roadmaps = {}
    for rid in sorted(roadmap_ids):
        record = {"classification": classification[rid]["distance"], "structure": measured[rid]}
        if rid in pairwise:
            record["pairwise"] = pairwise[rid]
        if declaration_fit and rid in complete:
            value = clamp(declaration_fit[0] + declaration_fit[1] * math.log1p(complete[rid]["missingDeclarations"]))
            record.update(distance=round(value, 2), basis="declarations")
        elif rid in pairwise and pairwise[rid]["judgements"] >= MIN_JUDGEMENTS:
            record.update(distance=pairwise[rid]["distance"], low=pairwise[rid]["low"], high=pairwise[rid]["high"], basis="pairwise")
        else:
            record.update(distance=float(classification[rid]["distance"]), basis="classification")
        roadmaps[rid] = record
    # A collection sits at the mean distance of its child roadmaps.
    children = defaultdict(list)
    for roadmap in atlas["roadmaps"]:
        if roadmap.get("parentRoadmapId") in roadmaps:
            children[roadmap["parentRoadmapId"]].append(roadmap["id"])
    for parent, kids in children.items():
        if any(roadmaps[k]["basis"] != "classification" for k in kids):
            roadmaps[parent].update(distance=round(sum(roadmaps[k]["distance"] for k in kids) / len(kids), 2), basis="children")

    membership = galaxy_membership(atlas, classification)
    members = defaultdict(list)
    for rid, gid in membership.items():
        members[gid].append(rid)
    galaxy_info = {}
    foundations = {}
    subjects = {}
    for gid, rids in members.items():
        rests_on = set()
        for rid in rids:
            for sid in graph.by_owner.get(rid, ()):
                rests_on |= graph.related(sid)
        foundations[gid] = {sid for sid in rests_on if graph.relatedness_weight(sid) > 0}
        codes = defaultdict(float)
        for rid in rids:
            record = classification[rid]
            if record.get("primaryMsc"):
                codes[str(record["primaryMsc"])[:3]] += 1.0
            for code in record.get("secondaryMsc") or []:
                codes[str(code)[:3]] += 0.5
        subjects[gid] = codes
        primary = [str(classification[rid].get("primaryMsc") or "") for rid in rids]
        lean = (sum(code.startswith("14") for code in primary) - sum(code.startswith("11") for code in primary)) / len(rids)
        galaxy_info[gid] = {"distance": sum(roadmaps[r]["distance"] for r in rids) / len(rids), "count": len(rids), "lean": lean}
    # Relatedness: the layers two galaxies rest on (rare layers count more,
    # layers still to be built count double), and the subject classes of
    # their references. Each is ranked before the two are combined.
    keys = sorted(galaxy_info)
    by_layers = tfidf_similarity(foundations, {sid: graph.relatedness_weight(sid) for sid in graph.owner})
    by_subject = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            dot = sum(w * subjects[b].get(code, 0.0) for code, w in subjects[a].items())
            norm = math.sqrt(sum(w * w for w in subjects[a].values()) * sum(w * w for w in subjects[b].values()))
            by_subject[(a, b)] = by_subject[(b, a)] = dot / norm if norm else 0.0
    layer_rank, subject_rank = rank_normalise(by_layers, keys), rank_normalise(by_subject, keys)
    similarity = {pair: LAYER_SHARE * layer_rank[pair] + (1 - LAYER_SHARE) * subject_rank[pair] for pair in layer_rank}
    directions, layout_stress = layout(galaxy_info, similarity)
    neighbours = {}
    for gid in galaxy_info:
        ranked = sorted((g for g in galaxy_info if g != gid), key=lambda g: (-similarity.get((gid, g), 0.0), g))
        neighbours[gid] = [{"galaxy": g, "similarity": round(similarity.get((gid, g), 0.0), 3)} for g in ranked[:4]]

    ids = sorted(roadmap_ids)
    validation = {
        "classificationVsMissingLayers": spearman([classification[r]["distance"] for r in ids], [measured[r]["missingLayers"] for r in ids]),
        "classificationVsDepth": spearman([classification[r]["distance"] for r in ids], [measured[r]["depth"] for r in ids]),
        "missingLayersVsDepth": spearman([measured[r]["missingLayers"] for r in ids], [measured[r]["depth"] for r in ids]),
        "completedRoadmaps": {r["id"]: roadmaps[r["id"]]["distance"] for r in atlas["roadmaps"] if r.get("lifecycle") == "completed"},
    }
    judged = [r for r in ids if r in pairwise]
    if judged:
        validation["pairwiseVsClassification"] = spearman([pairwise[r]["score"] for r in judged], [classification[r]["distance"] for r in judged])
        validation["pairwiseVsMissingLayers"] = spearman([pairwise[r]["score"] for r in judged], [measured[r]["missingLayers"] for r in judged])
        validation["pairwiseVsDepth"] = spearman([pairwise[r]["score"] for r in judged], [measured[r]["depth"] for r in judged])
    decl = [r for r in ids if measured[r].get("declarationLevel")]
    if len(decl) >= 3:
        validation["declarationsVsClassification"] = spearman([measured[r]["declarationLevel"]["missingDeclarations"] for r in decl],
                                                              [classification[r]["distance"] for r in decl])
    basis_counts = defaultdict(int)
    for record in roadmaps.values():
        basis_counts[record["basis"]] += 1

    document = {
        "version": 1,
        "purpose": "Distance from Mathlib for every roadmap, on a 0-10 scale, with the measures behind it. Generated by scripts/measure_distances.py; do not edit by hand.",
        "method": {
            "distance": f"A collection takes the mean of its child roadmaps. Otherwise, from the Bradley–Terry score of the pairwise judgements once a roadmap has at least {MIN_JUDGEMENTS}, placed on the 0-10 scale by a least-squares fit to the classification scores; from the classification score before that; from the log of missing declarations once a roadmap is fully decomposed, reviewed and calibrated.",
            "structure": "Layers still to be built in the prerequisite closure (a layer in progress counts half), and the longest chain of them, over the atlas's stage graph with completed layers as library material.",
            "interval": "The 16th to 84th percentile of 300 bootstrap refits over judgements.",
        },
        "bases": dict(basis_counts),
        "pairwise": pairwise_summary,
        "validation": validation,
        "roadmaps": roadmaps,
        "galaxies": {gid: {"distance": round(info["distance"], 2), "roadmaps": info["count"]} for gid, info in sorted(galaxy_info.items())},
    }
    (ROOT / "data" / "roadmap-distances.json").write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    layout_document = {
        "version": 1,
        "purpose": "Directions of the subject galaxies from Mathlib, computed from shared missing theory by scripts/measure_distances.py (scripts/radial_layout.py); do not edit by hand.",
        "method": "Relatedness: 60% the rank of the cosine similarity of the prerequisite layers two galaxies rest on (each layer weighted by its rarity across galaxies, layers still to be built counting double), 40% the rank of the cosine similarity of their references' subject classes. Directions minimise the weighted misfit to target angles that run from zero for the most related pair to a half turn for the least, with overlapping galaxies penalised; the result is turned so the roadmaps' mean direction points right, with algebraic geometry above that axis and number theory below it.",
        "stress": round(layout_stress, 4),
        "galaxies": {gid: {"direction": directions[gid], "neighbours": neighbours[gid]} for gid in sorted(directions)},
    }
    (ROOT / "data" / "galaxy-layout.json").write_text(json.dumps(layout_document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"bases": dict(basis_counts), "pairwise": pairwise_summary, "validation": validation,
                      "directions": dict(sorted(directions.items(), key=lambda kv: kv[1])), "stress": round(layout_stress, 4)}, indent=1))


if __name__ == "__main__":
    main()
