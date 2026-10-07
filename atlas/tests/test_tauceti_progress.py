import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from tauceti_progress import apply, counts  # noqa: E402


def atlas():
    return {
        "roadmaps": [{"id": "tauceti:TauCetiRoadmap/Curves", "origin": "tauceti"}, {"id": "tauceti:TauCetiRoadmap/Covers", "origin": "tauceti"},
                     {"id": "tauceti:TauCetiRoadmap/Gone", "origin": "tauceti"}, {"id": "Proposed", "origin": "campaign"}],
        "stages": [
            {"id": "c0", "owner": "tauceti:TauCetiRoadmap/Curves", "key": "Layer 0"},
            {"id": "c1", "owner": "tauceti:TauCetiRoadmap/Curves", "key": "Layer 1"},
            {"id": "c1a", "owner": "tauceti:TauCetiRoadmap/Curves", "key": "Layer 1a", "parentStageId": "c1"},
            {"id": "c1b", "owner": "tauceti:TauCetiRoadmap/Curves", "key": "Layer 1b", "parentStageId": "c1"},
            {"id": "c1x", "owner": "tauceti:TauCetiRoadmap/Curves", "key": "refinement", "parentStageId": "c1", "expansion": {"kind": "lemma"}},
            {"id": "c2", "owner": "tauceti:TauCetiRoadmap/Curves", "key": "Layer 2"},
            {"id": "v0", "owner": "tauceti:TauCetiRoadmap/Covers", "key": "Layer 0"},
            {"id": "g0", "owner": "tauceti:TauCetiRoadmap/Gone", "key": "Layer 0"},
        ],
        "progress": {"stages": {"c2": {"status": "complete", "basis": "old snapshot"}, "g0": {"status": "planned"}}, "roadmaps": {}},
    }


PROGRESS = {
    "exported_at": "2026-09-28T12:00:00Z",
    "rows": [
        {"id": "TauCetiRoadmap/Curves", "title": "curves", "completed": False, "layer_ids": json.dumps(["Layer 0", "Layer 1", "Layer 2"]),
         "states": json.dumps(["done", "partial", "unassessed"]), "assessment": json.dumps({"source": "marker", "remaining": {"Layer 1": "the dual isogeny"}}),
         "activity": json.dumps({"total": 12, "recent": 5, "last": "2026-09-27T10:00:00Z", "open": 1}), "readme": "TauCetiRoadmap/Curves/README.md",
         "status": {"frontier": [{"name": "The dual isogeny.", "text": "The general construction."}, {"name": "Weil pairing.", "text": "Bilinearity."}]}},
        {"id": "Completed/Covers", "title": "covers", "completed": True, "layer_ids": json.dumps(["Layer 0"]), "states": json.dumps(["partial"]),
         "assessment": json.dumps({"source": "hand-read"}), "activity": json.dumps({"total": 3, "recent": 0})},
        {"id": "TauCetiRoadmap/Fresh", "title": "fresh roadmap", "completed": False, "layer_ids": json.dumps(["Layer 0", "Layer 1"]),
         "states": json.dumps(["untouched", "partial"]), "assessment": None, "activity": None},
    ],
}


