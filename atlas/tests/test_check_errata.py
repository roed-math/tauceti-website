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

    def test_a_file_that_quotes_a_statement_must_say_which_text_it_read(self):
        """A published paper and its preprint differ; a quoted sentence may only exist in one."""
        data = {"paper": "PAPER-X", "protocol": "errata-v1", "sourceIssues": [
            {"id": "PAPER-X/E1", "kind": "error", "locator": "Theorem 1.3", "printed": "the claim",
             "correction": "the fix", "reason": "because", "affects": "a stated result", "known": "new",
             "searched": ["arXiv v1"]}]}
        self.assertIn("sourceVersions", " ".join(check(data, "PAPER-X")))
        data["sourceVersions"] = [{"kind": "published", "url": "https://doi.org/10.1090/jams/945", "read": "2026-09-24"}]
        self.assertEqual([e for e in check(data, "PAPER-X") if "sourceVersions" in e], [])

    def test_a_version_entry_says_what_it_is_and_where_it_came_from(self):
        data = {"paper": "PAPER-X", "protocol": "errata-v1", "sourceVersions": [{"kind": "postprint"}],
                "sourceIssues": []}
        found = " ".join(check(data, "PAPER-X"))
        self.assertIn("kind", found)

    def test_findings_in_the_older_form_are_converted_here(self):
        found = check({"paper": "PAPER-X", "protocol": "errata-v1", "sourceIssues": [{"id": "S1", "finding": "Old."}]}, "PAPER-X")
        self.assertIn("S1 is in the older form: convert it (PROTOCOL.md section 18)", found)


if __name__ == "__main__":
    unittest.main()
