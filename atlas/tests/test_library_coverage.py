"""What the reviewed library audit changes in the atlas, and what it must not."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from library_coverage import already_available, coverage_statuses  # noqa: E402

ATLAS = {"roadmaps": [{"id": "P", "origin": "campaign"}, {"id": "tauceti:T", "origin": "tauceti"}],
         "stages": [{"id": f"P:{n}", "owner": "P"} for n in range(4)] + [{"id": "tauceti:T:0", "owner": "tauceti:T"}]}
EVIDENCE = [{"library": "mathlib", "name": "CondensedMod", "file": "Mathlib/Condensed/Module.lean", "line": 1, "fit": "exact", "target": "condensed modules"}]
COVERAGE = {"layers": {
    "P:0": {"verdict": "built", "evidence": EVIDENCE, "targets": [{"target": "condensed modules", "library": "mathlib"}]},
    "P:1": {"verdict": "partly built", "evidence": EVIDENCE, "targets": [{"target": "condensed modules", "library": "mathlib"}]},
    "P:2": {"verdict": "process", "targets": [{"target": "migrate the imports", "library": "process"}]},
    "P:3": {"verdict": "not built", "targets": [{"target": "lisse sheaves", "library": "absent"}]},
    "tauceti:T:0": {"verdict": "built", "evidence": EVIDENCE, "targets": [{"target": "condensed modules", "library": "mathlib"}]},
}}


class ProposedRoadmaps(unittest.TestCase):
    def test_layers_already_in_the_libraries_or_not_mathematics_are_hidden(self):
        hidden = already_available(COVERAGE, ATLAS)
        self.assertEqual(sorted(hidden), ["P:0", "P:2"])
        self.assertTrue(all(item["hidden"] for item in hidden.values()))
        self.assertIn("CondensedMod", hidden["P:0"]["summary"])

    def test_a_tau_ceti_layer_built_in_the_libraries_counts_as_progress(self):
        statuses = coverage_statuses(COVERAGE, {}, {"tauceti:T:0"})
        self.assertEqual(statuses["tauceti:T:0"]["status"], "complete")
        self.assertNotIn("P:1", statuses)


if __name__ == "__main__":
    unittest.main()
