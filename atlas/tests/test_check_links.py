"""Link packets (PROTOCOL.md section 10): links between two Tau Ceti roadmaps are Tau Ceti's own."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_links import check  # noqa: E402

A, B, P = "tauceti:TauCetiRoadmap/A#layer-1", "tauceti:TauCetiRoadmap/B#layer-1", "PlannedRoadmap:P.1"
STAGES = {A: {"id": A, "owner": "tauceti:TauCetiRoadmap/A", "description": "Construct the widget and its universal property."},
          B: {"id": B, "owner": "tauceti:TauCetiRoadmap/B", "description": "Uses the widget and its universal property."},
          P: {"id": P, "owner": "PlannedRoadmap", "description": "Also uses the widget and its universal property."}}
WORLD = (STAGES, {s["owner"]: "" for s in STAGES.values()}, {})


def link(source, target):
    return {"source": source, "target": target, "confidence": "explicit", "reason": "The target uses the widget.",
            "evidence": [{"stageId": source, "quote": STAGES[source]["description"]}, {"stageId": target, "quote": STAGES[target]["description"]}]}


class TauCetiLinks(unittest.TestCase):
    def errors(self, packet, recorded=frozenset()):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "links.json"
            path.write_text(json.dumps(dict({"roadmapId": "tauceti:TauCetiRoadmap/A", "protocol": "links-v1", "status": "complete",
                                             "examined": [{"roadmapId": "PlannedRoadmap", "result": "linked"}]}, **packet)))
            return check(path, WORLD, [], recorded)[0]

    def test_a_new_link_between_two_tau_ceti_roadmaps_is_refused(self):
        found = self.errors({"links": [link(A, B), link(A, P)]})
        self.assertEqual(len(found), 1)
        self.assertIn("Tau Ceti roadmaps", found[0])
        self.assertIn(f"{A} -> {B}", found[0])

    def test_one_recorded_before_stays_as_it_is(self):
        self.assertEqual(self.errors({"links": [link(A, B), link(A, P)]}, {(A, B)}), [])

    def test_a_note_for_the_maintainer_needs_its_text(self):
        self.assertEqual(self.errors({"links": [link(A, P)], "upstreamNotes": [{"roadmaps": ["tauceti:TauCetiRoadmap/B"], "note": "B's layer 1 needs A."}]}), [])
        self.assertTrue(self.errors({"links": [link(A, P)], "upstreamNotes": [{"roadmaps": [], "note": " "}]}))


if __name__ == "__main__":
    unittest.main()
