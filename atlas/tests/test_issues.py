"""GitHub issue rendering for the blueprint queue: states and public text."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
from issues import body, deliverables_complete, labels_for, publicize, refresh_payload, title, transition  # noqa: E402


def job(jid, state="pending", after=(), kind="review"):
    return {"id": jid, "kind": kind, "priority": 2, "state": state, "after": list(after), "roadmapIds": []}


class States(unittest.TestCase):
    def test_a_job_waiting_for_unfinished_work_is_blocked_not_available(self):
        blueprint = job("BP-X", kind="blueprint")
        review = job("REV-X", after=["BP-X"])
        by_id = {"BP-X": blueprint, "REV-X": review}
        self.assertIn("state:blocked", labels_for(review, {}, by_id))
        self.assertNotIn("state:available", labels_for(review, {}, by_id))
        blueprint["state"] = "done"
        self.assertIn("state:available", labels_for(review, {}, by_id))

    def test_a_job_without_prerequisites_is_available(self):
        blueprint = job("BP-X", kind="blueprint")
        self.assertIn("state:available", labels_for(blueprint, {}, {"BP-X": blueprint}))


class RefreshPayload(unittest.TestCase):
    def test_a_superseded_job_closes_its_issue_as_not_planned_and_says_why(self):
        gone = job("BP-X", state="superseded", kind="blueprint")
        gone["note"] = "Planned upstream."
        payload = refresh_payload(gone, "Old body.", "Body.")
        self.assertEqual(payload["state"], "closed")
        self.assertEqual(payload["state_reason"], "not_planned")
        self.assertTrue(payload["body"].startswith("**Superseded.** Planned upstream."))
        self.assertTrue(payload["body"].endswith("Body."))

    def test_a_refresh_rewrites_the_body_and_never_the_state(self):
        # Claims live on GitHub until a sync brings them into the queue, so a state
        # computed from the queue would hand a claimed job to everyone again.
        live = job("BP-Y", kind="blueprint")
        self.assertEqual(refresh_payload(live, "Old body.", "Body."), {"body": "Body."})

    def test_an_issue_already_up_to_date_is_left_alone(self):
        self.assertIsNone(refresh_payload(job("BP-Y", kind="blueprint"), "Body.", "Body."))


class Sync(unittest.TestCase):
    """transition(job, labels, complete, ready) -> (queue state, state label)."""

    def test_a_claim_on_github_reaches_the_queue(self):
        self.assertEqual(transition(job("BP-X", kind="blueprint"), ["swarm", "state:claimed"], False, True),
                         ("external", "state:claimed"))

    def test_a_submitted_job_is_nobody_elses_to_claim(self):
        # A pull request is open; the issue says so until the intake merges or releases it.
        for state in ("pending", "external"):
            self.assertEqual(transition(job("RS-01", state=state, kind="restructure"), ["state:submitted"], False, True),
                             ("external", "state:submitted"))

    def test_deliverables_on_main_finish_the_job_whoever_held_the_claim(self):
        # A worker may release the claim once the pull request is open.
        self.assertEqual(transition(job("RS-01", kind="restructure"), ["state:available"], True, True),
                         ("done", "state:done"))
        self.assertEqual(transition(job("REV-RS-01", state="external"), ["state:claimed"], True, True),
                         ("done", "state:done"))

    def test_a_finished_blueprint_waits_for_promotion_before_it_closes(self):
        self.assertEqual(transition(job("BP-X", state="external", kind="blueprint"), ["state:submitted"], True, True),
                         ("done", "state:submitted"))
        integrated = dict(job("BP-X", state="external", kind="blueprint"), integrated=True)
        self.assertEqual(transition(integrated, ["state:submitted"], True, True), ("done", "state:done"))

    def test_a_released_claim_makes_the_job_available_again(self):
        self.assertEqual(transition(job("BP-X", state="external", kind="blueprint"), ["state:available"], False, True),
                         ("pending", "state:available"))
        self.assertEqual(transition(job("REV-X", state="external"), ["state:available"], False, False),
                         ("pending", "state:blocked"))

    def test_local_work_is_left_to_the_local_swarm(self):
        self.assertEqual(transition(job("BP-X", state="running", kind="blueprint"), ["state:available"], True, True),
                         ("running", "state:running"))

    def test_a_superseded_job_has_no_state_label_to_set(self):
        self.assertEqual(transition(job("BP-X", state="superseded", kind="blueprint"), ["state:available"], False, True),
                         ("superseded", None))


class Deliverables(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        for name in ("packets", "readmes", "restructure", "reviews", "redteam"):
            (self.root / name).mkdir()

    def tearDown(self):
        self.folder.cleanup()

    def write(self, name, content):
        (self.root / name).write_text(content if isinstance(content, str) else json.dumps(content))

    def test_every_output_must_exist(self):
        proposal = {"id": "RS-01", "kind": "restructure", "outputs": ["restructure/RS-01.result.json", "restructure/RS-01.md"]}
        self.write("restructure/RS-01.result.json", {"family": "RS-01"})
        self.assertFalse(deliverables_complete(proposal, self.root))
        self.write("restructure/RS-01.md", "Reasons.")
        self.assertTrue(deliverables_complete(proposal, self.root))

    def test_a_planning_job_is_finished_when_every_layer_in_scope_is_decomposed(self):
        # Coverage `source_decomposed`: every definition and theorem of the sources is outlined.
        plan = {"id": "BP-R", "kind": "blueprint", "scope": ["R:L0", "R:L1"], "outputs": ["packets/R.json", "readmes/R.md"]}
        self.write("readmes/R.md", "The roadmap document.")

        def packet(*statuses):
            self.write("packets/R.json", {"status": "partial", "coverage": [
                {"stageId": f"R:L{i}", "status": status} for i, status in enumerate(statuses)]})
        packet("source_decomposed", "partial")
        self.assertFalse(deliverables_complete(plan, self.root))
        packet("source_decomposed")
        self.assertFalse(deliverables_complete(plan, self.root))
        packet("source_decomposed", "closed")
        self.assertTrue(deliverables_complete(plan, self.root))

    def test_a_planning_job_is_finished_by_a_complete_pass_or_planned_stages(self):
        # PROTOCOL.md section 0: a pass ends at the node budget, or when every stage is planned.
        plan = {"id": "BP-R", "kind": "blueprint", "scope": ["R:L0", "R:L1"], "outputs": ["packets/R.json", "readmes/R.md"]}
        self.write("readmes/R.md", "The roadmap document.")
        self.write("packets/R.json", {"status": "partial", "coverage": [
            {"stageId": "R:L0", "status": "planned"}, {"stageId": "R:L1", "status": "partial"}]})
        self.assertFalse(deliverables_complete(plan, self.root))
        self.write("packets/R.json", {"status": "partial", "coverage": [
            {"stageId": "R:L0", "status": "planned"}, {"stageId": "R:L1", "status": "closed"}]})
        self.assertTrue(deliverables_complete(plan, self.root))
        self.write("packets/R.json", {"status": "complete", "coverage": [
            {"stageId": "R:L0", "status": "partial"}, {"stageId": "R:L1", "status": "not_read"}]})
        self.assertTrue(deliverables_complete(plan, self.root))

    def test_a_link_map_is_finished_when_it_says_so(self):
        links = {"id": "LINK-R", "kind": "link", "outputs": ["packets/links-R.json"]}
        self.write("packets/links-R.json", {"status": "partial"})
        self.assertFalse(deliverables_complete(links, self.root))
        self.write("packets/links-R.json", {"status": "complete"})
        self.assertTrue(deliverables_complete(links, self.root))

    def test_an_errata_job_is_finished_when_every_mistake_is_recorded_in_full(self):
        job = {"id": "ERRATA-PAPER-X", "kind": "errata", "outputs": ["packets/PAPER-X.errata.json", "packets/PAPER-X.errata.md"]}
        self.write("packets/PAPER-X.errata.md", "Report.")
        self.assertFalse(deliverables_complete(job, self.root))
        self.write("packets/PAPER-X.errata.json", {"paper": "PAPER-X", "sourceIssues": [{"id": "S1", "finding": "an older form"}]})
        self.assertFalse(deliverables_complete(job, self.root))
        self.write("packets/PAPER-X.errata.json", {"paper": "PAPER-X", "sourceIssues": []})
        self.assertTrue(deliverables_complete(job, self.root))

    def test_a_red_team_is_finished_when_its_result_says_so(self):
        attack = {"id": "RT-AUDIT-01", "kind": "redteam", "outputs": ["packets/RT-AUDIT-01.result.json", "packets/RT-AUDIT-01.md"]}
        self.write("packets/RT-AUDIT-01.md", "Report.")
        self.write("packets/RT-AUDIT-01.result.json", {"status": "partial"})
        self.assertFalse(deliverables_complete(attack, self.root))
        self.write("packets/RT-AUDIT-01.result.json", {"status": "complete"})
        self.assertTrue(deliverables_complete(attack, self.root))


    def test_a_blueprint_review_is_finished_only_when_the_packet_records_its_verdict(self):
        # A partial review checkpoint writes its report but records no verdict.
        review = {"id": "REV-R", "kind": "review", "after": ["BP-R"], "outputs": ["reviews/REV-R.md", "packets/R.json"]}
        self.write("reviews/REV-R.md", "Partial review; not accepted, and not a completed review job.")
        self.write("packets/R.json", {"status": "closed"})
        self.assertFalse(deliverables_complete(review, self.root))
        self.write("packets/R.json", {"status": "closed", "review": {"status": "accepted", "reviewer": "independent-review-REV-OTHER"}})
        self.assertFalse(deliverables_complete(review, self.root))
        self.write("packets/R.json", {"status": "closed", "review": {"status": "pending", "reviewer": "independent-review-REV-R"}})
        self.assertFalse(deliverables_complete(review, self.root))
        self.write("packets/R.json", {"status": "closed", "review": {"status": "needs_changes", "reviewer": "independent-review-REV-R"}})
        self.assertTrue(deliverables_complete(review, self.root))

    def test_a_fix_review_is_finished_only_when_every_file_it_reviews_records_its_verdict(self):
        (self.root / "links").mkdir()
        review = {"id": "REV-FIX-RT-AREA-x", "kind": "review", "after": ["FIX-RT-AREA-x"],
                  "outputs": ["reviews/REV-FIX-RT-AREA-x.md", "packets/R.json", "links/L.json"]}
        self.write("reviews/REV-FIX-RT-AREA-x.md", "Report.")
        mine = {"status": "accepted", "reviewer": "independent-review-REV-FIX-RT-AREA-x"}
        self.write("packets/R.json", {"review": mine})
        self.write("links/L.json", {"review": {"status": "accepted", "reviewer": "independent-review-REV-LINK-L"}})
        self.assertFalse(deliverables_complete(review, self.root))
        self.write("links/L.json", {"review": dict(mine, status="needs_changes")})
        self.assertTrue(deliverables_complete(review, self.root))

    def test_a_red_team_verification_is_finished_when_every_finding_has_a_verdict(self):
        verify = {"id": "REV-RT-X", "kind": "review", "after": ["RT-X"], "outputs": ["redteam/RT-X.review.json", "reviews/REV-RT-X.md"]}
        self.write("reviews/REV-RT-X.md", "Report.")
        self.write("redteam/RT-X.result.json", {"status": "complete", "findings": [{"id": "RT-X/1"}, {"id": "RT-X/2"}]})
        self.write("redteam/RT-X.review.json", {"redteam": "RT-X", "findings": [{"finding": "RT-X/1", "verdict": "confirmed"}]})
        self.assertFalse(deliverables_complete(verify, self.root))
        self.write("redteam/RT-X.review.json", {"redteam": "RT-X", "findings": [
            {"finding": "RT-X/1", "verdict": "confirmed"}, {"finding": "RT-X/2", "verdict": "rejected"}]})
        self.assertTrue(deliverables_complete(verify, self.root))

    def test_other_reviews_still_finish_when_their_outputs_exist(self):
        review = {"id": "REV-SRC-R", "kind": "review", "after": ["SRC-R"], "outputs": ["reviews/REV-SRC-R.md", "packets/R.json"]}
        self.write("reviews/REV-SRC-R.md", "Verdict: accepted")
        self.write("packets/R.json", {"status": "partial"})
        self.assertTrue(deliverables_complete(review, self.root))

class RedTeamText(unittest.TestCase):
    def test_an_area_red_team_looks_for_what_is_missing_and_a_job_red_team_attacks_accepted_work(self):
        area = {"id": "RT-AREA-padic-1", "kind": "redteam", "priority": 2, "name": "area: p-adic geometry, part 1 of 3", "roadmapIds": [], "after": []}
        attack = dict(area, id="RT-AUDIT-01", name="library audit AUDIT-01")
        self.assertIn("What the area is missing", body(area, [area], {}, {}))
        self.assertNotIn("An attack on accepted work", body(area, [area], {}, {}))
        self.assertIn("An attack on accepted work", body(attack, [attack], {}, {}))
        self.assertEqual(title(area, {}), "[Red team] area: p-adic geometry, part 1 of 3")

    def test_an_errata_issue_says_what_it_records(self):
        job = {"id": "ERRATA-PAPER-X", "kind": "errata", "priority": 1, "name": "Fu (2024): Bianchi multiplicities", "roadmapIds": [], "after": []}
        self.assertEqual(title(job, {}), "[Errata] Fu (2024): Bianchi multiplicities")
        self.assertIn("Every mistake in the published source", body(job, [job], {}, {}))

    def test_the_issue_names_the_work_its_worker_must_not_have_done(self):
        attack = {"id": "RT-AUDIT-01", "kind": "redteam", "priority": 2, "roadmapIds": [], "after": [], "independentOf": ["AUDIT-01", "REV-AUDIT-01"]}
        self.assertIn("Must be done by an agent that did none of `AUDIT-01`, `REV-AUDIT-01`.", body(attack, [attack], {}, {}))

class Listing(unittest.TestCase):
    # `gh issue list` stops at 1000 issues; the swarm has more.
    def test_every_issue_is_listed_page_by_page_without_pull_requests(self):
        from issues import issue_command
        command = issue_command("swarm", "all")
        self.assertEqual(command[:3], ["gh", "api", "--paginate"])
        self.assertIn("issues?labels=swarm&state=all&per_page=100", command[3])
        self.assertIn("select(.pull_request | not)", command[-1])
        self.assertNotIn("body", command[-1])
        self.assertIn("body", issue_command("swarm", "open", body=True)[-1])

    def test_the_listing_reads_one_issue_a_line(self):
        from issues import parse_issues
        text = '{"number": 82, "state": "OPEN", "labels": [{"name": "swarm"}]}\n{"number": 83, "state": "CLOSED", "labels": []}\n'
        self.assertEqual([item["number"] for item in parse_issues(text)], [82, 83])


class PublicText(unittest.TestCase):
    def test_swarm_host_paths_never_reach_an_issue(self):
        prompt = ("You run unattended in a tmux session as job BP-X. Work in /home/chris/tauceti-swarm/tauceti-explorer. "
                  "Your scratch directory is /home/chris/tauceti-swarm/workers/BP-X (create it).\n"
                  "- Library baseline (what exists today): /home/chris/tauceti-swarm/workers/baseline/BASELINE.json\n")
        public = publicize(prompt)
        self.assertIsNotNone(public)
        self.assertNotIn("/home/", public)
        self.assertIn("a clone of https://github.com/CBirkbeck/tauceti-explorer", public)


class StaleClaims(unittest.TestCase):
    def comment(self, login, body, when):
        return {"user": {"login": login}, "body": body, "created_at": when}

    def test_progress_is_a_worker_s_comment_a_claim_or_a_pull_request_not_the_orchestrator_s_notes(self):
        from issues import BOT, worker_activity
        claimed = [self.comment("CBirkbeck", "/claim Codex — codex-1a2b3c", "2026-09-26T16:07:00Z"),
                   self.comment(BOT, "Claimed for Codex — codex-1a2b3c by @CBirkbeck", "2026-09-26T16:07:10Z")]
        self.assertEqual(worker_activity(claimed, []), "2026-09-26T16:07:10Z")
        later = claimed + [self.comment("CBirkbeck", "Orchestrator: the queue now lists the packets.", "2026-09-30T16:00:00Z"),
                           self.comment(BOT, "Swarm intake: the submission check failed on 1234567.", "2026-09-30T16:05:00Z")]
        self.assertEqual(worker_activity(later, []), "2026-09-26T16:07:10Z")
        self.assertEqual(worker_activity(later + [self.comment("CBirkbeck", "Progress: C3 done.", "2026-09-28T09:00:00Z")], []), "2026-09-28T09:00:00Z")
        self.assertEqual(worker_activity(claimed, [{"updated_at": "2026-09-29T10:00:00Z"}]), "2026-09-29T10:00:00Z")
        self.assertIsNone(worker_activity([], []))

    def test_a_pull_request_names_an_issue_by_its_number(self):
        from issues import names_issue
        self.assertTrue(names_issue({"title": "Checkpoint", "body": "Refs #703"}, 703))
        self.assertFalse(names_issue({"title": "Checkpoint", "body": "Refs #7030"}, 703))


class ReviewTitles(unittest.TestCase):
    def test_a_review_of_a_fix_is_titled_as_one_not_as_a_blueprint_review(self):
        job = {"id": "REV-FIX-RT-LINK-tauceti_TauCetiRoadmap_Chebotarev", "kind": "review", "after": ["FIX-RT-LINK-tauceti_TauCetiRoadmap_Chebotarev"],
               "name": "link map LINK-tauceti_TauCetiRoadmap_Chebotarev: The Chebotarev density theorem",
               "roadmapIds": ["tauceti:TauCetiRoadmap/Chebotarev"]}
        self.assertEqual(title(job, {"tauceti:TauCetiRoadmap/Chebotarev": {"title": "The Chebotarev density theorem"}}),
                         "[Review] Fixes for the link map LINK-tauceti_TauCetiRoadmap_Chebotarev: The Chebotarev density theorem")

    def test_a_revision_round_and_its_review_say_which_round_they_are(self):
        roadmaps = {"R": {"title": "Roadmap R"}}
        revision = {"id": "BP-R~2", "kind": "blueprint", "roadmapIds": ["R"], "scope": ["R:L0"]}
        review = {"id": "REV-R~2", "kind": "review", "after": ["BP-R~2"], "roadmapIds": ["R"]}
        self.assertEqual(title(revision, roadmaps), "[Blueprint] Roadmap R (revision 2)")
        self.assertEqual(title(review, roadmaps), "[Review] Blueprint: Roadmap R (revision 2)")
        # Fix rounds keep their titles.
        fix = {"id": "FIX-RT-AREA-x~2", "kind": "fix", "name": "area x", "roadmapIds": ["R"]}
        self.assertEqual(title(fix, roadmaps), "[Fix] Red-team findings on the area x")


class Focus(unittest.TestCase):
    def test_the_work_that_finishes_a_focus_roadmap_is_labelled_focus(self):
        import issues
        focus = {"R"}
        cases = (({"id": "BP-R--L1", "kind": "blueprint", "roadmapIds": ["R"]}, True),
                 ({"id": "BP-R~2", "kind": "blueprint", "roadmapIds": ["R"]}, True),
                 ({"id": "REV-R--L1", "kind": "review", "after": ["BP-R--L1"], "roadmapIds": ["R"]}, True),
                 ({"id": "ASM-R", "kind": "assembly", "roadmapIds": ["R"]}, True),
                 ({"id": "FIX-RT-AREA-x", "kind": "fix", "roadmapIds": ["S", "R"]}, True),
                 # Red teams check finished work, and keep their turn.
                 ({"id": "RT-BP-R", "kind": "redteam", "roadmapIds": ["R"]}, False),
                 ({"id": "REV-RT-BP-R", "kind": "review", "after": ["RT-BP-R"], "roadmapIds": ["R"]}, False),
                 ({"id": "BP-S", "kind": "blueprint", "roadmapIds": ["S"]}, False))
        for item, expected in cases:
            self.assertEqual(issues.is_focus(item, focus), expected, item["id"])
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "focus.json").write_text(json.dumps({"areas": {"Area": ["R"]}}))
            with mock.patch.object(issues, "BP", Path(folder)):
                self.assertEqual(issues.focus_roadmaps(), {"R"})
                self.assertIn("focus", labels_for({"id": "BP-R", "kind": "blueprint", "roadmapIds": ["R"], "after": []}, {}, {}))
                self.assertNotIn("focus", labels_for({"id": "BP-S", "kind": "blueprint", "roadmapIds": ["S"], "after": []}, {}, {}))


class IssueSize(unittest.TestCase):
    def test_instructions_too_long_for_an_issue_shorten_their_longest_list_entries(self):
        from issues import fit_instructions
        text = "JOB: write the blueprint.\n" + "\n".join(f"- source {n}: " + "brief " * 400 for n in range(30)) + "\nMETHOD\n1. Read.\nRULES\n- Edit only the packet."
        fitted = fit_instructions(text, 20_000)
        self.assertLessEqual(len(fitted), 20_000)
        for kept in ("JOB: write the blueprint.", "METHOD", "1. Read.", "RULES", "- Edit only the packet.", "- source 29: brief"):
            self.assertIn(kept, fitted)
        self.assertIn("shortened to fit a GitHub issue", fitted)
        self.assertEqual(fit_instructions("short", 100), "short")


if __name__ == "__main__":
    unittest.main()
