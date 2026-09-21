"""Directions for the subject galaxies, computed from how related they are.

Each galaxy keeps the radius set by its distance from Mathlib; only its
direction is chosen here. Relatedness between two galaxies comes from the
prerequisite layers they build on and from the subject classes of their
references (scripts/measure_distances.py). Similarities are replaced by their
ranks, and each pair gets a target angle that runs from zero for the most
related pair to a half turn for the least related. The directions minimise the
weighted squared misfit to those angles, weighted towards related pairs, plus
a penalty for galaxies that would overlap on the map. The fit starts from a
spectral embedding of the similarities and from seeded random starts, and the
best is kept.

The areas of one field are ranked as more related than any two areas of
different fields (with_fields), and their misfit weighs FIELD_PULL times
more, so a field's areas lie side by side, each at its own distance. Among the
starts, the fit with the fewest areas lying between two areas of another
field (crossings) is kept, then the one with the least energy.

The result is turned so that the roadmaps' weighted mean direction points to
the right, and mirrored so that algebraic geometry (subject classes 14) lies above that
axis and number theory (subject classes 11) below it: the map has the same
orientation on every screen and after every recomputation.
"""
from __future__ import annotations

import math
import random

# Keep these in step with radiusFor, galaxySize and GALAXY_GAP in src/universe.js.
def radius_for(distance: float) -> float:
    return 260 + 95 * distance + 17 * distance * distance


def galaxy_size(count: int) -> float:
    return 170 + 80 * math.sqrt(max(1, count))


GALAXY_GAP = 70
OVERLAP_PENALTY = 4.0
# How much more the misfit of two areas of one field weighs than any other pair's.
FIELD_PULL = 6.0


def wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def rank_normalise(similarity: dict, keys: list) -> dict:
    """Each pair's similarity replaced by its rank, from 0 (least) to 1 (most); ties share a rank."""
    pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]]
    ordered = sorted(pairs, key=lambda p: (similarity.get(p, 0.0), p))
    n = max(1, len(ordered) - 1)
    ranks = {}
    position = 0
    while position < len(ordered):
        end = position
        while end + 1 < len(ordered) and similarity.get(ordered[end + 1], 0.0) == similarity.get(ordered[position], 0.0):
            end += 1
        value = (position + end) / 2 / n
        for pair in ordered[position:end + 1]:
            ranks[pair] = ranks[(pair[1], pair[0])] = value
        position = end + 1
    return ranks


