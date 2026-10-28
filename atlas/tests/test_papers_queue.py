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


class PaperDesigns(unittest.TestCase):
    ROADMAPS = {"Heights": {"title": "Heights and rational points"}, "tauceti:TauCetiRoadmap/Reductive": {"title": "Reductive groups"},
                "ReductivePartII": {"title": "Reductive groups, Part II"}}

    def call(self, route, pid="PAPER-X"):
        return route, {"id": pid, "citation": pid + " (2024)"}, f" (from {pid})"

    def test_every_part_ii_proposal_for_one_parent_is_one_design(self):
        massey = self.call({"route": "part-ii", "parent": "Heights", "roadmap": "HeightsPartIIMassey", "title": "Massey heights", "area": "arithmeticgeometry",
                            "brief": "Massey products.", "items": ["PAPER-X/1"]})
        fano = self.call({"route": "part-ii", "parent": "Heights", "roadmap": "HeightsPartIIFano", "title": "Random Fano", "area": "arithmeticgeometry",
                          "brief": "Fano varieties.", "items": ["PAPER-Y/2"]}, "PAPER-Y")
        [(job, rid, area, brief, title)] = make_queue.paper_designs([massey, fano], self.ROADMAPS)
        self.assertEqual((job, rid, area, title), ("DESIGN-HeightsPartII", "HeightsPartII", "arithmeticgeometry", "Heights and rational points, Part II"))
        self.assertIn("starts where that roadmap stops", brief)
        self.assertIn("Massey products.", brief)
        self.assertIn("Fano varieties.", brief)

    def test_a_parent_that_already_has_a_part_ii_gets_a_part_iii_built_on_it(self):
        route = self.call({"route": "part-ii", "parent": "tauceti:TauCetiRoadmap/Reductive", "roadmap": "ReductiveArithmeticPartII", "title": "Arithmetic",
                           "area": "langlands", "brief": "Arithmetic.", "items": ["PAPER-X/1"]})
        [(job, rid, area, brief, title)] = make_queue.paper_designs([route], self.ROADMAPS)
        self.assertEqual((job, rid, title), ("DESIGN-ReductivePartIII", "ReductivePartIII", "Reductive groups, Part III"))
        self.assertIn("ReductivePartII is already in the atlas", brief)

    def test_a_long_brief_is_quoted_briefly_and_pointed_to(self):
        route = self.call({"route": "new", "roadmap": "Fresh", "title": "Fresh theory", "area": "langlands", "items": [f"PAPER-X/{n}" for n in range(300)],
                           "brief": "First sentence of the plan. " + "More detail here. " * 3000})
        [(job, rid, area, brief, title)] = make_queue.paper_designs([route], self.ROADMAPS)
        self.assertLess(len(brief), 1500)
        self.assertIn("First sentence of the plan.", brief)
        self.assertIn("(300 items)", brief)
        self.assertIn("research/blueprint/papers/PAPER-X.result.json, the route to Fresh", brief)

    def test_a_direction_split_off_a_combined_design_is_a_design_of_its_own(self):
        massey = self.call({"route": "part-ii", "parent": "Heights", "roadmap": "HeightsPartIIMassey", "title": "Massey heights", "area": "arithmeticgeometry",
                            "brief": "Massey products.", "items": ["PAPER-X/1"]})
        fano = self.call({"route": "part-ii", "parent": "Heights", "roadmap": "HeightsPartIIFano", "title": "Random Fano", "area": "arithmeticgeometry",
                          "brief": "Fano varieties.", "items": ["PAPER-Y/2"]}, "PAPER-Y")
        splits = {"HeightsPartIIFano": {"design": "DESIGN-HeightsPartII", "parent": "Heights", "packet": "research/blueprint/packets/HeightsPartII.json",
                                        "roadmaps": ["HeightsPartIIFano"], "notes": {"HeightsPartIIFano": "Mind the Massey part."}}}
        designs = {d[0]: d for d in make_queue.paper_designs([massey, fano], self.ROADMAPS, splits)}
        self.assertEqual(sorted(designs), ["DESIGN-HeightsPartII", "DESIGN-HeightsPartIIFano"])
        self.assertIn("Massey products.", designs["DESIGN-HeightsPartII"][3])
        self.assertNotIn("Fano varieties.", designs["DESIGN-HeightsPartII"][3])
        job, rid, area, brief, title = designs["DESIGN-HeightsPartIIFano"]
        self.assertEqual((rid, area, title), ("HeightsPartIIFano", "arithmeticgeometry", "Random Fano"))
        self.assertIn("extends Heights", brief)
        self.assertIn("research/blueprint/packets/HeightsPartII.json", brief)
        self.assertIn("Mind the Massey part.", brief)
        self.assertIn("Fano varieties.", brief)
        # A split names its parent: a route of another roadmap's Part II stays where it was.
        other = self.call({"route": "part-ii", "parent": "Other", "roadmap": "HeightsPartIIFano", "title": "Elsewhere", "area": "langlands",
                           "brief": "Other.", "items": ["PAPER-Z/1"]}, "PAPER-Z")
        self.assertEqual([d[0] for d in make_queue.paper_designs([other], self.ROADMAPS, splits)], ["DESIGN-OtherPartII"])

    def test_a_new_roadmap_several_papers_call_for_is_one_design(self):
        route = {"route": "new", "roadmap": "Fresh", "title": "Fresh theory", "area": "langlands", "brief": "Fresh.", "items": ["PAPER-X/4"]}
        designs = make_queue.paper_designs([self.call(route), self.call(dict(route, brief="Also fresh.", items=["PAPER-Y/1"]), "PAPER-Y")], self.ROADMAPS)
        self.assertEqual([(d[0], d[1], d[4]) for d in designs], [("DESIGN-Fresh", "Fresh", "Fresh theory")])
        self.assertIn("Fresh.", designs[0][3])
        self.assertIn("Also fresh.", designs[0][3])
