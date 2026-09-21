#!/usr/bin/env python3
"""Check red-team results and their verification (research/blueprint/PROTOCOL.md, section 17).

Usage:
  python3 scripts/check_redteam.py research/blueprint/redteam/RT-XYZ.result.json [RT-XYZ.review.json ...]

A red team tries to break accepted work: every finding says precisely what is
wrong or missing, where, on what evidence, and how to fix it; a red team that
finds nothing says what it checked. A verification gives each finding a verdict
with a reason. Errors make the exit status 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

KINDS = {"missing", "error", "duplicate", "library-claim", "other"}
SEVERITIES = {"high", "medium", "low"}


def text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def check(data, name: str) -> list:
    if not isinstance(data, dict):
        return ["the result is not a JSON object"]
    errors = []
    if data.get("redteam") != name:
        errors.append(f"redteam must be {name}")
    if data.get("protocol") != "redteam-v1":
        errors.append("protocol must be redteam-v1")
    if data.get("status") not in ("partial", "complete"):
        errors.append("status must be 'partial' or 'complete'")
    if not text(data.get("target")):
        errors.append("target: the job or area red-teamed")
    if not text(data.get("summary")):
        errors.append("a summary of what was found")
    checked = data.get("checked") or []
    if not checked or not all(text(item) for item in checked):
        errors.append("checked: say what was checked, so that finding nothing means something")
    seen = set()
    for finding in data.get("findings") or []:
        fid = finding.get("id")
        if not text(fid) or not fid.startswith(name + "/"):
            errors.append(f"finding id {fid!r} must start with {name}/")
            continue
        if fid in seen:
            errors.append(f"{fid} appears twice")
        seen.add(fid)
        if finding.get("kind") not in KINDS:
            errors.append(f"{fid}: kind is one of {', '.join(sorted(KINDS))}")
        if finding.get("severity") not in SEVERITIES:
            errors.append(f"{fid}: severity is one of {', '.join(sorted(SEVERITIES))}")
        for field in ("where", "claim", "evidence", "fix"):
            if not text(finding.get(field)):
                errors.append(f"{fid}: needs its {field}")
    return errors


def check_review(data, name: str, result: dict) -> list:
    if not isinstance(data, dict):
        return ["the verification is not a JSON object"]
    errors = [] if data.get("redteam") == name else [f"redteam must be {name}"]
    verdicts = {entry.get("finding"): entry for entry in data.get("findings") or []}
    for finding in result.get("findings") or []:
        fid = finding.get("id")
        entry = verdicts.get(fid)
        if entry is None:
            errors.append(f"{fid} has no verdict")
            continue
        if entry.get("verdict") not in ("confirmed", "rejected"):
            errors.append(f"{fid}: verdict is confirmed or rejected")
        if not text(entry.get("reason")):
            errors.append(f"{fid}: needs a reason")
    return errors


def main(paths) -> int:
    failed = False
    for path in map(Path, paths):
        name = path.name.split(".")[0]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if path.name.endswith(".review.json"):
                found = check_review(data, name, json.loads(path.with_name(f"{name}.result.json").read_text(encoding="utf-8")))
            else:
                found = check(data, name)
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
