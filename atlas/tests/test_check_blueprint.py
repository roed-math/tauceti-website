"""Blueprint packet checks: unit tests for definitions and planets for the atlas."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_blueprint import NODE_BUDGET, check  # noqa: E402

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
            "uses": [{"where": "Source, Theorem 2.1", "how": "Its universal property builds the comparison map."}],
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


class Quotation(unittest.TestCase):
    """PROTOCOL.md section 5: citations give a locator and the worker's own words, never a passage of the source."""

    def warnings_for(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "R.json"
            path.write_text(json.dumps(data))
            _, warnings, _ = check(path, None, CONTEXT)
        return warnings

    def test_a_citation_needs_a_locator_and_a_match_but_no_excerpt(self):
        quiet = definition(sources=[{"sourceId": "s", "locator": "Theorem 2.1, p. 1", "match": "It defines the object."}])
        self.assertFalse([e for e in errors_for(packet([quiet])) if "source reference" in e])
        self.assertFalse([w for w in self.warnings_for(packet([quiet])) if "verbatim" in w])
        self.assertTrue([e for e in errors_for(packet([definition(sources=[{"sourceId": "s", "locator": "p. 1"}])])) if "missing match" in e])

    def test_an_excerpt_is_flagged_for_removal(self):
        quoted = definition(sources=[{"sourceId": "s", "locator": "p. 1", "excerpt": "Definition.", "match": "exact"}])
        self.assertTrue([w for w in self.warnings_for(packet([quoted])) if "verbatim source excerpt" in w])


class Passes(unittest.TestCase):
    """PROTOCOL.md section 0: a pass is complete at the node budget or when every stage is planned."""

    def lemmas(self, count):
        return [definition(f"R:L0/item-{i}") for i in range(count)]

    def test_a_pass_may_not_end_early_while_stages_are_unplanned(self):
        data = packet(self.lemmas(3))
        data["status"] = "complete"
        self.assertTrue(any("under the budget" in e for e in errors_for(data)))

    def test_a_pass_ends_when_every_stage_is_planned(self):
        data = packet([definition(), definition("R:L1/other", "R:L1")])
        data["status"] = "complete"
        data["coverage"] = [{"stageId": "R:L0", "status": "planned", "remaining": ["Refine the comparison."]},
                            {"stageId": "R:L1", "status": "closed", "remaining": []}]
        self.assertEqual([e for e in errors_for(data) if "budget" in e or "coverage" in e], [])

    def test_at_the_budget_open_stages_go_to_follow_ups_with_what_remains(self):
        data = packet(self.lemmas(NODE_BUDGET))
        data["status"] = "complete"
        self.assertEqual([e for e in errors_for(data) if "budget" in e or "remaining" in e], [])
        data["coverage"][1] = {"stageId": "R:L1", "status": "not_read"}
        self.assertTrue(any("without a `remaining` list" in e for e in errors_for(data)))

    def test_a_planned_stage_must_be_realised_here_or_in_the_roadmaps_other_packets(self):
        data = packet([definition()])
        data["coverage"][1] = {"stageId": "R:L1", "status": "planned", "remaining": []}
        self.assertTrue(any("planned but no node realises it" in e for e in errors_for(data)))
        atlas, stages, roadmaps, nodes, _, reserved = CONTEXT
        other = {"roadmapId": "R", "nodes": [definition("R:L1/elsewhere", "R:L1")]}
        context = (atlas, stages, roadmaps, nodes, {Path("/elsewhere/R--L1.json"): other}, reserved)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "R.json"
            path.write_text(json.dumps(data))
            errors, _, _ = check(path, None, context)
        self.assertFalse(any("realises" in e for e in errors))


class Prerequisites(unittest.TestCase):
    """PROTOCOL.md section 3: a prerequisite is a node, a library declaration or an atlas stage."""
    TAU = "tauceti:TauCetiRoadmap/StableReduction#layer-3-prestable-semistable-stable-and-pointed-curves"

    def results(self, data):
        atlas, stages, roadmaps, nodes, blueprints, reserved = CONTEXT
        context = (atlas, {**stages, self.TAU: "tauceti:TauCetiRoadmap/StableReduction"}, roadmaps, nodes, blueprints, reserved)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "R.json"
            path.write_text(json.dumps(data))
            errors, warnings, _ = check(path, None, context)
        return errors, warnings

    def test_a_tau_ceti_layer_is_a_stage_not_a_library_declaration(self):
        errors, warnings = self.results(packet([definition(prerequisites=[self.TAU])]))
        self.assertFalse(any("baseline prerequisite" in error for error in errors), errors)
        self.assertTrue(any("without a request entry" in warning for warning in warnings), warnings)

    def test_an_undeclared_library_declaration_is_still_an_error(self):
        errors, _ = self.results(packet([definition(prerequisites=["tauceti:TauCeti.StableCurve.mk"])]))
        self.assertTrue(any("baseline prerequisite tauceti:TauCeti.StableCurve.mk is not listed" in error for error in errors), errors)


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


class Uses(unittest.TestCase):
    # The API outline is derived from where and how the definition is used.
    def test_a_definition_records_where_it_is_used(self):
        node = definition()
        del node["uses"]
        self.assertIn("R:L0/object: a definition needs its uses (where and how it is used)", errors_for(packet([node])))

    def test_every_use_says_where_and_how(self):
        node = definition(uses=[{"where": "Source, Theorem 2.1", "how": ""}])
        self.assertIn("R:L0/object: each use needs 'where' and 'how'", errors_for(packet([node])))


class Planets(unittest.TestCase):
    def test_a_named_definition_or_theorem_may_be_a_planet(self):
        theorem = definition(nid="R:L0/main", kind="theorem", planet={"name": "Main theorem"})
        del theorem["api"], theorem["tests"], theorem["uses"]
        self.assertEqual(errors_for(packet([definition(planet={"name": "The object"}), theorem])), [])

    def test_a_lemma_is_not_a_planet(self):
        lemma = definition(nid="R:L0/step", kind="lemma", planet={"name": "A step"})
        del lemma["api"], lemma["tests"], lemma["uses"]
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



class SourceMistakes(unittest.TestCase):
    def test_a_packet_records_the_mistakes_found_in_its_sources(self):
        data = packet([definition()])
        data["sourceIssues"] = [{"id": "R/E1", "kind": "gap", "locator": "Lemma 3", "printed": "Clearly f is surjective.",
                                 "correction": "Surjectivity needs the hypothesis n ≥ 2.", "reason": "It fails for n = 1.",
                                 "affects": "the proof", "known": "new", "searched": ["arXiv v2"]}]
        self.assertEqual(errors_for(data), [])
        data["sourceIssues"][0]["id"] = "Q/E1"
        self.assertIn("finding id 'Q/E1' must start with R/E", errors_for(data))


class Restructuring(unittest.TestCase):
    def test_a_layer_an_accepted_restructuring_drops_is_closed_without_nodes(self):
        import check_blueprint
        data = packet([definition()])
        data["coverage"][1] = {"stageId": "R:L1", "status": "closed", "remaining": [], "note": "Dropped by RS-01: S:S1 supplies it."}
        self.assertIn("coverage R:L1: closed but no node realises it", errors_for(data))
        check_blueprint.DROPPED_STAGES.add("R:L1")
        try:
            self.assertEqual(errors_for(data), [])
        finally:
            check_blueprint.DROPPED_STAGES.discard("R:L1")


if __name__ == "__main__":
    unittest.main()
