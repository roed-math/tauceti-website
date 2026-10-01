"""The key definitions page (scripts/definitions_page.py, PROTOCOL.md section 19)."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from definitions_page import load_surveys, page  # noqa: E402

GALAXIES = {"fields": [{"id": "algebraic-geometry"}, {"id": "algebraic-number-theory"}],
            "galaxies": [{"id": "algebraicnt", "label": "Number fields and class field theory", "field": "algebraic-number-theory"},
                         {"id": "algebraicgeometry", "label": "Schemes, curves and moduli", "field": "algebraic-geometry"}]}
ATLAS = {"roadmaps": [{"id": "R", "title": "Roadmap: Schemes and stacks"}],
         "stages": [{"id": "R:L1", "owner": "R", "key": "L1", "title": "Coherent sheaves"}]}
PAPERS = {"PAPER-A": {"short": "Author–One (2024): A title", "link": "https://example.org/a"},
          "PAPER-B": {"short": "Author–Two (2025): Another title", "link": ""},
          "PAPER-C": {"short": "Author–Three (2023): A third title", "link": ""}}


def entry(eid, name, papers, owners=("R:L1",), depends=(), size="L"):
    return {"id": eid, "name": name, "short": name[:60], "define": f"What to define for {name}, with n < m and `Foo.bar`.",
            "library": {"has": ["mathlib:Foo.bar"], "missing": "the rest of it"},
            "papers": [{"paper": p, "items": [f"{p}/1"]} for p in papers], "owners": list(owners), "dependsOn": list(depends), "size": size,
            "api": [{"kind": "theorem", "statement": "A theorem it exists to support, stated with care."},
                    {"kind": "counterexample", "statement": "A counterexample showing that the hypothesis matters."},
                    {"kind": "example", "statement": "A worked example with its value computed exactly."}]}


def surveys():
    geometry = {"job": "KEYDEF-algebraicgeometry", "area": "algebraicgeometry", "definitions": [
        entry("algebraicgeometry/stack", "Algebraic stack", ["PAPER-A", "PAPER-B"], owners=()),
        entry("algebraicgeometry/coherent", "Coherent sheaf on a scheme", ["PAPER-A", "PAPER-B", "PAPER-C"], depends=["algebraicgeometry/stack"])],
        "reserve": [{"name": "Standing notation", "items": ["PAPER-C/2"], "reason": "one paper only"}]}
    number = {"job": "KEYDEF-algebraicnt", "area": "algebraicnt", "definitions": [
        entry("algebraicnt/selmer", "Selmer group of a Galois representation", ["PAPER-A", "PAPER-C"],
              depends=["algebraicgeometry/coherent", "tauceti:TauCetiRoadmap/GaloisCohomology#layer-3"], size="XL")]}
    return [("KEYDEF-algebraicgeometry", geometry), ("KEYDEF-algebraicnt", number)]


class DefinitionsPage(unittest.TestCase):
    def test_entries_are_ordered_by_field_area_and_papers(self):
        text = page(ATLAS, surveys(), GALAXIES, PAPERS, ["algebraicgeometry", "algebraicnt"])
        order = [m for m in re.findall(r'<h3><span class="num">(\d+)</span> ([^<]+)</h3>', text)]
        self.assertEqual([name for _, name in order], ["Coherent sheaf on a scheme", "Algebraic stack", "Selmer group of a Galois representation"])
        self.assertIn("3 key definitions from 2 areas, needed by 3 papers; 2 of them in a roadmap so far", text)
        self.assertNotIn("Still being surveyed", text)

    def test_each_entry_says_whether_a_roadmap_plans_it_and_which(self):
        assigned = {"algebraicgeometry/stack": {"owner": "BP-Stacks", "roadmap": "Stacks", "title": "Stacks and gerbes",
                                                "reserved": "Stacks:key/stack"}}
        text = page(ATLAS, surveys(), GALAXIES, PAPERS, [], assigned)
        rows = dict((name, cell) for name, cell in re.findall(r'<td><a href="#[^"]+">([^<]+)</a></td><td>[^<]*</td><td class="n">\d+</td><td>(.*?)</td></tr>', text))
        self.assertEqual(rows["Coherent sheaf on a scheme"], "Schemes and stacks")
        self.assertEqual(rows["Algebraic stack"], '<span class="gap">Not yet</span> · going to Stacks and gerbes')
        self.assertIn('Yes: <a href="index.html#view=roadmap&amp;id=R&amp;layer=R%3AL1&amp;selected=R%3AL1">Schemes and stacks · L1 Coherent sheaves</a>', text)
        self.assertIn("whose queued job <code>BP-Stacks</code> plans it as <code>Stacks:key/stack</code>", text)
        self.assertNotIn("Dependency layer", text)
        self.assertNotIn("<th>Size</th>", text)
        # Once the owner's blueprint is promoted, its reserved node puts the key definition in that roadmap.
        built = {**ATLAS, "roadmaps": ATLAS["roadmaps"] + [{"id": "Stacks", "title": "Stacks and gerbes",
                                                             "blueprint": {"layers": {"Stacks:S1": [["key/stack", "definition", "Algebraic stacks", 0]]}}}],
                 "stages": ATLAS["stages"] + [{"id": "Stacks:S1", "owner": "Stacks", "key": "S1", "title": "Stacks"}]}
        text = page(built, surveys(), GALAXIES, PAPERS, [], assigned)
        self.assertIn("Yes: <a href=\"index.html#view=roadmap&amp;id=Stacks&amp;layer=Stacks%3AS1&amp;selected=Stacks%3AS1\">Stacks and gerbes · S1 Stacks</a>", text)
        # One no queued job receives says so.
        text = page(ATLAS, surveys(), GALAXIES, PAPERS, [], {})
        self.assertIn("no queued job receives its items: it needs a roadmap", text)

    def test_each_entry_carries_its_facts_and_sample_api(self):
        text = page(ATLAS, surveys(), GALAXIES, PAPERS, [])
        self.assertIn('<a href="#kd-algebraicgeometry-stack">Algebraic stack</a>', text)
        self.assertIn("Tau Ceti GaloisCohomology, layer 3", text)
        self.assertIn("n &lt; m and <code>Foo.bar</code>", text)
        self.assertIn('<a href="https://example.org/a" target="_blank" rel="noopener">Author–One (2024)</a>', text)
        # Examples first, then counterexamples, then theorems.
        api = re.search(r'<ol class="api">(.*?)</ol>', text, re.S).group(1)
        self.assertLess(api.index("example</span>"), api.index("counterexample</span>"))
        self.assertLess(api.index("counterexample</span>"), api.index("theorem</span>"))
        self.assertIn("1 near miss, with why each was left out", text)

    def test_before_any_review_the_page_says_what_is_under_way(self):
        text = page(ATLAS, [], GALAXIES, PAPERS, ["algebraicgeometry", "algebraicnt"])
        self.assertIn("No area&#x27;s list has passed its review yet", text)
        self.assertIn("Still being surveyed: Schemes, curves and moduli, Number fields and class field theory.", text)
        self.assertNotIn('id="index"', text)
        for tag in ("section", "div", "article", "dl", "ol", "ul", "details"):
            self.assertEqual(len(re.findall(f"<{tag}[ >]", text)), text.count(f"</{tag}>"), tag)

    def test_the_markup_is_balanced(self):
        text = page(ATLAS, surveys(), GALAXIES, PAPERS, [])
        for tag in ("section", "div", "article", "dl", "ol", "ul", "details", "table"):
            self.assertEqual(len(re.findall(f"<{tag}[ >]", text)), text.count(f"</{tag}>"), tag)

    def test_a_survey_the_page_cannot_read_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "data" / "keydefs"
            folder.mkdir(parents=True)
            (folder / "KEYDEF-algebraicgeometry.json").write_text(json.dumps(surveys()[0][1]))
            self.assertEqual([stem for stem, _ in load_surveys(Path(tmp))], ["KEYDEF-algebraicgeometry"])
            broken = surveys()[1][1]
            del broken["definitions"][0]["api"]
            (folder / "KEYDEF-algebraicnt.json").write_text(json.dumps(broken))
            with self.assertRaises(ValueError):
                load_surveys(Path(tmp))


if __name__ == "__main__":
    unittest.main()
