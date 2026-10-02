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
from make_queue import handed_keydefs_text, keydef_owners, keydef_parts, keydef_slices, route_job  # noqa: E402
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


def key(kid, items, owners=(), planned_by=None):
    entry = {"id": kid, "name": "Name of " + kid, "define": "What to define for " + kid,
             "papers": [{"paper": paper, "items": ids} for paper, ids in items], "owners": list(owners),
             "api": [{"kind": "example", "statement": "An example of " + kid}]}
    if planned_by:
        entry["plannedBy"] = planned_by
    return ("data/keydefs/KEYDEF-x.json", entry)


class Owners(unittest.TestCase):
    """Who plans a key definition no layer plans (PROTOCOL.md section 19)."""
    JOBS = [{"id": "BP-Found", "kind": "blueprint", "roadmapIds": ["Found"], "scope": ["Found:F1"], "order": 10},
            {"id": "BP-Use", "kind": "blueprint", "roadmapIds": ["Use"], "scope": ["Use:U1"], "order": 20},
            {"id": "DESIGN-FoundPartII", "kind": "design", "roadmapIds": ["FoundPartII"], "name": "Foundations, Part II", "order": 30},
            {"id": "DESIGN-NewThing", "kind": "design", "roadmapIds": ["NewThing"], "name": "A new thing", "order": 40},
            {"id": "BP-Done", "kind": "blueprint", "roadmapIds": ["Done"], "scope": ["Done:D1"], "order": 50}]
    ROUTES = {"A/1": {"route": "source", "roadmap": "Found", "stages": ["Found:F1"]},
              "A/2": {"route": "source", "roadmap": "Use", "stages": ["Use:U1"]},
              "B/1": {"route": "source", "roadmap": "Use"},
              "B/2": {"route": "part-ii", "parent": "Found", "roadmap": "FoundMore"},
              "C/1": {"route": "new", "roadmap": "NewThing"},
              "C/2": {"route": "source", "roadmap": "Done"}}
    STATES = {"BP-Done": "done"}
    TITLES = {"Found": "Roadmap: Foundations", "Use": "Uses", "Done": "Done already"}

    def owners(self, entries):
        return keydef_owners(entries, self.ROUTES, self.JOBS, self.STATES, {"Use": {"Found"}, "Found": set()}, self.TITLES)

    def test_routes_lead_to_the_jobs_that_plan_them(self):
        by_id = {j["id"]: j for j in self.JOBS}
        self.assertEqual([route_job(self.ROUTES[i], by_id) for i in ("A/1", "B/1", "B/2", "C/1")],
                         ["BP-Found", "BP-Use", "DESIGN-FoundPartII", "DESIGN-NewThing"])

    def test_the_most_foundational_job_owns_it_and_the_others_cite_it(self):
        found = self.owners([key("ag/excellent", [("A", ["A/1", "A/2"]), ("B", ["B/1", "B/2"])])])["ag/excellent"]
        # BP-Use receives most items, but Found supplies Use and is the parent of the Part II.
        self.assertEqual((found["owner"], found["roadmap"], found["title"], found["reserved"]), ("BP-Found", "Found", "Foundations", "Found:key/excellent"))
        self.assertEqual(found["importers"], ["BP-Use", "DESIGN-FoundPartII"])
        self.assertIn("most foundational", found["reason"])

    def test_without_a_supplier_among_them_most_items_decide(self):
        found = self.owners([key("ag/torsor", [("A", ["A/2"]), ("B", ["B/1"]), ("C", ["C/1"])])])["ag/torsor"]
        self.assertEqual(found["owner"], "BP-Use")
        self.assertEqual(found["importers"], ["DESIGN-NewThing"])

    def test_finished_or_claimed_jobs_are_never_handed_work(self):
        found = self.owners([key("ag/gerbe", [("C", ["C/1", "C/2"])])])["ag/gerbe"]
        self.assertEqual((found["owner"], found["title"], found["unrouted"]), ("DESIGN-NewThing", "A new thing", 1))

    def test_the_survey_can_name_the_owner_and_planned_ones_are_left_alone(self):
        found = self.owners([key("ag/named", [("A", ["A/1"]), ("B", ["B/2"])], planned_by="Use"),
                             key("ag/planned", [("A", ["A/1"]), ("B", ["B/1"])], owners=["Found:F1"]),
                             key("ag/stranded", [("D", ["D/1"]), ("E", ["E/1"])])])
        self.assertEqual(found["ag/named"]["owner"], "BP-Use")
        self.assertNotIn("ag/planned", found)
        self.assertIsNone(found["ag/stranded"]["owner"])

    def test_the_maintainers_decision_comes_first(self):
        entries = [key("ag/excellent", [("A", ["A/1", "A/2"]), ("B", ["B/1", "B/2"])], planned_by="Found"),
                   key("ag/stranded", [("D", ["D/1"]), ("E", ["E/1"])])]
        found = keydef_owners(entries, self.ROUTES, self.JOBS, self.STATES, {"Use": {"Found"}, "Found": set()}, self.TITLES,
                              {"ag/excellent": "Use", "ag/stranded": "NewThing"})
        self.assertEqual((found["ag/excellent"]["owner"], found["ag/excellent"]["reason"]), ("BP-Use", "the maintainer decided on Use"))
        self.assertEqual(found["ag/excellent"]["importers"], ["BP-Found", "DESIGN-FoundPartII"])
        self.assertEqual(found["ag/stranded"]["owner"], "DESIGN-NewThing")

    def test_an_assignment_stands_once_its_jobs_are_claimed_or_finished(self):
        entries = [key("ag/excellent", [("A", ["A/1", "A/2"]), ("B", ["B/1", "B/2"])])]
        first = self.owners(entries)
        claimed = {"BP-Found": "external", "BP-Use": "running", "DESIGN-FoundPartII": "done"}
        later = keydef_owners(entries, self.ROUTES, self.JOBS, claimed, {"Use": {"Found"}, "Found": set()}, self.TITLES, None, first)
        self.assertEqual((later["ag/excellent"]["owner"], later["ag/excellent"]["reserved"]), ("BP-Found", "Found:key/excellent"))
        self.assertEqual(later["ag/excellent"]["importers"], ["BP-Use", "DESIGN-FoundPartII"])
        self.assertEqual(later["ag/excellent"]["reason"], first["ag/excellent"]["reason"])
        # Without the earlier assignment, nothing claimed is handed the definition.
        fresh = keydef_owners(entries, self.ROUTES, self.JOBS, claimed, {"Use": {"Found"}, "Found": set()}, self.TITLES)
        self.assertIsNone(fresh["ag/excellent"]["owner"])

    def test_a_withdrawn_owner_or_a_new_decision_moves_it(self):
        entries = [key("ag/excellent", [("A", ["A/1", "A/2"]), ("B", ["B/1", "B/2"])])]
        first = self.owners(entries)
        gone = keydef_owners(entries, self.ROUTES, self.JOBS, {"BP-Found": "superseded"}, {"Use": {"Found"}, "Found": set()},
                             self.TITLES, None, first)
        self.assertEqual(gone["ag/excellent"]["owner"], "BP-Use")
        decided = keydef_owners(entries, self.ROUTES, self.JOBS, {"BP-Found": "external"}, {"Use": {"Found"}, "Found": set()},
                                self.TITLES, {"ag/excellent": "Use"}, first)
        self.assertEqual((decided["ag/excellent"]["owner"], decided["ag/excellent"]["reason"]), ("BP-Use", "the maintainer decided on Use"))

    def test_the_owner_is_handed_the_entry_and_the_others_the_reserved_id(self):
        entries = [key("ag/excellent", [("A", ["A/1", "A/2"]), ("B", ["B/1", "B/2"])])]
        found = self.owners(entries)
        owned = handed_keydefs_text({"ag/excellent": found["ag/excellent"]}, None, entries)
        self.assertIn("reserved node id `Found:key/excellent`", owned)
        self.assertIn("Plan each once, as generally as all its uses need", owned)
        self.assertIn("(example) An example of ag/excellent", owned)
        cited = handed_keydefs_text(None, {"ag/excellent": found["ag/excellent"]}, entries)
        self.assertIn("Cite the reserved node id", cited)
        self.assertIn("planned by BP-Found (Found)", cited)
        self.assertEqual(handed_keydefs_text(None, None, entries), "")


class Rounds(unittest.TestCase):
    def test_a_survey_its_review_did_not_accept_is_revised_and_reviewed_again(self):
        jobs = {j["id"]: j for j in json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]}
        checked = 0
        for jid, job in jobs.items():
            if job["kind"] != "keydef" or "~" in jid:
                continue
            survey = ROOT / job["outputs"][0]
            review = (json.loads(survey.read_text()).get("review") or {}) if survey.exists() else {}
            if jobs.get("REV-" + jid, {}).get("state") != "done" or review.get("reviewer") != f"independent-review-REV-{jid}" \
                    or review.get("status") not in ("needs_changes", "rejected"):
                continue
            revision = jobs.get(jid + "~2")
            self.assertIsNotNone(revision, jid)
            self.assertEqual(revision["after"], ["REV-" + jid])
            self.assertIn(f"research/blueprint/handoff/{jid}~2.md", revision["outputs"])
            again = jobs["REV-" + jid + "~2"]
            self.assertEqual(again["after"], [jid + "~2"])
            self.assertTrue({jid, "REV-" + jid, jid + "~2"} <= set(again["independentOf"]))
            checked += 1
        if not checked:
            self.skipTest("no key-definition survey is waiting for a revision")


if __name__ == "__main__":
    unittest.main()