class Overlay(unittest.TestCase):
    def setUp(self):
        self.atlas = atlas()
        apply(self.atlas, PROGRESS)
        self.stages = self.atlas["progress"]["stages"]

    def test_layer_states_become_statuses_of_the_layers_leaves(self):
        self.assertEqual(self.stages["c0"]["status"], "complete")
        # A layer with sub-layers passes its state to each of them, never to a refinement.
        self.assertEqual((self.stages["c1a"]["status"], self.stages["c1b"]["status"]), ("in_progress", "in_progress"))
        self.assertNotIn("c1x", self.stages)
        self.assertIn("Tau Ceti Progress page", self.stages["c0"]["basis"])

    def test_an_unassessed_layer_has_no_status_even_if_the_snapshot_had_one(self):
        self.assertNotIn("c2", self.stages)

    def test_a_roadmap_moved_to_completed_matches_its_completed_row(self):
        # The maintainers' archiving is final, whatever the report says of a layer.
        self.assertEqual(self.stages["v0"]["status"], "complete")
        self.assertEqual(self.atlas["progress"]["roadmaps"]["tauceti:TauCetiRoadmap/Covers"]["status"], "complete")

    def test_a_roadmap_the_page_no_longer_reports_keeps_its_snapshot(self):
        self.assertEqual(self.stages["g0"]["status"], "planned")

    def test_notes_activity_and_roadmaps_not_on_the_map_are_kept_for_the_page(self):
        info = self.atlas["taucetiProgress"]
        self.assertEqual(info["exportedAt"], "2026-09-28T12:00:00Z")
        self.assertEqual(info["remaining"]["c1"], "the dual isogeny")
        self.assertEqual(info["roadmaps"]["tauceti:TauCetiRoadmap/Curves"]["activity"]["recent"], 5)
        self.assertEqual(info["roadmaps"]["tauceti:TauCetiRoadmap/Curves"]["status"], "https://github.com/TauCetiProject/TauCetiRoadmap/blob/main/TauCetiRoadmap/Curves/STATUS.md")
        self.assertEqual(info["roadmaps"]["tauceti:TauCetiRoadmap/Curves"]["frontier"], ["The dual isogeny.", "Weil pairing."])
        self.assertEqual([row["id"] for row in info["unplaced"]], ["TauCetiRoadmap/Fresh"])

    def test_counts_are_the_boards_own_layer_counts(self):
        self.assertEqual(counts(PROGRESS), {"done": 1, "partial": 3, "untouched": 1, "unassessed": 1, "total": 6})



class TauCetiOnly(unittest.TestCase):
    def test_the_tau_ceti_build_keeps_only_the_roadmaps_the_board_reports(self):
        from tauceti_progress import tauceti_only
        data = atlas()
        data["stages"].append({"id": "p0", "owner": "Proposed", "key": "P0"})
        data.update({
            "stageEdges": [{"source": "c0", "target": "c1"}, {"source": "p0", "target": "c0"}],
            "edges": [{"source": "tauceti:TauCetiRoadmap/Curves", "target": "tauceti:TauCetiRoadmap/Covers"}, {"source": "Proposed", "target": "tauceti:TauCetiRoadmap/Curves"}],
            "roadmapLinks": [], "decompositions": [], "papers": [{"id": "paper:X"}], "restructurings": [{"id": "RS-1"}], "blueprintLayers": ["Proposed:P0"],
            "opportunities": {"areas": [{"id": "gap"}], "groups": [{"id": "g"}], "notes": []}, "deferredLinks": [], "unresolvedRepositoryLinks": [],
            "stagePresentation": {"c0": {"summary": "x"}, "p0": {"summary": "y"}}, "mappedStageStatuses": {}, "libraryStatuses": {"p0": {"status": "complete"}},
            "landmarkHidden": {"p0::landmark:1": "why"}, "landmarkLabels": {"c0::landmark:1": "Name"}, "roadmapSummaries": {"Proposed": "s", "tauceti:TauCetiRoadmap/Curves": "t"},
            "roadmapClassification": {"roadmaps": {"Proposed": {}, "tauceti:TauCetiRoadmap/Curves": {}}}, "roadmapDistances": {"roadmaps": {"Proposed": {}}},
            "libraryCoverage": {"reviews": {}, "pendingReview": [], "layers": {"p0": {}}},
        })
        apply(data, PROGRESS)
        cut = tauceti_only(data)
        self.assertEqual(cut["variant"], "tauceti")
        self.assertEqual([r["id"] for r in cut["roadmaps"]], ["tauceti:TauCetiRoadmap/Curves", "tauceti:TauCetiRoadmap/Covers"])
        self.assertEqual({s["owner"] for s in cut["stages"]}, {"tauceti:TauCetiRoadmap/Curves", "tauceti:TauCetiRoadmap/Covers"})
        self.assertEqual(cut["stageEdges"], [{"source": "c0", "target": "c1"}])
        self.assertEqual(len(cut["edges"]), 1)
        self.assertEqual((cut["papers"], cut["restructurings"], cut["blueprintLayers"], cut["opportunities"]["areas"]), ([], [], [], []))
        self.assertEqual(list(cut["stagePresentation"]), ["c0"])
        self.assertEqual((cut["libraryStatuses"], cut["landmarkHidden"], cut["libraryCoverage"]["layers"]), ({}, {}, {}))
        self.assertEqual(list(cut["roadmapSummaries"]), ["tauceti:TauCetiRoadmap/Curves"])
        self.assertEqual(list(cut["roadmapClassification"]["roadmaps"]), ["tauceti:TauCetiRoadmap/Curves"])
        self.assertNotIn("g0", cut["progress"]["stages"])



