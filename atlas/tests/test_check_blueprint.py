"""Blueprint packet checks: unit tests for definitions and planets for the atlas."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_blueprint import check  # noqa: E402

CONTEXT = ({}, {"R:L0": "R", "R:L1": "R"}, {"R"}, {}, {}, {})


def unit_tests(count):
    return [{"name": f"t{i}", "kind": "computation", "statement": f"A fact that pins the object down, number {i}."}
            for i in range(count)]


def definition(nid="R:L0/object", stage="R:L0", **extra):
    node = {"id": nid, "parentStageId": stage, "realises": [stage], "title": "An object", "kind": "definition",
            "statement": "The object, with every hypothesis.", "hypotheses": [], "proofSteps": ["Define it."],
            "acceptance": ["It agrees with the classical object."], "prerequisites": [],
            "api": [{"name": f"Object.lemma{i}", "role": "simp", "statement": "An evaluation rule."} for i in range(3)],
            "tests": unit_tests(3),
            "sources": [{"sourceId": "s", "locator": "p. 1", "excerpt": "Definition.", "match": "exact"}],
            "implementationStatus": "unchecked"}
    node.update(extra)
    return node


def packet(nodes):
    return {"roadmapId": "R", "protocol": "blueprint-v1", "part": None, "scope": ["R:L0", "R:L1"], "status": "partial",
            "summary": "A small packet for the checks.",
            "baseline": {"tauceti": "a" * 40, "mathlib": "b" * 40, "declarations": []},
            "sources": [{"id": "s", "title": "A book", "authors": "An author", "edition": "First",
                         "url": "https://example.org", "readSections": ["Chapter 1"]}],
            "nodes": nodes, "requests": [], "gaps": [],
            "coverage": [{"stageId": "R:L0", "status": "partial", "remaining": ["More."]},
                         {"stageId": "R:L1", "status": "partial", "remaining": ["More."]}]}


def errors_for(data):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "R.json"
        path.write_text(json.dumps(data))
        errors, _, _ = check(path, None, CONTEXT)
    return errors


class UnitTests(unittest.TestCase):
    def test_a_complete_definition_passes(self):
        self.assertEqual(errors_for(packet([definition()])), [])

    def test_a_definition_needs_three_unit_tests(self):
        node = definition(tests=unit_tests(2))
        self.assertIn("R:L0/object: a definition needs at least 3 unit tests", errors_for(packet([node])))
        missing = definition()
        del missing["tests"]
        self.assertIn("R:L0/object: a definition needs at least 3 unit tests", errors_for(packet([missing])))

    def test_every_unit_test_states_something(self):
        tests = unit_tests(3)
        tests[1] = {"name": "t1", "kind": "computation", "statement": " "}
        self.assertIn("R:L0/object: unit test 't1' needs a name and a statement", errors_for(packet([definition(tests=tests)])))


class Planets(unittest.TestCase):
    def test_a_named_definition_or_theorem_may_be_a_planet(self):
        theorem = definition(nid="R:L0/main", kind="theorem", planet={"name": "Main theorem"})
        del theorem["api"], theorem["tests"]
        self.assertEqual(errors_for(packet([definition(planet={"name": "The object"}), theorem])), [])

    def test_a_lemma_is_not_a_planet(self):
        lemma = definition(nid="R:L0/step", kind="lemma", planet={"name": "A step"})
        del lemma["api"], lemma["tests"]
        self.assertIn("R:L0/step: only definitions, constructions and theorems can be planets", errors_for(packet([lemma])))

    def test_a_planet_name_is_a_short_phrase(self):
        self.assertIn("R:L0/object: a planet needs a name of at most 60 characters",
                      errors_for(packet([definition(planet={"name": "x" * 61})])))
        self.assertIn("R:L0/object: a planet needs a name of at most 60 characters",
                      errors_for(packet([definition(planet={})])))

    def test_at_most_six_planets_per_layer(self):
        six = [definition(nid=f"R:L0/object{i}", planet={"name": f"Object {i}"}) for i in range(6)]
        self.assertEqual(errors_for(packet(six)), [])
        seven = six + [definition(nid="R:L0/object6", planet={"name": "Object 6"})]
        self.assertIn("R:L0: 7 planets; a layer shows at most 6", errors_for(packet(seven)))
        elsewhere = six + [definition(nid="R:L1/object", stage="R:L1", planet={"name": "Another object"})]
        self.assertEqual(errors_for(packet(elsewhere)), [])


if __name__ == "__main__":
    unittest.main()
