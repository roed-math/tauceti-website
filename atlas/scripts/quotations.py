#!/usr/bin/env python3
"""Keep the atlas in its own words: no verbatim passage of a source (PROTOCOL.md section 5).

Citations and misprint records used to carry an `excerpt`, a passage copied from the source. This removes
every one of them from:
- the plans (research/blueprint/packets);
- the paper extractions (research/blueprint/papers);
- their published copies (data/blueprints).

The statement each node makes, in the worker's own words, the theorem number in its `locator`, and the `match`
saying what is there all stay.

A file that an open pull request changes is left for a later run, so that the pull request still merges
cleanly. The intake runs this after its merges.

    python3 scripts/quotations.py            # what would change
    python3 scripts/quotations.py --write    # remove them, skipping files open pull requests change
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blueprints import drop_source_excerpts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("research/blueprint/packets", "research/blueprint/papers", "data/blueprints")


STRING = r'"(?:[^"\\]|\\.)*"'
# An excerpt followed by another key, then an excerpt that closes its object.
BEFORE = re.compile(r'"excerpt"\s*:\s*' + STRING + r'\s*,\s*')
LAST = re.compile(r'\s*,\s*"excerpt"\s*:\s*' + STRING + r'(?=\s*\})')


def indent_of(text: str) -> int:
    """The indentation a JSON file was written with."""
    found = re.search(r"\n( +)\S", text)
    return len(found.group(1)) if found else 1


def stripped(text: str) -> str | None:
    """The file's text without excerpts, or None when it has none.

    The excerpts are cut out of the text itself, so that the rest of the file keeps its layout and the diff shows
    only what went. The cut is checked against the parsed file; if it removed anything else, the file is
    rewritten whole instead."""
    data = json.loads(text)
    clean = drop_source_excerpts(data)
    if clean == data:
        return None
    cut = LAST.sub("", BEFORE.sub("", text))
    try:
        if json.loads(cut) == clean:
            return cut
    except ValueError:
        pass
    return json.dumps(clean, indent=indent_of(text), ensure_ascii=False) + "\n"


def open_pull_request_files(repo: str = "CBirkbeck/tauceti-explorer") -> set:
    """The files open pull requests change: left alone until they merge."""
    out = subprocess.run(["gh", "pr", "list", "-R", repo, "--state", "open", "--limit", "300", "--json", "files",
                          "--jq", ".[].files[].path"], capture_output=True, text=True, cwd=ROOT)
    if out.returncode != 0:
        raise SystemExit("could not list open pull requests: " + out.stderr.strip()[:300])
    return set(out.stdout.split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--all", action="store_true", help="also files that open pull requests change")
    args = ap.parse_args()
    busy = set() if args.all else open_pull_request_files()
    changed, waiting = [], []
    for folder in FOLDERS:
        for path in sorted((ROOT / folder).glob("*.json")):
            relative = str(path.relative_to(ROOT))
            try:
                text = stripped(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if text is None:
                continue
            if relative in busy:
                waiting.append(relative)
                continue
            changed.append(relative)
            if args.write:
                path.write_text(text, encoding="utf-8")
    print(f"{'removed excerpts from' if args.write else 'would remove excerpts from'} {len(changed)} file(s); "
          f"{len(waiting)} wait for open pull requests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
