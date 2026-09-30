"""Key-definition surveys in the queue, the issues and promotion (PROTOCOL.md section 19)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
sys.path.insert(0, str(ROOT / "scripts"))
import issues  # noqa: E402
from make_queue import keydef_parts, keydef_slices  # noqa: E402
from promote import candidates, destinations  # noqa: E402


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def item(iid, kind="definition", status="missing", planned=()):
    return {"id": iid, "kind": kind, "name": "Name of " + iid, "statement": "Statement of " + iid, "status": status, "planned": list(planned)}


class Slices(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write(self.root / "data/items/0.json", {"paper": "PAPER-A", "items": [
            item("PAPER-A/1", planned=["R:L1"]),                                        # planned by a layer of R
            item("PAPER-A/2", planned=["tauceti:TauCetiRoadmap/Schemes#layer-1"]),      # Tau Ceti owns it
            item("PAPER-A/3", status="library"),                                         # the libraries have it
            item("PAPER-A/4", kind="theorem"),                                           # not a definition
            item("PAPER-A/5"),                                                           # routed to a new roadmap
            item("PAPER-A/6", planned=["R:L1/node"])]})                                  # planned by a node of R:L1
        write(self.root / "data/items/1.json", {"paper": "PAPER-B", "items": [item("PAPER-B/1"), item("PAPER-B/2", kind="construction")]})
        write(self.root / "research/blueprint/papers/PAPER-A.result.json",
              {"routes": [{"route": "new", "roadmap": "NewStacks", "area": "algebraicgeometry", "items": ["PAPER-A/5"]}]})
        write(self.root / "research/blueprint/papers/PAPER-B.result.json",
              {"routes": [{"route": "part-ii", "roadmap": "SPartII", "parent": "S", "area": "legacy-area", "items": ["PAPER-B/1", "PAPER-B/2"]}]})
        self.stages = {"R:L1": {"id": "R:L1", "owner": "R"}}
        self.galaxy_of = {"R": "algebraicgeometry", "S": "algebraicnt"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_items_go_to_the_area_of_their_owner(self):
        slices = keydef_slices(self.stages, self.galaxy_of, {}, {"algebraicgeometry", "algebraicnt"}, root=self.root)
        self.assertEqual(sorted(i["id"] for i in slices["algebraicgeometry"]), ["PAPER-A/1", "PAPER-A/5", "PAPER-A/6"])
        # A Part II with an unknown area takes its parent's.
        self.assertEqual(sorted(i["id"] for i in slices["algebraicnt"]), ["PAPER-B/1", "PAPER-B/2"])
        first = next(i for i in slices["algebraicgeometry"] if i["id"] == "PAPER-A/1")
        self.assertEqual((first["owner"], first["layer"], first["paper"]), ("R", "R:L1", "PAPER-A"))

    def test_a_large_area_is_split_into_parts_of_whole_roadmaps(self):
        items = [{"id": f"X/{n}", "owner": owner} for n, owner in enumerate(["A"] * 3 + ["B"] * 2 + ["C"] * 4)]
        parts = keydef_parts(items, size=5)
        self.assertEqual([sorted({i["owner"] for i in part}) for part in parts], [["A", "B"], ["C"]])
        self.assertEqual(keydef_parts([], size=5), [[]])


class Issues(unittest.TestCase):
    def test_titles_labels_and_the_delivery_list(self):
        job = {"id": "KEYDEF-algebraicgeometry", "kind": "keydef", "name": "Schemes, curves and moduli", "area": "algebraicgeometry",
               "roadmapIds": [], "outputs": ["research/blueprint/keydefs/KEYDEF-algebraicgeometry.json"], "priority": 1}
        review = {"id": "REV-KEYDEF-algebraicgeometry", "kind": "review", "name": "Schemes, curves and moduli", "roadmapIds": [],
                  "after": ["KEYDEF-algebraicgeometry"], "area": "algebraicgeometry"}
        self.assertEqual(issues.title(job, {}), "[Key definitions] Schemes, curves and moduli")
        self.assertEqual(issues.title(review, {}), "[Review] Key definitions: Schemes, curves and moduli")
        self.assertIn("area:algebraicgeometry", issues.labels_for(job, {}, {job["id"]: job}))
        self.assertIn("A sample API that tells a right formalisation from a wrong one", issues.body(job, [job], {}, {}))

    def test_a_survey_and_its_review_are_done_when_their_files_say_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            survey = root / "research/blueprint/keydefs/KEYDEF-algebraicgeometry.json"
            report = root / "research/blueprint/keydefs/KEYDEF-algebraicgeometry.md"
            job = {"id": "KEYDEF-algebraicgeometry", "kind": "keydef", "outputs": [str(survey.relative_to(root)), str(report.relative_to(root))]}
            review = {"id": "REV-KEYDEF-algebraicgeometry", "kind": "review", "after": [job["id"]],
                      "outputs": ["research/blueprint/reviews/REV-KEYDEF-algebraicgeometry.md"] + job["outputs"]}
            write(survey, {"status": "partial"})
            report.write_text("report")
            self.assertFalse(issues.deliverables_complete(job, root))
            write(survey, {"status": "complete"})
            self.assertTrue(issues.deliverables_complete(job, root))
            (root / "research/blueprint/reviews").mkdir(parents=True)
            (root / "research/blueprint/reviews/REV-KEYDEF-algebraicgeometry.md").write_text("notes so far")
            self.assertFalse(issues.deliverables_complete(review, root))
            write(survey, {"status": "complete", "review": {"status": "accepted", "reviewer": "independent-review-REV-KEYDEF-algebraicgeometry", "date": "2026-10-01"}})
            self.assertTrue(issues.deliverables_complete(review, root))


class Promotion(unittest.TestCase):
    def test_an_accepted_survey_goes_to_data_keydefs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "research/blueprint/keydefs/KEYDEF-algebraicgeometry.json", {})
            write(root / "research/blueprint/keydefs/areas.json", {"enabled": []})
            write(root / "research/blueprint/keydefs/inputs/KEYDEF-algebraicgeometry.json", {"items": []})
            found = candidates(root)
            self.assertIn("research/blueprint/keydefs/KEYDEF-algebraicgeometry.json", found)
            self.assertFalse(any("areas.json" in path or "inputs" in path for path in found))
            files, problem = destinations(root, "research/blueprint/keydefs/KEYDEF-algebraicgeometry.json", {}, set())
            self.assertIsNone(problem)
            self.assertEqual(files, [("research/blueprint/keydefs/KEYDEF-algebraicgeometry.json", "data/keydefs/KEYDEF-algebraicgeometry.json")])


if __name__ == "__main__":
    unittest.main()
