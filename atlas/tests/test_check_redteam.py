"""Red-team results and their verification (PROTOCOL.md section 17)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_redteam import check, check_review  # noqa: E402


def result():
    return {"redteam": "RT-AUDIT-07", "protocol": "redteam-v1", "status": "complete", "target": "AUDIT-07",
            "summary": "Every library claim of the audit was re-checked.",
            "checked": ["every declaration the audit cites, at the pinned commit", "every target marked not built"],
            "findings": [{"id": "RT-AUDIT-07/1", "kind": "library-claim", "severity": "high", "where": "research/blueprint/audit/AUDIT-07.result.json",
                          "claim": "Layer R3's target 'Frobenius elements' is marked not built, but Mathlib has it.",
                          "evidence": "Mathlib/RingTheory/Frobenius.lean: arithFrobAt, read at 082e2d3.",
                          "fix": "Mark the target built and cite mathlib:arithFrobAt."}]}


class Results(unittest.TestCase):
    def test_a_complete_result_passes(self):
        self.assertEqual(check(result(), "RT-AUDIT-07"), [])

    def test_a_clean_result_still_says_what_it_checked(self):
        data = result()
        data["findings"], data["checked"] = [], []
        self.assertIn("checked: say what was checked, so that finding nothing means something", check(data, "RT-AUDIT-07"))
        data["checked"] = ["every declaration the audit cites"]
        self.assertEqual(check(data, "RT-AUDIT-07"), [])

    def test_a_finding_is_precise_and_evidenced(self):
        data = result()
        finding = data["findings"][0]
        finding.update(kind="bad", severity="huge", evidence="")
        found = check(data, "RT-AUDIT-07")
        self.assertIn("RT-AUDIT-07/1: kind is one of duplicate, error, library-claim, missing, other", found)
        self.assertIn("RT-AUDIT-07/1: severity is one of high, low, medium", found)
        self.assertIn("RT-AUDIT-07/1: needs its evidence", found)

    def test_ids_belong_to_the_red_team(self):
        data = result()
        data["findings"][0]["id"] = "RT-OTHER/1"
        self.assertIn("finding id 'RT-OTHER/1' must start with RT-AUDIT-07/", check(data, "RT-AUDIT-07"))


class Verification(unittest.TestCase):
    def test_every_finding_is_confirmed_or_rejected_with_a_reason(self):
        review = {"redteam": "RT-AUDIT-07", "findings": [{"finding": "RT-AUDIT-07/1", "verdict": "confirmed", "reason": "arithFrobAt is there."}]}
        self.assertEqual(check_review(review, "RT-AUDIT-07", result()), [])
        review["findings"] = []
        self.assertIn("RT-AUDIT-07/1 has no verdict", check_review(review, "RT-AUDIT-07", result()))
        review["findings"] = [{"finding": "RT-AUDIT-07/1", "verdict": "maybe", "reason": ""}]
        found = check_review(review, "RT-AUDIT-07", result())
        self.assertIn("RT-AUDIT-07/1: verdict is confirmed or rejected", found)
        self.assertIn("RT-AUDIT-07/1: needs a reason", found)


if __name__ == "__main__":
    unittest.main()
