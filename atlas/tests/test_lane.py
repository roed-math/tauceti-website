"""Which jobs a lane of the local swarm may claim (research/blueprint/lane.py)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
from lane import eligible  # noqa: E402


class Eligible(unittest.TestCase):
    def test_a_reviewer_never_reviews_its_own_work(self):
        jobs = {"AUDIT-07": {"id": "AUDIT-07", "state": "done", "account": "claude2"}}
        review = {"id": "REV-AUDIT-07", "state": "pending", "after": ["AUDIT-07"], "avoidAccountOf": "AUDIT-07"}
        self.assertFalse(eligible(review, jobs, "claude2"))
        self.assertTrue(eligible(review, jobs, "claude3"))

    def test_a_red_team_is_independent_of_the_work_and_of_its_review(self):
        jobs = {"AUDIT-07": {"id": "AUDIT-07", "state": "done", "account": "claude2"},
                "REV-AUDIT-07": {"id": "REV-AUDIT-07", "state": "done", "account": "claude3"}}
        red = {"id": "RT-AUDIT-07", "state": "pending", "after": [], "independentOf": ["AUDIT-07", "REV-AUDIT-07"]}
        self.assertFalse(eligible(red, jobs, "claude2"))
        self.assertFalse(eligible(red, jobs, "claude3"))
        self.assertTrue(eligible(red, jobs, "claude4"))


if __name__ == "__main__":
    unittest.main()
