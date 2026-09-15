"""Integrity checks for source refinements; no fixtures are published in the atlas."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from decompositions import merge_decompositions


class DecompositionIntegrity(unittest.TestCase):
    def setUp(self):
        self.atlas = {
            "meta": {}, "external": [],
            "roadmaps": [
                {"id": "A", "readme": "# A\n\nOriginal theorem.\n", "sourcePath": "content/A.md",
                 "stages": ["A:0"], "prerequisites": [], "consumers": []},
                {"id": "B", "readme": "# B\n", "sourcePath": "content/B.md", "stages": ["B:0"],
                 "prerequisites": [], "consumers": []}],
            "stages": [
                {"id": "A:0", "owner": "A", "parentStageId": None, "isLeaf": True,
                 "status": "original_status", "requires": [], "consumers": []},
                {"id": "B:0", "owner": "B", "parentStageId": None, "isLeaf": True,
                 "requires": [], "consumers": []}],
            "edges": [], "stageEdges": [],
        }
        self.packet = {
            "roadmapId": "A", "status": "partial", "summary": "A tested construction refinement.",
            "review": {"status": "accepted", "notes": "Synthetic integrity-test fixture."},
            "sources": [{"id": "test", "title": "Test source", "authors": "Test author",
                         "edition": "Test edition", "readSections": ["Section 1"]}],
            "nodes": [{
                "id": "A:0/construction", "parentStageId": "A:0", "title": "Test construction",
                "kind": "construction", "statement": "Construct the object under the stated hypothesis.",
                "hypotheses": ["The test hypothesis holds."],
                "proofSteps": ["Apply the cited construction."],
                "acceptance": ["Verify the stated universal property."],
                "sources": [{"sourceId": "test", "locator": "Section 1",
                             "excerpt": "Test excerpt", "match": "This is the construction cited."}],
                "implementationStatus": "unchecked"}],
            "links": [{"source": "A:0/construction", "target": "B:0",
                       "reason": "B uses the constructed object.",
                       "sources": [{"sourceId": "test", "locator": "Section 1"}]}],
            "coverage": [{"stageId": "A:0", "status": "partial", "remaining": ["Another proof"]}],
            "gaps": [],
        }

    def test_refinement_preserves_source_and_attaches_citation_locations(self):
        original = deepcopy(self.atlas)
        result, documents = merge_decompositions(self.atlas, [self.packet])
        self.assertEqual(self.atlas, original)
        self.assertTrue(documents["content/A.md"].startswith(self.atlas["roadmaps"][0]["readme"]))
        node = result["stages"][-1]
        lines = documents[node["sourcePath"]].splitlines()
        self.assertEqual("\n".join(lines[node["sourceLine"] - 1:node["contextEndLine"]]), node["description"])
        self.assertFalse(result["stages"][0]["isLeaf"])
        self.assertEqual(result["stages"][0]["status"], "original_status")
        self.assertEqual(node["implementationStatus"], "unchecked")
        self.assertNotIn("progress", node)

    def test_cross_roadmap_dependency_keeps_its_mathematical_evidence(self):
        result, _ = merge_decompositions(self.atlas, [self.packet])
        edge = result["stageEdges"][0]
        self.assertEqual(edge["evidence"][0]["reason"], self.packet["links"][0]["reason"])
        self.assertEqual(result["edges"], [{"source": "A", "target": "B", "kind": "stage_supported", "stageCount": 1}])
        self.assertEqual(result["roadmaps"][1]["prerequisites"], ["A"])

    def test_dependency_cycle_is_rejected(self):
        link = deepcopy(self.packet["links"][0])
        link["source"], link["target"] = link["target"], link["source"]
        self.packet["links"].append(link)
        with self.assertRaisesRegex(ValueError, "Cycle in mathematical prerequisites"):
            merge_decompositions(self.atlas, [self.packet])

    def test_unresolved_cross_reference_is_rejected(self):
        self.packet["links"][0]["source"] = "Unwritten:missing-theorem"
        with self.assertRaisesRegex(ValueError, "Invalid dependency"):
            merge_decompositions(self.atlas, [self.packet])

    def test_citation_without_a_verified_excerpt_is_rejected(self):
        self.packet["nodes"][0]["sources"][0]["excerpt"] = ""
        with self.assertRaisesRegex(ValueError, "Missing text"):
            merge_decompositions(self.atlas, [self.packet])

    def test_draft_cannot_be_published(self):
        self.packet.pop("review")
        with self.assertRaisesRegex(ValueError, "independent review"):
            merge_decompositions(self.atlas, [self.packet])

    def test_partial_source_work_cannot_claim_closure(self):
        self.packet["status"] = "source_decomposed"
        with self.assertRaisesRegex(ValueError, "closure is not established"):
            merge_decompositions(self.atlas, [self.packet])

    def test_parent_cannot_belong_to_another_roadmap(self):
        self.packet["nodes"][0]["parentStageId"] = "B:0"
        with self.assertRaisesRegex(ValueError, "parent in its own roadmap"):
            merge_decompositions(self.atlas, [self.packet])

    def test_link_to_an_unpromoted_packet_is_deferred_not_asserted(self):
        # B's refinement is named before B's own packet is accepted: the link
        # waits with its reason instead of becoming an edge or failing the build.
        self.packet["links"].append({"source": "B:0/unreviewed-lemma", "target": "A:0/construction",
                                     "reason": "Awaiting B's reviewed decomposition.",
                                     "sources": [{"sourceId": "test", "locator": "Section 2"}]})
        result, _ = merge_decompositions(self.atlas, [self.packet])
        self.assertEqual(len(result["stageEdges"]), 1)
        deferred = result["decompositions"][0]["deferredLinks"]
        self.assertEqual(deferred, [{"source": "B:0/unreviewed-lemma", "target": "A:0/construction",
                                     "reason": "Awaiting B's reviewed decomposition.",
                                     "awaiting": ["B:0/unreviewed-lemma"]}])

    def test_link_to_an_unknown_roadmap_is_still_rejected(self):
        self.packet["links"].append({"source": "Nowhere:0/lemma", "target": "A:0/construction",
                                     "reason": "No such roadmap.", "sources": [{"sourceId": "test", "locator": "x"}]})
        with self.assertRaisesRegex(ValueError, "Invalid dependency"):
            merge_decompositions(self.atlas, [self.packet])

    def test_node_added_during_review_is_marked_unreviewed(self):
        self.packet["nodes"][0]["addedBy"] = "reviewer"
        result, _ = merge_decompositions(self.atlas, [self.packet])
        node = result["stages"][-1]
        self.assertFalse(node["expansion"]["reviewed"])
        self.assertEqual(node["expansion"]["addedBy"], "reviewer")
        self.assertEqual(result["decompositions"][0]["review"]["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
