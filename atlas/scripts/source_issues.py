"""Mistakes found in published sources (research/blueprint/PROTOCOL.md, section 18).

A paper extraction or a blueprint packet records each mistake its worker finds
in a source under `sourceIssues`: a misprint (a slip whose intended meaning is
clear), an error (a false statement or a step that fails) or a gap (a step
asserted without adequate proof), quoted at its locator, with the correction,
the reason, how far it reaches, and whether a published correction already
exists. The independent reviewer adds a verdict to each. check_issues is shared
by scripts/check_paper.py and scripts/check_blueprint.py.
"""
from __future__ import annotations

KINDS = {"misprint", "error", "gap"}
REACH = {"nothing", "the proof", "a stated result"}
FIELDS = {"locator": "where in the source, with the version read",
          "printed": "what the source says, quoted",
          "correction": "what it should say, or what is missing",
          "reason": "the check or argument that shows it",
          "known": "'new', or the erratum or later version that already corrects it"}


def text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def check_issues(issues, owner: str) -> list:
    """Errors in a list of findings whose ids start with '<owner>/E'."""
    if issues is None:
        return []
    if not isinstance(issues, list):
        return ["sourceIssues is a list"]
    errors, seen = [], set()
    for issue in issues:
        if isinstance(issue, dict) and "kind" not in issue and "finding" in issue:
            # A finding in the older form, recorded before section 18; its errata job converts it.
            continue
        fid = issue.get("id") if isinstance(issue, dict) else None
        if not text(fid) or not fid.startswith(owner + "/E"):
            errors.append(f"finding id {fid!r} must start with {owner}/E")
            continue
        if fid in seen:
            errors.append(f"{fid} appears twice")
        seen.add(fid)
        if issue.get("kind") not in KINDS:
            errors.append(f"{fid}: kind is one of {', '.join(sorted(KINDS))}")
        if issue.get("affects") not in REACH:
            errors.append(f"{fid}: affects is one of {', '.join(sorted(REACH))}")
        for field, meaning in FIELDS.items():
            if not text(issue.get(field)):
                errors.append(f"{fid}: needs {field} ({meaning})")
        searched = issue.get("searched")
        if not isinstance(searched, list) or not searched or not all(text(item) for item in searched):
            errors.append(f"{fid}: searched lists where an existing correction was looked for")
        review = issue.get("review")
        if review is not None and (not isinstance(review, dict) or review.get("verdict") not in ("confirmed", "rejected")
                                   or not text(review.get("reason")) or not text(review.get("by"))):
            errors.append(f"{fid}: review verdict is confirmed or rejected, with a reason and the review job (by)")
    return errors
