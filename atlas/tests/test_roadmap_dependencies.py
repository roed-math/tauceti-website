import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from roadmap_dependencies import add_dependencies, dependencies, follow_pull_requests, target_folder  # noqa: E402

FOLDERS = {"TauCetiRoadmap/Curves": "tauceti:TauCetiRoadmap/Curves", "TauCetiRoadmap/Sheaves": "tauceti:TauCetiRoadmap/Sheaves",
           "TauCetiRoadmap/Toric": "tauceti:TauCetiRoadmap/Toric", "Completed/Residues": "tauceti:Completed/Residues",
           "TauCetiRoadmap/OperatorTheory/Toeplitz": "tauceti:TauCetiRoadmap/OperatorTheory/Toeplitz",
           "TauCetiRoadmap/EllipticCurves": "tauceti:TauCetiRoadmap/EllipticCurves", "TauCetiRoadmap/ClassFieldTheory": "tauceti:TauCetiRoadmap/ClassFieldTheory",
           "TauCetiRoadmap/Chebotarev": "tauceti:TauCetiRoadmap/Chebotarev"}


def found(text, folder="TauCetiRoadmap/Curves"):
    return [(source.split("/")[-1], target.split("/")[-1], section) for source, target, _, section in dependencies(text, folder, FOLDERS)]


class Links(unittest.TestCase):
    """A README link is read from the README's own folder, as GitHub resolves it."""

    def test_relative_absolute_and_anchored_links_name_their_roadmap_folder(self):
        self.assertEqual(target_folder("../Sheaves/README.md#layer-2", "TauCetiRoadmap/Curves"), "TauCetiRoadmap/Sheaves/README.md")
        self.assertEqual(target_folder("../../Completed/Residues/README.md", "TauCetiRoadmap/Curves"), "Completed/Residues/README.md")
        self.assertEqual(target_folder("https://github.com/TauCetiProject/TauCetiRoadmap/blob/main/TauCetiRoadmap/Toric/README.md",
                                       "TauCetiRoadmap/Curves"), "TauCetiRoadmap/Toric/README.md")
        self.assertIsNone(target_folder("https://mathlib.org", "TauCetiRoadmap/Curves"))
        self.assertIsNone(target_folder("#layer-3", "TauCetiRoadmap/Curves"))


class Dependencies(unittest.TestCase):
    """The roadmaps a README says it builds on, and those it says build on it."""

    def test_a_link_in_a_dependency_section_is_a_prerequisite(self):
        text = "# Curves\n\n## Dependencies\n\n- [Sheaves](../Sheaves/README.md) for line bundles.\n" \
               "- [Toeplitz](../OperatorTheory/Toeplitz/README.md), layer 2.\n"
        self.assertEqual(found(text), [("Sheaves", "Curves", "Dependencies"), ("Toeplitz", "Curves", "Dependencies")])

    def test_a_folder_name_names_a_roadmap_as_a_link_does_a_one_word_one_only_in_code_marks(self):
        text = "# Curves\n\n## Exact supplier contracts\n\n| `EllipticCurves`, Layers 1-4 | twists |\n\nChebotarev density is used, " \
               "as is `Chebotarev` Layer 2.\n"
        self.assertEqual(found(text), [("EllipticCurves", "Curves", "Exact supplier contracts"), ("Chebotarev", "Curves", "Exact supplier contracts")])

    def test_a_layers_own_dependency_list_counts_too(self):
        text = "# Curves\n\n## Layer 3: Jacobians\n\n### Dependencies\n\n[Residues](../../Completed/Residues/README.md)\n"
        self.assertEqual(found(text), [("Residues", "Curves", "Dependencies")])

    def test_a_section_of_what_the_roadmap_gives_others_points_the_other_way(self):
        text = "# Curves\n\n## Downstream consumers\n\n- [Toric](../Toric/README.md) for the divisor class group.\n\n" \
               "## Interfaces supplied to other roadmaps\n\nClassFieldTheory, through the Jacobian.\n"
        self.assertEqual(found(text), [("Curves", "Toric", "Downstream consumers"), ("Curves", "ClassFieldTheory", "Interfaces supplied to other roadmaps")])

    def test_the_verb_nearest_a_name_decides_which_way_it_runs(self):
        text = "# Curves\n\n## Layer 1\n\nThis layer consumes [Sheaves](../Sheaves/README.md). See also [Toric](../Toric/README.md). " \
               "Its divisors are used by [Residues](../../Completed/Residues/README.md).\n\n" \
               "EllipticCurves Layer 4 supplies the tame frame, and ClassFieldTheory Layer 7 supplies local reciprocity.\n"
        self.assertEqual(found(text), [("Sheaves", "Curves", ""), ("Curves", "Residues", ""), ("EllipticCurves", "Curves", ""),
                                       ("ClassFieldTheory", "Curves", "")])

    def test_a_hard_wrapped_paragraph_is_read_whole(self):
        text = "# Curves\n\n## Layer 1\n\nThe divisor map needs the Picard scheme of\nEllipticCurves Layer 2.\n"
        self.assertEqual(found(text), [("EllipticCurves", "Curves", "")])

    def test_a_roadmap_that_uses_something_else_is_not_read_as_using_this_one(self):
        text = "# Curves\n\n## Conventions\n\nClassFieldTheory uses the arithmetic Frobenius. EllipticCurves uses this roadmap's divisors.\n"
        self.assertEqual(found(text), [("Curves", "EllipticCurves", "")])

    def test_a_clause_that_says_the_roadmap_does_not_need_the_other_is_no_dependency(self):
        text = "# Curves\n\n## Dependencies\n\nThis roadmap does not depend on [Toric](../Toric/README.md). " \
               "We work independently of [Sheaves](../Sheaves/README.md).\n"
        self.assertEqual(found(text), [])

    def test_code_and_the_roadmap_itself_are_skipped(self):
        text = "# Curves\n\n## Dependencies\n\n```\n[Sheaves](../Sheaves/README.md)\n```\n\n[Curves](../Curves/README.md)\n"
        self.assertEqual(found(text), [])


