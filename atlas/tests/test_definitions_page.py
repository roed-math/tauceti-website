"""The list page of the atlas's definitions and constructions (scripts/definitions_page.py)."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from blueprints import merge_blueprints  # noqa: E402
from definitions_page import collect, page  # noqa: E402
from test_blueprints import atlas, node  # noqa: E402


def packet():
    added = node("R:L1/e", "construction", "The epsilon construction")
    added["addedBy"] = "independent-review-REV-R"
    return {"roadmapId": "R", "protocol": "blueprint-v1", "part": None, "status": "partial", "scope": ["R:L0", "R:L1"],
            "summary": "The blueprint of R.", "review": {"status": "accepted", "reviewer": "independent-review-REV-R", "date": "2026-09-22"},
            "nodes": [node("R:L0/g", "construction", "The gamma construction"),
                      node("R:L0/a", "definition", "The alpha object over `Foo.bar`, for n < m", planet="Alpha object"),
                      node("R:L0/b", "lemma", "A lemma on alpha", ["R:L0/a"]),
                      node("R:L0/c", "theorem", "The beta theorem", ["R:L0/b"], planet="Beta theorem"),
                      node("R:L1/d", "definition", "The delta object", ["R:L0/c"]), added]}


def refinement(sid, kind, title, parent, hidden=False):
    return {"id": sid, "owner": sid.split(":")[0], "key": sid.split(":", 1)[1], "title": title, "parentStageId": parent, "isLeaf": True,
            "expansion": {"kind": kind, "statement": "Statement of " + title, "hypotheses": [], "reviewed": True}}


def built():
    packets = [("R", packet())]
    result = merge_blueprints(atlas(), packets, documents={})
    result["stages"] += [refinement("S:S1/pairing", "definition", "The pairing", "S:S1"),
                         refinement("S:S1/pairing/norm", "construction", "Its norm", "S:S1/pairing"),
                         refinement("S:S1/bound", "theorem", "A bound", "S:S1"),
                         refinement("S:S1/admin", "definition", "Bookkeeping", "S:S1")]
    result["stagePresentation"] = {"S:S1/admin": {"summary": "Not mathematics.", "hidden": True}}
    return result, packets


class DefinitionsPage(unittest.TestCase):
    def test_blueprint_items_are_listed_with_their_planets_first(self):
        found = collect(*built())["blueprints"]
        self.assertEqual([item["id"] for item in found], ["R:L0/a", "R:L0/g", "R:L1/d", "R:L1/e"])
        alpha = found[0]
        self.assertTrue(alpha["planet"])
        self.assertEqual(alpha["name"], "Alpha object")
        self.assertEqual(alpha["title"], "The alpha object over `Foo.bar`, for n < m")
        self.assertEqual(found[1]["name"], "The gamma construction")
        self.assertFalse(found[1]["planet"])
        self.assertFalse(found[3]["reviewed"])

    def test_decomposition_items_sit_under_their_layer_and_hidden_ones_are_left_out(self):
        found = collect(*built())["decompositions"]
        self.assertEqual([(item["id"], item["layer"]) for item in found], [("S:S1/pairing", "S:S1"), ("S:S1/pairing/norm", "S:S1")])
        self.assertFalse(any(item["planet"] for item in found))

    def test_the_page_escapes_statements_and_reads_without_a_script(self):
        text = page(*built())
        self.assertIn("Alpha object", text)
        self.assertIn("<code>Foo.bar</code>", text)
        self.assertIn("for n &lt; m", text)
        self.assertNotIn("Beta theorem", text)
        self.assertNotIn("Bookkeeping", text)
        self.assertEqual(text.count("<details class=\"item\""), 6)
        self.assertIn("plan 4 definitions and constructions across 1 roadmap", text)
        for tag in ("section", "div", "details", "ul"):
            self.assertEqual(len(re.findall(f"<{tag}[ >]", text)), text.count(f"</{tag}>"), tag)
        self.assertIn('id="bar" hidden', text)


if __name__ == "__main__":
    unittest.main()
