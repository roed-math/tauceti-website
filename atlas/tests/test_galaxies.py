"""Regrouping roadmaps into subject galaxies (scripts/galaxies.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from galaxies import apply_galaxies  # noqa: E402
from classification import galaxy_rule  # noqa: E402


def galaxy(identifier, clusters, direction, field="science"):
    return {"id": identifier, "label": identifier.title(), "short": identifier, "caption": [identifier], "color": "#fff",
            "direction": direction, "clusters": clusters, "description": "About " + identifier, "topics": [identifier], "field": field}


GALAXIES = [galaxy("near", ["a"], 0), galaxy("far", ["b"], 90), galaxy("empty", ["c"], 180)]
FIELDS = [{"id": "science", "label": "Science", "short": "Sci.", "caption": ["Science"], "color": "#abc"},
          {"id": "art", "label": "Art", "short": "Art", "caption": ["Art"], "color": "#def"}]


def snapshot():
    return {"meta": {}, "groups": [{"id": "old"}],
            "roadmaps": [{"id": "R1", "group": "old"}, {"id": "R2", "group": "old"},
                         {"id": "R3", "group": "old", "parentRoadmapId": "R2"}],
            "edges": [{"source": "R1", "target": "R2"}, {"source": "R1", "target": "R3"}]}


def classification():
    return {"roadmaps": {"R1": {"galaxy": "near", "distance": 1, "tags": ["far"]},
                         "R2": {"galaxy": "far", "distance": 9, "tags": []},
                         "R3": {"galaxy": "near", "distance": 3, "tags": ["near"]}}}


class ApplyGalaxies(unittest.TestCase):
    def test_roadmaps_move_and_children_follow_their_parent(self):
        atlas = snapshot()
        apply_galaxies(atlas, GALAXIES, classification(), fields=FIELDS)
        self.assertEqual([r["group"] for r in atlas["roadmaps"]], ["near", "far", "far"])

    def test_groups_are_populated_galaxies_from_nearest_to_farthest(self):
        atlas = snapshot()
        apply_galaxies(atlas, GALAXIES, classification(), fields=FIELDS)
        self.assertEqual([g["id"] for g in atlas["groups"]], ["near", "far"])
        self.assertEqual(atlas["groups"][1]["roadmapIds"], ["R2", "R3"])
        self.assertEqual(atlas["groups"][1]["distance"], 6)
        self.assertEqual(atlas["meta"]["groupCount"], 2)

    def test_regions_record_bridges_and_secondary_tags(self):
        atlas = snapshot()
        regions = apply_galaxies(atlas, GALAXIES, classification(), fields=FIELDS)
        self.assertEqual(regions["groups"]["near"]["bridgeGroups"], ["far"])
        self.assertEqual(regions["roadmapTags"], {"R1": ["far"], "R3": ["near"]})
        self.assertNotIn("empty", regions["groups"])

    def test_every_roadmap_needs_a_known_galaxy(self):
        atlas = snapshot()
        records = classification()
        records["roadmaps"]["R2"]["galaxy"] = "nowhere"
        with self.assertRaises(ValueError):
            apply_galaxies(atlas, GALAXIES, records, fields=FIELDS)

    def test_a_cluster_belongs_to_one_galaxy(self):
        with self.assertRaises(ValueError):
            apply_galaxies(snapshot(), GALAXIES + [galaxy("twin", ["a"], 270)], classification(), fields=FIELDS)


class Fields(unittest.TestCase):
    """Labels at one level of abstraction: fields when zoomed out, their areas when zoomed in."""

    def test_areas_carry_their_field_and_its_colour(self):
        atlas = snapshot()
        apply_galaxies(atlas, GALAXIES, classification(), fields=FIELDS)
        self.assertEqual({g["id"]: (g["field"], g["color"]) for g in atlas["groups"]}, {"near": ("science", "#abc"), "far": ("science", "#abc")})

    def test_fields_list_their_areas_nearest_first(self):
        atlas = snapshot()
        apply_galaxies(atlas, GALAXIES, classification(), fields=FIELDS)
        self.assertEqual(atlas["fields"], [{"id": "science", "label": "Science", "short": "Sci.", "caption": ["Science"], "color": "#abc",
                                             "groupIds": ["near", "far"], "roadmaps": 3, "distance": 4.33}])

    def test_the_only_area_of_a_field_is_named_after_the_field(self):
        atlas = snapshot()
        areas = [galaxy("near", ["a"], 0, field="art"), galaxy("far", ["b"], 90)]
        apply_galaxies(atlas, areas, classification(), fields=FIELDS)
        near = next(g for g in atlas["groups"] if g["id"] == "near")
        self.assertEqual((near["label"], near["short"], near["caption"]), ("Art", "Art", ["Art"]))

    def test_every_area_needs_a_known_field(self):
        with self.assertRaises(ValueError):
            apply_galaxies(snapshot(), GALAXIES[:2] + [galaxy("empty", ["c"], 180, field="nowhere")], classification(), fields=FIELDS)


class GalaxyRule(unittest.TestCase):
    RULES = [{"id": "nt", "clusters": ["elementary"]}, {"id": "computational", "clusters": ["elementary"], "primaryMsc": ["11Y"]},
             {"id": "fields", "clusters": ["elementary"], "primaryMsc": ["11T", "11T7"]}]

    def test_a_primary_class_selects_a_split_galaxy(self):
        rule = galaxy_rule(self.RULES)
        self.assertEqual(rule("elementary", "11Y16"), "computational")
        self.assertEqual(rule("elementary", "11T71"), "fields")
        self.assertEqual(rule("elementary", "11A07"), "nt")
        self.assertEqual(rule("elementary", None), "nt")
        self.assertIsNone(rule("unknown", "11A"))

    def test_every_split_cluster_needs_one_default(self):
        with self.assertRaises(SystemExit):
            galaxy_rule(self.RULES[1:])
        with self.assertRaises(SystemExit):
            galaxy_rule(self.RULES + [{"id": "again", "clusters": ["elementary"]}])


if __name__ == "__main__":
    unittest.main()