class AddDependencies(unittest.TestCase):
    """The READMEs' prerequisites join the atlas's own as edges, with the line that states each and how surely."""

    def test_new_prerequisites_join_recorded_ones_with_their_line_and_weight(self):
        atlas = {"roadmaps": [{"id": rid} for rid in FOLDERS.values()],
                 "edges": [{"source": "tauceti:TauCetiRoadmap/Sheaves", "target": "tauceti:TauCetiRoadmap/Curves", "kind": "declared"}]}
        readmes = {"tauceti:TauCetiRoadmap/Curves": ("# Curves\n\n## Dependencies\n\n[Sheaves](../Sheaves/README.md) and [Toric](../Toric/README.md)\n\n"
                                                     "[Toric](../Toric/README.md) again\n", "TauCetiRoadmap/Curves", "https://example.org/Curves/README.md"),
                   "tauceti:TauCetiRoadmap/Toric": ("# Toric\n\n## Layer 2\n\nIts fans are used by [Curves](../Curves/README.md).\n",
                                                    "TauCetiRoadmap/Toric", "https://example.org/Toric/README.md")}
        self.assertEqual(add_dependencies(atlas, readmes), 1)
        edge = atlas["edges"][-1]
        self.assertEqual((edge["source"], edge["target"], edge["kind"]), ("tauceti:TauCetiRoadmap/Toric", "tauceti:TauCetiRoadmap/Curves", "readme"))
        self.assertEqual(edge["evidence"][0], {"readme": "https://example.org/Curves/README.md", "line": 5, "section": "Dependencies",
                                               "roadmap": "tauceti:TauCetiRoadmap/Curves"})
        # Twice in its dependent's dependency section (3 each), once in a sentence of its supplier's README (1).
        self.assertEqual(edge["weight"], 3 + 3 + 1)
        # The recorded edge is kept as it was.
        self.assertEqual(atlas["edges"][0]["kind"], "declared")



class PullRequests(unittest.TestCase):
    """What a pull request's description states outranks what is read from the READMEs."""

    def test_the_readme_links_are_held_to_the_merge_order_and_the_stated_prerequisites_join_them(self):
        def roadmap(name, pull=None):
            return {"id": "tauceti:TauCetiRoadmap/" + name, **({"origin": "proposed", "pull": {"number": pull}} if pull else {"origin": "tauceti"})}

        def readme(source, target):
            return {"source": "tauceti:TauCetiRoadmap/" + source, "target": "tauceti:TauCetiRoadmap/" + target, "kind": "readme", "weight": 2,
                    "evidence": [{"line": 4}]}
        atlas = {"roadmaps": [roadmap("Curves"), roadmap("Jacobians", 10), roadmap("Modularity", 11), roadmap("Theta", 12), roadmap("Toric", 13)],
                 "edges": [readme("Jacobians", "Curves"), readme("Curves", "Modularity"), readme("Theta", "Modularity"),
                           readme("Toric", "Modularity"), readme("Jacobians", "Modularity"), readme("Modularity", "Theta")]}
        pulls = [{"number": 11, "url": "https://github.com/o/r/pull/11", "stated": {"before": [10, 13], "prerequisites": [10, 13]}},
                 {"number": 12, "stated": None}]
        counts = follow_pull_requests(atlas, pulls)
        self.assertEqual(counts, {"pulls": 1, "onMain": 1, "outsideMergeOrder": 1, "confirmed": 2, "added": 0})
        links = {(e["source"].split("/")[-1], e["target"].split("/")[-1]): e for e in atlas["edges"]}
        # Curves is on main: it rests on no proposed roadmap. Theta is outside Modularity's merge order: it consumes it.
        self.assertEqual(set(links), {("Curves", "Modularity"), ("Toric", "Modularity"), ("Jacobians", "Modularity"), ("Modularity", "Theta")})
        self.assertEqual((links["Jacobians", "Modularity"]["kind"], links["Jacobians", "Modularity"]["pull"], links["Jacobians", "Modularity"]["evidence"]),
                         ("pull", 11, [{"line": 4}]))
        self.assertEqual(links["Curves", "Modularity"]["kind"], "readme")
        # A stated prerequisite no README names becomes a link of its own.
        atlas["edges"] = [e for e in atlas["edges"] if e["source"] != "tauceti:TauCetiRoadmap/Toric"]
        self.assertEqual(follow_pull_requests(atlas, pulls)["added"], 1)
        self.assertEqual(atlas["edges"][-1], {"source": "tauceti:TauCetiRoadmap/Toric", "target": "tauceti:TauCetiRoadmap/Modularity", "kind": "pull",
                                              "stageCount": 0, "evidence": [], "pull": 11, "url": "https://github.com/o/r/pull/11"})


if __name__ == "__main__":
    unittest.main()
