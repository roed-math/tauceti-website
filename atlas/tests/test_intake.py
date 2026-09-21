"""Taking in workers' pull requests: which job a submission is for, and what an
automatic merge must refuse."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
from intake import auto_refusals, claimants, file_problems, issue_for, job_for, own_files  # noqa: E402

RS = "research/blueprint/restructure/"
JOBS = [{"id": "RS-28", "kind": "restructure", "state": "pending", "after": [],
         "outputs": [RS + "RS-28.result.json", RS + "RS-28.md"]},
        {"id": "REV-RS-28", "kind": "review", "state": "pending", "after": ["RS-28"],
         "outputs": ["research/blueprint/reviews/REV-RS-28.md"]},
        {"id": "PLANETS-01", "kind": "naming", "state": "done", "after": [],
         "outputs": ["research/expansion/naming/PLANETS-01.result.json"]}]
BY_ID = {job["id"]: job for job in JOBS}


class Job(unittest.TestCase):
    def test_the_job_is_the_one_whose_deliverables_the_pull_request_adds(self):
        files = [RS + "RS-28.md", RS + "RS-28.result.json", "research/blueprint/handoff/RS-28.md"]
        self.assertEqual(job_for(files, "Restructure higher local fields as Class field theory, Part II", JOBS)["id"], "RS-28")

    def test_a_checkpoint_with_only_its_handoff_note_names_its_job(self):
        self.assertEqual(job_for(["research/blueprint/handoff/RS-28.md"], "", JOBS)["id"], "RS-28")

    def test_the_description_names_the_job_when_the_files_do_not(self):
        self.assertEqual(job_for(["research/blueprint/links/Other.json"], "Work for REV-RS-28.", JOBS)["id"], "REV-RS-28")
        self.assertIsNone(job_for(["research/blueprint/links/Other.json"], "No job named.", JOBS))

    def test_the_issue_comes_from_the_mapping_before_the_description(self):
        self.assertEqual(issue_for(BY_ID["RS-28"], {"RS-28": 856}, "Refs #900 and #3"), 856)
        self.assertEqual(issue_for(None, {}, "Agent: Codex. Refs #858."), 858)
        self.assertIsNone(issue_for(None, {}, "See PR #12."))


class AutomaticMerge(unittest.TestCase):
    def test_a_submission_touching_only_its_job_is_accepted(self):
        files = [RS + "RS-28.md", RS + "RS-28.result.json", "research/blueprint/handoff/RS-28.md"]
        self.assertEqual(auto_refusals(BY_ID["RS-28"], files, False, set(), set()), [])

    def test_the_job_must_be_known(self):
        self.assertIn("no job found for the submission", auto_refusals(None, [RS + "RS-28.md"], False, set(), set()))

    def test_another_jobs_files_are_left_to_the_maintainer(self):
        found = auto_refusals(BY_ID["RS-28"], [RS + "RS-28.md", "research/blueprint/reviews/REV-RS-28.md"], False, set(), set())
        self.assertIn("research/blueprint/reviews/REV-RS-28.md is not a deliverable of RS-28", found)

    def test_a_finished_job_is_not_overwritten(self):
        found = auto_refusals(BY_ID["PLANETS-01"], ["research/expansion/naming/PLANETS-01.result.json"], False, set(), set())
        self.assertIn("PLANETS-01 is already done", found)

    def test_a_draft_waits(self):
        self.assertIn("the pull request is a draft", auto_refusals(BY_ID["RS-28"], [RS + "RS-28.md"], True, set(), set()))

    def test_nobody_reviews_their_own_work(self):
        review = ["research/blueprint/reviews/REV-RS-28.md"]
        self.assertIn("the reviewer codex-a71f92 also did RS-28",
                      auto_refusals(BY_ID["REV-RS-28"], review, False, {"codex-a71f92"}, {"codex-a71f92", "gpt-1"}))
        self.assertEqual(auto_refusals(BY_ID["REV-RS-28"], review, False, {"astra-7c41e9"}, {"codex-a71f92"}), [])


class Files(unittest.TestCase):
    def test_every_deliverable_of_a_live_job_may_be_submitted(self):
        jobs = json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]
        refused = [path for job in jobs if job.get("state") in ("pending", "external")
                   for path in sorted(own_files(job)) if file_problems(path, "{}")]
        self.assertEqual(refused, [])

    def test_code_and_local_paths_are_refused(self):
        self.assertEqual(file_problems("scripts/build.py", ""), ["file outside swarm output paths: scripts/build.py"])
        self.assertEqual(file_problems(RS + "RS-28.md", "See /Users/someone/notes."), [f"local path in {RS}RS-28.md"])
        self.assertTrue(file_problems(RS + "RS-28.result.json", "{not json")[0].startswith("invalid JSON"))


class Claimants(unittest.TestCase):
    def test_sessions_come_from_the_claim_bot_replies(self):
        comments = [{"user": {"login": "github-actions[bot]"},
                     "body": "Claimed for Codex — codex-c83e7a by @someone (comment 1). Local swarm workers will skip this job."},
                    {"user": {"login": "github-actions[bot]"}, "body": "Released by @someone. The job is available again."},
                    {"user": {"login": "someone"}, "body": "Claimed for Codex — forged-1 by @someone"},
                    {"user": {"login": "github-actions[bot]"},
                     "body": "Claimed for ChatGPT Pro — gpt-20260921-c74f2a by @someone (comment 2)."}]
        self.assertEqual(claimants(comments), {"codex-c83e7a", "gpt-20260921-c74f2a"})


if __name__ == "__main__":
    unittest.main()
