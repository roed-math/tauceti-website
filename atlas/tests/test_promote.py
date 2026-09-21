"""Promotion of independently reviewed work into the atlas (scripts/promote.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from promote import decide, promote  # noqa: E402

PACKET = "research/blueprint/packets/R.json"
JOBS = [{"id": "BP-R", "kind": "blueprint", "state": "done", "outputs": [PACKET, "research/blueprint/readmes/R.md"]},
        {"id": "REV-R", "kind": "review", "state": "done", "after": ["BP-R"], "outputs": ["research/blueprint/reviews/REV-R.md"]}]
ACCEPTED = {"status": "accepted", "reviewer": "independent-review-REV-R", "date": "2026-09-22", "notes": "Checked every node."}


def packet(review=ACCEPTED):
    data = {"roadmapId": "R", "protocol": "blueprint-v1", "status": "partial", "nodes": []}
    if review is not None:
        data["review"] = dict(review)
    return data


class Decide(unittest.TestCase):
    def test_work_without_an_accepted_review_waits(self):
        self.assertEqual(decide(PACKET, packet(None), JOBS, {})[0], "skip")
        self.assertEqual(decide(PACKET, packet(dict(ACCEPTED, status="needs_changes")), JOBS, {})[0], "skip")

    def test_an_accepted_review_by_the_finished_review_job_promotes(self):
        self.assertEqual(decide(PACKET, packet(), JOBS, {}), ("promote", "accepted by REV-R"))

    def test_the_review_job_must_be_finished_and_must_review_this_file(self):
        unfinished = [JOBS[0], dict(JOBS[1], state="pending")]
        self.assertEqual(decide(PACKET, packet(), unfinished, {})[0], "skip")
        elsewhere = [JOBS[0], dict(JOBS[1], after=["BP-OTHER"])]
        verdict, reason = decide(PACKET, packet(), elsewhere, {})
        self.assertEqual(verdict, "refuse")
        self.assertIn("REV-R does not review", reason)

    def test_a_verdict_must_name_its_review_job(self):
        verdict, reason = decide(PACKET, packet(dict(ACCEPTED, reviewer="me")), JOBS, {})
        self.assertEqual(verdict, "refuse")
        self.assertIn("independent-review-<job>", reason)

    def test_a_review_already_acted_on_is_not_acted_on_again(self):
        from promote import signature
        record = {"promoted": {PACKET: {"review": signature(ACCEPTED)}}}
        self.assertEqual(decide(PACKET, packet(), JOBS, record)[0], "skip")
        self.assertEqual(decide(PACKET, packet(dict(ACCEPTED, date="2026-09-30")), JOBS, record)[0], "promote")
        refused = {"refused": {PACKET: {"review": signature(ACCEPTED)}}}
        self.assertEqual(decide(PACKET, packet(), JOBS, refused)[0], "skip")


class Promote(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        bp = self.root / "research" / "blueprint"
        for name in ("packets", "readmes", "roadmaps", "links"):
            (bp / name).mkdir(parents=True)
        (self.root / "data").mkdir()
        (bp / "queue.json").write_text(json.dumps({"jobs": JOBS}))
        (bp / "packets" / "R.json").write_text(json.dumps(packet()))
        (bp / "readmes" / "R.md").write_text("# R\n")
        (self.root / "data" / "atlas.json").write_text(json.dumps({"roadmaps": [{"id": "R"}]}))

    def tearDown(self):
        self.folder.cleanup()

    def test_accepted_work_is_copied_into_data_with_its_document_and_recorded(self):
        summary = promote(self.root, validate=lambda: None, now="2026-09-22T10:00:00Z")
        self.assertEqual(summary["promoted"], [PACKET])
        self.assertEqual(json.loads((self.root / "data/blueprints/R.json").read_text())["roadmapId"], "R")
        self.assertEqual((self.root / "data/blueprints/R.md").read_text(), "# R\n")
        record = json.loads((self.root / "data/promotions.json").read_text())
        self.assertEqual(record["promoted"][PACKET]["to"], ["data/blueprints/R.json", "data/blueprints/R.md"])
        self.assertEqual(promote(self.root, validate=lambda: None)["promoted"], [])

    def test_work_that_breaks_the_atlas_is_refused_and_rolled_back(self):
        def broken():
            if (self.root / "data/blueprints/R.json").exists():
                raise ValueError("Invalid dependency: R:L1 -> R:L0")
        summary = promote(self.root, validate=broken, now="2026-09-22T10:00:00Z")
        self.assertEqual(summary["refused"], [(PACKET, "Invalid dependency: R:L1 -> R:L0")])
        self.assertFalse((self.root / "data/blueprints/R.json").exists())
        record = json.loads((self.root / "data/promotions.json").read_text())
        self.assertIn(PACKET, record["refused"])

    def test_nothing_is_tried_when_the_atlas_does_not_build_as_it_is(self):
        calls = []

        def broken():
            calls.append(1)
            raise ValueError("data/galaxies.json is broken")
        with self.assertRaises(ValueError):
            promote(self.root, validate=broken)
        self.assertEqual(len(calls), 1)
        self.assertFalse((self.root / "data/promotions.json").exists())

    def test_the_workers_are_told_on_their_issue(self):
        from promote import notices
        (self.root / "research/blueprint/issues.json").write_text(json.dumps({"BP-R": 41}))
        summary = {"promoted": [PACKET], "refused": [("research/blueprint/packets/Q.json", "Invalid dependency")], "waiting": []}
        jobs = JOBS + [{"id": "BP-Q", "outputs": ["research/blueprint/packets/Q.json"]}]
        said = notices(self.root, summary, jobs)
        self.assertEqual([number for number, _ in said], [41])
        self.assertIn("is now in the atlas", said[0][1])
        self.assertIn("#view=roadmap&id=R", said[0][1])

    def test_a_new_roadmap_goes_live_with_its_definition(self):
        (self.root / "data" / "atlas.json").write_text(json.dumps({"roadmaps": []}))
        verdict = promote(self.root, validate=lambda: None)
        self.assertEqual(verdict["refused"], [(PACKET, "R is a new roadmap, but research/blueprint/roadmaps/R.json is missing")])
        (self.root / "research/blueprint/roadmaps/R.json").write_text(json.dumps({"id": "R", "stages": []}))
        (self.root / "research/blueprint/packets/R.json").write_text(json.dumps(packet(dict(ACCEPTED, date="2026-09-23"))))
        self.assertEqual(promote(self.root, validate=lambda: None)["promoted"], [PACKET])
        self.assertTrue((self.root / "data/blueprints/roadmaps/R.json").exists())

    def test_an_accepted_restructuring_goes_live_with_its_report(self):
        jobs = [{"id": "RS-01", "kind": "restructure", "state": "done", "outputs": ["research/blueprint/restructure/RS-01.result.json"]},
                {"id": "REV-RS-01", "kind": "review", "state": "done", "after": ["RS-01"], "outputs": []}]
        (self.root / "research/blueprint/queue.json").write_text(json.dumps({"jobs": jobs}))
        (self.root / "research/blueprint/packets/R.json").unlink()
        folder = self.root / "research/blueprint/restructure"
        folder.mkdir()
        (folder / "RS-01.result.json").write_text(json.dumps({"family": "RS-01", "review": dict(ACCEPTED, reviewer="independent-review-REV-RS-01")}))
        (folder / "RS-01.md").write_text("Why.")
        self.assertEqual(promote(self.root, validate=lambda: None)["promoted"], ["research/blueprint/restructure/RS-01.result.json"])
        self.assertTrue((self.root / "data/restructure/RS-01.result.json").exists())
        self.assertEqual((self.root / "data/restructure/RS-01.md").read_text(), "Why.")

    def test_an_accepted_link_map_goes_to_the_links_the_atlas_merges(self):
        jobs = [{"id": "LINK-R", "kind": "link", "state": "done", "outputs": ["research/blueprint/links/R.json"]},
                {"id": "REV-LINK-R", "kind": "review", "state": "done", "after": ["LINK-R"], "outputs": []}]
        (self.root / "research/blueprint/queue.json").write_text(json.dumps({"jobs": jobs}))
        (self.root / "research/blueprint/packets/R.json").unlink()
        review = dict(ACCEPTED, reviewer="independent-review-REV-LINK-R")
        (self.root / "research/blueprint/links/R.json").write_text(json.dumps({"roadmapId": "R", "protocol": "links-v1", "links": [], "review": review}))
        self.assertEqual(promote(self.root, validate=lambda: None)["promoted"], ["research/blueprint/links/R.json"])
        self.assertTrue((self.root / "data/links/R.json").exists())


if __name__ == "__main__":
    unittest.main()
