#!/usr/bin/env python3
"""Reject sorry-bodied data in a package Suggested.lean.

A `def`, `abbrev`, `instance`, `noncomputable def` or `structure`-field default whose body is
`sorry` asserts nothing and would block correct contributions (PACKAGE_REVIEW.md, "Shape of a
roadmap"). Theorems and examples may be proved by `sorry`. Exit 1 and print each offender.
"""
import re, sys

HEAD = re.compile(r'^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+|noncomputable\s+)*(def|abbrev|instance)\b')

def offenders(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    out = []
    i = 0
    while i < len(lines):
        m = HEAD.match(lines[i])
        if m:
            # the declaration runs until the next column-zero declaration or a blank line after ':='
            j = i; body = []
            while j < len(lines):
                body.append(lines[j]); j += 1
                if j < len(lines) and re.match(r'^(?:@\[|theorem|lemma|def|abbrev|instance|structure|class|example|namespace|end|section|open|variable|/-|--|#)', lines[j]):
                    break
            text = '\n'.join(body)
            if re.search(r':=\s*(?:by\s+)?sorry\b', text) or re.search(r'\bsorry\s*$', text.strip()):
                out.append((i + 1, m.group(1), lines[i].strip()[:100]))
            i = j
        else:
            i += 1
    return out

status = 0
for path in sys.argv[1:]:
    for ln, kind, text in offenders(path):
        print(f"{path}:{ln}: {kind} with a sorry body: {text}")
        status = 1
sys.exit(status)
