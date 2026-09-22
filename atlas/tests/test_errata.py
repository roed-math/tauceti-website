"""The register of mistakes found in published sources (scripts/errata.py, PROTOCOL.md section 18)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from errata import collect, register  # noqa: E402


def issue(n, known="new", review=None, **extra):
    item = {"id": f"PAPER-X/E{n}", "kind": "error", "locator": f"Lemma {n}", "printed": f"claim {n}", "correction": f"fix {n}",
            "reason": f"because {n}", "affects": "the proof", "known": known, "searched": ["arXiv v2"], **extra}
    if review:
        item["review"] = review
    return item


JOBS = [{"id": "PAPER-X", "kind": "paper", "state": "done", "outputs": ["research/blueprint/papers/PAPER-X.result.json"]},
        {"id": "REV-PAPER-X", "kind": "review", "state": "done", "after": ["PAPER-X"], "outputs": ["research/blueprint/papers/PAPER-X.result.json"]},
        {"id": "PAPER-Y", "kind": "paper", "state": "done", "outputs": ["research/blueprint/papers/PAPER-Y.result.json"]}]


class Register(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        papers = self.root / "research" / "blueprint" / "papers"
        papers.mkdir(parents=True)
        (self.root / "research" / "blueprint" / "packets").mkdir()
        confirmed = {"verdict": "confirmed", "reason": "Checked it.", "by": "REV-PAPER-X"}
        (papers / "PAPER-X.result.json").write_text(json.dumps({"paper": "PAPER-X", "source": {"title": "A paper", "authors": "An author"},
            "sourceIssues": [issue(1, review=confirmed), issue(2), issue(3, known="Erratum, J. Math. 12 (2024)", review=confirmed),
                             issue(4, review={"verdict": "rejected", "reason": "The source is right.", "by": "REV-PAPER-X"}),
                             issue(5, review={"verdict": "confirmed", "reason": "Self-confirmed.", "by": "PAPER-X"})]}))
        (papers / "PAPER-Y.result.json").write_text(json.dumps({"paper": "PAPER-Y", "source": {"title": "Another", "authors": "Someone"}}))
        (papers / "PAPER-Z.result.json").write_text(json.dumps({"paper": "PAPER-Z", "sourceIssues": [{"id": "S1", "finding": "an older form"}]}))

    def tearDown(self):
        self.folder.cleanup()

    def statuses(self):
        return {item["id"]: item["status"] for item in collect(self.root, JOBS)["issues"]}

    def test_a_finding_counts_as_confirmed_only_by_a_finished_review_of_its_file(self):
        self.assertEqual(self.statuses(), {"PAPER-X/E1": "confirmed", "PAPER-X/E2": "awaiting review", "PAPER-X/E3": "confirmed",
                                           "PAPER-X/E4": "rejected", "PAPER-X/E5": "awaiting review"})

    def test_the_register_puts_new_confirmed_mistakes_first_and_lists_what_is_unchecked(self):
        text = register(collect(self.root, JOBS))
        new, waiting, printed = text.index("## New mistakes, confirmed"), text.index("## New mistakes awaiting review"), text.index("## Already corrected in print")
        self.assertTrue(new < waiting < printed)
        self.assertIn("claim 1", text[new:waiting])
        self.assertIn("claim 2", text[waiting:printed])
        self.assertIn("Erratum, J. Math. 12 (2024)", text[printed:])
        self.assertNotIn("claim 4", text)
        self.assertIn("PAPER-Y", text[text.index("## Not yet checked"):])
        self.assertIn("PAPER-Z", text[text.index("## Not yet checked"):])
        self.assertNotIn("an older form", text)


if __name__ == "__main__":
    unittest.main()
