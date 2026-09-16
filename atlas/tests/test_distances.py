"""Distance measures: Bradley–Terry scores, the theory graph and the galaxy layout."""
import math
import random
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bradley_terry import fit, outcomes  # noqa: E402
from radial_layout import galaxy_size, layout, radius_for, GALAXY_GAP  # noqa: E402
from theory_graph import TheoryGraph, page_spans, tfidf_similarity  # noqa: E402


def spearman(a, b):
    ra = {k: i for i, k in enumerate(sorted(a, key=a.get))}
    rb = {k: i for i, k in enumerate(sorted(b, key=b.get))}
    n = len(a)
    return 1 - 6 * sum((ra[k] - rb[k]) ** 2 for k in a) / (n * (n * n - 1))


class BradleyTerry(unittest.TestCase):
    def test_recovers_the_order_of_known_strengths(self):
        rng = random.Random(1)
        truth = {f"r{i}": i / 3 for i in range(20)}
        judgements = []
        for _ in range(400):
            a, b = rng.sample(sorted(truth), 2)
            p = 1 / (1 + math.exp(truth[b] - truth[a]))
            judgements.append({"a": a, "b": b, "farther": "a" if rng.random() < p else "b", "strength": "clear"})
        scores = fit(truth, outcomes(judgements))
        self.assertGreater(spearman(truth, scores), 0.9)

    def test_ties_and_slight_verdicts_are_partial_wins(self):
        games = outcomes([{"a": "x", "b": "y", "farther": "tie"}, {"a": "x", "b": "y", "farther": "b", "strength": "slight"}])
        self.assertEqual(sorted(games), [("x", "y", 0.25), ("x", "y", 0.5), ("y", "x", 0.5), ("y", "x", 0.75)])
        self.assertEqual(outcomes([{"a": "x", "b": "x", "farther": "a"}, {"a": "x", "b": "y", "farther": "maybe"}]), [])

    def test_an_unbeaten_roadmap_keeps_a_finite_score(self):
        judgements = [{"a": "top", "b": f"r{i}", "farther": "a", "strength": "clear"} for i in range(6)]
        scores = fit(["top"] + [f"r{i}" for i in range(6)], outcomes(judgements))
        self.assertTrue(all(math.isfinite(v) for v in scores.values()))
        self.assertEqual(max(scores, key=scores.get), "top")
        self.assertAlmostEqual(sum(scores.values()), 0.0, places=9)


def toy_atlas():
    stages = [{"id": "A:1", "owner": "A"}, {"id": "A:2", "owner": "A"},
              {"id": "B:1", "owner": "B"}, {"id": "B:2", "owner": "B", "parentStageId": None},
              {"id": "B:2a", "owner": "B", "parentStageId": "B:2"}, {"id": "B:2b", "owner": "B", "parentStageId": "B:2"},
              {"id": "C:1", "owner": "C"}]
    for stage in stages:
        stage.setdefault("parentStageId", None)
    edges = [("A:1", "A:2"), ("A:2", "B:1"), ("B:1", "B:2a"), ("B:2a", "B:2b"), ("C:1", "B:1")]
    return {"stages": stages, "stageEdges": [{"source": s, "target": t} for s, t in edges]}


class Graph(unittest.TestCase):
    def test_built_layers_end_chains_and_parents_weigh_nothing(self):
        graph = TheoryGraph(toy_atlas(), {"A:1": "complete", "C:1": "in_progress"}, hidden=set())
        self.assertEqual(graph.depth("A:1"), 0)
        self.assertEqual(graph.depth("B:2b"), 4)  # A:2, B:1, B:2a, B:2b
        self.assertEqual(graph.depth("B:2"), 4)   # the parent adds no layer
        needed = graph.roadmap_closure("B")
        self.assertEqual(graph.missing(needed), 1 + 1 + 1 + 1 + 0.5)  # A:2, B:1, B:2a, B:2b, half of C:1
        self.assertIn("A:1", needed)
        self.assertEqual(graph.weight["A:1"], 0.0)
        self.assertEqual(graph.weight["B:2"], 0.0)

    def test_related_layers_include_built_ones(self):
        graph = TheoryGraph(toy_atlas(), {"A:2": "complete"}, hidden=set())
        self.assertNotIn("A:1", graph.closure("B:1"))
        self.assertIn("A:1", graph.related("B:1"))
        self.assertEqual(graph.relatedness_weight("A:2"), 0.5)

    def test_page_spans_merge_overlapping_citations(self):
        spans = page_spans([("s", "Lemma 2.1, p. 9"), ("s", "pp. 9–11"), ("s", "p.12"), ("t", "pages 3-4"), ("s", "no page")])
        self.assertEqual(spans, {"s": [(9, 12)], "t": [(3, 4)]})

    def test_rare_shared_layers_make_galaxies_similar(self):
        sim = tfidf_similarity({"x": {"common", "rare"}, "y": {"common", "rare"}, "z": {"common", "other"}}, {})
        self.assertGreater(sim[("x", "y")], sim[("x", "z")])


class Layout(unittest.TestCase):
    def test_related_galaxies_point_the_same_way(self):
        galaxies = {name: {"distance": d, "count": 4, "lean": lean}
                    for name, d, lean in (("nt1", 3, -1), ("nt2", 8, -1), ("geo1", 4, 1), ("geo2", 9, 1), ("far", 2, 0))}
        sim = {}
        names = sorted(galaxies)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                value = 0.9 if a[:2] == b[:2] else 0.4 if "far" not in (a, b) else 0.0
                sim[(a, b)] = sim[(b, a)] = value
        directions, _ = layout(galaxies, sim, starts=4)
        gap = lambda a, b: abs((directions[a] - directions[b] + 180) % 360 - 180)
        self.assertLess(gap("nt1", "nt2"), gap("nt1", "far"))
        self.assertLess(gap("geo1", "geo2"), gap("geo1", "far"))
        # Geometry lies above the axis (negative angles) and number theory below.
        self.assertLess(directions["geo1"] + directions["geo2"], directions["nt1"] + directions["nt2"])
        again, _ = layout(galaxies, sim, starts=4)
        self.assertEqual(directions, again)

    def test_python_and_javascript_share_the_geometry(self):
        source = (ROOT / "src" / "universe.js").read_text()
        self.assertIn("const radiusFor = distance => 260 + 95 * distance + 17 * distance * distance;", source)
        self.assertIn("const galaxySize = count => 170 + 80 * Math.sqrt(Math.max(1, count));", source)
        self.assertEqual(int(re.search(r"const GALAXY_GAP = (\d+);", source).group(1)), GALAXY_GAP)
        self.assertEqual(radius_for(2), 260 + 190 + 68)
        self.assertEqual(galaxy_size(4), 330)


if __name__ == "__main__":
    unittest.main()
