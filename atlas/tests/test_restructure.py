"""Accepted restructuring proposals in the atlas build (scripts/restructure.py, PROTOCOL.md section 15)."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from restructure import apply_restructurings  # noqa: E402


def stage(sid, owner):
    return {"id": sid, "owner": owner, "title": "Layer " + sid, "description": "Everything " + sid + " plans.",
            "requires": [], "consumers": [], "parentStageId": None}


def atlas():
    return {"roadmaps": [{"id": "A", "title": "Roadmap A", "origin": "campaign", "stages": ["A:1", "A:2"], "prerequisites": [], "consumers": []},
                         {"id": "B", "title": "Roadmap B", "origin": "campaign", "stages": ["B:1"], "prerequisites": [], "consumers": []},
                         {"id": "tauceti:X", "title": "Upstream X", "origin": "tauceti", "stages": ["tauceti:X:1"], "prerequisites": [], "consumers": []}],
            "stages": [stage("A:1", "A"), stage("A:2", "A"), stage("B:1", "B"), stage("tauceti:X:1", "tauceti:X")],
            "stageEdges": [], "edges": []}


def proposal():
    return {"family": "RS-01", "review": {"status": "accepted", "reviewer": "independent-review-REV-RS-01"},
            "roadmaps": {"A": {"action": "extend", "extends": "tauceti:X", "title": "Upstream X, Part II: more", "reason": "It extends X."},
                         "B": {"action": "keep", "reason": "Distinct."}},
            "layers": {"A:1": {"action": "narrow", "keeps": "Only the local statement.", "suppliedBy": ["B:1"], "reason": "B owns the global one."},
                       "A:2": {"action": "drop", "suppliedBy": ["B:1"], "reason": "B:1 plans it."},
                       "tauceti:X:1": {"action": "narrow", "keeps": "Less.", "reason": "Wrong."}},
            "links": [{"source": "B:1", "target": "A:1", "reason": "The global statement."},
                      {"source": "Q:9", "target": "A:1", "reason": "Unknown."}]}


class Restructurings(unittest.TestCase):
    def applied(self):
        return apply_restructurings(atlas(), [proposal()])

    def test_an_extension_takes_its_title_and_builds_on_its_base(self):
        result, _ = self.applied()
        a = next(r for r in result["roadmaps"] if r["id"] == "A")
        self.assertEqual((a["title"], a["extends"]), ("Upstream X, Part II: more", "tauceti:X"))
        self.assertIn({"source": "tauceti:X", "target": "A", "kind": "declared"}, result["edges"])

    def test_a_narrowed_layer_plans_only_what_it_keeps(self):
        result, _ = self.applied()
        layer = next(s for s in result["stages"] if s["id"] == "A:1")
        self.assertTrue(layer["description"].startswith("Only the local statement."))
        self.assertEqual(layer["restructured"], {"proposal": "RS-01", "action": "narrow", "keeps": "Only the local statement.",
                                                 "suppliedBy": ["B:1"], "reason": "B owns the global one."})

    def test_a_dropped_layer_leaves_the_map_and_names_its_supplier(self):
        result, hidden = self.applied()
        self.assertTrue(hidden["A:2"]["hidden"])
        self.assertIn("B:1", hidden["A:2"]["summary"])
        self.assertEqual(next(s for s in result["stages"] if s["id"] == "A:2")["restructured"]["action"], "drop")

    def test_its_links_join_the_atlas_and_unknown_ones_are_recorded(self):
        result, _ = self.applied()
        edge = next(e for e in result["stageEdges"] if (e["source"], e["target"]) == ("B:1", "A:1"))
        self.assertEqual(edge["kind"], "restructure")
        self.assertEqual(edge["evidence"], [{"proposal": "RS-01", "reason": "The global statement."}])
        self.assertIn("B", next(r for r in result["roadmaps"] if r["id"] == "A")["prerequisites"])
        record = result["restructurings"][0]
        self.assertEqual(record["skippedLinks"], [["Q:9", "A:1"]])

    def test_tau_ceti_roadmaps_never_change(self):
        result, _ = self.applied()
        upstream = next(s for s in result["stages"] if s["id"] == "tauceti:X:1")
        self.assertEqual(upstream["description"], "Everything tauceti:X:1 plans.")
        self.assertIn("tauceti:X:1", result["restructurings"][0]["unchanged"])

    def test_the_snapshot_is_not_changed(self):
        base = atlas()
        kept = copy.deepcopy(base)
        apply_restructurings(base, [proposal()])
        self.assertEqual(base, kept)


if __name__ == "__main__":
    unittest.main()
