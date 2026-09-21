"""What the reviewed library audit (data/library-coverage.json) changes in the atlas.

On a Tau Ceti roadmap, a layer the accepted audit finds fully built, with
declarations that show it, counts as complete, and a partly built one as in
progress when nothing better is recorded; recorded statuses are never lowered.
A proposed roadmap shows only what still has to be built: what the libraries
already contain is its starting point, never its progress, so a layer the audit
finds already built, or finds to be process rather than mathematics, is hidden.
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


def already_available(coverage: dict, atlas: dict) -> dict:
    """Presentation records hiding the layers of proposed roadmaps that the reviewed
    audit finds already in Mathlib or Tau Ceti, or finds to be process."""
    proposed = {roadmap["id"] for roadmap in atlas["roadmaps"] if roadmap.get("origin") != "tauceti"}
    owner = {stage["id"]: stage["owner"] for stage in atlas["stages"]}
    out = {}
    for sid, layer in (coverage.get("layers") or {}).items():
        if owner.get(sid) not in proposed:
            continue
        if layer.get("verdict") == "built" and layer.get("evidence"):
            names = sorted({item.get("name") for item in layer["evidence"] if item.get("name")})
            out[sid] = {"hidden": True, "summary": "Already in Mathlib or Tau Ceti, by the reviewed library audit: " + ", ".join(names[:6]) + "."}
        elif layer.get("verdict") == "process":
            what = "; ".join(t.get("target", "") for t in layer.get("targets") or [] if t.get("target"))
            out[sid] = {"hidden": True, "summary": ("Process, not mathematics, by the reviewed library audit: " + what)[:400]}
    return out
