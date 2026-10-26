"""The data step of the Mathlib disk (scripts/mathlib_disk.py). It needs evidence-core, numpy and PyYAML
(requirements-data.txt): run it with the data environment, `.venv/bin/python -m unittest tests.test_mathlib_disk`.
Without them these tests are skipped, so the page's own suite runs with the standard library alone."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import evidence_core  # noqa: F401
    import numpy  # noqa: F401
    import yaml  # noqa: F401
except ImportError:
    md = None
else:
    import mathlib_disk as md  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "mathlib"


@unittest.skipUnless(md, "needs requirements-data.txt")
class Catalogues(unittest.TestCase):
    """The landmarks: the declarations Mathlib's catalogues name, with the catalogues' words for them."""

    def setUp(self):
        self.found = md.catalogue_entries(FIXTURES / "docs")

    def test_a_subject_tree_names_its_declarations_with_their_place_in_the_tree(self):
        self.assertEqual(self.found["CompleteSpace"]["catalogues"], [["overview", "Topology / Metric spaces"]])
        self.assertEqual(self.found["CompleteSpace"]["title"], "Complete metric space")

    def test_a_declaration_named_twice_keeps_every_catalogue(self):
        self.assertEqual(self.found["IsDedekindDomain"]["catalogues"],
                         [["overview", "General algebra / Rings"], ["undergrad", "Ring Theory / Ideals"]])

    def test_the_famous_lists_title_it_first_freeks_hundred_before_the_thousand(self):
        entry = self.found["irrational_sqrt_two"]
        self.assertEqual(entry["title"], "The Irrationality of the Square Root of 2")
        self.assertEqual([c[0] for c in entry["catalogues"]], ["100", "1000"])

    def test_every_declaration_of_an_entry_is_a_landmark_and_one_without_any_is_none(self):
        self.assertEqual(self.found["num_dvd_of_is_root"]["title"], "Rational root theorem")
        self.assertIn("den_dvd_of_is_root", self.found)
        self.assertNotIn("", self.found)
        self.assertFalse(any("Prime Number Theorem" == e["title"] for e in self.found.values()))


@unittest.skipUnless(md, "needs requirements-data.txt")
class PlainTitles(unittest.TestCase):
    """A catalogue's TeX ($\\Z/n\\Z$) becomes plain Unicode, so that a label on the map reads as its panel does."""

    def test_tex_in_a_title_becomes_unicode(self):
        for tex, plain in (("$\\Z/n\\Z$ and its invertible elements", "ℤ/nℤ and its invertible elements"),
                           ("$L^p$ space", "Lᵖ space"), ("Hensel's lemma (for $\\mathbb{Z}_p$)", "Hensel's lemma (for ℤₚ)"),
                           ("$A[{X_i}]$ is a UFD when $A$ is a UFD", "A[Xᵢ] is a UFD when A is a UFD"),
                           ("Norms $\\lVert\\cdot\\rVert_p$ on $\\R^n$ and $\\C^n$", "Norms ‖·‖ₚ on ℝⁿ and ℂⁿ"),
                           ("Fourier transforms on $\\mathcal{S}(\\R^d)$", "Fourier transforms on 𝒮(ℝᵈ)"),
                           ("$\\varepsilon$-NFA", "ε-NFA"), ("Multiplication by a function $C^\\infty$ of slow growth", "Multiplication by a function C^∞ of slow growth"),
                           ("Euler's totient function ($\\varphi$)", "Euler's totient function (φ)"), ("Group", "Group")):
            self.assertEqual(md.plain_tex(tex), plain)


