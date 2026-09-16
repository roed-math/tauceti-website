"""Regrouping roadmaps into subject galaxies (scripts/galaxies.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from galaxies import apply_galaxies  # noqa: E402


def galaxy(identifier, clusters, direction):
    return {"id": identifier, "label": identifier.title(), "short": identifier, "caption": [identifier], "color": "#fff",
            "direction": direction, "clusters": clusters, "description": "About " + identifier, "topics": [identifier]}


GALAXIES = [galaxy("near", ["a"], 0), galaxy("far", ["b"], 90), galaxy("empty", ["c"], 180)]


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
        apply_galaxies(atlas, GALAXIES, classification())
        self.assertEqual([r["group"] for r in atlas["roadmaps"]], ["near", "far", "far"])

    def test_groups_are_populated_galaxies_from_nearest_to_farthest(self):
        atlas = snapshot()
        apply_galaxies(atlas, GALAXIES, classification())
        self.assertEqual([g["id"] for g in atlas["groups"]], ["near", "far"])
        self.assertEqual(atlas["groups"][1]["roadmapIds"], ["R2", "R3"])
        self.assertEqual(atlas["groups"][1]["distance"], 6)
        self.assertEqual(atlas["meta"]["groupCount"], 2)

    def test_regions_record_bridges_and_secondary_tags(self):
        atlas = snapshot()
        regions = apply_galaxies(atlas, GALAXIES, classification())
        self.assertEqual(regions["groups"]["near"]["bridgeGroups"], ["far"])
        self.assertEqual(regions["roadmapTags"], {"R1": ["far"], "R3": ["near"]})
        self.assertNotIn("empty", regions["groups"])

    def test_every_roadmap_needs_a_known_galaxy(self):
        atlas = snapshot()
        records = classification()
        records["roadmaps"]["R2"]["galaxy"] = "nowhere"
        with self.assertRaises(ValueError):
            apply_galaxies(atlas, GALAXIES, records)

    def test_a_cluster_belongs_to_one_galaxy(self):
        with self.assertRaises(ValueError):
            apply_galaxies(snapshot(), GALAXIES + [galaxy("twin", ["a"], 270)], classification())


if __name__ == "__main__":
    unittest.main()
