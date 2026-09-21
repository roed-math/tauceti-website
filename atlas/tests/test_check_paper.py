"""Paper extractions (PROTOCOL.md section 16): the checks a submission must pass."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_paper import check  # noqa: E402

ROADMAPS = {"R": {"origin": "campaign", "title": "Completed cohomology"}, "tauceti:T": {"origin": "tauceti", "title": "Modular forms"}}
STAGES = {"R:R1": "R", "R:R2": "R", "tauceti:T:L1": "tauceti:T"}
BRIEF = " ".join(["Final theorem: the main theorem of the paper, with every definition and key theorem it uses or proves."] * 6)


def extraction():
    return {"paper": "PAPER-X", "protocol": "paper-v1", "status": "complete",
            "source": {"title": "A paper", "authors": "An author", "venue": "Ann. of Math.", "doi": "10.4007/x", "readSections": ["all"]},
            "summary": "What the paper proves and what it needs.",
            "items": [
                {"id": "PAPER-X/1", "kind": "definition", "name": "Tower", "statement": "The tower of modular curves.", "locator": "§2.1",
                 "status": "library", "library": ["mathlib:ModularCurve"]},
                {"id": "PAPER-X/2", "kind": "construction", "name": "Completed cohomology", "statement": "The completed cohomology.", "locator": "§2.2",
                 "status": "planned", "planned": ["R:R1"]},
                {"id": "PAPER-X/3", "kind": "theorem", "name": "Classicality", "statement": "Every regular de Rham representation is classical.",
                 "locator": "Theorem 1.1", "status": "missing"},
                {"id": "PAPER-X/4", "kind": "definition", "name": "Sen operator", "statement": "The geometric Sen operator.", "locator": "§3",
                 "status": "missing"}],
            "prerequisites": [{"citation": "Part I of the paper", "link": "doi:10.1/partone", "why": "It constructs the Sen operator."}],
            "routes": [
                {"route": "source", "roadmap": "R", "stages": ["R:R2"], "items": ["PAPER-X/2", "PAPER-X/3"], "reason": "Classicality is R2's target."},
                {"route": "part-ii", "parent": "R", "roadmap": "RPartII", "title": "Completed cohomology, Part II: Sen theory", "area": "langlands",
                 "items": ["PAPER-X/4"], "brief": BRIEF, "reason": "Geometric Sen theory needs new layers."}]}


def errors(data, name="PAPER-X"):
    return check(data, name, ROADMAPS, STAGES)


class Extractions(unittest.TestCase):
    def test_a_complete_extraction_passes(self):
        self.assertEqual(errors(extraction()), [])

    def test_every_missing_item_is_routed_once_when_complete(self):
        data = extraction()
        data["routes"] = data["routes"][:1]
        self.assertIn("PAPER-X/4 is missing but no route takes it", errors(data))
        data = extraction()
        data["routes"][1]["items"].append("PAPER-X/3")
        self.assertIn("PAPER-X/3 is taken by 2 routes", errors(data))
        partial = extraction()
        partial["status"], partial["routes"] = "partial", []
        self.assertEqual(errors(partial), [])

    def test_a_status_is_backed_by_a_declaration_or_a_layer(self):
        data = extraction()
        del data["items"][0]["library"]
        data["items"][1]["planned"] = ["R:R9"]
        found = errors(data)
        self.assertIn("PAPER-X/1: a library item cites its declarations (mathlib:… or tauceti:…)", found)
        self.assertIn("PAPER-X/2: R:R9 is not a layer of the atlas", found)

    def test_a_tau_ceti_roadmap_is_extended_by_a_part_two_never_re_planned(self):
        data = extraction()
        data["routes"][0].update(roadmap="tauceti:T", stages=["tauceti:T:L1"])
        self.assertIn("a source route cannot re-plan the Tau Ceti roadmap tauceti:T; propose a Part II", errors(data))

    def test_a_part_two_names_its_parent_and_says_so(self):
        data = extraction()
        data["routes"][1].update(parent="Nowhere", title="Sen theory")
        found = errors(data)
        self.assertIn("route 2: unknown parent roadmap Nowhere", found)
        self.assertIn("route 2: a Part II is titled '<parent title>, Part II: <topic>'", found)

    def test_a_new_roadmap_brings_a_real_brief(self):
        data = extraction()
        data["routes"][1] = {"route": "new", "roadmap": "Fresh", "title": "Fresh theory", "area": "langlands",
                             "items": ["PAPER-X/4"], "brief": "Prove it.", "reason": "Nothing like it exists."}
        self.assertIn("route 2: a brief of at least 60 words (final theorems, what to cover, what to import)", errors(data))

    def test_a_new_roadmap_id_is_new(self):
        data = extraction()
        data["routes"][1]["roadmap"] = "R"
        self.assertIn("route 2: R already exists; extend it instead", errors(data))

    def test_the_file_names_its_paper(self):
        self.assertIn("paper must be PAPER-Y", errors(extraction(), name="PAPER-Y"))


if __name__ == "__main__":
    unittest.main()
