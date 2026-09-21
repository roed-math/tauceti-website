"""GitHub issue rendering for the blueprint queue: states and public text."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
from issues import labels_for, publicize  # noqa: E402


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