@unittest.skipUnless(md, "needs requirements-data.txt")
class Headers(unittest.TestCase):
    """The main definitions and results a file's header lists, with its words for each."""

    def setUp(self):
        self.found = md.header_entries(FIXTURES)

    def test_each_name_a_main_section_lists_with_the_bullets_words(self):
        listed = dict(self.found["Mathlib.RingTheory.Example"])
        self.assertEqual(listed["IsDedekindDomain"], "defines a Dedekind domain as a Dedekind ring that is a domain.")
        self.assertEqual(listed["span"], "the submodule spanned by a set.")

    def test_a_bullet_naming_several_gives_each_the_same_words_across_subheadings(self):
        listed = dict(self.found["Mathlib.RingTheory.Example"])
        for name in ("Ideal.isMaximal_iff", "Ideal.IsMaximal.ne_top", "Ideal.exists_le_maximal"):
            self.assertEqual(listed[name], "maximal ideals, characterised.")

    def test_notation_and_other_sections_are_not_names(self):
        names = [name for name, _ in self.found["Mathlib.RingTheory.Example"]]
        self.assertNotIn("notThisOne", names)
        self.assertFalse(any(" " in name for name in names))

    def test_resolving_a_written_name(self):
        names = {"IsDedekindDomain", "Submodule.span", "Set.span", "Ideal.span"}
        by_module = {"M.A": ["Submodule.span", "IsDedekindDomain"], "M.B": ["Set.span", "Ideal.span"]}
        self.assertEqual(md.resolve("IsDedekindDomain", "M.B", names, by_module), "IsDedekindDomain")
        self.assertEqual(md.resolve("span", "M.A", names, by_module), "Submodule.span")
        self.assertIsNone(md.resolve("span", "M.B", names, by_module))  # two in M.B end with it
        self.assertIsNone(md.resolve("span", "M.C", names, by_module))


