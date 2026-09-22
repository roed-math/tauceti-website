#!/usr/bin/env python3
"""Check the files of errata jobs (research/blueprint/PROTOCOL.md, section 18).

Usage:
  python3 scripts/check_errata.py research/blueprint/errata/<paper id or roadmap id>.json [...]

An errata job records, in its own file, the mistakes in a published source that
earlier work on it found: {"paper" (or "roadmapId"), "protocol": "errata-v1",
"sourceIssues": [...]}. Each finding is in the form of section 18; findings in
an older form are converted. Errors make the exit status 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from source_issues import check_issues  # noqa: E402


def check(data, name: str) -> list:
    if not isinstance(data, dict):
        return ["the file is not a JSON object"]
    errors = []
    if (data.get("paper") or data.get("roadmapId")) != name:
        errors.append(f"paper (or roadmapId) must be {name}")
    if data.get("protocol") != "errata-v1":
        errors.append("protocol must be errata-v1")
    issues = data.get("sourceIssues")
    if not isinstance(issues, list):
        errors.append("sourceIssues is a list (empty when none were found)")
        return errors
    errors += [f"{item.get('id')} is in the older form: convert it (PROTOCOL.md section 18)"
               for item in issues if isinstance(item, dict) and "kind" not in item]
    errors += check_issues([item for item in issues if not (isinstance(item, dict) and "kind" not in item)], name)
    return errors


def main(paths) -> int:
    failed = False
    for path in map(Path, paths):
        try:
            found = check(json.loads(path.read_text(encoding="utf-8")), path.stem)
        except (OSError, ValueError) as exc:
            found = [str(exc)]
        print(f"{path}: {'ok' if not found else str(len(found)) + ' error(s)'}")
        for error in found:
            print(f"  ERROR {error}")
        failed |= bool(found)
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
