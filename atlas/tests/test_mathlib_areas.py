import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from arxiv_groups import CATEGORIES  # noqa: E402
from mathlib_areas import area_of, load_rules  # noqa: E402

RULES = load_rules(ROOT / "data" / "mathlib-areas.json")
# The top-level folders of Mathlib at the pinned commit (2cabef97b63d).
TOP = ["Algebra", "AlgebraicGeometry", "AlgebraicTopology", "Analysis", "Basic", "CategoryTheory", "Combinatorics", "Computability",
       "Condensed", "Control", "Data", "Deprecated", "Dynamics", "FieldTheory", "Geometry", "GroupTheory", "InformationTheory", "Init",
       "Lean", "LinearAlgebra", "Logic", "MeasureTheory", "ModelTheory", "NumberTheory", "Order", "Probability", "RepresentationTheory",
       "RingTheory", "SetTheory", "Tactic", "Testing", "Topology", "Util"]


class Areas(unittest.TestCase):
    """Where on the disk a Mathlib module's declarations go: its area, by the longest prefix in the table."""

    def test_a_module_takes_the_area_of_its_longest_prefix(self):
        self.assertEqual(area_of("Mathlib.NumberTheory.ModularForms.Basic", RULES), "math.NT/automorphic")
        self.assertEqual(area_of("Mathlib.Topology.Homotopy.Basic", RULES), "math.AT")
        self.assertEqual(area_of("Mathlib.Topology.Compactness.Compact", RULES), "math.GN")

    def test_a_prefix_matches_whole_components_only(self):
        rules = [("Mathlib.Topology", "math.GN")]
        self.assertEqual(area_of("Mathlib.Topology", rules), "math.GN")
        self.assertIsNone(area_of("Mathlib.Topologyx.Foo", rules))

    def test_elementary_number_theory_is_the_categorys_catch_all(self):
        self.assertEqual(area_of("Mathlib.NumberTheory.Pell", RULES), "math.NT/other")

    def test_tactics_and_tooling_are_left_out(self):
        for module in ("Mathlib.Tactic.Ring.Basic", "Mathlib.Util.Superscript", "Mathlib.Lean.Expr.Basic", "Mathlib.Testing.Plausible.Functions",
                       "Mathlib.Deprecated.Aliases"):
            self.assertIsNone(area_of(module, RULES), module)

    def test_every_area_is_a_category_of_the_map_or_one_of_its_finer_areas(self):
        finer = json.loads((ROOT / "data" / "arxiv-subareas.json").read_text(encoding="utf-8"))["categories"]
        for prefix, area in RULES:
            if area is None:
                continue
            code, _, sub = area.partition("/")
            self.assertIn(code, CATEGORIES, prefix)
            if sub:
                self.assertIn(sub, [a["id"] for a in finer.get(code, [])], prefix)

    def test_every_top_level_folder_has_a_rule(self):
        for top in TOP:
            self.assertTrue(any(prefix == "Mathlib." + top for prefix, _ in RULES), top)

    def test_longer_prefixes_come_first(self):
        lengths = [len(prefix.split(".")) for prefix, _ in RULES]
        self.assertEqual(lengths, sorted(lengths, reverse=True))


if __name__ == "__main__":
    unittest.main()