def write_dataset(root: Path, decls: list[tuple], edges: dict[str, list[tuple[int, int]]], facets: dict[str, list[dict]] | None = None) -> Path:
    """A dataset in the extractor's format (ltb-dataset/2): decls are (name, module, kind, isProp, package); facets
    map a facet's name to its rows."""
    import json
    from array import array
    (root / "edges").mkdir(parents=True)
    (root / "facets").mkdir()
    for name, rows in (facets or {}).items():
        (root / "facets" / f"{name}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with (root / "decls.jsonl").open("w", encoding="utf-8") as f:
        for i, (name, module, kind, is_prop, package) in enumerate(decls):
            f.write(json.dumps({"id": i, "name": name, "module": module, "kind": kind, "isProp": is_prop, "package": package,
                                "scope": "project" if package == "mathlib" else "upstream", "hashes": {}}) + "\n")
    entries = []
    for notion, pairs in edges.items():
        data = array("i", [x for pair in pairs for x in pair])
        (root / "edges" / f"{notion}.bin").write_bytes(data.tobytes())
        entries.append({"name": notion, "format": "i32le-pairs", "file": f"edges/{notion}.bin", "count": len(pairs)})
    (root / "meta.json").write_text(json.dumps({"spec": "ltb-dataset/2", "edges": entries,
                                                "facets": [{"name": name, "file": f"facets/{name}.jsonl"} for name in facets or {}],
                                                "library": {"commit": "c0ffee"}}), encoding="utf-8")
    return root


@unittest.skipUnless(md, "needs requirements-data.txt")
class Sketches(unittest.TestCase):
    """Counting distinct definitions without holding every closure: HyperLogLog, exact while small."""

    def test_a_large_count_is_within_five_percent(self):
        import numpy as np
        for n in (2_000, 20_000, 200_000):
            estimate = md.estimate(md.registers_for(np.arange(n, dtype=np.int64)))
            self.assertLess(abs(estimate - n) / n, .05, n)

    def test_merging_is_the_union(self):
        import numpy as np
        a, b = md.registers_for(np.arange(0, 6000, dtype=np.int64)), md.registers_for(np.arange(4000, 10_000, dtype=np.int64))
        self.assertLess(abs(md.estimate(np.maximum(a, b)) - 10_000) / 10_000, .05)

    def test_an_empty_sketch_counts_nothing(self):
        import numpy as np
        self.assertEqual(round(md.estimate(md.registers_for(np.arange(0, dtype=np.int64)))), 0)


@unittest.skipUnless(md, "needs requirements-data.txt")
class Measures(unittest.TestCase):
    """How much of Mathlib a declaration needs: to state it, to state and prove it, and its deepest chain."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from evidence_core.dataset import Dataset
        from evidence_core.graphs import Graphs
        decls = [("A", "Mathlib.Foo.A", "definition", False, "mathlib"),              # 0, built on Nat only
                 ("B", "Mathlib.Foo.B", "definition", False, "mathlib"),              # 1, built on A
                 ("C", "Mathlib.Foo.C", "structure", False, "mathlib"),               # 2, built on B
                 ("L", "Mathlib.Foo.L", "theorem", True, "mathlib"),                  # 3, about C
                 ("T", "Mathlib.Foo.T", "theorem", True, "mathlib"),                  # 4, about A; its proof uses L and K
                 ("Mathlib.Tactic.Ring.K", "Mathlib.Tactic.Ring.Basic", "theorem", True, "mathlib"),  # 5, about D
                 ("D", "Mathlib.Foo.D", "definition", False, "mathlib"),              # 6, only the tactic lemma uses it
                 ("Nat", "Init.Prelude", "inductive", False, "lean4"),                # 7, Lean's own
                 ("E", "Mathlib.Foo.E", "definition", False, "mathlib")]              # 8, built on B and C
        meaning = [(0, 7), (1, 0), (2, 1), (3, 2), (4, 0), (5, 6), (8, 1), (8, 2)]
        term = meaning + [(4, 3), (4, 5)]
        root = write_dataset(Path(tempfile.mkdtemp()) / "ds", decls, {"meaning": meaning, "statement": meaning, "term": term})
        ds = Dataset.load(root)
        rules = [("Mathlib.Tactic", None), ("Mathlib", "math.LO")]
        cls.m = md.measures(ds, Graphs(ds), rules)
        cls.id = {d.name: d.id for d in ds.decls}

    def at(self, measure, name):
        return int(getattr(self.m, measure)[self.id[name]])

    def test_to_state_and_prove_counts_every_definition_beneath_its_statement_and_its_proofs_lemmas(self):
        self.assertEqual(self.at("needed", "T"), 3)   # A from its statement; C, B from the lemma L its proof uses
        self.assertEqual(self.at("needed", "L"), 3)
        self.assertEqual(self.at("needed", "A"), 0)   # Lean's Nat does not count

    def test_a_tactics_lemmas_and_what_only_they_use_do_not_count(self):
        self.assertEqual(self.at("needed", "T"), 3)   # not D, which only the tactic lemma K mentions

    def test_to_state_counts_only_the_statements_definitions(self):
        self.assertEqual(self.at("stated", "T"), 1)
        self.assertEqual(self.at("stated", "C"), 2)
        self.assertEqual(self.at("stated", "E"), 3)   # B and C, and A beneath both, once

    def test_the_deepest_chain_of_definitions(self):
        self.assertEqual(self.at("depth", "A"), 1)
        self.assertEqual(self.at("depth", "C"), 3)
        self.assertEqual(self.at("depth", "E"), 4)
        self.assertEqual(self.at("depth", "L"), 3)    # a theorem takes its statement's deepest definition
        self.assertEqual(self.at("depth", "T"), 1)


@unittest.skipUnless(md, "needs requirements-data.txt")
class DiskData(unittest.TestCase):
    """data/mathlib-disk.json: the items with their words, measures and areas, and the dust."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from evidence_core.dataset import Dataset
        from evidence_core.graphs import Graphs
        from mathlib_areas import load_rules
        decls = [("IsDedekindDomain", "Mathlib.RingTheory.Example", "class", False, "mathlib"),          # 0
                 ("Submodule.span", "Mathlib.RingTheory.Example", "definition", False, "mathlib"),       # 1
                 ("CompleteSpace", "Mathlib.Topology.Basic", "class", False, "mathlib"),                 # 2
                 ("irrational_sqrt_two", "Mathlib.Data.Real.Irrational", "theorem", True, "mathlib"),     # 3
                 ("Mathlib.Tactic.Ring.ring", "Mathlib.Tactic.Ring", "definition", False, "mathlib"),     # 4
                 ("Real", "Mathlib.Data.Real.Basic", "structure", False, "mathlib")]                      # 5
        edges = [(0, 1), (2, 5), (3, 5), (4, 5)]
        long_doc = "A complete space. " + "Every Cauchy filter converges. " * 30
        facets = {"signature": [{"decl": "IsDedekindDomain", "text": "IsDedekindDomain.{u_2} (A : Type u_2) [CommRing A] : Prop"}],
                  "docstring": [{"decl": "CompleteSpace", "text": long_doc}],
                  "source": [{"decl": "IsDedekindDomain", "path": "Mathlib/RingTheory/Example.lean", "start": [12, 0], "end": [14, 3], "keyword": "class"}]}
        root = write_dataset(Path(tempfile.mkdtemp()) / "ds", decls, {"meaning": edges, "statement": edges, "term": edges}, facets)
        ds = Dataset.load(root)
        g = Graphs(ds)
        rules = load_rules(ROOT / "data" / "mathlib-areas.json")
        cls.data = md.disk_data(ds, g, md.measures(ds, g, rules), FIXTURES, rules)
        cls.items = {item["name"]: item for item in cls.data["items"]}

    def test_the_catalogues_landmarks_and_the_headers_items(self):
        self.assertEqual({name: item["tier"] for name, item in self.items.items()},
                         {"IsDedekindDomain": 1, "CompleteSpace": 1, "irrational_sqrt_two": 1, "Submodule.span": 2})

    def test_what_the_dataset_lacks_or_the_table_leaves_out_is_dropped_and_counted(self):
        self.assertNotIn("Mathlib.Tactic.Ring.ring", self.items)
        self.assertEqual(self.data["dropped"]["catalogue"], 3)   # Ideal.IsMaximal, num_dvd_of_is_root, den_dvd_of_is_root
        self.assertEqual(self.data["dropped"]["header"], 3)      # the three Ideal.* results
        self.assertEqual(self.data["dropped"]["excluded"], 1)    # the tactic, which its header lists

    def test_an_items_words_statement_and_place(self):
        dedekind = self.items["IsDedekindDomain"]
        self.assertEqual(dedekind["title"], "Dedekind domain")
        self.assertEqual(dedekind["summary"], "defines a Dedekind domain as a Dedekind ring that is a domain.")
        self.assertEqual(dedekind["signature"], "IsDedekindDomain (A : Type u_2) [CommRing A] : Prop")
        self.assertEqual((dedekind["path"], dedekind["line"], dedekind["keyword"]), ("Mathlib/RingTheory/Example.lean", 12, "class"))
        self.assertEqual((dedekind["area"], self.items["CompleteSpace"]["area"], self.items["irrational_sqrt_two"]["area"]),
                         ("math.AC", "math.GN", "math.NT/analytic"))
        self.assertEqual(dedekind["needed"], 1)

    def test_a_summary_is_at_most_four_hundred_characters(self):
        summary = self.items["CompleteSpace"]["summary"]
        self.assertLessEqual(len(summary), 400)
        self.assertTrue(summary.startswith("A complete space.") and summary.endswith("…"))

    def test_the_file_reads_back_as_written_one_item_a_line(self):
        import json
        import tempfile
        path = Path(tempfile.mkdtemp()) / "disk.json"
        md.write(self.data, path)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), self.data)
        self.assertTrue(any(line.startswith('{"name":"IsDedekindDomain"') for line in path.read_text(encoding="utf-8").splitlines()))

    def test_the_dust_counts_every_definition_and_result_by_area(self):
        dust = self.data["dust"]
        self.assertEqual(dust["bins"], 40)
        self.assertEqual(sum(sum(counts) for counts in dust["areas"].values()), 5)   # all but the tactic
        self.assertTrue(all(len(counts) == 40 for counts in dust["areas"].values()))


if __name__ == "__main__":
    unittest.main()
