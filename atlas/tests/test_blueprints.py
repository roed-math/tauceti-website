"""Promoted blueprints in the atlas build (scripts/blueprints.py, PROTOCOL.md sections 6, 7, 8 and 14)."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from blueprints import add_new_roadmaps, merge_blueprints, replaced_layers, trim_decompositions  # noqa: E402


def stage(sid, requires=()):
    return {"id": sid, "owner": sid.split(":")[0], "key": sid.split(":")[1], "title": "Layer " + sid, "description": "Targets of " + sid,
            "requires": list(requires), "consumers": [], "parentStageId": None, "isLeaf": True}


def atlas():
    return {"meta": {}, "roadmaps": [
                {"id": "R", "title": "Roadmap R", "origin": "campaign", "readme": "# R", "sourcePath": "content/campaign/R/README.md",
                 "stages": ["R:L0", "R:L1"], "prerequisites": [], "consumers": []},
                {"id": "S", "title": "Roadmap S", "origin": "campaign", "readme": "# S", "sourcePath": "content/campaign/S/README.md",
                 "stages": ["S:S1"], "prerequisites": [], "consumers": []}],
            "stages": [stage("R:L0"), stage("R:L1", ["R:L0"]), stage("S:S1")],
            "stageEdges": [{"source": "R:L0", "target": "R:L1"}], "edges": []}


def node(nid, kind, title, prerequisites=(), planet=None, parent=None):
    item = {"id": nid, "parentStageId": parent or nid.split("/")[0], "realises": [nid.split("/")[0]], "title": title, "kind": kind,
            "statement": "Statement of " + title, "hypotheses": ["h"], "proofSteps": ["p"], "acceptance": ["a"],
            "prerequisites": list(prerequisites), "sources": [], "implementationStatus": "unchecked"}
    if planet:
        item["planet"] = {"name": planet}
    return item


def packet():
    return {"roadmapId": "R", "protocol": "blueprint-v1", "part": None, "status": "partial", "scope": ["R:L0", "R:L1"],
            "summary": "The blueprint of R.", "review": {"status": "accepted", "reviewer": "independent-review-REV-R", "date": "2026-09-22"},
            "nodes": [node("R:L0/a", "definition", "The alpha object", planet="Alpha object"),
                      node("R:L0/b", "lemma", "A lemma on alpha", ["R:L0/a"]),
                      node("R:L0/c", "theorem", "The beta theorem", ["R:L0/b", "S:S1", "mathlib:Foo"], planet="Beta theorem"),
                      node("R:L1/d", "definition", "The delta object", ["R:L0/c"])],
            "coverage": [{"stageId": "R:L0", "status": "source_decomposed", "remaining": []}]}


class Blueprints(unittest.TestCase):
    def merged(self, packets=None):
        return merge_blueprints(atlas(), packets or [("R", packet())], documents={"R": "data/blueprints/R.md"})

    def test_the_planets_the_workers_chose_orbit_their_layers(self):
        result = self.merged()
        planets = {s["id"]: s for s in result["stages"] if s.get("expansion")}
        self.assertEqual(sorted(planets), ["R:L0/a", "R:L0/c"])
        self.assertEqual(planets["R:L0/c"]["title"], "Beta theorem")
        self.assertEqual(planets["R:L0/c"]["parentStageId"], "R:L0")
        self.assertTrue(planets["R:L0/c"]["expansion"]["blueprint"])
        self.assertEqual(planets["R:L0/c"]["expansion"]["statement"], "Statement of The beta theorem")
        self.assertEqual(result["blueprintLayers"], ["R:L0"])

    def test_every_declaration_is_listed_under_its_layer_with_the_document(self):
        blueprint = next(r for r in self.merged()["roadmaps"] if r["id"] == "R")["blueprint"]
        self.assertEqual(blueprint["layers"]["R:L0"], [["L0/a", "definition", "The alpha object", 0], ["L0/b", "lemma", "A lemma on alpha", 0],
                                                        ["L0/c", "theorem", "The beta theorem", 0]])
        self.assertEqual(blueprint["layers"]["R:L1"], [["L1/d", "definition", "The delta object", 0]])
        self.assertEqual(blueprint["files"], ["R"])
        self.assertEqual(blueprint["documents"], ["data/blueprints/R.md"])
        self.assertEqual((blueprint["declarations"], blueprint["planets"]), (4, 2))

    def test_planets_are_linked_through_the_lemmas_between_them(self):
        edges = {(e["source"], e["target"]) for e in self.merged()["stageEdges"]}
        self.assertIn(("R:L0/a", "R:L0/c"), edges)

    def test_a_prerequisite_from_another_roadmap_links_the_layers(self):
        result = self.merged()
        edge = next(e for e in result["stageEdges"] if (e["source"], e["target"]) == ("S:S1", "R:L0"))
        self.assertEqual(edge["kind"], "blueprint")
        self.assertIn("The beta theorem", edge["evidence"][0]["reason"])
        r = next(x for x in result["roadmaps"] if x["id"] == "R")
        self.assertIn("S", r["prerequisites"])
        self.assertIn("S:S1", next(s for s in result["stages"] if s["id"] == "R:L0")["requires"])

    def test_a_link_counts_the_declarations_that_use_it(self):
        data = packet()
        data["nodes"].append(node("R:L0/e", "lemma", "Another use of S", ["S:S1"]))
        edge = next(e for e in merge_blueprints(atlas(), [("R", data)], documents={})["stageEdges"] if (e["source"], e["target"]) == ("S:S1", "R:L0"))
        self.assertEqual(edge["uses"], 2)

    def test_a_link_that_would_close_a_cycle_is_left_out_and_recorded(self):
        base = atlas()
        base["stageEdges"].append({"source": "R:L1", "target": "S:S1"})
        result = merge_blueprints(base, [("R", packet())], documents={})
        self.assertNotIn(("S:S1", "R:L0"), {(e["source"], e["target"]) for e in result["stageEdges"]})
        self.assertEqual(next(r for r in result["roadmaps"] if r["id"] == "R")["blueprint"]["skippedLinks"], [["S:S1", "R:L0"]])

    def test_the_parts_of_a_roadmap_make_one_blueprint(self):
        first, second = packet(), packet()
        first.update(part="P1", scope=["R:L0"], nodes=first["nodes"][:3])
        second.update(part="P2", scope=["R:L1"], nodes=second["nodes"][3:])
        blueprint = next(r for r in self.merged([("R--P1", first), ("R--P2", second)])["roadmaps"] if r["id"] == "R")["blueprint"]
        self.assertEqual(blueprint["files"], ["R--P1", "R--P2"])
        self.assertEqual(blueprint["layers"]["R:L1"], [["L1/d", "definition", "The delta object", 1]])

    def test_the_snapshot_is_not_changed(self):
        base = atlas()
        kept = copy.deepcopy(base)
        merge_blueprints(base, [("R", packet())], documents={})
        self.assertEqual(base, kept)


class Decompositions(unittest.TestCase):
    def test_a_blueprint_replaces_the_decomposition_of_the_layers_it_covers(self):
        older = {"roadmapId": "R", "nodes": [{"id": "R:L0/x", "parentStageId": "R:L0"}, {"id": "R:L1/y", "parentStageId": "R:L1"}],
                 "coverage": [{"stageId": "R:L0"}, {"stageId": "R:L1"}],
                 "links": [{"source": "R:L0/x", "target": "R:L1/y"}, {"source": "S:S1", "target": "R:L1/y"}]}
        covered = replaced_layers([("R", dict(packet(), scope=["R:L0"]))])
        self.assertEqual(covered, {"R:L0"})
        [kept] = trim_decompositions([older], covered)
        self.assertEqual([n["id"] for n in kept["nodes"]], ["R:L1/y"])
        self.assertEqual(kept["coverage"], [{"stageId": "R:L1"}])
        self.assertEqual(kept["links"], [{"source": "S:S1", "target": "R:L1/y"}])
        self.assertEqual(trim_decompositions([older], {"R:L0", "R:L1"}), [])


class NewRoadmaps(unittest.TestCase):
    def definition(self, **extra):
        return dict({"id": "N", "title": "A new roadmap", "group": "diophantine", "summary": "Why N.", "readme": "# N",
                     "prerequisites": ["S"], "stages": [{"key": "N.0", "title": "Start", "description": "First layer.", "requires": ["S:S1"]},
                                                       {"key": "N.1", "title": "End", "description": "Last layer.", "requires": ["N:N.0", "X:Y"]}]},
                    **extra)

    def records(self):
        return {"R": {"galaxy": "padic", "distance": 6}, "S": {"galaxy": "langlands", "distance": 7}}

    def test_a_new_roadmap_enters_with_its_layers_and_links(self):
        result, records = add_new_roadmaps(atlas(), [self.definition()], self.records(), {"padic": "p-adic", "langlands": "galois"})
        roadmap = next(r for r in result["roadmaps"] if r["id"] == "N")
        self.assertEqual((roadmap["origin"], roadmap["lifecycle"], roadmap["stages"]), ("campaign", "proposed", ["N:N.0", "N:N.1"]))
        edges = {(e["source"], e["target"]) for e in result["stageEdges"]}
        self.assertTrue({("S:S1", "N:N.0"), ("N:N.0", "N:N.1")} <= edges)
        self.assertEqual(roadmap["pendingLinks"], [["X:Y", "N:N.1"]])
        self.assertIn("S", roadmap["prerequisites"])
        self.assertIn("N", next(r for r in result["roadmaps"] if r["id"] == "S")["consumers"])

    def test_it_is_placed_by_its_area_then_its_base_then_its_prerequisites(self):
        galaxies = {"padic": "p-adic", "langlands": "galois"}
        self.assertEqual(add_new_roadmaps(atlas(), [self.definition()], self.records(), galaxies)[1]["N"]["galaxy"], "langlands")
        self.assertEqual(add_new_roadmaps(atlas(), [self.definition(parent="R")], self.records(), galaxies)[1]["N"]["galaxy"], "padic")
        self.assertEqual(add_new_roadmaps(atlas(), [self.definition(area="padic", parent="S")], self.records(), galaxies)[1]["N"]["galaxy"], "padic")
        with self.assertRaises(ValueError):
            add_new_roadmaps(atlas(), [self.definition(prerequisites=[], stages=[])], self.records(), galaxies)

    def test_a_group_that_names_an_area_places_it(self):
        galaxies = {"padic": "p-adic", "langlands": "galois"}
        self.assertEqual(add_new_roadmaps(atlas(), [self.definition(group="padic")], self.records(), galaxies)[1]["N"]["galaxy"], "padic")

    def test_without_an_area_or_a_base_it_goes_where_its_group_usually_is(self):
        grouped = atlas()
        grouped["roadmaps"][0]["group"] = "diophantine"
        galaxies = {"padic": "p-adic", "langlands": "galois"}
        self.assertEqual(add_new_roadmaps(grouped, [self.definition()], self.records(), galaxies)[1]["N"]["galaxy"], "padic")


if __name__ == "__main__":
    unittest.main()
