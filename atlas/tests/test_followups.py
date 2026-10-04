"""Follow-up jobs for the stages a complete planning pass leaves open (PROTOCOL.md section 0)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
sys.path.insert(0, str(ROOT / "scripts"))
import make_queue  # noqa: E402
from make_queue import open_stages, review_job  # noqa: E402


class FollowUps(unittest.TestCase):
    def test_a_stage_is_open_until_it_is_planned(self):
        packet = {"coverage": [{"stageId": "R:L0", "status": "planned", "remaining": ["Refine."]},
                               {"stageId": "R:L1", "status": "partial", "remaining": ["The comparison map."]},
                               {"stageId": "R:L2", "status": "closed", "remaining": []}]}
        self.assertEqual(open_stages(packet, ["R:L0", "R:L1", "R:L2", "R:L3"]),
                         [("R:L1", ["The comparison map."]), ("R:L3", [])])

    def test_reviews_are_named_as_the_queue_names_them(self):
        self.assertEqual(review_job("BP-R--L3"), "REV-R--L3")
        self.assertEqual(review_job("DESIGN-RPartII"), "REV-DESIGN-RPartII")

    def test_only_an_accepted_complete_pass_hands_on_its_open_stages(self):
        job = {"id": "BP-R", "kind": "blueprint", "outputs": ["research/blueprint/packets/R.json"]}
        done = {"REV-R": {"state": "done"}}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "research" / "blueprint" / "packets").mkdir(parents=True)
            path = root / "research" / "blueprint" / "packets" / "R.json"
            with mock.patch.object(make_queue, "REPO", root):
                for status, review, prior, expected in (
                        ("complete", "accepted", done, True),
                        ("complete", "accepted", {"REV-R": {"state": "pending"}}, False),
                        ("complete", "needs_changes", done, False),
                        # Accepted while partial under the earlier rule: its gaps go to red teams and fixes.
                        ("partial", "accepted", done, False)):
                    path.write_text(json.dumps({"status": status, "review": {"status": review}}))
                    self.assertEqual(bool(make_queue.accepted_pass(job, prior)), expected, (status, review, prior))


if __name__ == "__main__":
    unittest.main()
