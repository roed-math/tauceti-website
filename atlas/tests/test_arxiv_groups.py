import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from arxiv_groups import ORDER, UNCLASSIFIED, area_categories, categories_of, group_by_arxiv  # noqa: E402

AREAS = {"math.NT": {"areas": ["algebraicnt", "padic"], "default": "algebraicnt"}, "math.AG": {"areas": ["algebraicgeometry", "etale", "padic"], "default": "algebraicgeometry"},
         "math.FA": {"areas": ["analysis"], "default": "analysis"}, "math.DS": {"areas": ["analysis"], "default": "analysis"}}


def atlas(*roadmaps, edges=(), links=()):
    return {"meta": {}, "roadmaps": [{"id": rid, "group": group} for rid, group in roadmaps],
            "edges": [{"source": s, "target": t} for s, t in edges], "roadmapLinks": [{"source": s, "target": t} for s, t in links],
            "groups": [{"id": "etale"}], "fields": [{"id": "algebraic-geometry", "groupIds": ["etale"]}]}


class Categories(unittest.TestCase):
    """Each roadmap's arXiv category, and how it was settled."""

    def test_a_roadmap_has_the_category_its_metadata_declares(self):
        found = categories_of(atlas(("tauceti:TauCetiRoadmap/Weil", "etale")), {"tauceti:TauCetiRoadmap/Weil": "math.AG"})
        self.assertEqual(found, {"tauceti:TauCetiRoadmap/Weil": ("math.AG", "declared")})

    def test_one_that_declares_none_takes_the_nearest_declared_folder_above_it_on_the_map_or_not(self):
        found = categories_of(atlas(("tauceti:TauCetiRoadmap/OperatorTheory/Unbounded", "analysis")), {"tauceti:TauCetiRoadmap/OperatorTheory": "math.FA"})
        self.assertEqual(found["tauceti:TauCetiRoadmap/OperatorTheory/Unbounded"], ("math.FA", "parent"))

    def test_else_the_category_most_of_its_linked_roadmaps_have_when_they_clearly_agree(self):
        map_ = atlas(("tauceti:A", "x"), ("tauceti:B", "x"), ("tauceti:C", "x"), ("tauceti:Lead", "x"), ("tauceti:Tie", "x"),
                     edges=[("tauceti:A", "tauceti:Lead"), ("tauceti:B", "tauceti:Lead"), ("tauceti:A", "tauceti:Tie")], links=[("tauceti:Lead", "tauceti:C"), ("tauceti:Tie", "tauceti:C")])
        found = categories_of(map_, {"tauceti:A": "math.NT", "tauceti:B": "math.NT", "tauceti:C": "math.AG"})
        self.assertEqual(found["tauceti:Lead"], ("math.NT", "links"))
        # One link to each: no lead, and no area to fall back on.
        self.assertEqual(found["tauceti:Tie"], (UNCLASSIFIED, "none"))

    def test_else_the_category_of_the_subject_its_title_named_then_none(self):
        map_ = atlas(("tauceti:Flows", "analysis"), ("tauceti:Walks", "unclassified"))
        found = categories_of(map_, {}, area_categories(AREAS))
        self.assertEqual(found, {"tauceti:Flows": ("math.FA", "area"), "tauceti:Walks": (UNCLASSIFIED, "none")})

    def test_an_area_reads_back_to_the_first_category_whose_default_it_is(self):
        self.assertEqual(area_categories(AREAS), {"algebraicnt": "math.NT", "algebraicgeometry": "math.AG", "analysis": "math.FA",
                                                  "padic": "math.NT", "etale": "math.AG"})

    def test_undeclared_sub_roadmaps_settle_together_once_some_are_placed(self):
        # Two links only to its undeclared sibling, which its title places: it follows the sibling.
        map_ = atlas(("tauceti:P/Counting/One", "etale"), ("tauceti:P/Counting/Two", "unclassified"),
                     links=[("tauceti:P/Counting/Two", "tauceti:P/Counting/One")])
        found = categories_of(map_, {}, area_categories(AREAS))
        self.assertEqual(found, {"tauceti:P/Counting/One": ("math.AG", "area"), "tauceti:P/Counting/Two": ("math.AG", "links")})


