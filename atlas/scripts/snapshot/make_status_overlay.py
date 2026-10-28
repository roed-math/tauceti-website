"""Build the status overlay for a TauCetiRoadmap checkout.

Usage: python3 scripts/snapshot/make_status_overlay.py --repository <checkout> --inventory <REPOSITORY_INVENTORY.json> \
           --previous data/status.json --out <pipeline dir>/status_overlay.json

Roadmap-level status is read mechanically: a roadmap archived under Completed/ is
complete (100%, evidence: its line in Completed/README.md with the declared date), a
roadmap with a maintained STATUS.md is in progress (the 50% category, evidence: the
first paragraph under "Where this roadmap stands"), and a roadmap without a report has
no status. Every stage of an archived roadmap is complete; other stage-level entries are
carried over from the previous overlay when the stage still exists. Nothing here is a
fresh verification of proofs.
"""
import argparse, datetime, hashlib, json, re
from pathlib import Path


def declared_complete(repo):
    text = (repo / 'Completed/README.md').read_text(); lines = text.splitlines()
    out, sha = {}, hashlib.sha256(text.encode()).hexdigest()
    for i, line in enumerate(lines):
        m = re.search(r'\]\(([A-Za-z0-9]+)/README\.md\)', line)
        if not m:
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ''
        d = re.search(r'declared complete (\d{4}-\d{2}-\d{2})', line + ' ' + nxt)
        two = bool(d) and d.start() > len(line)
        out[m.group(1)] = {'date': d.group(1) if d else None, 'lineStart': i + 1, 'lineEnd': i + 2 if two else i + 1,
                           'quote': (line + '\n' + nxt).strip() if two else line.strip(), 'sha256': sha}
    return out


def reported(repo, relpath, head, today):
    path = repo / relpath / 'STATUS.md'; text = path.read_text(); lines = text.splitlines()
    hdr = re.search(r'<!--tauceti-status:v1 (\{.*?\})-->', text); meta = json.loads(hdr.group(1)) if hdr else {}
    start = next((i + 1 for i, l in enumerate(lines) if re.match(r'^##\s+Where this roadmap stands', l)), None)
    if start is None:
        start = next((i for i, l in enumerate(lines) if '**At a glance' in l), None)
    if start is None:
        start = next((i + 1 for i, l in enumerate(lines) if l.startswith('# ')), 0)
    i = start
    while i < len(lines) and not lines[i].strip():
        i += 1
    j = i
    while j < len(lines) and lines[j].strip():
        j += 1
    return {'status': 'in_progress', 'percent': 50,
            'basis': 'The maintained status report describes implemented mathematics and remaining roadmap targets; the whole roadmap is not declared complete. The percentage is the in-progress category, not a measurement.',
            'evidence': [{'path': str(path), 'repositoryPath': relpath + '/STATUS.md', 'lineStart': i + 1, 'lineEnd': j,
                          'quote': '\n'.join(lines[i:j]).strip()[:1200], 'sha256': hashlib.sha256(text.encode()).hexdigest()}],
            'commit': meta.get('to_sha', head), 'snapshotDate': meta.get('ts', today), 'snapshotStatus': 'reported',
            'sourceRepositoryCommit': head, 'source': 'upstream_checkout'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repository', type=Path, required=True); ap.add_argument('--inventory', type=Path, required=True)
    ap.add_argument('--previous', type=Path, default=None); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--source-note', default='upstream checkout')
    a = ap.parse_args()
    inv = json.loads(a.inventory.read_text()); prev = json.loads(a.previous.read_text()) if a.previous else {'stages': {}}
    head = inv['snapshot']['head']; today = datetime.date.today().isoformat()
    stages_by_roadmap = {}
    for s in inv['stages']:
        stages_by_roadmap.setdefault(s['owner'], []).append(s['id'])
    declared = declared_complete(a.repository)
    new = {'schemaVersion': prev.get('schemaVersion', 1), 'created': today, 'sourceRepositoryCommit': head, 'source': a.source_note,
           'localTauCetiCommit': prev.get('localTauCetiCommit'), 'roadmaps': {}, 'stages': {}, 'limits': prev.get('limits')}
    counts = {'complete': 0, 'reported': 0, 'unknown': 0}
    for r in inv['roadmaps']:
        rid, rel = r['id'], r['repositoryPath'].removesuffix('/README.md'); name = rel.split('/')[-1]
        if rel.startswith('Completed/'):
            d = declared.get(name, {})
            ev = {'path': str(a.repository / 'Completed/README.md'), 'repositoryPath': 'Completed/README.md', 'lineStart': d.get('lineStart'), 'lineEnd': d.get('lineEnd'), 'quote': d.get('quote', ''), 'sha256': d.get('sha256')}
            entry = {'status': 'complete', 'percent': 100, 'basis': 'Maintainers archived this roadmap as complete against its README' + (', declared %s.' % d['date'] if d.get('date') else '.'),
                     'evidence': [ev], 'commit': head, 'snapshotDate': d.get('date') or today, 'snapshotStatus': 'maintainer_completed', 'sourceRepositoryCommit': head, 'source': 'upstream_checkout'}
            new['roadmaps'][rid] = entry; counts['complete'] += 1
            for sid in stages_by_roadmap.get(rid, []):
                new['stages'][sid] = {'status': 'complete', 'basis': 'Every stage of a roadmap the maintainers archived as complete inherits the declaration.', 'evidence': [ev], 'commit': head,
                                      'snapshotDate': entry['snapshotDate'], 'snapshotStatus': 'maintainer_completed', 'sourceRepositoryCommit': head, 'source': 'upstream_checkout'}
        elif (a.repository / rel / 'STATUS.md').exists():
            new['roadmaps'][rid] = reported(a.repository, rel, head, today); counts['reported'] += 1
        else:
            counts['unknown'] += 1
    stage_ids = {s['id'] for s in inv['stages']}; carried = 0
    for sid, entry in prev.get('stages', {}).items():
        owner = sid.split('#')[0]
        if sid in stage_ids and new['roadmaps'].get(owner, {}).get('status') == 'in_progress':
            new['stages'][sid] = entry; carried += 1
    a.out.write_text(json.dumps(new, indent=1, ensure_ascii=False))
    print('roadmaps', counts, '| stages: complete', sum(1 for e in new['stages'].values() if e['status'] == 'complete'), 'carried', carried)


if __name__ == '__main__':
    main()
