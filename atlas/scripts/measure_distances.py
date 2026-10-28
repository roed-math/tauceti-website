#!/usr/bin/env python3
"""Measure each roadmap's distance from Mathlib and lay out the subject galaxies.

The distance function. A roadmap's distance from Mathlib is measured from the
theory it still needs, over the prerequisite closure of its layers
(scripts/theory_graph.py), where a layer the libraries already contain is built:

    measurement = w_T ln(1 + T) + w_D D

T is the number of targets in that closure still missing from Mathlib and Tau
Ceti, counted by the reviewed library audits (research/blueprint/audit): an
absent target counts one, a partial one a half, a process layer none, and a
layer without an accepted audit counts the mean of the audited layers still to
be built. D is the longest chain of layers still to be built. The weights are
fitted to the pairwise judgements (research/blueprint/compare):
sigmoid(measurement_i - measurement_j) is the chance that roadmap i is judged
farther than roadmap j. Each roadmap then moves from its measurement with its
own judgements, in a Bradley–Terry model that takes the measurement as its
prior (standard deviation TAU on the log-odds scale). Last, the distances are
placed on the atlas's 0-10 scale: 0 is already in the libraries and 10 is the
farthest roadmap in the atlas. A collection sits at the mean of its child
roadmaps.

The choice is checked by leave-one-block-out prediction of the judgements
(cross_validate in scripts/bradley_terry.py) against the measurement alone, the
reference classification's 0-10 score alone, and the previous method (the
classification score moved by the judgements). The results are recorded in the
validation block of the output.

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
from blueprints import add_new_roadmaps, load_promoted  # noqa: E402
from restructure import apply_restructurings, load_accepted  # noqa: E402
from bradley_terry import agreement, cross_validate, fit_on_scale, fit_weights  # noqa: E402
from galaxies import galaxy_membership  # noqa: E402
from radial_layout import layout, rank_normalise  # noqa: E402
from retirements import apply_retirements  # noqa: E402
from theory_graph import structure, tfidf_similarity  # noqa: E402

FRONTIER = 7.0
# Prior standard deviation of a roadmap's distance around its measurement, on
# the log-odds scale; 1.5 predicts held-out judgements best (1.0 to 2.5 tried).
TAU = 1.5
# The previous method's prior standard deviation, on the classification's 0-10 scale.
PREVIOUS_TAU = 1.5
LAYER_SHARE = 0.6
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


def features(measured):
    """The distance function's inputs: ln(1 + missing targets) and the depth of missing layers."""
    return {rid: [math.log1p(m["missingTargets"]), float(m["depth"])] for rid, m in measured.items()}


def linear(weights, values):
    return sum(w * x for w, x in zip(weights, values))


def judged_distances(x, judgements):
    """Fit the measurement's weights, then move each roadmap with its own judgements (log-odds scale)."""
    weights = fit_weights(x, judgements)
    measurement = {rid: linear(weights, values) for rid, values in x.items()}
    distance, sds, scale = fit_on_scale(measurement, judgements, tau=TAU)
    return weights, measurement, distance, sds, scale


def on_atlas_scale(values, sds, top=None, built=()):
    """Distances on the log-odds scale placed on the atlas's 0-10 scale.

    The farthest roadmap (or `top`, when given) sits at 10; nothing goes below
    0, and a roadmap with nothing left to build (in `built`) sits at 0 whatever
    its judgements say. Returns roadmap -> (distance, low, high), the interval
    being one standard deviation either side.
    """
    top = max(values.values()) if top is None else top
    factor = 10 / top if top > 0 else 1.0
    return {rid: (0.0, 0.0, 0.0) if rid in built else tuple(round(clamp(x * factor), 2) for x in (value, value - sds[rid], value + sds[rid]))
            for rid, value in values.items()}


def model_checks(blocks, x, classification):
    """Held-out prediction of the judgements by the adopted function and its alternatives."""
    scores = {rid: [float(classification[rid]["distance"])] for rid in x}

    def measurement_only(training):
        weights = fit_weights(x, training)
        return {rid: linear(weights, values) for rid, values in x.items()}

    def adopted(training):
        _, _, distance, _, scale = judged_distances(x, training)
        return {rid: value / scale for rid, value in distance.items()}

    def classification_only(training):
        weights = fit_weights(scores, training)
        return {rid: linear(weights, values) for rid, values in scores.items()}

    def previous_method(training):
        distance, _, scale = fit_on_scale({rid: values[0] for rid, values in scores.items()}, training, tau=PREVIOUS_TAU)
        return {rid: value / scale for rid, value in distance.items()}

    return {"adopted": cross_validate(blocks, adopted), "measurementOnly": cross_validate(blocks, measurement_only),
            "classificationOnly": cross_validate(blocks, classification_only),
            "previousMethod": cross_validate(blocks, previous_method)}