class Grouping(unittest.TestCase):
    """The map's galaxies become the arXiv categories, round Mathlib in a fixed order."""

    def test_each_category_is_a_galaxy_named_with_its_identifier_and_fields_go(self):
        map_ = atlas(("tauceti:Weil", "etale"), ("tauceti:Heights", "algebraicnt"), ("tauceti:Walks", "unclassified"))
        counts = group_by_arxiv(map_, {"tauceti:Weil": "math.AG", "tauceti:Heights": "math.NT"}, AREAS)
        self.assertEqual(counts, {"math.NT": 1, "math.AG": 1, UNCLASSIFIED: 1})
        groups = {group["id"]: group for group in map_["groups"]}
        self.assertEqual((groups["math.AG"]["label"], groups["math.AG"]["caption"], groups["math.AG"]["arxiv"]),
                         ("Algebraic Geometry (math.AG)", ["Algebraic Geometry", "math.AG"], "math.AG"))
        self.assertEqual((groups[UNCLASSIFIED]["label"], groups[UNCLASSIFIED]["arxiv"]), ("No arXiv category", None))
        self.assertEqual(map_["fields"], [])
        self.assertEqual({r["id"]: (r["group"], r["arxiv"]) for r in map_["roadmaps"]},
                         {"tauceti:Weil": ("math.AG", "math.AG"), "tauceti:Heights": ("math.NT", "math.NT"), "tauceti:Walks": (UNCLASSIFIED, None)})
        self.assertIn("metadata.toml declares", map_["roadmapClassification"]["roadmaps"]["tauceti:Weil"]["rationale"])

    def test_galaxies_go_round_in_the_fixed_order_each_given_a_share_that_grows_with_it(self):
        self.assertEqual(ORDER[:2], ["math.NT", "math.AG"])
        self.assertEqual(ORDER[ORDER.index("math.RT") - 1:ORDER.index("math.RT") + 1], ["math.QA", "math.RT"])
        roadmaps = [(f"tauceti:N{i}", "x") for i in range(9)] + [("tauceti:G", "x"), ("tauceti:R", "x")]
        map_ = atlas(*roadmaps)
        group_by_arxiv(map_, {**{f"tauceti:N{i}": "math.NT" for i in range(9)}, "tauceti:G": "math.AG", "tauceti:R": "math.RT"})
        direction = {group["id"]: group["direction"] for group in map_["groups"]}
        # Shares 4 : 2 : 2 of the circle, from the bottom of the map: number theory's middle is a quarter of the way round.
        self.assertEqual([group["id"] for group in map_["groups"]], ["math.NT", "math.AG", "math.RT"])
        self.assertEqual(direction, {"math.NT": 180.0, "math.AG": 315.0, "math.RT": 45.0})

    def test_what_uses_a_roadmap_is_counted_again_by_category(self):
        map_ = atlas(("tauceti:A", "x"), ("tauceti:B", "x"), ("tauceti:C", "x"), edges=[("tauceti:A", "tauceti:B"), ("tauceti:A", "tauceti:C")])
        map_["roadmapDistances"] = {"roadmaps": {"tauceti:A": {"distance": 3, "usedBy": [{"galaxy": "etale", "roadmaps": 9}]}}, "galaxies": {"etale": {}}}
        group_by_arxiv(map_, {"tauceti:A": "math.NT", "tauceti:B": "math.AG", "tauceti:C": "math.NT"})
        self.assertEqual(map_["roadmapDistances"]["roadmaps"]["tauceti:A"]["usedBy"], [{"galaxy": "math.AG", "roadmaps": 1}])
        self.assertEqual(map_["roadmapDistances"]["galaxies"], {})


if __name__ == "__main__":
    unittest.main()
