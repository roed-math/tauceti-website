#!/usr/bin/env python3
"""Count Tau Ceti's theorems and definitions at the end of each UTC day, into data/library-counts.json.

A declaration is counted by the keyword that opens it in the source under TauCeti/: theorems are
`theorem` and `lemma`; definitions are `def`, `abbrev`, `structure`, `class`, `inductive` and
`opaque`; instances are counted apart. Attributes and modifiers (`@[simp]`, `private`,
`noncomputable`, ...) before the keyword on the same line are allowed. This counts what is written,
so declarations a command generates (structure projections, auxiliary lemmas) are not included;
Tau Ceti Review's dataset, which elaborates the library, counts more.

Usage: python3 scripts/library_counts.py --tauceti-repo PATH [--out data/library-counts.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from collections import Counter
from pathlib import Path

PATTERN = (r"^[[:space:]]*(@\[[^]]*\][[:space:]]*)*"
           r"((private|protected|noncomputable|partial|unsafe|nonrec|scoped|local)[[:space:]]+)*"
           r"(theorem|lemma|def|abbrev|structure|class|inductive|opaque|instance)[[:space:]]")
KIND = {"theorem": "theorems", "lemma": "theorems", "def": "definitions", "abbrev": "definitions",
        "structure": "definitions", "class": "definitions", "inductive": "definitions",
        "opaque": "definitions", "instance": "instances"}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def count(repo: Path, commit: str) -> Counter:
    out = subprocess.run(["git", "-C", str(repo), "grep", "-h", "-o", "-E", PATTERN, commit, "--", "TauCeti"],
                         capture_output=True, text=True)
    if out.returncode not in (0, 1):  # 1: no match
        raise RuntimeError(out.stderr)
    c = Counter()
    for line in out.stdout.splitlines():
        c[KIND[line.split()[-1]]] += 1
    return c


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tauceti-repo", type=Path, required=True, help="a full (non-shallow) clone of TauCeti")
    ap.add_argument("--out", type=Path, default=Path("data/library-counts.json"))
    args = ap.parse_args()

    end = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    first = dt.date.fromisoformat(git(args.tauceti_repo, "log", "--reverse", "--first-parent", "--format=%cs", "HEAD").split()[0])
    dates, series = [], {k: [] for k in ("theorems", "definitions", "instances")}
    last_commit, last = None, Counter()
    d = first
    while d <= end:
        commit = git(args.tauceti_repo, "rev-list", "-1", "--first-parent", f"--before={d.isoformat()}T23:59:59Z", "HEAD").strip()
        if commit and commit != last_commit:
            last, last_commit = count(args.tauceti_repo, commit), commit
        dates.append(d.isoformat())
        for k in series:
            series[k].append(last[k])
        d += dt.timedelta(days=1)
    out = {"generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
           "commit": last_commit, "last_full_day": end.isoformat(), "dates": dates, **series}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {args.out}: {series['theorems'][-1]:,} theorems, {series['definitions'][-1]:,} definitions, "
          f"{series['instances'][-1]:,} instances on {end}")


if __name__ == "__main__":
    main()
