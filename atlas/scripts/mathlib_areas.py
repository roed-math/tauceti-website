"""The area of the disk a Mathlib module belongs to, from data/mathlib-areas.json: the area of the longest prefix of
the module's name that the table names, whole components only. An area is an arXiv category of the map, or one of its
finer areas (`math.NT/analytic`); None leaves the module out (tactics and tooling)."""
from __future__ import annotations

import json
from pathlib import Path


def load_rules(path: Path) -> list[tuple[str, str | None]]:
    """(prefix, area) for each line of the table, the longest prefixes first."""
    rules = json.loads(Path(path).read_text(encoding="utf-8"))["rules"]
    return sorted(rules.items(), key=lambda rule: (-len(rule[0].split(".")), rule[0]))


def area_of(module: str, rules: list[tuple[str, str | None]]) -> str | None:
    """The area of the longest prefix that names the module, else None."""
    for prefix, area in rules:
        if module == prefix or module.startswith(prefix + "."):
            return area
    return None
