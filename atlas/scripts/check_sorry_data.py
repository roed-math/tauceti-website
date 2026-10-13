#!/usr/bin/env python3
"""Reject sorry-bodied data in a package Suggested.lean.

A `def`, `abbrev` or `instance` whose body is `sorry`, or a structure instance whose DATA field
(carrier, toFun, obj, map, hom, inv, r, functor, ...) is `sorry`, asserts nothing and would block
correct contributions (PACKAGE_REVIEW.md, "Shape of a roadmap"). Proof fields (`add_mem'`,
`iseqv`, `coherence`, `symmetric`, ...) may be `sorry`: a proposition's proof does not change
the data. Theorems and examples may be proved by `sorry`. Exit 1 and print each offender.
"""
import re, sys

HEAD = re.compile(r'^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+|noncomputable\s+)*(def|abbrev|instance)\b')
STOP = re.compile(r'^(?:@\[|theorem|lemma|def|abbrev|instance|structure|class|example|namespace|end\b|section|open|variable|/-|--|#|noncomputable|private|protected)')
DATA_FIELDS = ('carrier', 'toFun', 'invFun', 'obj', 'map', 'hom', 'inv', 'r', 'dual', 'matrix', 'inverse',
               'pairing', 'functor', 'val', 'fst', 'snd', 'toEquiv', 'toLinearMap', 'toRingHom', 'toMonoidHom',
               'toAddMonoidHom', 'toFunctor', 'toPrefunctor', 'biddual', 'ι', 'basis', 'point', 'section',
               'sheaf', 'presheaf', 'space', 'ring', 'group', 'module', 'topology', 'uniformity', 'order',
               'norm', 'dist', 'measure', 'smul', 'mul', 'add', 'one', 'zero', 'neg', 'sub', 'div', 'npow', 'nsmul')
DATA_FIELD = re.compile(r'^\s*(' + '|'.join(re.escape(f) for f in DATA_FIELDS) + r')\s*(?:\([^)]*\)\s*|[A-Za-z_][A-Za-z0-9_]*\s*)*:=\s*(?:by\s+)?sorry\b')

def offenders(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    out = []
    i = 0
    while i < len(lines):
        m = HEAD.match(lines[i])
        if not m:
            i += 1; continue
        j = i + 1; body = [lines[i]]
        while j < len(lines) and not STOP.match(lines[j]):
            body.append(lines[j]); j += 1
        text = '\n'.join(body)
        bad = False
        where = re.search(r'\bwhere\b', text)
        if where:
            # the signature ends at `where`; only data-named fields count
            for ln in body:
                if DATA_FIELD.match(ln):
                    bad = True; break
        else:
            # the signature ends at the first top-level `:=`; the body is everything after it
            k = text.find(':=')
            if k >= 0:
                rest = text[k + 2:].strip()
                if re.match(r'^(?:by\s+)?sorry\b', rest):
                    bad = True
        if bad:
            out.append((i + 1, m.group(1), lines[i].strip()[:100]))
        i = j
    return out

status = 0
for path in sys.argv[1:]:
    for ln, kind, text in offenders(path):
        print(f"{path}:{ln}: {kind} with a sorry body: {text}")
        status = 1
sys.exit(status)
