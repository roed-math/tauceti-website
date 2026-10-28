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


KINDS = ("published", "preprint", "author copy")


def versions_checked(data: dict, issues: list) -> list:
    """A file that quotes a statement has to say which text it was read from.

    A published paper and its preprint are different documents, and a sentence
    quoted from one may not exist in the other: BSTTTZ's Theorem 1.3(a) gained a
    factor between arXiv v1 and the Journal of the AMS, and a finding written
    against the preprint accused the published theorem of being wrong. Recording
    the reading is what makes that catchable.
    """
    listed = data.get("sourceVersions")
    quotes = [item for item in issues if isinstance(item, dict) and item.get("affects") == "a stated result"]
    if quotes and not listed:
        return ["sourceVersions is required when a finding quotes a stated result: list what was read, "
                "as [{\"kind\": \"published\"|\"preprint\"|\"author copy\", \"url\": ..., \"read\": <date>, "
                "\"sha256\": ...}] (PROTOCOL.md section 18)"]
    errors = []
    for entry in listed or []:
        if not isinstance(entry, dict):
            errors.append("each sourceVersions entry is an object")
        elif entry.get("kind") not in KINDS:
            errors.append(f"sourceVersions kind must be one of {', '.join(KINDS)}, not {entry.get('kind')!r}")
        elif not entry.get("url") and not entry.get("citation"):
            errors.append("each sourceVersions entry needs a url or a citation")
    return errors


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
    errors += versions_checked(data, issues)
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
