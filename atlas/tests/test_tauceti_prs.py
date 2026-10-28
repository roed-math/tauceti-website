import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from tauceti_prs import add_proposed, arxiv, open_pulls, proposed, stated  # noqa: E402


def pull(number, updated, *files, **extra):
    return dict({"number": number, "updatedAt": updated, "files": {"nodes": [{"path": path, "changeType": change} for path, change in files]}}, **extra)


class Proposals(unittest.TestCase):
    """The roadmaps open pull requests to TauCetiRoadmap propose."""

    def test_a_roadmap_is_a_readme_a_pull_request_adds_where_main_has_none(self):
        pulls = [pull(1, "2026-10-20", ("TauCetiRoadmap/Sheaves/README.md", "ADDED"), ("TauCetiRoadmap/Sheaves/Suggested.lean", "ADDED")),
                 pull(2, "2026-10-21", ("TauCetiRoadmap/Curves/README.md", "MODIFIED")),
                 pull(3, "2026-10-21", ("TauCetiRoadmap/Curves/README.md", "ADDED")),
                 pull(4, "2026-10-19", ("TauCetiRoadmap/OperatorTheory/Toeplitz/README.md", "ADDED"), ("docs/notes.md", "ADDED"))]
        chosen = proposed(pulls, {"TauCetiRoadmap/Curves"})
        self.assertEqual({folder: p["number"] for folder, p in chosen.items()},
                         {"TauCetiRoadmap/Sheaves": 1, "TauCetiRoadmap/OperatorTheory/Toeplitz": 4})

    def test_of_two_pull_requests_adding_one_roadmap_the_one_updated_last_wins(self):
        pulls = [pull(5, "2026-10-21T09:00:00Z", ("TauCetiRoadmap/Sheaves/README.md", "ADDED")),
                 pull(6, "2026-10-21T10:00:00Z", ("TauCetiRoadmap/Sheaves/README.md", "ADDED")),
                 pull(7, "2026-10-20T10:00:00Z", ("TauCetiRoadmap/Sheaves/README.md", "ADDED"))]
        self.assertEqual(proposed(pulls, set())["TauCetiRoadmap/Sheaves"]["number"], 6)

    def test_the_arxiv_category_is_the_topic_metadata_declares(self):
        self.assertEqual(arxiv('topic = "math.NT"\n'), "math.NT")
        self.assertIsNone(arxiv(""))
        self.assertIsNone(arxiv("topic = [1, 2]\n"))
        self.assertIsNone(arxiv("topic = \n"))

    def test_a_description_states_what_must_merge_first_and_which_of_those_its_readme_cites(self):
        body = ("Adds the roadmap.\n\n<!-- merge-order -->\n**Merge order.** #848 (ComplexComparisonPartII) → #1104 (AbhyankarLemma, tdupu) → "
                "#873 (LefschetzPencils) → **this pull request** (#1048). It also depends on other authors' pull requests that add roadmaps "
                "it cites, which must merge first: #1104.\n<!-- /merge-order -->\n\nDependencies (cited in the README by roadmap name and "
                "section). In open pull requests of ours: #873 (LefschetzPencils, LPV.2 §2.8). GlobalGaloisDeformations (#920) is a "
                "downstream consumer, not a prerequisite.\n\nValidation: #999 builds.\n")
        self.assertEqual(stated(body, 1048), {"before": [848, 873, 1104], "prerequisites": [873, 1104]})
        self.assertEqual(stated("<!-- merge-order -->**Merge order.** **this pull request** (#7). It depends on no other author's open pull "
                                "request.<!-- /merge-order -->\n\nDependencies. In open pull requests of ours: none.", 7),
                         {"before": [], "prerequisites": []})
        self.assertIsNone(stated("Dependencies: #12 and #13.", 14))
        self.assertIsNone(stated(None, 14))

    def test_every_page_of_open_pull_requests_is_read(self):
        pages = [{"data": {"repository": {"pullRequests": {"pageInfo": {"hasNextPage": True, "endCursor": "c1"}, "nodes": [{"number": 1}]}}}},
                 {"data": {"repository": {"pullRequests": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [{"number": 2}]}}}}]
        calls = []

        def run(args):
            calls.append(args)
            return json.dumps(pages[len(calls) - 1])
        self.assertEqual([p["number"] for p in open_pulls(run)], [1, 2])
        self.assertEqual(calls[1][-2:], ["-f", "cursor=c1"])


