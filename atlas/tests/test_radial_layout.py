"""Directions of the areas around Mathlib (scripts/radial_layout.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from radial_layout import crossings, layout, with_fields  # noqa: E402


def symmetric(pairs):
    similarity = {}
    for (a, b), value in pairs.items():
        similarity[(a, b)] = similarity[(b, a)] = value
    return similarity


class Fields(unittest.TestCase):
    def test_areas_of_one_field_rank_above_every_other_pair(self):
        similarity = symmetric({("a", "b"): .1, ("a", "c"): .9, ("b", "c"): .5})
        ranked = with_fields(similarity, {"a": "F", "b": "F", "c": "G"})
        self.assertGreater(ranked[("a", "b")], ranked[("a", "c")])
        self.assertEqual(ranked[("a", "c")], .9)
        self.assertEqual(ranked[("b", "a")], ranked[("a", "b")])

    def test_a_fields_areas_lie_side_by_side(self):
        # Across the two fields, a is most like c and b most like d: alone, that
        # would interleave the fields around the sun.
        similarity = symmetric({("a", "c"): .9, ("b", "d"): .9, ("a", "d"): .2, ("b", "c"): .2, ("a", "b"): .1, ("c", "d"): .1})
        areas = {key: {"distance": 5, "count": 4, "lean": 0} for key in "abcd"}
        directions, _ = layout(areas, similarity, fields={"a": "F", "b": "F", "c": "G", "d": "G"})

        def gap(x, y):
            return abs((directions[x] - directions[y] + 180) % 360 - 180)
        self.assertLess(gap("a", "b"), min(gap("a", "c"), gap("a", "d")))
        self.assertLess(gap("c", "d"), min(gap("c", "a"), gap("c", "b")))


class Crossings(unittest.TestCase):
    """An area lies between two areas of another field when the straight line
    between them passes through its middle (within half its radius of its centre)."""
    RADIUS = {"a": 1000, "b": 1000, "x": 1000}
    SIZE = {"a": 200, "b": 200, "x": 200}
    FIELDS = {"a": "F", "b": "F", "x": "G"}

    def at(self, **degrees):
        import math
        return crossings({k: math.radians(v) for k, v in degrees.items()}, self.RADIUS, self.SIZE, self.FIELDS)

    def test_an_area_in_the_middle_of_the_line_lies_between(self):
        self.assertEqual(self.at(a=0, x=10, b=20), [("x", "a", "b")])

    def test_an_area_beside_the_line_or_beyond_its_ends_does_not(self):
        self.assertEqual(self.at(a=0, b=20, x=40), [])
        self.assertEqual(crossings({"a": 0.0, "b": 0.35, "x": 0.17}, {"a": 1000, "b": 1000, "x": 1400}, self.SIZE, self.FIELDS), [])


class TheAtlas(unittest.TestCase):
    def test_no_area_lies_between_two_areas_of_another_field(self):
        # Each field reads as one region; a field nearer the sun may share its directions.
        import json
        import math
        from radial_layout import galaxy_size, radius_for
        root = Path(__file__).resolve().parents[1]
        fields = {area["id"]: area["field"] for area in json.loads((root / "data" / "galaxies.json").read_text())["galaxies"]}
        placed = json.loads((root / "data" / "galaxy-layout.json").read_text())["galaxies"]
        measured = json.loads((root / "data" / "roadmap-distances.json").read_text())["galaxies"]
        angles = {gid: math.radians(item["direction"]) for gid, item in placed.items()}
        radius = {gid: radius_for(measured[gid]["distance"]) for gid in placed}
        size = {gid: galaxy_size(measured[gid]["roadmaps"]) for gid in placed}
        self.assertEqual(crossings(angles, radius, size, fields), [])


if __name__ == "__main__":
    unittest.main()
