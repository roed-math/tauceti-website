import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atlas_distances import measure, readme_links, scale_factor  # noqa: E402

WEIGHTS = {"lnMissingTargets": 0.9569, "depth": 0.0375}


def raw(targets, depth):
    return WEIGHTS["lnMissingTargets"] * math.log1p(targets) + WEIGHTS["depth"] * depth


def recorded(**roadmaps):
    # One roadmap measured on the 0-10 scale at half its log-odds measurement: the factor is 0.5.
    return {"pairwise": {"weights": WEIGHTS},
            "roadmaps": {"campaign:X": {"structure": {"missingTargets": 10, "depth": 2}, "measurement": raw(10, 2) / 2, "basis": "measured"}, **roadmaps}}


def atlas():
    # P and R are two-layer roadmaps still to be built, R's README naming P as a prerequisite; S is built.
    return {"roadmaps": [{"id": "tauceti:P", "origin": "tauceti"}, {"id": "tauceti:R", "origin": "proposed"}, {"id": "tauceti:S", "origin": "tauceti"}],
            "stages": [{"id": f"{name}:{index}", "owner": f"tauceti:{name}"} for name in ("P", "R", "S") for index in (1, 2)],
            "stageEdges": [{"source": f"{name}:1", "target": f"{name}:2"} for name in ("P", "R", "S")],
            "edges": [{"source": "tauceti:P", "target": "tauceti:R", "kind": "readme"}],
            "progress": {"stages": {"S:1": {"status": "complete"}, "S:2": {"status": "complete"}}},
            "stagePresentation": {}}


class PageDistances(unittest.TestCase):
    """Every roadmap on the published page measured by the distance function, on the snapshot's scale."""

    def test_the_scale_is_read_back_from_the_measured_roadmaps(self):
        self.assertAlmostEqual(scale_factor(recorded()), .5)

    def test_a_readme_prerequisite_puts_all_of_the_other_roadmap_before_the_dependents_first_layer(self):
        self.assertEqual(readme_links(atlas()), [{"source": "P:2", "target": "R:1"}])
        # A pair a layer link already joins needs none.
        joined = atlas()
        joined["stageEdges"].append({"source": "P:1", "target": "R:2"})
        self.assertEqual(readme_links(joined), [])

    def test_each_roadmap_is_measured_over_its_prerequisites_and_a_built_one_sits_at_zero(self):
        out = measure(atlas(), recorded(), {})
        self.assertEqual(out["tauceti:R"]["structure"]["missingLayers"], 4)
        self.assertEqual((out["tauceti:R"]["structure"]["depth"], out["tauceti:P"]["structure"]["depth"]), (4, 2))
        # No audit counts the targets: a layer still to be built counts one.
        self.assertEqual(out["tauceti:R"]["distance"], round(raw(4, 4) / 2, 2))
        self.assertEqual(out["tauceti:P"]["distance"], round(raw(2, 2) / 2, 2))
        self.assertEqual((out["tauceti:S"]["distance"], out["tauceti:S"]["basis"]), (0.0, "built"))
        self.assertEqual(out["tauceti:R"]["basis"], "measured")

    def test_a_roadmap_the_swarm_judged_keeps_its_judged_distance(self):
        judged = {"distance": 7.1, "basis": "judged", "judgements": 12}
        out = measure(atlas(), recorded(**{"tauceti:P": judged}), {})
        self.assertIs(out["tauceti:P"], judged)


if __name__ == "__main__":
    unittest.main()
