"""GitHub issue rendering for the blueprint queue: states and public text."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

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
                         ("done", "state:submitted"))
        self.assertEqual(transition(job("REV-RS-01", state="external"), ["state:claimed"], True, True),
                         ("done", "state:done"))

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
        for name in ("packets", "readmes", "restructure"):
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

    def test_a_link_map_is_finished_when_it_says_so(self):
        links = {"id": "LINK-R", "kind": "link", "outputs": ["packets/links-R.json"]}
        self.write("packets/links-R.json", {"status": "partial"})
        self.assertFalse(deliverables_complete(links, self.root))
        self.write("packets/links-R.json", {"status": "complete"})
        self.assertTrue(deliverables_complete(links, self.root))

    def test_an_errata_job_is_finished_when_every_mistake_is_recorded_in_full(self):
        job = {"id": "ERRATA-PAPER-X", "kind": "errata", "outputs": ["packets/PAPER-X.result.json", "packets/PAPER-X.md"]}
        self.write("packets/PAPER-X.md", "Report.")
        self.write("packets/PAPER-X.result.json", {"paper": "PAPER-X"})
        self.assertFalse(deliverables_complete(job, self.root))
        self.write("packets/PAPER-X.result.json", {"paper": "PAPER-X", "sourceIssues": [{"id": "S1", "finding": "an older form"}]})
        self.assertFalse(deliverables_complete(job, self.root))
        self.write("packets/PAPER-X.result.json", {"paper": "PAPER-X", "sourceIssues": []})
        self.assertTrue(deliverables_complete(job, self.root))

    def test_a_red_team_is_finished_when_its_result_says_so(self):
        attack = {"id": "RT-AUDIT-01", "kind": "redteam", "outputs": ["packets/RT-AUDIT-01.result.json", "packets/RT-AUDIT-01.md"]}
        self.write("packets/RT-AUDIT-01.md", "Report.")
        self.write("packets/RT-AUDIT-01.result.json", {"status": "partial"})
        self.assertFalse(deliverables_complete(attack, self.root))
        self.write("packets/RT-AUDIT-01.result.json", {"status": "complete"})
        self.assertTrue(deliverables_complete(attack, self.root))


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
        self.assertIn("Every mistake in the paper", body(job, [job], {}, {}))

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


if __name__ == "__main__":
    unittest.main()
