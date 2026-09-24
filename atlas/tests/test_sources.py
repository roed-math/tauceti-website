"""Which sources the roadmaps depend on, and whether a reader can get them (scripts/sources.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sources import blocked, citations, dependencies, documents, report, unregistered  # noqa: E402

REGISTER = {
    "checkHosts": ["doi.org", "link.springer.com", "www.jstor.org"],
    "works": [
        {"id": "NEUKIRCH-ANT", "title": "Neukirch, Algebraic Number Theory", "access": "restricted",
         "match": [r"Neukirch, \*Algebraic Number Theory\*"],
         "substitute": "MILNE-ANT", "note": "Grundlehren 322."},
        {"id": "MILNE-ANT", "title": "Milne, Algebraic Number Theory (course notes)", "access": "free",
         "match": [r"Milne, \*?Algebraic Number Theory"], "urls": ["https://www.jmilne.org/math/CourseNotes/ANT.pdf"]},
        {"id": "HUBER96", "title": "Huber, Étale Cohomology of Rigid Analytic Varieties", "access": "restricted",
         "match": [r"\bHub96\b"], "substitute": None, "note": "Vieweg 1996, out of print."},
        {"id": "SHIMURA-IAT", "title": "Shimura, Introduction to the Arithmetic Theory", "access": "restricted",
         "match": [r"Shimura, \*Introduction to the Arithmetic Theory"], "substitute": None},
        {"id": "TAO-VU", "title": "Tao–Vu, Additive Combinatorics", "access": "restricted",
         "match": [r"Tao[-–]Vu"], "substitute": None,
         "urls": ["https://doi.org/10.1017/CBO9780511755149"]},
    ],
}


class Citations(unittest.TestCase):
    def test_a_work_is_found_by_any_of_its_patterns(self):
        self.assertEqual(citations("The source route is Hub96 4.1.1(c).", REGISTER), {"HUBER96"})

    def test_a_lookalike_phrase_is_not_a_citation(self):
        text = "Construct the finite-level Shimura variety and its Hecke tower."
        self.assertEqual(citations(text, REGISTER), set())

    def test_a_document_citing_nothing_registered_is_empty(self):
        self.assertEqual(citations("Define the Witt vectors.", REGISTER), set())


class Dependencies(unittest.TestCase):
    def setUp(self):
        self.found = dependencies({
            "AdicEtaleGeometry": "Hub96 §4 and ECD.",
            "ClassFieldTheory": "- J. Neukirch, *Algebraic Number Theory*, Chapter VII.",
            "Chebotarev": "- J. Neukirch, *Algebraic Number Theory*, Ch. I.",
        }, REGISTER)

    def test_a_work_lists_every_roadmap_that_cites_it(self):
        self.assertEqual(self.found["NEUKIRCH-ANT"], ["Chebotarev", "ClassFieldTheory"])

    def test_a_work_nothing_cites_is_absent(self):
        self.assertNotIn("TAO-VU", self.found)


class Unregistered(unittest.TestCase):
    def test_a_link_to_a_checked_host_that_no_work_claims_is_flagged(self):
        text = "See [a book](https://link.springer.com/book/10.1007/978-1-4757-6046-0)."
        self.assertEqual(unregistered({"FunctionFieldArithmetic": text}, REGISTER),
                         [("FunctionFieldArithmetic", "https://link.springer.com/book/10.1007/978-1-4757-6046-0")])

    def test_a_registered_url_is_not_flagged(self):
        text = "[Tao-Vu, Additive Combinatorics](https://doi.org/10.1017/CBO9780511755149)"
        self.assertEqual(unregistered({"AdditiveCombinatorics": text}, REGISTER), [])

    def test_a_free_host_is_not_flagged(self):
        text = "[BMS](https://arxiv.org/abs/1602.03148) and [Stacks](https://stacks.math.columbia.edu/tag/01WC)"
        self.assertEqual(unregistered({"AInfCohomology": text}, REGISTER), [])


class Blocked(unittest.TestCase):
    def setUp(self):
        self.deps = dependencies({
            "AdicEtaleGeometry": "Hub96 §4.",
            "ClassFieldTheory": "- J. Neukirch, *Algebraic Number Theory*, Chapter VII.",
            "PadicHodge": "Milne, *Algebraic Number Theory*, §2.",
        }, REGISTER)

    def test_a_restricted_work_with_no_substitute_must_be_provided(self):
        self.assertEqual([w["id"] for w in blocked(self.deps, REGISTER)], ["HUBER96"])

    def test_a_restricted_work_with_a_free_substitute_is_not_blocking(self):
        self.assertNotIn("NEUKIRCH-ANT", [w["id"] for w in blocked(self.deps, REGISTER)])

    def test_the_report_names_the_roadmaps_that_would_stall(self):
        self.assertIn("AdicEtaleGeometry", report(self.deps, REGISTER))
        self.assertIn("Huber", report(self.deps, REGISTER))


class Documents(unittest.TestCase):
    """A roadmap's README and its atlas JSON share a name; both must survive."""

    def setUp(self):
        self.tree = tempfile.TemporaryDirectory()
        root = Path(self.tree.name)
        (root / "content" / "campaign" / "AdicEtaleGeometry").mkdir(parents=True)
        (root / "content" / "campaign" / "AdicEtaleGeometry" / "README.md").write_text("The main source is Hub96.")
        (root / "content" / "tau-ceti" / "AdicEtaleGeometry").mkdir(parents=True)
        (root / "content" / "tau-ceti" / "AdicEtaleGeometry" / "README.md").write_text("Shimura varieties appear here.")
        (root / "content" / "campaign-guide").mkdir(parents=True)
        (root / "content" / "campaign-guide" / "EXTENSION_SOURCES.md").write_text("Tao-Vu is the source.")
        (root / "roadmaps").mkdir()
        (root / "roadmaps" / "tauceti_TauCetiRoadmap_AdicEtaleGeometry.json").write_text(json.dumps(
            {"summary": "Adic etale cohomology.",
             "stages": [{"description": "- J. Neukirch, *Algebraic Number Theory*, Ch. II."}]}))
        self.found = documents(root / "content", root / "roadmaps")

    def tearDown(self):
        self.tree.cleanup()

    def test_every_file_of_a_roadmap_lands_under_its_one_name(self):
        self.assertEqual(sorted(self.found), ["AdicEtaleGeometry", "EXTENSION_SOURCES"])
        self.assertEqual(citations(self.found["AdicEtaleGeometry"], REGISTER), {"HUBER96", "NEUKIRCH-ANT"})

    def test_a_guide_file_stands_for_itself(self):
        self.assertEqual(citations(self.found["EXTENSION_SOURCES"], REGISTER), {"TAO-VU"})


if __name__ == "__main__":
    unittest.main()
