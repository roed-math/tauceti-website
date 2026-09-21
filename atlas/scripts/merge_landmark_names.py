"""Validate a landmark-naming result and merge accepted names into data/landmark-labels.json.

Usage: python3 scripts/merge_landmark_names.py research/expansion/naming/NAME-13.result.json [--apply]

Without --apply nothing is written; the report lists what would be accepted and why
each rejected entry fails. Rules (all mechanical):
  * every result id must be a planet listed in research/expansion/naming/planets-current.json
    (or, for the first batches, landmarks-all.json), and every planet of the job must be decided
    exactly once;
  * decision "keep": current label unchanged (curated entries must be "keep");
  * decision "name": 3-48 characters, no trailing punctuation or quotes, does not start with an
    imperative or bookkeeping word, differs from the current label, unique within its star
    (against the other accepted names and the existing curated names), and every alphabetic word
    of at least four letters occurs, as a word or as a stem of at least four letters, in the
    landmark's excerpt, current label, or its layer's title and description in data/atlas.json;
  * decision "drop" (or "procedural"): the planet is hidden from the map through
    data/landmark-hidden.json with the job's reason, and any curated name it had is removed;
    a later "keep" or "name" for the same id un-hides it.
A planet that is a node of a source decomposition (an id without "::landmark:") takes its name
as the title of that node in data/stage-presentation.json, and a drop hides the node there.
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
    landmarks = {}
    for universe in ('landmarks-all.json', 'planets-current.json'):
        path = ROOT / 'research/expansion/naming' / universe
        if path.exists():
            landmarks.update({r['id']: r for r in json.loads(path.read_text())})
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
        if decision in ('procedural', 'drop'):
            procedural.append({'id': lid, 'label': lm['label'], 'reason': entry.get('reason', '') or 'not a key definition, named theorem or central construction'}); continue
        if decision != 'name':
            rejected.append((lid, f'unknown decision {decision!r}')); continue
        name = (entry.get('label') or '').strip()
        problems = []
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
        # Nodes of source decompositions are named and hidden through the stage presentation.
        presentation = json.loads((ROOT / 'data/stage-presentation.json').read_text())
        is_node = lambda pid: '::landmark:' not in pid
        named_nodes = sum(1 for pid in accepted if is_node(pid))
        hidden_nodes = sum(1 for e in procedural if is_node(e['id']))
        for pid, name in [(pid, name) for pid, name in accepted.items() if is_node(pid)]:
            item = presentation.setdefault(pid, {})
            item['title'] = name
            item.setdefault('summary', (landmarks[pid].get('excerpt') or name)[:400])
            item.pop('hidden', None)
            del accepted[pid]
        for entry in [e for e in procedural if is_node(e['id'])]:
            item = presentation.setdefault(entry['id'], {})
            item['hidden'] = True
            item.setdefault('summary', (landmarks[entry['id']].get('excerpt') or entry['reason'])[:400])
            procedural.remove(entry)
        for pid in [e['id'] for e in seen.values() if e.get('decision') == 'keep' and is_node(e['id'])]:
            presentation.get(pid, {}).pop('hidden', None)
        (ROOT / 'data/stage-presentation.json').write_text(json.dumps(presentation, indent=2, ensure_ascii=False) + '\n')
        print(f'decomposition planets: {named_nodes} named, {hidden_nodes} hidden')
        hidden = json.loads((ROOT / 'data/landmark-hidden.json').read_text())
        merged = dict(curated); merged.update(accepted)
        for item in procedural:
            merged.pop(item['id'], None)
            hidden[item['id']] = f"{job}: {item['reason']}"[:200]
        for lid in list(accepted) + [e['id'] for e in seen.values() if e.get('decision') == 'keep' and not is_node(e['id'])]:
            hidden.pop(lid, None)
        (ROOT / 'data/landmark-labels.json').write_text(json.dumps(merged, indent=2, ensure_ascii=False) + '\n')
        (ROOT / 'data/landmark-hidden.json').write_text(json.dumps(dict(sorted(hidden.items())), indent=2, ensure_ascii=False) + '\n')
        (ROOT / f'research/expansion/naming/{job}.procedural.json').write_text(json.dumps(procedural, indent=2, ensure_ascii=False) + '\n')
        print(f'applied: {len(merged)} names, {len(hidden)} hidden planets; {len(procedural)} dropped by this job')
    return 0 if not undecided else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
