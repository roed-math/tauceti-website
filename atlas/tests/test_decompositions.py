"""Integrity checks for source refinements; no fixtures are published in the atlas."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from decompositions import merge_decompositions, merge_links


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




class ReviewedLinks(unittest.TestCase):
    def setUp(self):
        self.atlas = {
            "meta": {}, "external": [], "edges": [], "stageEdges": [],
            "roadmaps": [{"id": "A", "stages": ["A:0"]}, {"id": "B", "stages": ["B:0"]}],
            "stages": [{"id": "A:0", "owner": "A", "requires": [], "consumers": []},
                       {"id": "B:0", "owner": "B", "requires": [], "consumers": []}],
        }
        self.link = {"source": "A:0", "target": "B:0", "reason": "A supplies the object B uses.", "confidence": "explicit",
                     "evidence": [{"stageId": "A:0", "quote": "constructs the object"},
                                  {"stageId": "B:0", "quote": "uses the object"}]}

    def packet(self, **changes):
        packet = {"roadmapId": "A", "protocol": "links-v1", "links": [deepcopy(self.link)],
                  "review": {"status": "accepted", "reviewer": "independent-review-test"}}
        packet.update(changes)
        return packet

    def test_accepted_link_becomes_a_stage_dependency_with_evidence(self):
        atlas = merge_links(self.atlas, [self.packet()])
        edge = atlas["stageEdges"][0]
        self.assertEqual((edge["source"], edge["target"]), ("A:0", "B:0"))
        self.assertEqual(edge["evidence"][0]["reviewer"], "independent-review-test")
        self.assertIn("A:0", next(s for s in atlas["stages"] if s["id"] == "B:0")["requires"])
        self.assertEqual(self.atlas["stageEdges"], [])

    def test_unreviewed_link_packet_is_refused(self):
        with self.assertRaises(ValueError):
            merge_links(self.atlas, [self.packet(review={"status": "needs_changes", "reviewer": "x"})])

    def test_one_sided_evidence_is_refused(self):
        packet = self.packet()
        packet["links"][0]["evidence"] = packet["links"][0]["evidence"][:1]
        with self.assertRaises(ValueError):
            merge_links(self.atlas, [packet])

    def test_links_from_upstream_prerequisites_do_not_stop_a_merge(self):
        self.atlas["external"] = [{"id": "UPSTREAM:X"}]
        self.atlas["stageEdges"] = [{"source": "UPSTREAM:X", "target": "A:0"}]
        atlas = merge_links(self.atlas, [self.packet()])
        self.assertIn(("A:0", "B:0"), {(e["source"], e["target"]) for e in atlas["stageEdges"]})

    def test_a_link_to_a_layer_not_in_the_atlas_waits_and_the_rest_merges(self):
        later = deepcopy(self.link)
        later["target"] = "C:0"
        atlas = merge_links(self.atlas, [self.packet(links=[deepcopy(self.link), later])])
        self.assertEqual({(e["source"], e["target"]) for e in atlas["stageEdges"]}, {("A:0", "B:0")})
        self.assertEqual(atlas["deferredLinks"], [{"source": "A:0", "target": "C:0", "packet": "A", "awaiting": ["C:0"]}])

    def test_link_that_closes_a_cycle_is_refused(self):
        reverse = deepcopy(self.link)
        reverse["source"], reverse["target"] = "B:0", "A:0"
        with self.assertRaises(ValueError):
            merge_links(self.atlas, [self.packet(links=[deepcopy(self.link), reverse])])


if __name__ == "__main__":
    unittest.main()