def split_half(blocks, x):
    """Refit on alternate judgement blocks and compare how far each half moves roadmaps from their measurements."""
    halves = [[], []]
    for index, name in enumerate(sorted(blocks)):
        halves[index % 2] += blocks[name]
    if not halves[0] or not halves[1]:
        return None, 0
    shifts, counts = [], []
    for half in halves:
        _, measurement, distance, _, _ = judged_distances(x, half)
        shifts.append({rid: distance[rid] - measurement[rid] for rid in x})
        seen = defaultdict(int)
        for item in half:
            seen[item["a"]] += 1
            seen[item["b"]] += 1
        counts.append(seen)
    both = [rid for rid in sorted(x) if counts[0][rid] >= 2 and counts[1][rid] >= 2]
    if len(both) < 5:
        return None, len(both)
    return spearman([shifts[0][r] for r in both], [shifts[1][r] for r in both]), len(both)


def main() -> None:
    atlas = apply_retirements(load(ROOT / "data" / "atlas.json"))
    classification = load(ROOT / "data" / "roadmap-classification.json")["roadmaps"]
    # New roadmaps promoted with their reviewed blueprints are measured like the rest.
    _packets, _documents, definitions = load_promoted(ROOT)
    clusters = {galaxy["id"]: (galaxy.get("clusters") or [None])[0] for galaxy in load(ROOT / "data" / "galaxies.json")["galaxies"]}
    atlas, classification = add_new_roadmaps(atlas, definitions, classification, clusters)
    atlas, _dropped = apply_restructurings(atlas, load_accepted(ROOT))
    roadmap_ids = {roadmap["id"] for roadmap in atlas["roadmaps"]}
    measured, graph = structure(atlas)
    blocks = {name: [item for item in items if item.get("a") in roadmap_ids and item.get("b") in roadmap_ids]
              for name, items in judgements_by_job().items()}
    judgements = [item for items in blocks.values() for item in items]
    if not judgements:
        raise SystemExit("No pairwise judgements in research/blueprint/compare: the distance function cannot be calibrated.")

    x = features({rid: measured[rid] for rid in roadmap_ids})
    weights, measurement, judged, sds, scale = judged_distances(x, judgements)
    counts = defaultdict(int)
    for item in judgements:
        counts[item["a"]] += 1
        counts[item["b"]] += 1
    # Nothing left to build in the whole prerequisite closure: in the libraries.
    built = {rid for rid in roadmap_ids if not measured[rid]["missingLayers"] and not measured[rid]["missingTargets"]}
    placed = on_atlas_scale(judged, sds, built=built)
    baseline = on_atlas_scale(measurement, {rid: 0.0 for rid in measurement}, top=max(judged.values()), built=built)

    roadmaps = {}
    for rid in sorted(roadmap_ids):
        distance, low, high = placed[rid]
        roadmaps[rid] = {"classification": classification[rid]["distance"], "structure": measured[rid],
                         "measurement": baseline[rid][0], "judgements": counts[rid], "distance": distance, "low": low, "high": high,
                         "basis": "built" if rid in built else "judged" if counts[rid] else "measured"}
    # A collection sits at the mean distance of its child roadmaps.
    children = defaultdict(list)
    for roadmap in atlas["roadmaps"]:
        if roadmap.get("parentRoadmapId") in roadmaps:
            children[roadmap["parentRoadmapId"]].append(roadmap["id"])
    for parent, kids in children.items():
        roadmaps[parent].update(distance=round(sum(roadmaps[k]["distance"] for k in kids) / len(kids), 2), basis="children")
        roadmaps[parent].pop("low", None)
        roadmaps[parent].pop("high", None)

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
    # A field's areas lie side by side, so the field reads as one region.
    field_of = {area["id"]: area["field"] for area in load(ROOT / "data" / "galaxies.json")["galaxies"]}
    directions, layout_stress = layout(galaxy_info, similarity, fields=field_of)
    neighbours = {}
    for gid in galaxy_info:
        ranked = sorted((g for g in galaxy_info if g != gid), key=lambda g: (-similarity.get((gid, g), 0.0), g))
        neighbours[gid] = [{"galaxy": g, "similarity": round(similarity.get((gid, g), 0.0), 3)} for g in ranked[:4]]

    # Why each galaxy is here: which other subjects use its roadmaps directly,
    # and which frontier roadmaps (distance >= FRONTIER) rest on them through
    # a chain of layer prerequisites.
    consumers = defaultdict(set)
    for edge in atlas["edges"]:
        if edge["source"] in roadmaps and edge["target"] in roadmaps and edge["source"] != edge["target"]:
            consumers[edge["source"]].add(edge["target"])
    # Reach is followed along layer links, which have no cycles; roadmap-level
    # links do, and would make every roadmap seem to support nearly all others.
    later = defaultdict(set)
    for target, sources in graph.prereqs.items():
        for source in sources:
            later[source].add(target)
    downstream = {}
    for rid in roadmaps:
        seen, stack = set(), [sid for sid in graph.by_owner.get(rid, ())]
        while stack:
            sid = stack.pop()
            for nxt in later[sid]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        downstream[rid] = {graph.owner[sid] for sid in seen if graph.owner[sid] in roadmaps} - {rid}
    use = {}
    for gid, rids in members.items():
        direct = defaultdict(list)
        for rid in rids:
            for other in sorted(consumers[rid]):
                if membership[other] != gid:
                    direct[membership[other]].append({"supplier": rid, "consumer": other})
        frontier = defaultdict(set)
        for rid in rids:
            for other in downstream[rid]:
                if membership[other] != gid and roadmaps[other]["distance"] >= FRONTIER:
                    frontier[membership[other]].add(other)
        use[gid] = {
            "supplies": [{"galaxy": g, "links": len(pairs), "examples": pairs[:3]}
                         for g, pairs in sorted(direct.items(), key=lambda kv: (-len(kv[1]), kv[0]))],
            "frontier": [{"galaxy": g, "roadmaps": len(found)} for g, found in sorted(frontier.items(), key=lambda kv: (-len(kv[1]), kv[0]))],
            "frontierRoadmaps": len(set().union(*frontier.values())) if frontier else 0,
            "upstreamOnly": all(rid.startswith("tauceti:") for rid in rids),
        }
    for rid, record in roadmaps.items():
        outside = defaultdict(int)
        for other in consumers[rid]:
            if membership[other] != membership[rid]:
                outside[membership[other]] += 1
        record["usedBy"] = [{"galaxy": g, "roadmaps": n} for g, n in sorted(outside.items(), key=lambda kv: (-kv[1], kv[0]))]

    ids = sorted(roadmap_ids)
    distance_of = [roadmaps[r]["distance"] for r in ids]
    reliability, shared = split_half(blocks, x)
    validation = {
        "crossValidation": model_checks(blocks, x, classification),
        "splitHalfShiftSpearman": reliability, "splitHalfRoadmaps": shared,
        "distanceVsClassification": spearman(distance_of, [classification[r]["distance"] for r in ids]),
        "distanceVsMissingTargets": spearman(distance_of, [measured[r]["missingTargets"] for r in ids]),
        "distanceVsMissingLayers": spearman(distance_of, [measured[r]["missingLayers"] for r in ids]),
        "distanceVsDepth": spearman(distance_of, [measured[r]["depth"] for r in ids]),
        "completedRoadmaps": {r["id"]: roadmaps[r["id"]]["distance"] for r in atlas["roadmaps"] if r.get("lifecycle") == "completed"},
    }
    decl = [r for r in ids if measured[r].get("declarationLevel")]
    if len(decl) >= 3:
        validation["declarationsVsDistance"] = spearman([measured[r]["declarationLevel"]["missingDeclarations"] for r in decl],
                                                        [roadmaps[r]["distance"] for r in decl])
    by_classification = agreement(judgements, {rid: float(classification[rid]["distance"]) for rid in roadmap_ids})
    by_targets = agreement(judgements, {rid: measured[rid]["missingTargets"] for rid in roadmap_ids})
    by_layers = agreement(judgements, {rid: measured[rid]["missingLayers"] for rid in roadmap_ids})
    by_depth = agreement(judgements, {rid: measured[rid]["depth"] for rid in roadmap_ids})
    pairwise_summary = {
        "judgements": len(judgements), "jobs": len(blocks), "ties": sum(1 for item in judgements if item.get("farther") == "tie"),
        "roadmapsJudged": sum(1 for r in ids if counts[r]), "judgeScale": round(scale, 3), "tau": TAU,
        "weights": {"lnMissingTargets": round(weights[0], 4), "depth": round(weights[1], 4)},
        "targetsPerUnauditedLayer": round(graph.target_fallback, 2),
        "agreesWithClassification": {"share": by_classification[0], "decided": by_classification[1]},
        "agreesWithMissingTargets": {"share": by_targets[0], "decided": by_targets[1]},
        "agreesWithMissingLayers": {"share": by_layers[0], "decided": by_layers[1]},
        "agreesWithDepth": {"share": by_depth[0], "decided": by_depth[1]},
    }
    basis_counts = defaultdict(int)
    for record in roadmaps.values():
        basis_counts[record["basis"]] += 1

    document = {
        "version": 2,
        "purpose": "Distance from Mathlib for every roadmap, on a 0-10 scale, with the measures behind it. Generated by scripts/measure_distances.py; do not edit by hand.",
        "method": {
            "distance": (f"Measured from the theory a roadmap still needs, then moved by its pairwise judgements. The measurement is "
                         f"{weights[0]:.3f} ln(1 + T) + {weights[1]:.3f} D, where T is the number of targets still missing from Mathlib and "
                         f"Tau Ceti in the prerequisite closure of the roadmap's layers and D is the longest chain of layers still to be "
                         f"built; the weights are fitted to the judgements, so that a difference of one in the measurement means odds of e "
                         f"to one of being judged farther. Each roadmap then moves with its own judgements in a Bradley–Terry model whose "
                         f"prior is its measurement (standard deviation {TAU} on the log-odds scale). A collection takes the mean of its "
                         f"child roadmaps."),
            "structure": ("Over the atlas's stage graph, where a layer recorded as complete, or found built by a reviewed library audit, "
                          "is library material. Targets are counted by the reviewed audits: absent from both libraries one, partial a "
                          f"half, process layers none; a layer without an accepted audit counts {graph.target_fallback:.2f} targets, the "
                          "mean of the audited layers still to be built, or half that when in progress. Layers still to be built count "
                          "one each (in progress a half) and the chain is the longest run of them."),
            "scale": "0 means every layer in the prerequisite closure is built (such a roadmap sits at 0 whatever its judgements say); 10 is the farthest roadmap in the atlas. The measurement shown per roadmap uses the same scale.",
            "interval": "One posterior standard deviation either side, from the curvature of the posterior at its peak.",
            "validation": ("Each judgement block is predicted by a model fitted to the other blocks. The adopted function is compared with "
                           "the measurement alone, the reference classification's 0-10 score alone, and the previous method, which moved "
                           "the classification score with the judgements."),
        },
        "bases": dict(basis_counts),
        "pairwise": pairwise_summary,
        "validation": validation,
        "roadmaps": roadmaps,
        "galaxies": {gid: {"distance": round(info["distance"], 2), "roadmaps": info["count"], **use[gid]} for gid, info in sorted(galaxy_info.items())},
    }
    (ROOT / "data" / "roadmap-distances.json").write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    layout_document = {
        "version": 1,
        "purpose": "Directions of the subject galaxies from Mathlib, computed from shared missing theory by scripts/measure_distances.py (scripts/radial_layout.py); do not edit by hand.",
        "method": "Relatedness: 60% the rank of the cosine similarity of the prerequisite layers two galaxies rest on (each layer weighted by its rarity across galaxies, layers still to be built counting double), 40% the rank of the cosine similarity of their references' subject classes. The areas of one field rank above any pair from different fields, so a field's areas lie side by side. Directions minimise the weighted misfit to target angles that run from zero for the most related pair to a half turn for the least, with overlapping galaxies penalised; the result is turned so the roadmaps' mean direction points right, with algebraic geometry above that axis and number theory below it.",
        "stress": round(layout_stress, 4),
        "galaxies": {gid: {"direction": directions[gid], "neighbours": neighbours[gid]} for gid in sorted(directions)},
    }
    (ROOT / "data" / "galaxy-layout.json").write_text(json.dumps(layout_document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"bases": dict(basis_counts), "pairwise": pairwise_summary, "validation": validation,
                      "directions": dict(sorted(directions.items(), key=lambda kv: kv[1])), "stress": round(layout_stress, 4)}, indent=1))


if __name__ == "__main__":
    main()
