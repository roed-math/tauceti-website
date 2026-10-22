import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from roadmap_dependencies import add_dependencies, dependencies, target_folder  # noqa: E402

FOLDERS = {"TauCetiRoadmap/Curves": "tauceti:TauCetiRoadmap/Curves", "TauCetiRoadmap/Sheaves": "tauceti:TauCetiRoadmap/Sheaves",
           "TauCetiRoadmap/Toric": "tauceti:TauCetiRoadmap/Toric", "Completed/Residues": "tauceti:Completed/Residues",
           "TauCetiRoadmap/OperatorTheory/Toeplitz": "tauceti:TauCetiRoadmap/OperatorTheory/Toeplitz"}


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

    def test_a_layers_own_dependency_list_counts_too(self):
        text = "# Curves\n\n## Layer 3: Jacobians\n\n### Dependencies\n\n[Residues](../../Completed/Residues/README.md)\n"
        self.assertEqual(found(text), [("Residues", "Curves", "Dependencies")])

    def test_a_downstream_section_points_the_other_way(self):
        text = "# Curves\n\n## Downstream consumers\n\n- [Toric](../Toric/README.md) uses the divisor class group.\n"
        self.assertEqual(found(text), [("Curves", "Toric", "Downstream consumers")])

    def test_elsewhere_only_a_line_that_says_it_builds_on_the_roadmap_counts(self):
        text = "# Curves\n\n## Layer 1\n\nThis layer consumes [Sheaves](../Sheaves/README.md).\nSee also [Toric](../Toric/README.md).\n" \
               "It is used by [Residues](../../Completed/Residues/README.md).\n"
        self.assertEqual(found(text), [("Sheaves", "Curves", ""), ("Curves", "Residues", "")])

    def test_a_line_that_says_it_does_not_need_the_roadmap_is_no_dependency(self):
        text = "# Curves\n\n## Dependencies\n\nThis roadmap does not depend on [Toric](../Toric/README.md).\n" \
               "We work independently of [Sheaves](../Sheaves/README.md).\n"
        self.assertEqual(found(text), [])

    def test_code_and_the_roadmap_itself_are_skipped(self):
        text = "# Curves\n\n## Dependencies\n\n```\n[Sheaves](../Sheaves/README.md)\n```\n[Curves](../Curves/README.md)\n"
        self.assertEqual(found(text), [])


class AddDependencies(unittest.TestCase):
    """The READMEs' prerequisites join the atlas's own as edges, with the line that states each."""

    def test_new_prerequisites_join_recorded_ones_with_their_line(self):
        atlas = {"roadmaps": [{"id": rid} for rid in FOLDERS.values()],
                 "edges": [{"source": "tauceti:TauCetiRoadmap/Sheaves", "target": "tauceti:TauCetiRoadmap/Curves", "kind": "declared"}]}
        readmes = {"tauceti:TauCetiRoadmap/Curves": ("# Curves\n\n## Dependencies\n\n[Sheaves](../Sheaves/README.md) and [Toric](../Toric/README.md)\n"
                                                     "[Toric](../Toric/README.md) again\n", "TauCetiRoadmap/Curves", "https://example.org/Curves/README.md")}
        self.assertEqual(add_dependencies(atlas, readmes), 1)
        edge = atlas["edges"][-1]
        self.assertEqual((edge["source"], edge["target"], edge["kind"]), ("tauceti:TauCetiRoadmap/Toric", "tauceti:TauCetiRoadmap/Curves", "readme"))
        self.assertEqual(edge["evidence"], [{"readme": "https://example.org/Curves/README.md", "line": 5, "section": "Dependencies",
                                             "roadmap": "tauceti:TauCetiRoadmap/Curves"},
                                            {"readme": "https://example.org/Curves/README.md", "line": 6, "section": "Dependencies",
                                             "roadmap": "tauceti:TauCetiRoadmap/Curves"}])
        # The recorded edge is kept as it was.
        self.assertEqual(atlas["edges"][0]["kind"], "declared")


if __name__ == "__main__":
    unittest.main()
