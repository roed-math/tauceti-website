"""Key-definition surveys against PROTOCOL.md section 19 (scripts/check_keydefs.py)."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_keydefs import check  # noqa: E402

AREA = "algebraicgeometry"
JOB = f"KEYDEF-{AREA}"


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def entry(eid="algebraicgeometry/coherent-sheaf", items=(("PAPER-A", ["PAPER-A/1"]), ("PAPER-B", ["PAPER-B/1"])), depends=()):
    return {"id": eid, "name": "Coherent sheaf on a scheme", "short": "Coherent sheaf",
            "define": "An O_X-module on a scheme X that is, on every affine open Spec A, the sheaf of a finitely presented "
                      "A-module, together with the abelian category these form on a noetherian scheme.",
            "library": {"has": ["mathlib:AlgebraicGeometry.Scheme.Modules"], "missing": "coherence as a predicate on O_X-modules"},
            "papers": [{"paper": paper, "items": list(ids)} for paper, ids in items],
            "owners": ["R:L1"], "dependsOn": list(depends), "size": "L",
            "api": [{"kind": "example", "statement": "The structure sheaf of a noetherian scheme is coherent."},
                    {"kind": "example", "statement": "On Spec A for noetherian A, coherent sheaves are finitely generated modules."},
                    {"kind": "counterexample", "statement": "The sheaf of Q on Spec Z is quasi-coherent but not coherent."},
                    {"kind": "theorem", "statement": "Proper pushforward preserves coherence on noetherian schemes."},
                    {"kind": "compatibility", "statement": "Kernels and cokernels of coherent sheaves are coherent on a noetherian scheme."}]}


def survey(**changes):
    data = {"job": JOB, "protocol": "keydef-v1", "area": AREA, "status": "complete",
            "baseline": {"tauceti": "abc", "mathlib": "def"}, "definitions": [entry()],
            "elsewhere": [], "reserve": [{"name": "Standing notation", "items": ["PAPER-C/1"], "reason": "one paper, and notation only"}],
            "routine": ["PAPER-B/2"]}
    data.update(changes)
    return data


class CheckKeydefs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write(self.root / "data/items/0.json", {"paper": "PAPER-A", "items": [{"id": "PAPER-A/1", "kind": "definition"}, {"id": "PAPER-A/2", "kind": "theorem"}]})
        write(self.root / "data/items/1.json", {"paper": "PAPER-B", "items": [{"id": "PAPER-B/1", "kind": "construction"}, {"id": "PAPER-B/2", "kind": "definition"}]})
        write(self.root / "data/items/2.json", {"paper": "PAPER-C", "items": [{"id": "PAPER-C/1", "kind": "definition"}]})
        write(self.root / "data/atlas.json", {"stages": [{"id": "R:L1", "owner": "R"}, {"id": "S:S1", "owner": "S"}], "roadmaps": []})
        write(self.root / "data/galaxies.json", {"galaxies": [{"id": AREA, "label": "Schemes, curves and moduli", "field": "algebraic-geometry"}]})
        write(self.root / f"research/blueprint/keydefs/inputs/{JOB}.json", {"items": [{"id": i} for i in ("PAPER-A/1", "PAPER-B/1", "PAPER-B/2", "PAPER-C/1")]})
        self.path = self.root / f"research/blueprint/keydefs/{JOB}.json"

    def tearDown(self):
        self.tmp.cleanup()

    def result(self, data, index=None):
        write(self.path, data)
        return check(self.path, self.root, index)

    def test_a_sound_survey_passes(self):
        errors, warnings = self.result(survey())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_a_key_definition_needs_two_papers_shown_by_definitions(self):
        errors, _ = self.result(survey(definitions=[entry(items=(("PAPER-A", ["PAPER-A/1"]),))], routine=["PAPER-B/1", "PAPER-B/2"]))
        self.assertTrue(any("at least two papers" in e for e in errors), errors)
        errors, _ = self.result(survey(definitions=[entry(items=(("PAPER-A", ["PAPER-A/2"]), ("PAPER-B", ["PAPER-B/1"])))],
                                       routine=["PAPER-A/1", "PAPER-B/2"]))
        self.assertTrue(any("is a theorem" in e for e in errors), errors)
        errors, _ = self.result(survey(definitions=[entry(items=(("PAPER-A", ["PAPER-B/2"]), ("PAPER-B", ["PAPER-B/1"])))],
                                       routine=["PAPER-A/1"]))
        self.assertTrue(any("is an item of PAPER-B, not of PAPER-A" in e for e in errors), errors)

    def test_the_sample_api_must_discriminate(self):
        bad = entry()
        bad["api"] = [item for item in bad["api"] if item["kind"] != "counterexample"] + [{"kind": "example", "statement": "The zero sheaf is coherent on every scheme."}]
        errors, _ = self.result(survey(definitions=[bad]))
        self.assertTrue(any("at least one counterexample" in e for e in errors), errors)

    def test_every_input_item_is_accounted_for(self):
        errors, _ = self.result(survey(routine=[]))
        self.assertTrue(any("not accounted for" in e and "PAPER-B/2" in e for e in errors), errors)
        errors, warnings = self.result(survey(routine=[], status="partial", remaining=["account for PAPER-B/2"]))
        self.assertEqual(errors, [])
        self.assertTrue(any("still to account for" in w for w in warnings))

    def test_owners_are_atlas_layers_and_never_tau_ceti(self):
        tau = entry()
        tau["owners"] = ["tauceti:TauCetiRoadmap/AlgebraicGeometry#layer-2"]
        errors, _ = self.result(survey(definitions=[tau]))
        self.assertTrue(any("goes under `elsewhere`" in e for e in errors), errors)
        twice = entry()
        twice["owners"] = ["R:L1", "S:S1"]
        errors, warnings = self.result(survey(definitions=[twice]))
        self.assertEqual(errors, [])
        self.assertTrue(any("a duplication" in w for w in warnings))

    def test_dependencies_resolve_and_do_not_cycle(self):
        errors, _ = self.result(survey(definitions=[entry(depends=["algebraicgeometry/nowhere"])]))
        self.assertTrue(any("no key definition of any survey" in e for e in errors), errors)
        first = entry(depends=["algebraicgeometry/second"])
        second = entry("algebraicgeometry/second", depends=["algebraicgeometry/coherent-sheaf"])
        errors, _ = self.result(survey(definitions=[first, second]))
        self.assertTrue(any("cycle" in e for e in errors), errors)
        fine = entry(depends=["tauceti:TauCetiRoadmap/AlgebraicGeometry#layer-2-schemes"])
        self.assertEqual(self.result(survey(definitions=[fine]))[0], [])

    def test_library_claims_are_read_against_the_pinned_index(self):
        errors, _ = self.result(survey(), index={("mathlib", "Other.Name"): ("def", "Mathlib/X.lean", "1")})
        self.assertTrue(any("not a declaration at the pinned commits" in e for e in errors), errors)
        found = {("mathlib", "AlgebraicGeometry.Scheme.Modules"): ("def", "Mathlib/X.lean", "1")}
        self.assertEqual(self.result(survey(), index=found)[0], [])

    def test_one_entry_per_notion_across_surveys(self):
        other = survey(job="KEYDEF-etale", area="etale")
        write(self.root / "data/keydefs/KEYDEF-etale.json", other)
        errors, _ = self.result(survey())
        self.assertTrue(any("already used in data/keydefs/KEYDEF-etale.json" in e for e in errors), errors)
        # The promoted copy of this survey is the same survey, not another.
        (self.root / "data/keydefs/KEYDEF-etale.json").unlink()
        write(self.root / f"data/keydefs/{JOB}.json", survey())
        self.assertEqual(self.result(survey())[0], [])

    def test_names_and_the_file_must_agree(self):
        errors, _ = self.result(survey(job="KEYDEF-other"))
        self.assertTrue(any("must be the file name" in e for e in errors), errors)
        wrong = copy.deepcopy(entry())
        wrong["id"] = "etale/coherent-sheaf"
        errors, _ = self.result(survey(definitions=[wrong]))
        self.assertTrue(any("must start with the area" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