class NewRoadmaps(unittest.TestCase):
    """A roadmap Tau Ceti accepts appears on the Tau Ceti atlas at the next refresh."""
    README = """# Roadmap: restricted products and adelic diagonals

The generic infrastructure for restricted products, used by [global number fields](../GlobalFields/README.md).

## Layer 0: reference families and the integral subgroup

Families of open subgroups.

## Layer 1: functoriality and reindexing

Change of family.
"""

    def board(self, *rows):
        return {"exported_at": "2026-09-28T12:00:00Z", "rows": list(rows)}

    def row(self, name, layers, states, readme=True):
        return {"id": "TauCetiRoadmap/" + name, "title": name.lower(), "completed": False, "readme": f"TauCetiRoadmap/{name}/README.md" if readme else None,
                "layer_ids": json.dumps([layer.split(":")[0] for layer in layers]), "layers": json.dumps(layers), "states": json.dumps(states)}

    def atlas(self):
        return {"roadmaps": [{"id": "tauceti:TauCetiRoadmap/GlobalFields", "origin": "tauceti", "group": "classical", "stages": []},
                             {"id": "tauceti:TauCetiRoadmap/Schemes", "origin": "tauceti", "group": "schemes", "stages": []}],
                "stages": [], "roadmapLinks": [], "progress": {"stages": {}, "roadmaps": {}},
                "groups": [{"id": "classical", "label": "Number fields and class field theory"}, {"id": "schemes", "label": "Schemes, curves and moduli"},
                           {"id": "etale", "label": "Etale cohomology"}],
                "fields": [{"id": "algebraic-geometry", "label": "Algebraic geometry", "groupIds": ["schemes", "etale"]}]}

    def test_a_new_roadmap_is_built_from_its_readme_and_placed_by_its_links(self):
        from tauceti_progress import add_new_roadmaps
        data = self.atlas()
        board = self.board(self.row("RestrictedProducts", ["Layer 0: reference families and the integral subgroup", "Layer 1: functoriality and reindexing"], ["partial", "untouched"]))
        added = add_new_roadmaps(data, board, {"TauCetiRoadmap/RestrictedProducts": self.README})
        self.assertEqual(added, ["tauceti:TauCetiRoadmap/RestrictedProducts"])
        roadmap = data["roadmaps"][-1]
        self.assertEqual((roadmap["title"], roadmap["group"], roadmap["origin"]), ("Restricted products and adelic diagonals", "classical", "tauceti"))
        stages = [s for s in data["stages"] if s["owner"] == roadmap["id"]]
        self.assertEqual([(s["key"], s["title"]) for s in stages], [("Layer 0", "reference families and the integral subgroup"), ("Layer 1", "functoriality and reindexing")])
        self.assertEqual(stages[1]["requires"], [stages[0]["id"]])
        self.assertIn("Families of open subgroups.", stages[0]["description"])
        self.assertEqual(data["roadmapLinks"][-1]["target"], "tauceti:TauCetiRoadmap/GlobalFields")
        apply(data, board)
        self.assertEqual(data["progress"]["stages"][stages[0]["id"]]["status"], "in_progress")
        self.assertEqual(data["taucetiProgress"]["unplaced"], [])

    def test_a_new_roadmap_is_summarised_by_its_opening_prose(self):
        from tauceti_progress import summary
        text = ("# Roadmap: x\n\n| a | b |\n|---|---|\n\nShort opening, see [the ring roadmap](../Rings/README.md).\n\n## Scope\n\n- a list item\n\n```lean\nexample : 1 = 1 := rfl\n```\n\n"
                "**Bold opening.** It still counts as prose.\n\n"
                + " ".join(["Every layer is planned against Mathlib and the sources."] * 8) + "\n")
        words = summary(text).split()
        self.assertTrue(40 <= len(words) <= 160)
        self.assertTrue(summary(text).startswith("Short opening, see the ring roadmap."))
        self.assertNotIn("|", summary(text))
        self.assertIn("Bold opening", summary(text))
        self.assertNotIn("rfl", summary(text))

    def test_a_summary_starts_where_the_readme_says_what_the_roadmap_does(self):
        from tauceti_progress import summary
        text = ("# Roadmap: y\n\nMathlib has the algebra and nothing for it to act on. It has " + "a great many things, " * 90 + "and more.\n\n"
                "This roadmap develops " + "the arithmetic of the groups, " * 12 + "and their local theory.\n")
        self.assertTrue(summary(text).startswith("This roadmap develops"))
        self.assertGreaterEqual(len(summary("# Roadmap: z\n\nShort first sentence. It has " + "a great many things, " * 90 + "and more.\n").split()), 40)

    def test_a_roadmap_with_no_links_is_placed_by_its_title_and_one_with_no_signal_waits(self):
        from tauceti_progress import add_new_roadmaps
        data = self.atlas()
        board = self.board(self.row("RealAlgebraicGeometry", ["Layer 1: univariate real algebra"], ["done"]),
                           self.row("Mystery", ["Layer 0: things"], ["untouched"]))
        added = add_new_roadmaps(data, board, {"TauCetiRoadmap/RealAlgebraicGeometry": "# Real algebraic geometry: sign determination\n\n## Layer 1: univariate real algebra\n\nSturm sequences.\n",
                                                "TauCetiRoadmap/Mystery": "# Roadmap: things\n\n## Layer 0: things\n\nStuff.\n"})
        self.assertEqual(added, ["tauceti:TauCetiRoadmap/RealAlgebraicGeometry"])
        self.assertEqual(data["roadmaps"][-1]["group"], "schemes")
        apply(data, board)
        self.assertEqual([row["id"] for row in data["taucetiProgress"]["unplaced"]], ["TauCetiRoadmap/Mystery"])

    def test_the_title_comes_before_the_roadmaps_a_readme_names_and_a_tie_waits_for_a_choice(self):
        from tauceti_progress import add_new_roadmaps
        data = {"roadmaps": [{"id": "tauceti:TauCetiRoadmap/PDE", "origin": "tauceti", "group": "pde", "stages": []},
                             {"id": "tauceti:TauCetiRoadmap/AlgebraicTopology", "origin": "tauceti", "group": "topology", "stages": []}],
                "stages": [], "roadmapLinks": [], "progress": {"stages": {}, "roadmaps": {}},
                "groups": [{"id": "pde", "label": "Partial differential equations"}, {"id": "topology", "label": "Topology"},
                           {"id": "diffgeom", "label": "Differential geometry"}, {"id": "grouptheory", "label": "Group theory"}],
                "fields": [{"id": "differential-geometry", "label": "Differential geometry", "groupIds": ["diffgeom"]}]}
        # Both READMEs name one roadmap in each of two areas: the roadmaps they build on.
        names = "It builds on [PDE](../PDE/README.md) and [algebraic topology](../AlgebraicTopology/README.md).\n\n## Layer 0: forms\n\nForms.\n"
        board = self.board(self.row("DifferentialGeometry", ["Layer 0: forms"], ["untouched"]), self.row("Peripheral", ["Layer 0: forms"], ["untouched"]))
        readmes = {"TauCetiRoadmap/DifferentialGeometry": "# Roadmap: differential geometry — forms, flows, and degree\n\n" + names,
                   "TauCetiRoadmap/Peripheral": "# Roadmap: peripheral actions\n\n" + names}
        self.assertEqual(add_new_roadmaps(data, board, readmes, {}), ["tauceti:TauCetiRoadmap/DifferentialGeometry"])
        self.assertEqual(data["roadmaps"][-1]["group"], "diffgeom")
        self.assertEqual(data["roadmapClassification"]["roadmaps"]["tauceti:TauCetiRoadmap/DifferentialGeometry"]["rationale"],
                         "Placed provisionally in the area its title names.")
        # The tie is not broken by name; a maintainer's choice settles it.
        chosen = {"TauCetiRoadmap/Peripheral": {"galaxy": "grouptheory", "reason": "group theory about free pro-p groups."}}
        self.assertEqual(add_new_roadmaps(data, board, readmes, chosen), ["tauceti:TauCetiRoadmap/Peripheral"])
        self.assertEqual(data["roadmaps"][-1]["group"], "grouptheory")
        record = data["roadmapClassification"]["roadmaps"]["tauceti:TauCetiRoadmap/Peripheral"]
        self.assertEqual((record["basis"], record["rationale"]), ("provisional", "Placed where the maintainers chose: group theory about free pro-p groups."))


if __name__ == "__main__":
    unittest.main()
