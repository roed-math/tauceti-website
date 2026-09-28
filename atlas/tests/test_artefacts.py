import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from artefacts import paper_artefacts  # noqa: E402


ATLAS = {
    "roadmaps": [{"id": "Heights"}, {"id": "Shimura"}],
    "stages": [{"id": "Heights:H1", "owner": "Heights"}, {"id": "Heights:H2", "owner": "Heights"}, {"id": "Shimura:S1", "owner": "Shimura"}],
}


class PaperArtefacts(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.papers = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def write(self, name, content):
        (self.papers / name).write_text(json.dumps(content))

    def paper(self, pid, routes, verdict="accept", accepted=None, review=True):
        self.write(f"{pid}.result.json", {"paper": pid, "routes": routes})
        if review:
            numbers = accepted if accepted is not None else range(1, len(routes) + 1)
            self.write(f"{pid}.review.json", {"verdict": verdict, "routes": [{"route": n, "verdict": "accept"} for n in numbers]})

    def registry(self, *papers):
        self.write("papers.json", {"papers": [{"id": pid, "short": short, "citation": short + ", in full", "link": "https://example.org/" + pid}
                                              for pid, short in papers]})

    def test_a_paper_sits_by_the_roadmap_most_of_its_items_go_to_and_needs_the_layers_its_routes_name(self):
        self.registry(("PAPER-A", "Author (2024): A title"))
        self.paper("PAPER-A", [
            {"route": "source", "roadmap": "Heights", "stages": ["Heights:H1", "Heights:H2", "Heights:GONE"], "items": ["a", "b", "c"]},
            {"route": "part-ii", "parent": "Shimura", "roadmap": "ShimuraPartII", "items": ["d"]},
            {"route": "new", "roadmap": "Brand", "area": "langlands", "items": ["e"]},
        ])
        [artefact] = paper_artefacts(ATLAS, self.papers)
        self.assertEqual(artefact["id"], "paper:PAPER-A")
        self.assertEqual(artefact["label"], "Author (2024)")
        self.assertEqual(artefact["citation"], "Author (2024): A title, in full")
        self.assertEqual(artefact["link"], "https://example.org/PAPER-A")
        self.assertEqual(artefact["home"], "Heights")
        # A layer no longer in the atlas is dropped; a Part II needs all of its parent.
        self.assertEqual(artefact["needs"], ["Heights:H1", "Heights:H2"])
        self.assertEqual(artefact["roadmaps"], ["Shimura"])
        # Roadmaps the paper calls for that are not in the atlas yet keep it locked.
        self.assertEqual(artefact["pending"], ["Brand", "ShimuraPartII"])

    def test_only_routes_the_review_accepted_count(self):
        self.registry(("PAPER-A", "Author (2024)"))
        self.paper("PAPER-A", [
            {"route": "source", "roadmap": "Heights", "stages": ["Heights:H1"], "items": ["a"]},
            {"route": "source", "roadmap": "Shimura", "stages": ["Shimura:S1"], "items": ["b", "c"]},
        ], accepted=[1])
        [artefact] = paper_artefacts(ATLAS, self.papers)
        self.assertEqual((artefact["home"], artefact["needs"]), ("Heights", ["Heights:H1"]))

    def test_a_paper_without_an_accepted_review_or_a_place_on_the_atlas_is_not_drawn(self):
        self.registry(("PAPER-A", "A (2020)"), ("PAPER-B", "B (2021)"), ("PAPER-C", "C (2022)"))
        self.paper("PAPER-A", [{"route": "source", "roadmap": "Heights", "stages": ["Heights:H1"], "items": ["a"]}], verdict="reject")
        self.paper("PAPER-B", [{"route": "source", "roadmap": "Heights", "stages": ["Heights:H1"], "items": ["a"]}], review=False)
        self.paper("PAPER-C", [{"route": "new", "roadmap": "Brand", "area": "langlands", "items": ["a"]}])
        self.assertEqual(paper_artefacts(ATLAS, self.papers), [])

    def test_no_registry_means_no_artefacts(self):
        self.assertEqual(paper_artefacts(ATLAS, self.papers / "missing"), [])


if __name__ == "__main__":
    unittest.main()
