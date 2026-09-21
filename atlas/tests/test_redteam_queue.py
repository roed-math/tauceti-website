"""Red-team jobs in the queue (research/blueprint/make_queue.py, PROTOCOL.md section 17)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
import make_queue  # noqa: E402


class AreaParts(unittest.TestCase):
    def test_a_small_area_is_one_part(self):
        members = [f"R{i}" for i in range(8)]
        self.assertEqual(make_queue.area_parts(members, []), [members])

    def test_a_large_area_splits_into_parts_that_keep_linked_roadmaps_together(self):
        first, second = [f"A{i}" for i in range(8)], [f"B{i}" for i in range(7)]
        links = [(a, b) for a in first for b in first if a < b] + [(a, b) for a in second for b in second if a < b] + [("A0", "B0")]
        self.assertEqual(make_queue.area_parts(sorted(first + second), links), [first, second])

    def test_parts_are_balanced_and_cover_the_area_once(self):
        members = [f"R{i:02d}" for i in range(23)]
        parts = make_queue.area_parts(members, [])
        self.assertEqual(sorted(map(len, parts)), [7, 8, 8])
        self.assertEqual(sorted(r for part in parts for r in part), members)


class Prompts(unittest.TestCase):
    def test_jobs_that_check_or_extract_are_not_told_to_continue_a_decomposition(self):
        for template in (make_queue.PAPER_TEMPLATE, make_queue.REDTEAM_TEMPLATE, make_queue.REDTEAM_AREA_TEMPLATE, make_queue.FIX_TEMPLATE):
            self.assertNotIn("Build on it: keep its node ids", template)
            self.assertIn("- Library baseline (what exists today):", template)


class Queue(unittest.TestCase):
    def test_a_verifier_is_independent_of_the_red_team_and_of_the_work_it_attacked(self):
        jobs = {j["id"]: j for j in json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]}
        verifications = [j for jid, j in jobs.items() if jid.startswith("REV-RT-")]
        self.assertTrue(verifications)
        for verification in verifications:
            red = jobs[verification["id"][4:]]
            self.assertEqual(set(verification.get("independentOf") or []), {red["id"], *red["independentOf"]}, verification["id"])


class Reviews(unittest.TestCase):
    def test_a_review_may_write_its_verdict_into_the_files_it_reviews(self):
        # The verdict goes into the reviewed file (PROTOCOL.md section 8), and the
        # intake merges only a job's own outputs.
        jobs = {j["id"]: j for j in json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]}
        checked = 0
        for job in jobs.values():
            live = job["kind"] == "review" and job.get("state") != "superseded"
            target = jobs.get((job.get("after") or [None])[0]) if live else None
            if target and target["kind"] in ("blueprint", "design", "link", "restructure"):
                reviewed = {path for path in target["outputs"] if path.endswith(".json")}
                self.assertLessEqual(reviewed, set(job["outputs"]), job["id"])
                checked += 1
        self.assertGreater(checked, 300)


if __name__ == "__main__":
    unittest.main()
