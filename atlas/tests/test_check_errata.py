"""Files of the errata jobs (scripts/check_errata.py, PROTOCOL.md section 18)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_errata import check  # noqa: E402

FINDING = {"id": "PAPER-X/E1", "kind": "misprint", "locator": "(16)", "printed": "bounded", "correction": "tending to zero",
           "reason": "c_(pj) = p^(-j) is bounded and does not tend to zero.", "affects": "the proof", "known": "new", "searched": ["arXiv v1, v2"]}


class ErrataFiles(unittest.TestCase):
    def test_a_complete_file_passes_and_an_empty_list_says_none_were_found(self):
        self.assertEqual(check({"paper": "PAPER-X", "protocol": "errata-v1", "sourceIssues": [FINDING]}, "PAPER-X"), [])
        self.assertEqual(check({"paper": "PAPER-X", "protocol": "errata-v1", "sourceIssues": []}, "PAPER-X"), [])

    def test_the_file_names_its_work_and_lists_its_findings(self):
        found = check({"paper": "PAPER-Y", "protocol": "errata-v1"}, "PAPER-X")
        self.assertIn("paper (or roadmapId) must be PAPER-X", found)
        self.assertIn("sourceIssues is a list (empty when none were found)", found)

    def test_findings_in_the_older_form_are_converted_here(self):
        found = check({"paper": "PAPER-X", "protocol": "errata-v1", "sourceIssues": [{"id": "S1", "finding": "Old."}]}, "PAPER-X")
        self.assertIn("S1 is in the older form: convert it (PROTOCOL.md section 18)", found)


if __name__ == "__main__":
    unittest.main()
