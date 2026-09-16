"""Validate a status-mapping result and merge it into data/stage-status-reports.json.

Usage: python3 scripts/merge_stage_status.py research/expansion/status/STATUS-00.result.json [--apply]

Each entry {stageId, roadmapId, status, quote, lineStart, lineEnd, note} is accepted only when
the stage exists in data/atlas.json, the status is complete / in_progress / not_started /
unknown, and, for a decided status, the quote occurs verbatim in the roadmap's STATUS.md
under content/ (the file named in research/expansion/status/reported-roadmaps.json) and the
line range contains the quote's first line. "not_started" is stored as the app's "planned";
"unknown" entries are recorded nowhere. With --apply the accepted entries replace earlier
entries for the same stage in data/stage-status-reports.json, which scripts/build.py merges
over the imported status snapshot at build time. Nothing here verifies proofs: a mapped
status repeats what the maintained report says about that layer.
"""
import hashlib, json, re, sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = {'complete': ('complete', 100), 'in_progress': ('in_progress', 50), 'not_started': ('planned', 0)}


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    path = Path(argv[1]); apply = '--apply' in argv; job = path.name.split('.')[0]
    atlas = json.loads((ROOT / 'data/atlas.json').read_text()); stage_ids = {s['id'] for s in atlas['stages']}
    reported = {r['roadmapId']: r for r in json.loads((ROOT / 'research/expansion/status/reported-roadmaps.json').read_text())}
    results = json.loads(path.read_text()); accepted, rejected, unknown, seen = {}, [], 0, set()
    texts = {}
    for e in results:
        sid, rid, status = e.get('stageId'), e.get('roadmapId'), e.get('status')
        if sid in seen:
            rejected.append((sid, 'decided twice')); continue
        seen.add(sid)
        if sid not in stage_ids or not sid.startswith(rid + '#'):
            rejected.append((sid, 'unknown stage for this roadmap')); continue
        if status == 'unknown':
            unknown += 1; continue
        if status not in STATUS:
            rejected.append((sid, f'unknown status {status!r}')); continue
        report = reported.get(rid)
        if not report:
            rejected.append((sid, 'roadmap has no status report')); continue
        if rid not in texts:
            texts[rid] = (ROOT / report['statusPath']).read_text()
        text = texts[rid]; quote = (e.get('quote') or '').strip()
        if len(quote) < 12:
            rejected.append((sid, 'quote too short')); continue
        if quote not in text:
            rejected.append((sid, 'quote not found verbatim in ' + report['statusPath'])); continue
        first_line = text[:text.index(quote)].count('\n') + 1
        ls, le = e.get('lineStart'), e.get('lineEnd')
        if not isinstance(ls, int) or not isinstance(le, int) or not (ls - 2 <= first_line <= le + 2):
            rejected.append((sid, f'line range {ls}-{le} does not contain the quote (line {first_line})')); continue
        app_status, percent = STATUS[status]
        hdr = re.search(r'<!--tauceti-status:v1 (\{.*?\})-->', text); meta = json.loads(hdr.group(1)) if hdr else {}
        accepted[sid] = {'status': app_status, 'percent': percent,
                         'basis': f'The maintained status report speaks about this stage ({status.replace("_", " ")}).' + (' ' + e['note'] if e.get('note') else ''),
                         'evidence': [{'repositoryPath': report['statusPath'].replace('content/tau-ceti/', 'TauCetiRoadmap/', 1) if not report['statusPath'].startswith('content/tau-ceti/Completed/') else report['statusPath'].replace('content/tau-ceti/', '', 1),
                                       'path': report['statusPath'], 'lineStart': first_line, 'lineEnd': max(le, first_line), 'quote': quote[:1200],
                                       'sha256': hashlib.sha256(text.encode()).hexdigest()}],
                         'commit': meta.get('to_sha'), 'snapshotDate': meta.get('ts', datetime.date.today().isoformat()),
                         'snapshotStatus': 'reported_mapping', 'source': f'status-mapping job {job}'}
    missing = [s['id'] for r in reported.values() for s in r['stages'] if s['id'].startswith(tuple(set(e.get('roadmapId', '') + '#' for e in results))) and s['id'] not in seen]
    print(f'{job}: {len(results)} entries, accepted {len(accepted)}, unknown {unknown}, rejected {len(rejected)}, undecided stages {len(missing)}')
    for sid, why in rejected[:40]:
        print('  REJECT', sid[:90], '|', why)
    if apply:
        out_path = ROOT / 'data/stage-status-reports.json'
        current = json.loads(out_path.read_text()) if out_path.exists() else {}
        current.update(accepted)
        out_path.write_text(json.dumps(dict(sorted(current.items())), indent=2, ensure_ascii=False) + '\n')
        print(f'applied: data/stage-status-reports.json holds {len(current)} mapped stage statuses')
    return 0 if not rejected else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
