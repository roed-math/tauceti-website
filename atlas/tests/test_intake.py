"""Taking in workers' pull requests: which job a submission is for, and what an
automatic merge must refuse."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
from intake import auto_refusals, claimants, file_problems, issue_for, job_for, latest_checks, mark_state, own_files, swarm_checked  # noqa: E402

RS = "research/blueprint/restructure/"
JOBS = [{"id": "RS-28", "kind": "restructure", "state": "pending", "after": [],
         "outputs": [RS + "RS-28.result.json", RS + "RS-28.md"]},
        {"id": "REV-RS-28", "kind": "review", "state": "pending", "after": ["RS-28"],
         "outputs": ["research/blueprint/reviews/REV-RS-28.md"]},
        {"id": "PLANETS-01", "kind": "naming", "state": "done", "after": [],
         "outputs": ["research/expansion/naming/PLANETS-01.result.json"]}]
BY_ID = {job["id"]: job for job in JOBS}


def rollup(*runs):
    return {"statusCheckRollup": [{"__typename": "CheckRun", "workflowName": workflow, "name": name, "status": "COMPLETED",
                                   "conclusion": result, "startedAt": f"2026-09-21T{time}:00Z"}
                                  for workflow, name, result, time in runs]}


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

    def test_a_second_submission_for_a_finished_job_is_left_to_the_maintainer(self):
        # Two workers did the same job: the first merge completed it on main.
        found = auto_refusals(BY_ID["RS-28"], [RS + "RS-28.md"], False, set(), set(), already_complete=True)
        self.assertIn("RS-28's deliverables on main are already complete", found)

    def test_only_pull_requests_whose_submission_check_passed_are_swept(self):
        self.assertTrue(swarm_checked(rollup(("Swarm submission check", "check", "SUCCESS", "13:12"))))
        self.assertFalse(swarm_checked(rollup(("Swarm submission check", "check", "FAILURE", "13:12"))))
        self.assertFalse(swarm_checked(rollup(("Some other workflow", "check", "SUCCESS", "13:12"))))
        self.assertFalse(swarm_checked(rollup()))

    def test_only_the_latest_run_of_each_check_counts(self):
        # A pull request run again on the same commit keeps its earlier runs in the rollup.
        pr = rollup(("Swarm submission check", "check", "FAILURE", "13:11"), ("Swarm submission check", "check", "SUCCESS", "13:12"),
                    ("Swarm submissions", "mark", "SUCCESS", "13:11"), ("Swarm submissions", "mark", "SUCCESS", "13:12"))
        self.assertEqual([(c["workflowName"], c["conclusion"]) for c in latest_checks(pr["statusCheckRollup"])],
                         [("Swarm submission check", "SUCCESS"), ("Swarm submissions", "SUCCESS")])
        self.assertTrue(swarm_checked(pr))
        broken = rollup(("Swarm submission check", "check", "SUCCESS", "13:11"), ("Swarm submission check", "check", "FAILURE", "13:12"))
        self.assertFalse(swarm_checked(broken))

    def test_a_red_teamer_attacks_only_work_they_neither_did_nor_reviewed(self):
        red = {"id": "RT-AUDIT-07", "kind": "redteam", "state": "pending", "after": [], "independentOf": ["AUDIT-07", "REV-AUDIT-07"],
               "outputs": ["research/blueprint/redteam/RT-AUDIT-07.result.json"]}
        self.assertIn("the red teamer codex-1 also did AUDIT-07 or REV-AUDIT-07",
                      auto_refusals(red, ["research/blueprint/redteam/RT-AUDIT-07.result.json"], False, {"codex-1"}, {"codex-1"}))

    def test_nobody_reviews_their_own_work(self):
        review = ["research/blueprint/reviews/REV-RS-28.md"]
        self.assertIn("the reviewer codex-a71f92 also did RS-28",
                      auto_refusals(BY_ID["REV-RS-28"], review, False, {"codex-a71f92"}, {"codex-a71f92", "gpt-1"}))
        self.assertEqual(auto_refusals(BY_ID["REV-RS-28"], review, False, {"astra-7c41e9"}, {"codex-a71f92"}), [])


class Marking(unittest.TestCase):
    """mark_state(event, merged, pull request's state now, issue labels, job done) -> label to set."""

    def test_opening_a_pull_request_submits_the_job(self):
        self.assertEqual(mark_state("opened", False, "OPEN", ["swarm", "state:claimed"], False), "state:submitted")
        self.assertEqual(mark_state("reopened", False, "OPEN", ["swarm", "state:available"], False), "state:submitted")

    def test_closing_it_unmerged_releases_the_job(self):
        self.assertEqual(mark_state("closed", False, "CLOSED", ["swarm", "state:submitted"], False), "state:available")

    def test_a_merged_or_finished_job_is_not_released(self):
        self.assertIsNone(mark_state("closed", True, "MERGED", ["swarm", "state:submitted"], False))
        self.assertIsNone(mark_state("closed", False, "CLOSED", ["swarm", "state:submitted"], True))

    def test_an_event_overtaken_by_a_later_one_changes_nothing(self):
        # Closed and reopened at once: each run acts only if the pull request is still as its event left it.
        self.assertIsNone(mark_state("closed", False, "OPEN", ["swarm", "state:submitted"], False))
        self.assertIsNone(mark_state("reopened", False, "CLOSED", ["swarm", "state:available"], False))

    def test_a_blocked_or_running_job_is_left_alone(self):
        self.assertIsNone(mark_state("opened", False, "OPEN", ["swarm", "state:blocked"], False))
        self.assertIsNone(mark_state("opened", False, "OPEN", ["swarm", "state:running"], False))


class Files(unittest.TestCase):
    def test_every_deliverable_of_a_live_job_may_be_submitted(self):
        jobs = json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]
        refused = [path for job in jobs if job.get("state") in ("pending", "external")
                   for path in sorted(own_files(job)) if file_problems(path, "{}")]
        self.assertEqual(refused, [])

    def test_errata_files_are_swarm_output(self):
        self.assertEqual(file_problems("research/blueprint/errata/PAPER-FU-24.json", '{"paper": "PAPER-FU-24"}'), [])
        self.assertEqual(file_problems("research/blueprint/errata/PAPER-FU-24.md", "What the paper says."), [])

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
