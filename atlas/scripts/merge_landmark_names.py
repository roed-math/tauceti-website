"""Validate a landmark-naming result and merge accepted names into data/landmark-labels.json.

Usage: python3 scripts/merge_landmark_names.py research/expansion/naming/NAME-13.result.json [--apply]

Without --apply nothing is written; the report lists what would be accepted and why
each rejected entry fails. Rules (all mechanical):
  * every result id must be a landmark listed in research/expansion/naming/landmarks-all.json,
    and every landmark of the job must be decided exactly once;
  * decision "keep": current label unchanged (curated entries must be "keep");
  * decision "name": 3-48 characters, no trailing punctuation or quotes, does not start with an
    imperative or bookkeeping word, differs from the current label, unique within its star
    (against the other accepted names and the existing curated names), and every alphabetic word
    of at least four letters occurs, as a word or as a stem of at least four letters, in the
    landmark's excerpt, current label, or its layer's title and description in data/atlas.json;
  * decision "procedural": recorded in research/expansion/naming/<job>.procedural.json for the
    orchestrator; nothing is hidden or renamed by this script.
"""
import json, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_START = re.compile(r"^(?:construct|prove|define|state|record|consume|supply|implement|identify|establish|derive|compute|show|introduce|use|reuse|import|export|own|check|verify|assert|do not|then|that|this|these|those|thus|so|if|for|by|of|on|with|and|or|where|which|when|here|there|it|its|we)\b", re.I)
FUNCTION_WORDS = {'over', 'with', 'from', 'into', 'under', 'onto', 'upon', 'between', 'along', 'their', 'that', 'this', 'these', 'those', 'through', 'without', 'within', 'about', 'after', 'before', 'versus'}
BOOKKEEPING = re.compile(r"\b(?:owners?|roadmaps?|supply|supplies|supplied|consume[sd]?|API|milestones?|checkpoints?|tickets?|download(?:ed|s)?|Mathlib|Lean|sorry|placeholder)\b", re.I)


def fold(text):
    text = unicodedata.normalize('NFKD', text or '')
    return ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()


def words(text):
    # Hyphens and dashes separate words: "Harder--Narasimhan" yields both names.
    return set(re.findall(r"[a-z][a-z']{1,}", re.sub(r"[-\u2010-\u2015]+", " ", fold(text))))


def vocabulary_ok(name, pool):
    pool_words = words(pool)
    stems = {w[:4] for w in pool_words if len(w) >= 4} | {w[:5] for w in pool_words if len(w) >= 5}
    missing = []
    for w in words(name):
        if len(w) < 4 or w in pool_words or w in FUNCTION_WORDS:
            continue
        if any(w.startswith(s) and len(s) >= 4 for s in stems) or any(p.startswith(w) for p in pool_words):
            continue
        missing.append(w)
    return missing


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    result_path = Path(argv[1]); apply = '--apply' in argv
    job = result_path.name.split('.')[0]
    landmarks = {r['id']: r for r in json.loads((ROOT / 'research/expansion/naming/landmarks-all.json').read_text())}
    job_ids = {r['id'] for r in json.loads((ROOT / f'research/expansion/naming/{job}.json').read_text())}
    atlas = json.loads((ROOT / 'data/atlas.json').read_text())
    stages = {s['id']: s for s in atlas['stages']}
    curated = json.loads((ROOT / 'data/landmark-labels.json').read_text())
    results = json.loads(result_path.read_text())
    seen, accepted, rejected, procedural = {}, {}, [], []
    by_star = {}
    for lid, label in curated.items():
        if lid in landmarks:
            by_star.setdefault(landmarks[lid]['starId'], set()).add(fold(label))
    for entry in results:
        lid = entry.get('id'); decision = entry.get('decision')
        if lid not in landmarks or lid not in job_ids:
            rejected.append((lid, 'unknown id for this job')); continue
        if lid in seen:
            rejected.append((lid, 'decided twice')); continue
        seen[lid] = entry; lm = landmarks[lid]
        if decision == 'keep':
            continue
        if decision == 'procedural':
            if lm['curated']:
                rejected.append((lid, 'curated landmark cannot be marked procedural')); continue
            procedural.append({'id': lid, 'label': lm['label'], 'reason': entry.get('reason', '')}); continue
        if decision != 'name':
            rejected.append((lid, f'unknown decision {decision!r}')); continue
        name = (entry.get('label') or '').strip()
        problems = []
        if lm['curated']: problems.append('curated landmark must be kept')
        if not 3 <= len(name) <= 48: problems.append(f'length {len(name)}')
        if re.search(r'[.:;,]$', name) or '"' in name or '“' in name: problems.append('punctuation')
        if re.search(r'[\\${}^]', name): problems.append('characters the builder rejects')
        if FORBIDDEN_START.match(name): problems.append('starts with a verb or connective')
        if BOOKKEEPING.search(name): problems.append('bookkeeping vocabulary')
        if fold(name) == fold(lm['label']): problems.append('unchanged label should be "keep"')
        stage = stages.get(lm['starId'], {})
        pool = ' '.join([lm.get('excerpt', ''), lm.get('label', ''), stage.get('title', ''), stage.get('description', '')])
        missing = vocabulary_ok(name, pool)
        if missing: problems.append('words not in passage: ' + ', '.join(missing))
        star_names = by_star.setdefault(lm['starId'], set())
        if fold(name) in star_names: problems.append('duplicate name within star')
        if problems:
            rejected.append((lid, '; '.join(problems))); continue
        star_names.add(fold(name)); accepted[lid] = name
    undecided = sorted(job_ids - set(seen))
    print(f'{job}: {len(results)} entries, accepted names {len(accepted)}, kept {sum(1 for e in seen.values() if e.get("decision") == "keep")}, procedural {len(procedural)}, rejected {len(rejected)}, undecided {len(undecided)}')
    for lid, why in rejected[:60]:
        print('  REJECT', lid.split('::')[0], '|', (seen.get(lid) or {}).get('label'), '|', why)
    if undecided:
        print('  undecided:', ', '.join(u.split('::')[0] for u in undecided[:10]), '...' if len(undecided) > 10 else '')
    if apply:
        merged = dict(curated); merged.update(accepted)
        (ROOT / 'data/landmark-labels.json').write_text(json.dumps(merged, indent=2, ensure_ascii=False) + '\n')
        (ROOT / f'research/expansion/naming/{job}.procedural.json').write_text(json.dumps(procedural, indent=2, ensure_ascii=False) + '\n')
        print(f'applied: data/landmark-labels.json now has {len(merged)} names; {len(procedural)} procedural ids recorded')
    return 0 if not undecided else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
