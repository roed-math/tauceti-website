#!/usr/bin/env python3
"""The extractor release this repository uses: the newest of one series (0.13, which writes
`ltb-dataset/2`) for a Lean toolchain. Adapted from the Tau Ceti review site's scripts/extractor.py
(CBirkbeck/tauceti-reviewed-by-test), without its settings file.

  python3 scripts/extractor.py tag <toolchain>            the release for a toolchain (or a lean-toolchain file)
  python3 scripts/extractor.py install <toolchain> <dir>  unpack that release into <dir>; print its tag
"""
from __future__ import annotations

import re
import subprocess
import sys
import tarfile
from pathlib import Path

REPO, SERIES = "CBirkbeck/extractor", "0.13"
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)-lean-v(.+)$")
ASSET = "trust-extract-linux-x86_64.tar.gz"


def toolchain_of(value: str) -> str:
    """`leanprover/lean4:v4.36.0-rc1`, `v4.36.0-rc1` or a lean-toolchain file: `4.36.0-rc1`."""
    p = Path(value)
    if p.is_file():
        value = p.read_text(encoding="utf-8")
    return value.strip().split(":", 1)[-1].removeprefix("v")


def newest(tags: list[str], toolchain: str) -> str | None:
    """The newest release of the series for the toolchain."""
    major, minor = (int(x) for x in SERIES.split("."))
    found = [(int(m[3]), tag) for tag in tags if (m := TAG.match(tag))
             and (int(m[1]), int(m[2])) == (major, minor) and m[4] == toolchain]
    return max(found)[1] if found else None


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("tag", "install") or (argv[0] == "install" and len(argv) < 3):
        print(__doc__, file=sys.stderr)
        return 2
    tags = subprocess.run(["gh", "release", "list", "-R", REPO, "--limit", "200", "--json", "tagName", "--jq", ".[].tagName"],
                          check=True, capture_output=True, text=True).stdout.split()
    tag = newest(tags, toolchain_of(argv[1]))
    if tag is None:
        print(f"::error::the extractor has no release of series {SERIES} for Lean {toolchain_of(argv[1])}", file=sys.stderr)
        return 1
    if argv[0] == "install":
        dest = Path(argv[2])
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["gh", "release", "download", tag, "-R", REPO, "-p", ASSET, "-D", str(dest), "--clobber"], check=True)
        with tarfile.open(dest / ASSET) as tar:
            tar.extractall(dest, filter="tar")
        (dest / ASSET).unlink()
    print(tag)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
