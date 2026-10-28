"""Bradley–Terry scores from pairwise judgements of distance from Mathlib.

Each judgement says which of two roadmaps is farther from the library, how
clearly, or that they are tied. A clear verdict is a whole win, a slight one
three quarters of a win, and a tie half a win to each side. Every roadmap also
plays one virtual game, drawn, against a fixed reference roadmap: this weak
prior keeps every score finite, even for a roadmap that won or lost all its
comparisons. The fit uses Hunter's minorisation-maximisation algorithm, and a
bootstrap over judgements gives each score an interval.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict

CREDIT = {"clear": 1.0, "slight": 0.75}
PRIOR_GAMES = 1.0


def outcomes(judgements):
    """(winner, loser, credit) triples; a tie gives half a win each way."""
    games = []
    for item in judgements:
        a, b, verdict = item["a"], item["b"], item.get("farther")
        if a == b or verdict not in ("a", "b", "tie"):
            continue
        if verdict == "tie":
            games.append((a, b, 0.5))
            games.append((b, a, 0.5))
            continue
        winner, loser = (a, b) if verdict == "a" else (b, a)
        credit = CREDIT.get(item.get("strength"), 1.0)
        games.append((winner, loser, credit))
        if credit < 1:
            games.append((loser, winner, 1 - credit))
    return games


def fit(items, games, iterations=2000, tolerance=1e-9):
    """Log-strengths, centred on zero, for the given items."""
    items = sorted(set(items))
    wins = defaultdict(float)
    played = defaultdict(float)
    for winner, loser, credit in games:
        wins[winner] += credit
        # The credits of one judgement add up to one game between the pair.
        played[tuple(sorted((winner, loser)))] += credit
    opponents = defaultdict(dict)
    for (a, b), n in played.items():
        opponents[a][b] = n
        opponents[b][a] = n
    strength = {item: 1.0 for item in items}
    for _ in range(iterations):
        largest = 0.0
        for item in items:
            # The prior: PRIOR_GAMES drawn games against a reference of strength one.
            numerator = wins[item] + PRIOR_GAMES / 2
            denominator = PRIOR_GAMES / (strength[item] + 1.0)
            for other, n in opponents[item].items():
                denominator += n / (strength[item] + strength[other])
            new = numerator / denominator
            largest = max(largest, abs(math.log(new) - math.log(strength[item])))
            strength[item] = new
        if largest < tolerance:
            break
    logs = {item: math.log(value) for item, value in strength.items()}
    centre = sum(logs.values()) / len(logs)
    return {item: value - centre for item, value in logs.items()}


def bootstrap(items, judgements, replicates=300, seed=20260916):
    """Scores refitted on judgements resampled with replacement."""
    rng = random.Random(seed)
    draws = defaultdict(list)
    for _ in range(replicates):
        sample = [judgements[rng.randrange(len(judgements))] for _ in judgements]
        for item, value in fit(items, outcomes(sample), iterations=400, tolerance=1e-6).items():
            draws[item].append(value)
    return draws


def quantile(values, q):
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    position = q * (len(ordered) - 1)
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _sigmoid(x):
    if x >= 0:
        return 1 / (1 + math.exp(-x))
    z = math.exp(x)
    return z / (1 + z)


def fit_on_scale(prior, judgements, tau=1.5, iterations=20):
    """Distances on the 0-10 scale from judgements, with the prior scores as the starting belief.

    The chance that roadmap i is judged farther than roadmap j is
    sigmoid((d_i - d_j) / s); each d_i has a normal prior centred on prior[i]
    with standard deviation tau. The judges' noise s is estimated once, by
    maximum likelihood with every distance held at its prior (letting the
    distances move at the same time would let a few judgements separate every
    pair perfectly and drive s to zero). The distances are then the maximum a
    posteriori estimates for that s, found by diagonal Newton steps. Returns
    (distances, sds, s): sds come from the curvature of the posterior at its
    peak (a Laplace approximation).
    """
    items = sorted(prior)
    credits = defaultdict(float)
    played = defaultdict(float)
    for winner, loser, credit in outcomes([j for j in judgements if j.get("a") in prior and j.get("b") in prior]):
        credits[(winner, loser)] += credit
        played[tuple(sorted((winner, loser)))] += credit
    neighbours = defaultdict(list)
    for (a, b), n in played.items():
        neighbours[a].append((b, credits[(a, b)], n))
        neighbours[b].append((a, credits[(b, a)], n))
    d = {i: float(prior[i]) for i in items}

    def loglik(scale):
        total = 0.0
        for (a, b), n in played.items():
            x = (d[a] - d[b]) / scale
            total += credits[(a, b)] * math.log(max(1e-12, _sigmoid(x))) + credits[(b, a)] * math.log(max(1e-12, _sigmoid(-x)))
        return total

    def best_scale(low=0.3, high=6.0):
        ratio = (math.sqrt(5) - 1) / 2
        a, b = low, high
        c, e = b - ratio * (b - a), a + ratio * (b - a)
        fc, fe = loglik(c), loglik(e)
        for _ in range(40):
            if fc > fe:
                b, e, fe = e, c, fc
                c = b - ratio * (b - a)
                fc = loglik(c)
            else:
                a, c, fc = c, e, fe
                e = a + ratio * (b - a)
                fe = loglik(e)
        return (a + b) / 2

    scale = best_scale() if played else 1.0
    for _ in range(iterations):
        for _ in range(10):
            for i in items:
                gradient = -(d[i] - prior[i]) / tau ** 2
                curvature = 1 / tau ** 2
                for j, won, n in neighbours[i]:
                    p = _sigmoid((d[i] - d[j]) / scale)
                    gradient += (won - n * p) / scale
                    curvature += n * p * (1 - p) / scale ** 2
                d[i] += gradient / curvature
    sds = {}
    for i in items:
        curvature = 1 / tau ** 2
        for j, won, n in neighbours[i]:
            p = _sigmoid((d[i] - d[j]) / scale)
            curvature += n * p * (1 - p) / scale ** 2
        sds[i] = 1 / math.sqrt(curvature)
    return d, sds, scale


def agreement(judgements, ordering):
    """Share of decided judgements whose farther roadmap also ranks farther by another measure."""
    agree = total = 0
    for item in judgements:
        a, b, verdict = item.get("a"), item.get("b"), item.get("farther")
        if verdict not in ("a", "b") or a not in ordering or b not in ordering or ordering[a] == ordering[b]:
            continue
        total += 1
        farther, nearer = (a, b) if verdict == "a" else (b, a)
        agree += ordering[farther] > ordering[nearer]
    return (round(agree / total, 3), total) if total else (None, 0)


def _solve(matrix, vector):
    """Solve a small linear system by Gaussian elimination with partial pivoting."""
    size = len(vector)
    rows = [list(row) + [value] for row, value in zip(matrix, vector)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(rows[r][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(size):
            if r != col and rows[col][col]:
                factor = rows[r][col] / rows[col][col]
                for k in range(col, size + 1):
                    rows[r][k] -= factor * rows[col][k]
    return [rows[i][size] / rows[i][i] if rows[i][i] else 0.0 for i in range(size)]


def fit_weights(features, judgements, ridge=1e-3, iterations=100, tolerance=1e-10):
    """Weights w such that sigmoid(w . (x_i - x_j)) is the chance that roadmap i is judged farther than j.

    features: roadmap -> list of numbers, the same length for every roadmap.
    Verdicts count as in outcomes(): a clear verdict is a whole win, a slight
    one three quarters of a win, a tie half a win each way. The weights are the
    maximum likelihood estimates with a small ridge penalty, found by Newton's
    method; the likelihood is concave, so the steps converge.
    """
    games = [([a - b for a, b in zip(features[winner], features[loser])], credit)
             for winner, loser, credit in outcomes([j for j in judgements if j.get("a") in features and j.get("b") in features])]
    size = len(next(iter(features.values()))) if features else 0
    weights = [0.0] * size
    if not games or not size:
        return weights
    for _ in range(iterations):
        gradient = [-ridge * w for w in weights]
        curvature = [[ridge if r == c else 0.0 for c in range(size)] for r in range(size)]
        for dx, credit in games:
            p = _sigmoid(sum(w * x for w, x in zip(weights, dx)))
            for r in range(size):
                gradient[r] += credit * (1 - p) * dx[r]
                for c in range(size):
                    curvature[r][c] += credit * p * (1 - p) * dx[r] * dx[c]
        step = _solve(curvature, gradient)
        weights = [w + s for w, s in zip(weights, step)]
        if max(abs(s) for s in step) < tolerance:
            break
    return weights


def cross_validate(blocks, fit_and_score):
    """Leave-one-block-out check of a distance model against judgements it has not seen.

    blocks: block name -> judgements. fit_and_score(training judgements) returns
    a score per roadmap on the log-odds scale: a difference of d means odds of
    e^d to one that the higher roadmap is judged farther. Each block is scored
    by a model fitted to the others. Returns the held-out log-likelihood per
    judgement (verdicts weighted as in outcomes()) and the share of decided
    verdicts whose farther roadmap has the higher score, a tied score counting
    half.
    """
    names = sorted(blocks)
    total = right = 0.0
    count = decided = 0
    for held in names:
        score = fit_and_score([item for name in names if name != held for item in blocks[name]])
        for item in blocks[held]:
            a, b = item.get("a"), item.get("b")
            games = outcomes([item]) if a in score and b in score else []
            if not games:
                continue
            count += 1
            for winner, loser, credit in games:
                total += credit * math.log(max(1e-12, _sigmoid(score[winner] - score[loser])))
            if item.get("farther") in ("a", "b"):
                decided += 1
                farther, nearer = (a, b) if item["farther"] == "a" else (b, a)
                right += 1.0 if score[farther] > score[nearer] else 0.5 if score[farther] == score[nearer] else 0.0
    return {"judgements": count,
            "logLikelihoodPerJudgement": round(total / count, 4) if count else None,
            "accuracy": round(right / decided, 4) if decided else None}
