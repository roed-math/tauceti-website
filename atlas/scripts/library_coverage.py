"""Layer statuses implied by the reviewed library audit (data/library-coverage.json).

A layer the accepted audit finds fully built, with declarations that show it,
counts as complete. A partly built layer counts as in progress when nothing
better is recorded. Recorded statuses are never lowered.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_coverage(root: Path = ROOT) -> dict:
    path = root / "data" / "library-coverage.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"layers": {}}


def coverage_statuses(coverage: dict, current: dict, stage_ids) -> dict:
    """Status records to lay over the current ones: {layer id: {status, basis, evidence, ...}}."""
    out = {}
    for sid, layer in (coverage.get("layers") or {}).items():
        if sid not in stage_ids:
            continue
        now = (current.get(sid) or {}).get("status") if isinstance(current.get(sid), dict) else current.get(sid)
        if layer.get("verdict") == "built" and now != "complete" and layer.get("evidence"):
            status = "complete"
        elif layer.get("verdict") == "partly built" and now in (None, "unknown", "planned"):
            status = "in_progress"
        else:
            continue
        evidence = [{"quote": f"{item.get('library')}: {item.get('name')} ({item.get('file')}:{item.get('line')}), "
                              f"{item.get('fit')} for {item.get('target')}",
                     "path": item.get("file"), "lineStart": item.get("line")} for item in layer.get("evidence") or []]
        if not evidence:
            evidence = [{"quote": "; ".join(f"{t.get('target')}: {t.get('library')}" for t in layer.get("targets") or [])}]
        out[sid] = {"status": status, "basis": "library_audit", "evidence": evidence,
                    "auditJob": layer.get("job"), "snapshotStatus": "library_audit"}
    return out
