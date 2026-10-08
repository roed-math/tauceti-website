"""Roadmap packages: a complete roadmap written up in Tau Ceti's own form (research/blueprint/PROTOCOL.md section 20)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
sys.path.insert(0, str(ROOT / "scripts"))
import intake  # noqa: E402
import issues  # noqa: E402
import make_queue  # noqa: E402
import promote  # noqa: E402


def packet(status, coverage):
    return {"review": {"status": status}, "coverage": [{"stageId": sid, "status": st} for sid, st in coverage]}


class Complete(unittest.TestCase):
    def test_every_layer_planned_in_an_accepted_packet_and_assembled(self):
        stages = {"R:L1", "R:L2"}
        whole = {"R": packet("accepted", [("R:L1", "planned"), ("R:L2", "partial")]),
                 "R--L2": packet("accepted", [("R:L2", "source_decomposed")])}
        self.assertTrue(make_queue.roadmap_complete(stages, whole, "done"))
        self.assertTrue(make_queue.roadmap_complete(stages, whole, None))
        self.assertFalse(make_queue.roadmap_complete(stages, whole, "pending"), "a pending assembly")
        self.assertFalse(make_queue.roadmap_complete(stages, {"R": whole["R"]}, None), "L2 only partial")
        sent_back = dict(whole, **{"R--L2": packet("needs_changes", [("R:L2", "planned")])})
        self.assertFalse(make_queue.roadmap_complete(stages, sent_back, None), "L2 planned only in a packet sent back")

    def test_a_new_roadmap_is_measured_by_its_packets_coverage(self):
        self.assertTrue(make_queue.roadmap_complete(set(), {"N": packet("accepted", [("N:A", "planned"), ("N:B", "closed")])}, None))
        self.assertFalse(make_queue.roadmap_complete(set(), {"N": packet("accepted", [("N:A", "planned"), ("N:B", "partial")])}, None))
        self.assertFalse(make_queue.roadmap_complete(set(), {}, None))


class Issues(unittest.TestCase):
    def test_package_jobs_and_reviews_are_titled_and_focused(self):
        roadmaps = {"R": {"title": "A roadmap"}}
        job = {"id": "PKG-R", "kind": "package", "roadmapIds": ["R"], "after": []}
        review = {"id": "REV-PKG-R", "kind": "review", "roadmapIds": ["R"], "after": ["PKG-R"]}
        self.assertEqual(issues._title(job, roadmaps), "[Roadmap package] A roadmap")
        self.assertEqual(issues._title(review, roadmaps), "[Review] Roadmap package: A roadmap")
        self.assertTrue(issues.is_focus(job, {"R"}) and issues.is_focus(review, {"R"}))

    def test_a_package_pull_request_may_change_only_its_four_files(self):
        for name in ("README.md", "Suggested.lean", "metadata.toml", "review.json"):
            self.assertTrue(intake.ALLOWED.match(f"research/blueprint/packages/R/{name}"), name)
        self.assertFalse(intake.ALLOWED.match("research/blueprint/packages/R/notes.txt"))
        self.assertFalse(intake.ALLOWED.match("roadmaps/R/README.md"), "only promotion writes roadmaps/")


class Promotion(unittest.TestCase):
    def test_an_accepted_package_is_published_as_upstream_lays_out_a_roadmap(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pkg = root / "research" / "blueprint" / "packages" / "R"
            pkg.mkdir(parents=True)
            for name in ("README.md", "Suggested.lean", "metadata.toml"):
                (pkg / name).write_text("x")
            path = "research/blueprint/packages/R/review.json"
            files, problem = promote.destinations(root, path, {}, set())
            self.assertIsNone(problem)
            self.assertEqual(sorted(dest for _, dest in files), ["roadmaps/R/README.md", "roadmaps/R/Suggested.lean", "roadmaps/R/metadata.toml"])
            (pkg / "Suggested.lean").unlink()
            self.assertIn("lacks", promote.destinations(root, path, {}, set())[1])

    def test_its_review_must_review_the_job_that_wrote_the_readme(self):
        path = "research/blueprint/packages/R/review.json"
        files = ["research/blueprint/packages/R/README.md", "research/blueprint/packages/R/Suggested.lean"]
        jobs = [{"id": "PKG-R", "kind": "package", "outputs": files, "state": "done"},
                {"id": "REV-PKG-R", "kind": "review", "after": ["PKG-R"], "outputs": [path] + files, "state": "done"}]
        data = {"review": {"status": "accepted", "reviewer": "independent-review-REV-PKG-R", "date": "2026-10-08"}}
        self.assertEqual(promote.decide(path, data, jobs, {})[0], "promote")
        data["review"]["status"] = "needs_changes"
        self.assertEqual(promote.decide(path, data, jobs, {})[0], "skip")


if __name__ == "__main__":
    unittest.main()
