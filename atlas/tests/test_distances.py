"""Distance measures: Bradley–Terry scores, the theory graph and the galaxy layout."""
import math
import random
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bradley_terry import cross_validate, fit, fit_weights, outcomes  # noqa: E402
from measure_distances import on_atlas_scale  # noqa: E402
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


def judged(a, b, farther, strength="clear"):
    return {"a": a, "b": b, "farther": farther, "strength": strength}


class FeatureWeights(unittest.TestCase):
    # One feature, x one unit farther than y: when x is judged farther in three
    # games out of four, sigmoid(w) = 3/4 and so w = ln 3.
    def test_weights_match_the_share_of_verdicts_either_way_round(self):
        features = {"x": [1.0], "y": [0.0]}
        verdicts = [judged("x", "y", "a"), judged("x", "y", "a"), judged("y", "x", "b"), judged("y", "x", "a")]
        self.assertAlmostEqual(fit_weights(features, verdicts)[0], math.log(3), delta=0.01)

    def test_a_slight_verdict_is_three_quarters_of_a_win(self):
        features = {"x": [1.0], "y": [0.0]}
        self.assertAlmostEqual(fit_weights(features, [judged("x", "y", "a", "slight")] * 4)[0], math.log(3), delta=0.01)

    def test_a_tie_is_half_a_win_each_way(self):
        features = {"x": [1.0], "y": [0.0]}
        verdicts = [judged("x", "y", "a"), judged("x", "y", "tie", "slight")]
        self.assertAlmostEqual(fit_weights(features, verdicts)[0], math.log(3), delta=0.01)

    def test_recovers_a_known_two_feature_model(self):
        rng = random.Random(7)
        features = {f"r{i}": [rng.uniform(0, 5), rng.uniform(0, 30)] for i in range(40)}
        truth = [1.2, 0.05]
        verdicts = []
        for _ in range(3000):
            a, b = rng.sample(sorted(features), 2)
            logit = sum(w * (x - y) for w, x, y in zip(truth, features[a], features[b]))
            verdicts.append(judged(a, b, "a" if rng.random() < 1 / (1 + math.exp(-logit)) else "b"))
        weights = fit_weights(features, verdicts)
        self.assertAlmostEqual(weights[0], 1.2, delta=0.15)
        self.assertAlmostEqual(weights[1], 0.05, delta=0.02)


class CrossValidation(unittest.TestCase):
    def test_held_out_blocks_prefer_the_feature_that_generated_the_verdicts(self):
        rng = random.Random(11)
        signal = {f"r{i}": [rng.uniform(0, 6)] for i in range(30)}
        noise = {rid: [rng.uniform(0, 6)] for rid in signal}
        blocks = {}
        for block in range(6):
            items = []
            for _ in range(100):
                a, b = rng.sample(sorted(signal), 2)
                p = 1 / (1 + math.exp(-1.5 * (signal[a][0] - signal[b][0])))
                items.append(judged(a, b, "a" if rng.random() < p else "b"))
            blocks[f"B{block}"] = items

        def model(features):
            def fit_and_score(training):
                weights = fit_weights(features, training)
                return {rid: sum(w * x for w, x in zip(weights, xs)) for rid, xs in features.items()}
            return fit_and_score

        good, bad = cross_validate(blocks, model(signal)), cross_validate(blocks, model(noise))
        self.assertEqual(good["judgements"], 600)
        self.assertGreater(good["logLikelihoodPerJudgement"], bad["logLikelihoodPerJudgement"] + 0.1)
        self.assertGreater(good["accuracy"], 0.75)
        self.assertLess(bad["accuracy"], 0.65)

    def test_a_model_that_cannot_tell_two_roadmaps_apart_scores_half(self):
        # Integer scores tie often; a tie is a coin toss, neither right nor wrong.
        blocks = {"B0": [judged("x", "y", "a")], "B1": [judged("y", "x", "a")]}
        result = cross_validate(blocks, lambda training: {"x": 1.0, "y": 1.0})
        self.assertEqual(result["accuracy"], 0.5)
        self.assertAlmostEqual(result["logLikelihoodPerJudgement"], math.log(0.5), places=4)


class AtlasScale(unittest.TestCase):
    def test_the_farthest_roadmap_sits_at_ten_and_nothing_below_zero(self):
        scaled = on_atlas_scale({"x": 2.0, "y": 4.0, "z": -1.0}, {"x": 0.4, "y": 1.0, "z": 0.2})
        self.assertEqual(scaled["x"], (5.0, 4.0, 6.0))
        self.assertEqual(scaled["y"], (10.0, 7.5, 10.0))
        self.assertEqual(scaled["z"], (0.0, 0.0, 0.0))

    def test_a_roadmap_with_nothing_left_to_build_sits_at_zero_whatever_its_judgements(self):
        scaled = on_atlas_scale({"x": 2.0, "y": 4.0, "done": 0.5}, {"x": 0.4, "y": 1.0, "done": 0.3}, built={"done"})
        self.assertEqual(scaled["done"], (0.0, 0.0, 0.0))
        self.assertEqual(scaled["x"], (5.0, 4.0, 6.0))


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

    def test_missing_targets_come_from_the_audit_where_it_exists(self):
        # A:2 is audited: two targets absent, one partial, one in Tau Ceti -> 2.5.
        # B:1 is audited as process -> 0. C:1 is audited absent but recorded built -> 0.
        # Unaudited layers still to build count at the mean of the audited ones
        # still to build, (2.5 + 0) / 2 = 1.25: B:2a fully, B:2b (in progress) half.
        coverage = {"layers": {
            "A:2": {"verdict": "partly built", "targets": [{"library": "absent"}, {"library": "absent"},
                                                            {"library": "partial"}, {"library": "tauceti"}]},
            "B:1": {"verdict": "process", "targets": [{"library": "absent"}]},
            "C:1": {"verdict": "not built", "targets": [{"library": "absent"}]},
        }}
        graph = TheoryGraph(toy_atlas(), {"A:1": "complete", "C:1": "complete", "B:2b": "in_progress"}, hidden=set(), coverage=coverage)
        self.assertEqual(graph.missing_targets(graph.roadmap_closure("B")), 2.5 + 1.25 + 0.625)
        self.assertEqual(graph.missing_targets(graph.roadmap_closure("A")), 2.5)

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
