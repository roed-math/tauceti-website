"""The catalogue of what the papers use and prove (scripts/items.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from items import catalogue, page, shard, summary  # noqa: E402

RESULTS = [
    {"paper": "PAPER-A-20", "items": [
        {"id": "PAPER-A-20/1", "kind": "definition", "name": "Perfectoid space", "statement": "A perfectoid space is one locally of the form Spa(A, A⁺). It is a tilting story.",
         "locator": "§2, Definition 2.1, p. 7", "status": "missing", "note": "Mathlib has none."},
        {"id": "PAPER-A-20/2", "kind": "theorem", "name": "Tilting equivalence", "statement": "The categories are equivalent.",
         "locator": "§3, Theorem 3.1", "status": "planned", "planned": ["PerfectoidSpaces:PS.2"]}]},
    {"paper": "PAPER-B-19", "items": [
        {"id": "PAPER-B-19/1", "kind": "construction", "name": "Witt vectors", "statement": "The ring of Witt vectors.",
         "locator": "§1", "status": "library", "library": ["Mathlib.RingTheory.WittVector.Basic"]}]}]
PAPERS = {"papers": [{"id": "PAPER-A-20", "short": "Author (2020): A paper", "citation": "Author, \"A paper\", Annals (2020)", "link": "u"},
                     {"id": "PAPER-B-19", "short": "Other (2019): Another", "citation": "Other, \"Another\", Duke (2019)", "link": "v"}]}


class Catalogue(unittest.TestCase):
    def setUp(self):
        self.found = catalogue(RESULTS, PAPERS)

    def test_every_item_is_a_row_with_its_paper_kind_and_status(self):
        rows = [[self.found["names"][r[0]], self.found["kinds"][r[1]], self.found["statuses"][r[2]], self.found["papers"][r[3]]["id"]]
                for r in self.found["rows"]]
        self.assertEqual(rows, [["Perfectoid space", "definition", "missing", "PAPER-A-20"],
                                ["Tilting equivalence", "theorem", "planned", "PAPER-A-20"],
                                ["Witt vectors", "construction", "library", "PAPER-B-19"]])

    def test_it_counts_what_the_papers_found(self):
        self.assertEqual(self.found["counts"], {"items": 3, "papers": 2, "definition": 1, "theorem": 1, "construction": 1,
                                                "missing": 1, "planned": 1, "library": 1})

    def test_each_row_carries_a_sentence_to_search_and_show(self):
        self.assertEqual(self.found["summaries"][0], "A perfectoid space is one locally of the form Spa(A, A⁺).")
        self.assertEqual(summary(""), "")

    def test_a_paper_that_is_not_in_the_registry_still_appears(self):
        found = catalogue(RESULTS, {"papers": []})
        self.assertEqual(found["papers"][0]["short"], "PAPER-A-20")

    def test_each_paper_has_a_file_of_its_items_in_full(self):
        one = shard(RESULTS[0])
        self.assertEqual(one["paper"], "PAPER-A-20")
        self.assertEqual([i["locator"] for i in one["items"]], ["§2, Definition 2.1, p. 7", "§3, Theorem 3.1"])
        self.assertEqual(one["items"][1]["planned"], ["PerfectoidSpaces:PS.2"])
        self.assertIn("tilting story", one["items"][0]["statement"])

    def test_the_page_carries_the_counts_and_no_local_paths(self):
        html = page(self.found)
        self.assertIn("3 items", html)
        self.assertIn('id="search"', html)
        self.assertNotIn("/Users/", html)


class Files(unittest.TestCase):
    def test_writing_the_catalogue_leaves_an_index_and_one_file_per_paper(self):
        from items import write
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            write(RESULTS, PAPERS, out)
            self.assertTrue((out / "items.html").exists())
            index = json.loads((out / "data" / "items" / "index.json").read_text())
            self.assertEqual(len(index["rows"]), 3)
            self.assertEqual(json.loads((out / "data" / "items" / "0.json").read_text())["paper"], "PAPER-A-20")


if __name__ == "__main__":
    unittest.main()
