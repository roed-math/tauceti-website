"""The roadmap audit (scripts/audit_roadmaps.py)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_roadmaps import blueprint_paths, cites, citation_gaps, sourceless, unreviewed_done  # noqa: E402


class Cites(unittest.TestCase):
    def test_a_source_line_counts(self):
        self.assertTrue(cites("Build the ring. *Source:* Milne, ANT, Theorem 3.1."))

    def test_an_author_year_counts(self):
        self.assertTrue(cites("Following Bhatt–Scholze (2022) §3, define the prism."))

    def test_a_bare_plan_does_not(self):
        self.assertFalse(cites("Define the ring of Witt vectors and prove the comparison map is an isomorphism."))


class Gaps(unittest.TestCase):
    STAGES = [{"owner": "A", "description": "no source here"}, {"owner": "A", "description": "see Theorem 2"},
              {"owner": "B", "description": "nothing"}]

    def test_uncited_layers_are_counted_per_roadmap(self):
        self.assertEqual(citation_gaps(self.STAGES), {"A": (1, 2), "B": (1, 1)})

    def test_a_document_without_a_sources_section_is_named(self):
        self.assertEqual(sourceless({"A": {"readme": "# T\n\n## Sources\n- x"}, "B": {"readme": "# T\n\n## Plan\n"}}), ["B"])


class Paths(unittest.TestCase):
    JOBS = [{"id": "BP-X", "kind": "blueprint", "state": "pending", "roadmapIds": ["X"]},
            {"id": "BP-Y", "kind": "blueprint", "state": "done", "roadmapIds": ["Y"]},
            {"id": "REV-Y", "kind": "review", "state": "pending", "roadmapIds": ["Y"]},
            {"id": "BP-Z", "kind": "blueprint", "state": "done", "roadmapIds": ["Z"]}]

    def test_each_roadmap_gets_the_right_path(self):
        found = blueprint_paths({"X": {}, "Y": {}, "W": {}, "tauceti:TauCetiRoadmap/U": {}}, self.JOBS, {"Y"})
        self.assertEqual(found, {"X": "pending", "Y": "promoted", "W": "none", "tauceti:TauCetiRoadmap/U": "excluded"})

    def test_finished_work_with_no_review_job_is_named(self):
        self.assertEqual(unreviewed_done(self.JOBS), ["BP-Z"])


if __name__ == "__main__":
    unittest.main()
