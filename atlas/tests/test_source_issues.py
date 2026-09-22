"""Mistakes found in published sources (PROTOCOL.md section 18): the form a finding takes."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from source_issues import check_issues  # noqa: E402

ISSUE = {"id": "PAPER-X/E1", "kind": "error", "locator": "Lemma 2.4, p. 9 (arXiv v2 and the published version)",
         "printed": "the map is surjective for every n ≥ 1",
         "correction": "the map is surjective for n ≥ 2; for n = 1 its image has index 2",
         "reason": "For n = 1 the source's own formula (2.3) gives image 2Z.",
         "affects": "the proof", "known": "new",
         "searched": ["the journal's errata listing", "arXiv versions v1 and v2", "the authors' pages"]}


def errors(issues):
    return check_issues(issues, "PAPER-X")


class Findings(unittest.TestCase):
    def test_a_complete_finding_passes(self):
        self.assertEqual(errors([ISSUE]), [])

    def test_a_finding_quotes_the_source_and_says_why(self):
        issue = dict(ISSUE, printed="", reason=" ")
        found = errors([issue])
        self.assertIn("PAPER-X/E1: needs printed (what the source says, quoted)", found)
        self.assertIn("PAPER-X/E1: needs reason (the check or argument that shows it)", found)

    def test_its_kind_and_its_reach_are_named(self):
        found = errors([dict(ISSUE, kind="oops", affects="everything")])
        self.assertIn("PAPER-X/E1: kind is one of error, gap, misprint", found)
        self.assertIn("PAPER-X/E1: affects is one of a stated result, nothing, the proof", found)

    def test_a_finding_says_where_a_correction_was_looked_for(self):
        self.assertIn("PAPER-X/E1: searched lists where an existing correction was looked for", errors([dict(ISSUE, searched=[])]))

    def test_ids_belong_to_the_work(self):
        self.assertIn("finding id 'OTHER/E1' must start with PAPER-X/E", errors([dict(ISSUE, id="OTHER/E1")]))
        self.assertIn("PAPER-X/E1 appears twice", errors([ISSUE, copy.deepcopy(ISSUE)]))

    def test_a_reviewer_confirms_or_rejects_each_finding_with_a_reason(self):
        self.assertEqual(errors([dict(ISSUE, review={"verdict": "confirmed", "reason": "Checked n = 1.", "by": "REV-PAPER-X"})]), [])
        found = errors([dict(ISSUE, review={"verdict": "maybe", "reason": "", "by": ""})])
        self.assertIn("PAPER-X/E1: review verdict is confirmed or rejected, with a reason and the review job (by)", found)


if __name__ == "__main__":
    unittest.main()