def jacobi_eigen(matrix):
    """Eigenvalues and eigenvectors (columns) of a small symmetric matrix."""
    n = len(matrix)
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(100):
        off = sum(a[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < 1e-18:
            break
        for p in range(n):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-15:
                    continue
                theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = (1 if theta >= 0 else -1) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    return [a[i][i] for i in range(n)], v


def with_fields(similarity: dict, field_of: dict) -> dict:
    """Similarity in which the areas of one field are more alike than any two
    areas of different fields, so that a field's areas lie side by side; within
    and across fields the order is unchanged."""
    return {pair: value + (1.0 if field_of.get(pair[0]) is not None and field_of.get(pair[0]) == field_of.get(pair[1]) else 0.0)
            for pair, value in similarity.items()}


def crossings(angles: dict, radius: dict, size: dict, fields: dict) -> list:
    """(x, a, b) for each area x whose middle (within half its radius of its
    centre) the straight line between two areas a, b of another field passes
    through: x then lies between them, and their field no longer reads as one
    region. A field nearer the sun may share a field's directions."""
    keys = sorted(angles)
    where = {k: (radius[k] * math.cos(angles[k]), radius[k] * math.sin(angles[k])) for k in keys}
    found = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if fields.get(a) is None or fields.get(a) != fields.get(b):
                continue
            (ax, ay), (bx, by) = where[a], where[b]
            dx, dy = bx - ax, by - ay
            length = dx * dx + dy * dy
            if length == 0:
                continue
            for x in keys:
                if fields.get(x) == fields.get(a):
                    continue
                px, py = where[x]
                t = ((px - ax) * dx + (py - ay) * dy) / length
                if 0 < t < 1 and math.hypot(px - ax - t * dx, py - ay - t * dy) < size[x] / 4:
                    found.append((x, a, b))
    return found


def spectral_start(keys, ranks):
    """Angles from the two leading axes of classical scaling on 1 - similarity."""
    n = len(keys)
    d2 = [[0.0 if i == j else (1 - ranks[(keys[i], keys[j])]) ** 2 for j in range(n)] for i in range(n)]
    row = [sum(r) / n for r in d2]
    total = sum(row) / n
    b = [[-0.5 * (d2[i][j] - row[i] - row[j] + total) for j in range(n)] for i in range(n)]
    values, vectors = jacobi_eigen(b)
    order = sorted(range(n), key=lambda k: -values[k])
    first, second = order[0], order[1]
    return {keys[i]: math.atan2(vectors[i][second] * math.sqrt(max(values[second], 0)),
                                vectors[i][first] * math.sqrt(max(values[first], 0))) for i in range(n)}


def energy(angles, keys, radius, size, target, weight):
    total = 0.0
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            total += weight[(a, b)] * (abs(wrap(angles[a] - angles[b])) - target[(a, b)]) ** 2
            d = math.sqrt(max(1e-9, radius[a] ** 2 + radius[b] ** 2 - 2 * radius[a] * radius[b] * math.cos(angles[a] - angles[b])))
            needed = (size[a] + size[b]) / 2 + GALAXY_GAP
            if d < needed:
                total += OVERLAP_PENALTY * ((needed - d) / needed) ** 2
    return total


def solve(keys, radius, size, target, weight, angles, steps=1200):
    angles = dict(angles)
    moment = {k: 0.0 for k in keys}
    velocity = {k: 0.0 for k in keys}
    rate, beta1, beta2 = 0.02, 0.9, 0.999
    for step in range(1, steps + 1):
        grad = {k: 0.0 for k in keys}
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                delta = wrap(angles[a] - angles[b])
                sign = 1.0 if delta >= 0 else -1.0
                slope = 2 * weight[(a, b)] * (abs(delta) - target[(a, b)]) * sign
                d = math.sqrt(max(1e-9, radius[a] ** 2 + radius[b] ** 2 - 2 * radius[a] * radius[b] * math.cos(delta)))
                needed = (size[a] + size[b]) / 2 + GALAXY_GAP
                if d < needed:
                    slope -= 2 * OVERLAP_PENALTY * (needed - d) / needed ** 2 * radius[a] * radius[b] * math.sin(delta) / d
                grad[a] += slope
                grad[b] -= slope
        for k in keys:
            moment[k] = beta1 * moment[k] + (1 - beta1) * grad[k]
            velocity[k] = beta2 * velocity[k] + (1 - beta2) * grad[k] ** 2
            step_size = rate * (moment[k] / (1 - beta1 ** step)) / (math.sqrt(velocity[k] / (1 - beta2 ** step)) + 1e-12)
            angles[k] = wrap(angles[k] - step_size)
    return angles


def orient(angles, counts, lean_share):
    """Turn the weighted mean direction to the right, then mirror if needed.

    lean_share is positive for galaxies that should lie above the axis
    (algebraic geometry) and negative for those that should lie below
    (number theory); screen coordinates grow downward, so above is negative.
    """
    x = sum(counts[k] * math.cos(a) for k, a in angles.items())
    y = sum(counts[k] * math.sin(a) for k, a in angles.items())
    turn = math.atan2(y, x)
    turned = {k: wrap(a - turn) for k, a in angles.items()}
    lean = sum(counts[k] * lean_share.get(k, 0.0) * math.sin(a) for k, a in turned.items())
    if lean > 0:
        turned = {k: -a for k, a in turned.items()}
    return turned


def layout(galaxies: dict, similarity: dict, fields: dict | None = None, starts: int = 12, seed: int = 20260916):
    """galaxies: id -> {"distance", "count", "lean"}; returns (id -> degrees, energy).

    lean is the share of a galaxy's roadmaps in algebraic geometry minus its
    share in number theory, by primary subject class. fields maps each galaxy
    (an area) to its field: a field's areas rank as the most related pairs and
    their misfit weighs FIELD_PULL times more, so they lie side by side."""
    keys = sorted(galaxies)
    fields = fields or {}
    radius = {k: radius_for(galaxies[k]["distance"]) for k in keys}
    size = {k: galaxy_size(galaxies[k]["count"]) for k in keys}
    ranks = rank_normalise(with_fields(similarity, fields), keys)
    target = {pair: math.pi * (1 - value) for pair, value in ranks.items()}
    together = {pair for pair in ranks if fields.get(pair[0]) is not None and fields.get(pair[0]) == fields.get(pair[1])}
    weight = {pair: (0.25 + value) * (FIELD_PULL if pair in together else 1.0) for pair, value in ranks.items()}
    rng = random.Random(seed)
    first = spectral_start(keys, ranks)
    candidates = [first] + [{k: rng.uniform(-math.pi, math.pi) for k in keys} for _ in range(starts)]
    # The best fit among the starts whose fields read as regions: fewest
    # areas lying between two areas of another field, then the least energy.
    best, best_energy, best_rank = None, math.inf, None
    for start in candidates:
        angles = solve(keys, radius, size, target, weight, start)
        value = energy(angles, keys, radius, size, target, weight)
        rank = (len(crossings(angles, radius, size, fields)), value)
        if best_rank is None or rank < (best_rank[0], best_rank[1] - 1e-9):
            best, best_energy, best_rank = angles, value, rank
    oriented = orient(best, {k: galaxies[k]["count"] for k in keys}, {k: galaxies[k].get("lean", 0.0) for k in keys})
    return {k: round(math.degrees(a), 1) for k, a in oriented.items()}, best_energy
