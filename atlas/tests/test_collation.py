"""Which text a paper's findings were read from (scripts/collation.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from collation import exposure, provenance, published_exists, requests_page  # noqa: E402


def record(**extra):
    return {"paper": "PAPER-X", "sourceIssues": [
        {"id": "PAPER-X/E1", "kind": "error", "affects": "a stated result", "locator": "Theorem 1.3(a), p. 3"},
        {"id": "PAPER-X/E2", "kind": "misprint", "affects": "nothing", "locator": "§2"}], **extra}


class Provenance(unittest.TestCase):
    def test_a_recorded_published_reading_is_the_version_of_record(self):
        found = record(sourceVersions=[{"kind": "published", "url": "https://doi.org/10.1090/jams/945",
                                        "read": "2026-09-24", "sha256": "abc"}])
        self.assertEqual(provenance(found), "published")

    def test_a_recorded_preprint_reading_is_not(self):
        found = record(sourceVersions=[{"kind": "preprint", "url": "https://arxiv.org/abs/1701.02458v1",
                                        "read": "2026-09-20"}])
        self.assertEqual(provenance(found), "preprint")

    def test_notes_naming_a_publisher_copy_that_was_read_count_as_published(self):
        found = record(sourceIssues=[dict(record()["sourceIssues"][0],
                                          searched=["Read the published PDF https://doi.org/10.1090/jams/952, SHA-256 b7cf45"])])
        self.assertEqual(provenance(found), "published")

    def test_notes_naming_only_a_preprint_are_preprint(self):
        found = record(sourceIssues=[dict(record()["sourceIssues"][0],
                                          searched=["arXiv:1701.02458 lists only v1; the author copy was used"])])
        self.assertEqual(provenance(found), "preprint")

    def test_a_record_saying_nothing_is_unknown(self):
        self.assertEqual(provenance(record()), "unknown")


class PublishedExists(unittest.TestCase):
    def test_a_citation_naming_a_journal_and_year_has_a_version_of_record(self):
        self.assertTrue(published_exists({"citation": 'A, "T", Annals of Mathematics 191 (2020), no. 2'}))

    def test_an_arxiv_only_paper_has_none(self):
        self.assertFalse(published_exists({"citation": 'A, "T", arXiv:2405.19601 (2024)',
                                           "link": "https://arxiv.org/abs/2405.19601"}))


class Exposure(unittest.TestCase):
    PAPERS = {"PAPER-X": {"id": "PAPER-X", "citation": 'A, "T", Journal of the AMS 33 (2020)', "link": "https://doi.org/10.1090/jams/945"},
              "PAPER-Y": {"id": "PAPER-Y", "citation": 'B, "U", arXiv:2405.19601 (2024)', "link": "https://arxiv.org/abs/2405.19601"}}

    def test_a_preprint_reading_of_a_published_paper_is_exposed(self):
        rows = exposure({"PAPER-X": record(sourceVersions=[{"kind": "preprint", "url": "https://arxiv.org/abs/1"}])}, self.PAPERS)
        self.assertEqual([row["paper"] for row in rows], ["PAPER-X"])
        self.assertEqual(rows[0]["stated"], 1)
        self.assertEqual(rows[0]["locators"], ["Theorem 1.3(a), p. 3"])

    def test_a_paper_with_no_published_version_is_not_exposed(self):
        rows = exposure({"PAPER-Y": record(sourceVersions=[{"kind": "preprint", "url": "https://arxiv.org/abs/2"}])}, self.PAPERS)
        self.assertEqual(rows, [])

    def test_a_collated_paper_is_not_exposed(self):
        rows = exposure({"PAPER-X": record(sourceVersions=[{"kind": "published", "url": "https://doi.org/10.1090/jams/945"}])}, self.PAPERS)
        self.assertEqual(rows, [])

    def test_findings_that_quote_no_statement_do_not_expose_a_paper(self):
        quiet = {"paper": "PAPER-X", "sourceIssues": [{"id": "PAPER-X/E2", "kind": "misprint", "affects": "nothing"}],
                 "sourceVersions": [{"kind": "preprint", "url": "https://arxiv.org/abs/1"}]}
        self.assertEqual(exposure({"PAPER-X": quiet}, self.PAPERS), [])


class RequestsPage(unittest.TestCase):
    def test_the_page_names_the_paper_the_link_and_what_to_check(self):
        rows = exposure({"PAPER-X": record(sourceVersions=[{"kind": "preprint", "url": "https://arxiv.org/abs/1"}])},
                        Exposure.PAPERS)
        page = requests_page(rows)
        self.assertIn("PAPER-X", page)
        self.assertIn("https://doi.org/10.1090/jams/945", page)
        self.assertIn("Theorem 1.3(a), p. 3", page)


if __name__ == "__main__":
    unittest.main()