class AddProposed(unittest.TestCase):
    """Proposed roadmaps join the map from their READMEs on the pull request's branch."""

    def atlas(self):
        return {"roadmaps": [{"id": "tauceti:TauCetiRoadmap/Schemes", "origin": "tauceti", "group": "schemes", "stages": [], "title": "Schemes"}],
                "stages": [], "stageEdges": [], "roadmapLinks": [], "progress": {"stages": {}, "roadmaps": {}},
                "groups": [{"id": "schemes", "label": "Schemes, curves and moduli"}, {"id": "etale", "label": "Etale cohomology"}],
                "fields": [{"id": "algebraic-geometry", "label": "Algebraic geometry", "groupIds": ["schemes", "etale"]}]}

    def data(self):
        # Adic names Sheaves, which comes after it, and Schemes, on main; Sheaves names Adic. Mystery has no area.
        return {"pulls": [{"number": 10, "url": "https://github.com/TauCetiProject/TauCetiRoadmap/pull/10", "author": "kim-em", "draft": False,
                           "labels": ["awaiting-review"], "head": "TauCetiProject/TauCetiRoadmap", "sha": "abc123"},
                          {"number": 11, "url": "https://github.com/TauCetiProject/TauCetiRoadmap/pull/11", "author": "CBirkbeck", "draft": True,
                           "labels": [], "head": "CBirkbeck/TauCetiRoadmap", "sha": "def456"}],
                "roadmaps": {
                    "TauCetiRoadmap/Adic": {"pull": 10, "arxiv": None, "readme": "# Etale cohomology of adic spaces\n\nBuilds on [schemes](../Schemes/README.md) "
                                            "and [sheaves](../Sheaves/README.md).\n\n## A1. Adic spectra\n\nHuber pairs.\n\n## A2. Etale sites\n\nSites.\n"},
                    "TauCetiRoadmap/Sheaves": {"pull": 11, "arxiv": None, "readme": "# Sheaves on schemes\n\nUsed by [adic spaces](../Adic/README.md).\n\n"
                                               "## Layer 0: presheaves\n\nFunctors.\n"},
                    "TauCetiRoadmap/Mystery": {"pull": 11, "arxiv": None, "readme": "# Things\n\n## Layer 0: things\n\nStuff.\n"}}}

    def test_proposed_roadmaps_have_their_layers_area_pull_request_and_branch(self):
        atlas = self.atlas()
        added = add_proposed(atlas, self.data(), {}, {})
        self.assertEqual(added, ["tauceti:TauCetiRoadmap/Adic", "tauceti:TauCetiRoadmap/Sheaves"])
        adic = next(r for r in atlas["roadmaps"] if r["id"] == added[0])
        self.assertEqual((adic["origin"], adic["group"], adic["title"]), ("proposed", "etale", "Etale cohomology of adic spaces"))
        self.assertEqual(adic["pull"], {"number": 10, "url": "https://github.com/TauCetiProject/TauCetiRoadmap/pull/10", "author": "kim-em",
                                        "draft": False, "labels": ["awaiting-review"]})
        self.assertEqual(adic["sourcePath"], "https://github.com/TauCetiProject/TauCetiRoadmap/blob/abc123/TauCetiRoadmap/Adic/README.md")
        # The page reads the README from the branch when it is opened, rather than carrying it.
        self.assertEqual((adic["readme"], adic["readmeUrl"]),
                         ("", "https://raw.githubusercontent.com/TauCetiProject/TauCetiRoadmap/abc123/TauCetiRoadmap/Adic/README.md"))
        self.assertIn("Huber pairs.", next(s for s in atlas["stages"] if s["owner"] == added[0])["description"])
        stages = [s for s in atlas["stages"] if s["owner"] == added[0]]
        self.assertEqual([(s["key"], s["title"], s["origin"]) for s in stages], [("A1", "Adic spectra", "proposed"), ("A2", "Etale sites", "proposed")])
        self.assertEqual(atlas["stageEdges"][0]["origin"], "proposed")
        self.assertNotIn(stages[0]["id"], atlas["progress"]["stages"])

    def test_a_proposed_roadmap_links_to_every_roadmap_its_readme_names_proposed_or_not(self):
        atlas = self.atlas()
        add_proposed(atlas, self.data(), {}, {})
        links = {(link["source"].split("/")[-1], link["target"].split("/")[-1]) for link in atlas["roadmapLinks"]}
        self.assertEqual(links, {("Adic", "Schemes"), ("Adic", "Sheaves"), ("Sheaves", "Adic")})

    def test_a_proposed_roadmap_with_no_area_waits_like_a_new_tau_ceti_one(self):
        atlas = self.atlas()
        add_proposed(atlas, self.data(), {}, {})
        self.assertNotIn("tauceti:TauCetiRoadmap/Mystery", {r["id"] for r in atlas["roadmaps"]})


if __name__ == "__main__":
    unittest.main()
