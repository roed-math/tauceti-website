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
