"""Taking in workers' pull requests: which job a submission is for, and what an
automatic merge must refuse."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
from intake import (auto_refusals, claimants, file_problems, follow_up, issue_for, job_for, latest_checks, mark_state,  # noqa: E402
                    own_files, review_started, reviews_of, submitter, swarm_checked)

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

    def test_its_own_worker_may_correct_a_finished_job_before_its_review_starts(self):
        files = ["research/expansion/naming/PLANETS-01.result.json"]
        self.assertEqual(auto_refusals(BY_ID["PLANETS-01"], files, False, set(), set(), follow_up=True), [])
        self.assertEqual(auto_refusals(BY_ID["RS-28"], [RS + "RS-28.md"], False, set(), set(), already_complete=True, follow_up=True), [])
        # A follow-up still touches only the job's own files.
        self.assertIn("research/blueprint/reviews/REV-RS-28.md is not a deliverable of PLANETS-01",
                      auto_refusals(BY_ID["PLANETS-01"], files + ["research/blueprint/reviews/REV-RS-28.md"], False, set(), set(), follow_up=True))

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


class FollowUp(unittest.TestCase):
    """A finished job's own worker may still correct it while nobody has started its review."""

    def test_the_branch_is_named_after_a_session_that_claimed_the_job(self):
        self.assertTrue(follow_up("cc-fb70e5-paper-bsw22-fix", {"cc-fb70e5"}, False))
        self.assertTrue(follow_up("g6-astra-20260921-r7c4", {"g6-astra-20260921-r7c4"}, False))
        self.assertFalse(follow_up("codex-a71f92-paper-fix", {"cc-fb70e5"}, False))
        self.assertFalse(follow_up("cc-fb70e5x-fix", {"cc-fb70e5"}, False))

    def test_a_session_too_short_to_tell_workers_apart_does_not_count(self):
        self.assertFalse(follow_up("cc-anything", {"cc"}, False))

    def test_not_once_the_review_has_started(self):
        self.assertFalse(follow_up("cc-fb70e5-paper-bsw22-fix", {"cc-fb70e5"}, True))

    def test_the_reviews_of_a_job_are_those_that_check_it(self):
        self.assertEqual([job["id"] for job in reviews_of(BY_ID["RS-28"], JOBS)], ["REV-RS-28"])
        self.assertEqual(reviews_of(BY_ID["PLANETS-01"], JOBS), [])

    def test_a_review_has_started_once_claimed_or_past_pending(self):
        self.assertFalse(review_started(BY_ID["REV-RS-28"], ["swarm", "state:available"]))
        self.assertFalse(review_started(BY_ID["REV-RS-28"], ["swarm", "state:blocked"]))
        self.assertTrue(review_started(BY_ID["REV-RS-28"], ["swarm", "state:claimed"]))
        self.assertTrue(review_started(dict(BY_ID["REV-RS-28"], state="external"), ["swarm"]))
        self.assertTrue(review_started(dict(BY_ID["REV-RS-28"], state="done"), []))


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


class Submitter(unittest.TestCase):
    """Which session actually sent this pull request.

    A job claimed, refused and claimed again by somebody else carries both sessions
    in its comments forever. Judging independence on all of them fails the second,
    independent worker for the first one's conflict.
    """

    BOT = {"login": "github-actions[bot]"}
    COMMENTS = [
        {"user": BOT, "body": "Claimed for Claude Code — cc-7b31c4 by @owner (comment 1)."},
        {"user": BOT, "body": "Submitted in #2391. The job is nobody else's to claim while the pull request is open."},
        {"user": BOT, "body": "Swarm intake: left for the maintainer, because the reviewer cc-7b31c4 also did PAPER-X."},
        {"user": BOT, "body": "Claimed for Claude Code — cc-38267a by @owner (comment 2)."},
        {"user": BOT, "body": "Submitted in #2790. The job is nobody else's to claim while the pull request is open."},
    ]

    def test_the_session_is_the_one_claiming_before_that_submission(self):
        self.assertEqual(submitter(self.COMMENTS, 2790), {"cc-38267a"})
        self.assertEqual(submitter(self.COMMENTS, 2391), {"cc-7b31c4"})

    def test_an_unannounced_submission_falls_back_to_the_latest_claim(self):
        self.assertEqual(submitter(self.COMMENTS, 9999), {"cc-38267a"})

    def test_no_claim_at_all_names_nobody(self):
        self.assertEqual(submitter([{"user": self.BOT, "body": "Released by @owner."}], 1), set())

    def test_a_forged_claim_outside_the_bot_is_ignored(self):
        comments = [{"user": {"login": "someone"}, "body": "Claimed for Codex — forged-1 by @someone"},
                    {"user": self.BOT, "body": "Submitted in #7."}]
        self.assertEqual(submitter(comments, 7), set())


class IndependenceOfTheSubmitter(unittest.TestCase):
    def test_an_earlier_conflicted_claim_does_not_fail_a_later_independent_one(self):
        # The reviewer here is cc-38267a; cc-7b31c4 did the paper and its refused review.
        found = auto_refusals(BY_ID["REV-RS-28"], ["research/blueprint/reviews/REV-RS-28.md"], False,
                              {"cc-38267a"}, {"cc-7b31c4"})
        self.assertEqual(found, [])

    def test_the_submitting_session_having_done_the_work_still_fails(self):
        found = auto_refusals(BY_ID["REV-RS-28"], ["research/blueprint/reviews/REV-RS-28.md"], False,
                              {"cc-7b31c4"}, {"cc-7b31c4"})
        self.assertEqual(found, ["the reviewer cc-7b31c4 also did RS-28"])


if __name__ == "__main__":
    unittest.main()
