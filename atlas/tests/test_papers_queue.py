"""Applying reviewed paper extractions to the queue (research/blueprint/make_queue.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
import make_queue  # noqa: E402

ROUTES = [{"route": "source", "roadmap": "R", "stages": ["R:R2"], "items": ["PAPER-X/3"], "reason": "R2's target."},
          {"route": "new", "roadmap": "Fresh", "title": "Fresh theory", "area": "langlands", "items": ["PAPER-X/4"], "brief": "…", "reason": "New."}]


class AcceptedRoutes(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.saved = make_queue.BP
        make_queue.BP = Path(self.folder.name)
        (make_queue.BP / "papers").mkdir()
        (make_queue.BP / "papers" / "PAPER-X.result.json").write_text(json.dumps({"paper": "PAPER-X", "routes": ROUTES}))

    def tearDown(self):
        make_queue.BP = self.saved
        self.folder.cleanup()

    def review(self, verdict, routes):
        (make_queue.BP / "papers" / "PAPER-X.review.json").write_text(json.dumps({"paper": "PAPER-X", "verdict": verdict, "routes": routes}))

    def test_only_the_routes_the_review_accepted_are_applied(self):
        self.review("accept", [{"route": 1, "verdict": "reject", "reason": "Wrong layer."}, {"route": 2, "verdict": "accept", "reason": "Right."}])
        self.assertEqual([r["roadmap"] for r in make_queue.accepted_routes("PAPER-X")], ["Fresh"])

    def test_a_review_asking_for_revision_applies_nothing(self):
        self.review("revise", [{"route": 1, "verdict": "accept", "reason": "Fine."}])
        self.assertEqual(make_queue.accepted_routes("PAPER-X"), [])

    def test_an_unreviewed_extraction_applies_nothing(self):
        self.assertEqual(make_queue.accepted_routes("PAPER-X"), [])


if __name__ == "__main__":
    unittest.main()
