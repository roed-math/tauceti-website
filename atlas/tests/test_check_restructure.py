"""Restructuring proposals (PROTOCOL.md section 15): the checks a pull request must pass."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_restructure import check  # noqa: E402

ROADMAPS = {"A": "campaign", "B": "campaign", "tauceti:T": "tauceti"}
STAGES = {"A:0": "A", "A:1": "A", "B:0": "B", "B:1": "B", "tauceti:T:0": "tauceti:T"}
FAMILY = {"id": "RS-01", "members": [{"id": "A"}, {"id": "B"}], "anchors": [{"id": "tauceti:T"}]}


def proposal(**changes):
    data = {"family": "RS-01",
            "roadmaps": {"A": {"action": "keep", "reason": "Owns the construction."},
                         "B": {"action": "extend", "extends": "tauceti:T", "title": "T, Part II: more", "reason": "Starts where T stops."}},
            "layers": {"B:0": {"action": "drop", "suppliedBy": ["tauceti:T:0"], "reason": "T owns it."}},
            "links": [{"source": "tauceti:T:0", "target": "B:1", "reason": "B:1 used B:0's target."}],
            "owners": [{"target": "The construction", "owner": "tauceti:T:0", "formerly": ["B:0"]}]}
    data.update(changes)
    return data


def errors(data):
    return check(data, FAMILY, ROADMAPS, STAGES)


class Proposals(unittest.TestCase):
    def test_a_complete_proposal_passes(self):
        self.assertEqual(errors(proposal()), [])

    def test_every_member_is_decided(self):
        data = proposal(roadmaps={"A": {"action": "keep", "reason": "Owns it."}})
        self.assertIn("no decision for member roadmap B", errors(data))

    def test_a_tau_ceti_roadmap_never_changes(self):
        data = proposal()
        data["roadmaps"]["tauceti:T"] = {"action": "retire", "reason": "Covered."}
        data["layers"]["tauceti:T:0"] = {"action": "drop", "suppliedBy": ["A:0"], "reason": "A owns it."}
        found = errors(data)
        self.assertIn("tauceti:T is a Tau Ceti roadmap and never changes", found)
        self.assertIn("tauceti:T:0 belongs to a Tau Ceti roadmap and never changes", found)

    def test_a_dropped_layer_names_its_supplier(self):
        data = proposal(layers={"B:0": {"action": "drop", "reason": "Duplicate."}})
        self.assertIn("B:0: a dropped layer names the layers that supply it (suppliedBy)", errors(data))

    def test_an_extension_names_what_it_extends(self):
        data = proposal()
        del data["roadmaps"]["B"]["extends"]
        self.assertIn("B: an extension names the roadmap it extends", errors(data))

    def test_unknown_ids_are_errors(self):
        data = proposal(links=[{"source": "tauceti:T:9", "target": "B:1", "reason": "?"}])
        self.assertIn("link source tauceti:T:9 is not a layer of the atlas", errors(data))

    def test_the_libraries_may_supply_a_dropped_layer(self):
        # UPSTREAM: ids stand for the libraries and upstream sources, as in the atlas's own links.
        data = proposal(layers={"B:0": {"action": "drop", "suppliedBy": ["UPSTREAM:Mathlib:CommutativeAlgebra"], "reason": "Mathlib has it."}},
                        links=[{"source": "UPSTREAM:Mathlib:CommutativeAlgebra", "target": "B:1", "reason": "B:1 used it."}],
                        owners=[{"target": "Localisation", "owner": "UPSTREAM:Mathlib:CommutativeAlgebra", "formerly": ["B:0"]}])
        self.assertEqual(errors(data), [])

    def test_a_retired_roadmap_leaves_no_layer_behind(self):
        data = proposal()
        data["roadmaps"]["A"] = {"action": "retire", "reason": "Everything is owned elsewhere."}
        data["layers"]["A:0"] = {"action": "drop", "suppliedBy": ["tauceti:T:0"], "reason": "T owns it."}
        self.assertIn("A is retired but its layer A:1 is neither moved nor dropped", errors(data))


if __name__ == "__main__":
    unittest.main()
