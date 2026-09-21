"""GitHub issue rendering for the blueprint queue: states and public text."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
from issues import deliverables_complete, labels_for, publicize, refresh_payload, transition  # noqa: E402


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
