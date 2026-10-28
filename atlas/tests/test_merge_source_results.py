"""Merging accepted source jobs into the access register (scripts/merge_source_results.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from merge_source_results import apply_edits, merge, accepted  # noqa: E402

REGISTER = {"checkHosts": [], "blockedHosts": [], "works": [
    {"id": "STICHTENOTH", "kind": "book", "access": "restricted", "title": "H. Stichtenoth, Algebraic Function Fields",
     "match": [r"\*Algebraic Function Fields\*"], "substitute": None},
]}
RESULT = {
    "roadmap": "AlgebraicCurves",
    "citations": [
        {"book": "STICHTENOTH", "file": "content/tau-ceti/AlgebraicCurves/README.md", "line": 12,
         "outcome": "replaced", "source": "FULTON-CURVES", "locator": "Ch. 8, Prop. 3"},
        {"book": "STICHTENOTH", "file": "content/tau-ceti/AlgebraicCurves/README.md", "line": 40,
         "outcome": "kept", "source": None, "reason": "no free source proves the ramification bound"},
    ],
    "edits": [
        {"file": "content/tau-ceti/AlgebraicCurves/README.md", "line": 2,
         "old": "- H. Stichtenoth, *Algebraic Function Fields*, Ch. 3, for the genus.",
         "new": "- Fulton, *Algebraic Curves*, Ch. 8, Prop. 3, for the genus."},
    ],
    "register": [
        {"id": "FULTON-CURVES", "kind": "notes", "access": "free", "title": "Fulton, Algebraic Curves",
         "urls": ["https://example.org/curves.pdf"], "match": [r"Fulton, \*Algebraic Curves\*"], "note": "Author released it."},
    ],
}


class Accepted(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / "results").mkdir()
        (self.root / "reviews").mkdir()
        (self.root / "results" / "SRC-AlgebraicCurves.json").write_text(json.dumps(RESULT))

    def tearDown(self):
        self.dir.cleanup()

    def test_a_result_with_an_accepting_review_is_used(self):
        (self.root / "reviews" / "REV-SRC-AlgebraicCurves.md").write_text("Verdict: accepted\n\nChecked all.")
        self.assertEqual([r["roadmap"] for r in accepted(self.root / "results", self.root / "reviews")], ["AlgebraicCurves"])

    def test_a_rejected_review_keeps_the_result_out(self):
        (self.root / "reviews" / "REV-SRC-AlgebraicCurves.md").write_text("Verdict: rejected\n\nThe locator is wrong.")
        self.assertEqual(accepted(self.root / "results", self.root / "reviews"), [])

    def test_an_unreviewed_result_keeps_out(self):
        self.assertEqual(accepted(self.root / "results", self.root / "reviews"), [])

    def test_an_attribution_result_is_taken_the_same_way(self):
        att = self.root / "attribution"; att.mkdir()
        (att / "ATT-PDE.json").write_text(json.dumps({"roadmap": "PDE", "citations": [], "edits": [], "register": []}))
        (self.root / "reviews" / "REV-ATT-PDE.md").write_text("Verdict: accepted\n")
        self.assertIn("PDE", [r["roadmap"] for r in accepted(self.root / "results", self.root / "reviews", att)])

    def test_a_review_that_does_not_say_is_not_an_acceptance(self):
        (self.root / "reviews" / "REV-SRC-AlgebraicCurves.md").write_text("Looks broadly fine to me.")
        self.assertEqual(accepted(self.root / "results", self.root / "reviews"), [])


class Merge(unittest.TestCase):
    def test_a_new_free_work_is_added(self):
        reg, notes = merge(json.loads(json.dumps(REGISTER)), [RESULT])
        found = {work["id"]: work for work in reg["works"]}
        self.assertEqual(found["FULTON-CURVES"]["access"], "free")
        self.assertEqual(found["FULTON-CURVES"]["urls"], ["https://example.org/curves.pdf"])

    def test_the_replaced_book_records_what_now_covers_it(self):
        reg, notes = merge(json.loads(json.dumps(REGISTER)), [RESULT])
        found = {work["id"]: work for work in reg["works"]}
        self.assertEqual(found["STICHTENOTH"]["substitute"], "FULTON-CURVES")

    def test_a_kept_citation_is_reported_as_still_needed(self):
        reg, notes = merge(json.loads(json.dumps(REGISTER)), [RESULT])
        self.assertIn("no free source proves the ramification bound", " ".join(notes))

    def test_a_registered_work_is_not_duplicated(self):
        reg, _ = merge(json.loads(json.dumps(REGISTER)), [RESULT, RESULT])
        self.assertEqual(len([w for w in reg["works"] if w["id"] == "FULTON-CURVES"]), 1)

    def test_a_result_may_not_mark_a_restricted_work_free(self):
        bad = json.loads(json.dumps(RESULT))
        bad["register"][0] = {"id": "STICHTENOTH", "access": "free", "title": "H. Stichtenoth", "urls": [], "match": []}
        with self.assertRaises(ValueError):
            merge(json.loads(json.dumps(REGISTER)), [bad])


class ApplyEdits(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        path = self.root / "content" / "tau-ceti" / "AlgebraicCurves"
        path.mkdir(parents=True)
        (path / "README.md").write_text(
            "# Algebraic curves\n- H. Stichtenoth, *Algebraic Function Fields*, Ch. 3, for the genus.\n- Keep me.\n")

    def tearDown(self):
        self.dir.cleanup()

    def read(self):
        return (self.root / "content" / "tau-ceti" / "AlgebraicCurves" / "README.md").read_text().splitlines()

    def test_a_matching_line_is_replaced_and_its_neighbours_are_not(self):
        applied, refused = apply_edits([RESULT], self.root)
        self.assertEqual(len(applied), 1)
        self.assertEqual(refused, [])
        self.assertEqual(self.read()[1], "- Fulton, *Algebraic Curves*, Ch. 8, Prop. 3, for the genus.")
        self.assertEqual(self.read()[2], "- Keep me.")

    def test_a_line_that_has_moved_since_is_refused_not_guessed(self):
        path = self.root / "content" / "tau-ceti" / "AlgebraicCurves" / "README.md"
        path.write_text("# Algebraic curves\n\n- H. Stichtenoth, *Algebraic Function Fields*, Ch. 3, for the genus.\n")
        applied, refused = apply_edits([RESULT], self.root)
        self.assertEqual(applied, [])
        self.assertEqual(len(refused), 1)
        self.assertIn("line 2", refused[0])

    def test_nothing_is_written_when_any_edit_of_a_file_is_refused(self):
        path = self.root / "content" / "tau-ceti" / "AlgebraicCurves" / "README.md"
        before = path.read_text()
        bad = json.loads(json.dumps(RESULT))
        bad["edits"].append({"file": "content/tau-ceti/AlgebraicCurves/README.md", "line": 3,
                             "old": "- Not what is there.", "new": "- Something else."})
        applied, refused = apply_edits([bad], self.root)
        self.assertEqual(path.read_text(), before)
        self.assertEqual(applied, [])


if __name__ == "__main__":
    unittest.main()
