"""Planet-naming results: the dry run that a worker's pull request must pass."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from merge_landmark_names import main  # noqa: E402

JOB = "PLANETS-01"
PLANETS = [entry["id"] for entry in json.loads((ROOT / "research" / "expansion" / "naming" / f"{JOB}.json").read_text())]


def run(entries, *flags):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"{JOB}.result.json"
        path.write_text(json.dumps(entries))
        with contextlib.redirect_stdout(io.StringIO()):
            return main(["merge_landmark_names.py", str(path), *flags])


class Strict(unittest.TestCase):
    def test_a_result_that_decides_everything_well_passes(self):
        self.assertEqual(run([{"id": pid, "decision": "keep"} for pid in PLANETS], "--strict"), 0)

    def test_a_rejected_name_fails_only_the_strict_check(self):
        entries = [{"id": pid, "decision": "keep"} for pid in PLANETS]
        entries[0] = {"id": PLANETS[0], "decision": "name", "label": "Construct the case"}
        self.assertEqual(run(entries), 0)
        self.assertEqual(run(entries, "--strict"), 1)

    def test_an_undecided_planet_fails(self):
        self.assertEqual(run([{"id": pid, "decision": "keep"} for pid in PLANETS[1:]], "--strict"), 1)


if __name__ == "__main__":
    unittest.main()
