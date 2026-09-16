#!/usr/bin/env python3
"""Build the local explorer's self-contained data from the revised campaign.

Only Python's standard library is used. Regenerate with:
    python3 build_data.py [--source CAMPAIGN] [--graph GRAPH_DIRECTORY]
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
DEFAULT_SOURCE = None  # pass --source: the revised campaign directory (EDITION.json, campaign/, ...)
DEFAULT_GRAPH = None  # pass --graph: the campaign graph directory (NODE_INDEX.json, EDGE_INDEX.json)
# These identifiers, labels and colours match the existing full Mermaid graph.
GROUPS = [
    ('foundations', 'Shared foundations', '#e2e8f0'),
    ('classical', 'Classical, analytic and computational number theory', '#dbeafe'),
    ('diophantine', 'Arithmetic geometry and Diophantine methods', '#dcfce7'),
    ('modular', 'Modular, Shimura and Galois theory', '#fef3c7'),
    ('automorphic', 'General automorphic theory', '#ffedd5'),
    ('diamonds', 'Diamonds and geometric Langlands', '#f3e8ff'),
    ('cohomology', 'Cohomology and nonarchimedean geometry', '#cffafe'),
    ('motivic', 'K-theory, motives, periods and Habiro', '#fce7f3'),
    ('iwasawa', 'Iwasawa, Euler systems and BSD', '#fee2e2'),
    ('functionfields', 'Function fields and higher local fields', '#ecfccb'),
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def plain(markdown: str) -> str:
    """A short plain-text preview; the complete Markdown is kept separately."""
    text = re.sub(r'<[^>]+>', '', markdown)
    text = re.sub(r'!?\[([^\]]+)\]\([^\n]*?\)', r'\1', text)
    text = re.sub(r'[*`]', '', text)
    text = re.sub(r'^\s*[-+]\s+', '', text, flags=re.M)
    return re.sub(r'\s+', ' ', text).strip()


def short(text: str, limit: int = 1150) -> str:
    if len(text) <= limit:
        return text
    # A preview only; avoid cutting a word or implying the source ends here.
    return text[:limit].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'


def summary_for(markdown: str, stage_titles: list[str]) -> str:
    """Prefer the author's scope prose, not campaign/review scaffolding."""
    lines = markdown.splitlines()
    headings = [(i, line.lstrip('# ').strip()) for i, line in enumerate(lines)
                if re.match(r'^#{1,6}\s', line)]
    preferred = [(i, title) for i, title in headings if i > 0
                 and re.search(r'\b(scope|purpose)\b', title, re.I)
                 and not re.search(r'^(?:[A-Z][A-Z\d]*[.\d:]|September)', title)]
    blocks = []
    if preferred:
        start = preferred[0][0] + 1
        end = next((i for i, _ in headings if i >= start), len(lines))
        blocks.append('\n'.join(lines[start:end]))
    # Introductory paragraphs are next best. Several historical roadmaps have
    # a campaign boilerplate paragraph followed by the genuine introduction.
    first_stage = next((i for i, title in headings if i and
                        re.match(r'(?:[A-Z][A-Z\d]*[.\d:]|[A-Z]\d+)', title)), len(lines))
    blocks.append('\n'.join(lines[1:first_stage]))
    ignored = (
        'revision:', 'status:', 'this specification uses the shared', 'the milestones below',
        'the milestones are dependency ordered', 'subject families:', 'use the campaign',
        'every stage requires', 'these stages must', 'suggested home:',
        'references are ', 'references:', 'sources:', 'the source register',
        'this roadmap is part of', 'these checkpoints preserve', 'campaign dependencies:',
        'kedlaya chapters 20-21 are explicitly incomplete',
    )
    for block in blocks:
        candidates = []
        for para in re.split(r'\n\s*\n', block):
            stripped = para.strip()
            if not stripped or stripped.startswith(('#', '<', '|', '```', '- ', '* ')):
                continue
            value = plain(stripped)
            if len(value) < 35 or value.lower().startswith(ignored):
                continue
            if 'canonical owner table and original-to-canonical' in value:
                continue
            candidates.append(value)
            if len(' '.join(candidates)) >= 450 or len(candidates) == 2:
                break
        if candidates:
            result = ' '.join(candidates)
            if len(result) < 450:
                result += ' Stages cover ' + '; '.join(stage_titles[:4]).rstrip('.') + '.'
            return short(result)
    return 'Stages cover ' + '; '.join(stage_titles[:5]).rstrip('.') + '.'


def human_suffix(text: str) -> str:
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    return text.replace('-', ' ').replace('_', ' ').strip()


def stage_title(task: dict, catalogue: dict, markdown: str) -> str:
    """Retain genuine stage/substage labels, including named bold checkpoints."""
    key = task['stage']
    lines = markdown.splitlines()
    source_index = max(0, task['target_line'] - 1)
    # Anchor-based K-source readiness checkpoints have bold descriptive labels.
    for line in lines[source_index:source_index + 6]:
        match = re.match(r'\s*\*\*(.+?)\*\*', line)
        if match and key.lower() in match.group(1).lower():
            candidate = plain(match.group(1)).rstrip('.')
            candidate = re.sub(r'^' + re.escape(key) + r'\s*[.\-–—:]?\s*', '', candidate)
            if candidate and candidate != key and not re.fullmatch(r'\([^)]*\)', candidate):
                # A label such as 'Finiteness (N.3:finite-generation)' still
                # identifies its particular substage and can stand alone.
                candidate = re.sub(r'\s*\(' + re.escape(key) + r'\)', '', candidate)
                return candidate.strip(' .—–-') or key
    # target_text contains the heading enclosing an anchor's full context.
    headings = [plain(re.sub(r'^#{1,6}\s+', '', line))
                for line in task['target_text'].splitlines()
                if re.match(r'^#{1,6}\s+', line)]
    heading = headings[0] if headings else key
    base_key = key.split(':', 1)[0]
    for prefix in (key, base_key):
        if re.match(r'^' + re.escape(prefix) + r'(?:\b|[ .:—–-])', heading):
            heading = re.sub(r'^' + re.escape(prefix) + r'\s*[.\-–—:]?\s*', '', heading)
            break
    heading = heading.strip(' .—–-') or key
    if ':' in key and key not in (headings[0] if headings else ''):
        suffix = human_suffix(key.split(':', 1)[1])
        if suffix.lower() not in heading.lower():
            heading += ' — ' + suffix
    return heading


# Repository source integration. Reading this checkout never mutates it.
def heading_slug(text):
    value = plain(text).lower()
    value = re.sub(r'[^\w\- ]', '', value, flags=re.U)
    return value.replace(' ', '-')


def repository_inventory(repo):
    import subprocess
    repo = repo.resolve()
    paths = sorted(p for base in ('TauCetiRoadmap', 'Completed')
                   for p in (repo / base).rglob('README.md')
                   if p.parent != repo / base and 'references' not in [s.lower() for s in p.parts])
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo, text=True).splitlines()
    snapshot = {'repositoryPath': str(repo), 'head': head, 'dirty': bool(dirty), 'dirtyEntries': dirty,
                'source': 'local_working_tree', 'remoteRefreshed': False,
                'meaning': 'Local README and maintained report snapshot; no fresh proof verification.'}
    roadmaps, stages = [], []
    for path in paths:
        relative = path.relative_to(repo).as_posix()
        rid = 'tauceti:' + path.parent.relative_to(repo).as_posix()
        markdown = path.read_text(encoding='utf-8')
        lines = markdown.splitlines()
        headings, candidates = [], []
        seen_slugs = Counter()
        in_fence = False
        current_heading = None
        for i, line in enumerate(lines):
            if re.match(r'^\s*```', line):
                in_fence = not in_fence
            if in_fence:
                continue
            match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if match:
                level, title = len(match.group(1)), plain(match.group(2))
                slug = heading_slug(title)
                index = seen_slugs[slug]
                seen_slugs[slug] += 1
                slug += f'-{index}' if index else ''
                current_heading = {'line': i + 1, 'level': level, 'title': title, 'anchor': slug}
                headings.append(current_heading)
                stage_match = re.match(r'^(Layer\s+[\w.′]+|Lane\s+\w+|Stage\s+[\w.]+|Part\s+\w+|Milestone\b[^:—–]*|\d+[A-Z]|[A-Z]\d+[′]?)(?=\s|[—–:,.]|$)', title)
                if stage_match:
                    candidates.append(dict(current_heading, key=stage_match.group(1), kind='heading'))
                continue
            # Explicit named milestones also appear as bold list labels.
            bold = re.match(r'^\s*(?:[-*]\s+)?\*\*((?:L\d+[A-Z]?|Milestone(?:\s+\d+)?)\s*[—–:]\s*.+?)\*\*', line)
            if bold and current_heading and (current_heading['title'].startswith(('Layers ', 'Part '))):
                title = plain(bold.group(1)).rstrip('.')
                key = re.split(r'\s*[—–:]\s*', title, 1)[0]
                slug = 'milestone-' + heading_slug(title)
                candidates.append({'line': i + 1, 'level': (current_heading or {}).get('level', 1) + 1,
                                   'title': title, 'anchor': slug, 'key': key,
                                   'kind': 'bold_milestone'})
                continue
            numbered = re.match(r'^(\d+)\.\s+(.+)$', line)
            if numbered and current_heading and current_heading['title'].startswith('Lane '):
                key = re.match(r'Lane\s+(\w+)', current_heading['title']).group(1) + '.' + numbered.group(1)
                raw_title = numbered.group(2)
                # Prefer a bold label, preserving the full content in description.
                btitle = re.match(r'\*\*(.*?)\*\*', raw_title)
                title = plain(btitle.group(1) if btitle else raw_title).rstrip('.')
                candidates.append({'line': i + 1, 'level': current_heading['level'] + 1,
                                   'title': title, 'anchor': 'milestone-' + key.lower().replace('.', '-'),
                                   'key': key, 'kind': 'numbered_milestone'})
        stage_ids = []
        for item in candidates:
            start = item['line'] - 1
            boundary = min([len(lines)] + [h['line'] - 1 for h in headings
                        if h['line'] > item['line'] and h['level'] <= item['level']]
                        + [other['line'] - 1 for other in candidates
                        if other['line'] > item['line'] and other['level'] <= item['level']])
            parent = next((other for other in reversed(candidates)
                           if other['line'] < item['line'] and other['level'] < item['level']
                           and not any(other['line'] < h['line'] < item['line'] and h['level'] <= other['level'] for h in headings)), None)
            sid = rid + '#' + item['anchor']
            stage_ids.append(sid)
            stage = {'id': sid, 'owner': rid, 'key': item['key'], 'title': item['title'],
                     'description': '\n'.join(lines[start:boundary]).strip(),
                     'requires': [], 'consumers': [], 'depth': 0, 'sourcePath': str(path),
                     'sourceLine': item['line'], 'contextStartLine': item['line'],
                     'contextEndLine': boundary, 'status': 'unknown', 'origin': 'tauceti',
                     'repositoryPath': relative, 'anchor': item['anchor'],
                     'sectionKind': item['kind'], 'headingLevel': item['level'],
                     'parentStageId': rid + '#' + parent['anchor'] if parent else None,
                     'statusSnapshot': snapshot,
                     'firstAction': 'Read the source README and its maintained status reports; confirm current proof status before claiming work.'}
            stages.append(stage)
        title = next((plain(l[2:]) for l in lines if l.startswith('# ')), path.parent.name)
        title = re.sub(r'^Roadmap:\s*', '', title)
        title = title[:1].upper() + title[1:]
        parent_path = next((p.parent for p in paths if p.parent in path.parent.parents), None)
        roadmaps.append({'id': rid, 'title': title, 'readme': markdown,
                         'summary': summary_for(markdown.split('\n## ', 1)[0], [s['title'] for s in stages if s['owner'] == rid]),
                         'sourcePath': str(path), 'repositoryPath': relative,
                         'stages': stage_ids, 'prerequisites': [], 'consumers': [],
                         'origin': 'tauceti', 'lifecycle': 'completed' if relative.startswith('Completed/') else 'active',
                         'parentRoadmapId': 'tauceti:' + parent_path.relative_to(repo).as_posix() if parent_path else None,
                         'statusMarkdown': (path.parent / 'STATUS.md').read_text() if (path.parent / 'STATUS.md').exists() else '',
                         'progressMarkdown': (path.parent / 'PROGRESS.md').read_text() if (path.parent / 'PROGRESS.md').exists() else '',
                         'statusSnapshot': snapshot, 'sections': headings,
                         'sourceSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'statusSha256': hashlib.sha256((path.parent / 'STATUS.md').read_bytes()).hexdigest() if (path.parent / 'STATUS.md').exists() else None,
                         'progressSha256': hashlib.sha256((path.parent / 'PROGRESS.md').read_bytes()).hexdigest() if (path.parent / 'PROGRESS.md').exists() else None,
                         'suggestedPath': str(path.parent / 'Suggested.lean') if (path.parent / 'Suggested.lean').exists() else None})
    parent_ids = {s['parentStageId'] for s in stages if s['parentStageId']}
    for stage in stages:
        stage['isLeaf'] = stage['id'] not in parent_ids
    inventory = {'snapshot': snapshot, 'roadmapCount': len(roadmaps), 'stageCount': len(stages),
                 'roadmaps': [{k: r[k] for k in ('id', 'title', 'repositoryPath', 'sourcePath', 'lifecycle', 'parentRoadmapId', 'stages')} for r in roadmaps],
                 'stages': [{k: s[k] for k in ('id', 'owner', 'key', 'title', 'sourceLine', 'repositoryPath', 'parentStageId', 'isLeaf')} for s in stages]}
    (OUT / 'REPOSITORY_INVENTORY.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n')
    return roadmaps, stages, snapshot


def extend_with_repository(data, repo):
    from urllib.parse import unquote
    roadmaps, stages, snapshot = repository_inventory(repo)
    existing_areas = {r['id']: r for r in data['roadmaps']}
    local_areas = {r['id']: r for r in roadmaps}
    by_path = {Path(r['sourcePath']).resolve(): r for r in roadmaps}
    by_short = {Path(r['sourcePath']).parent.name: r for r in roadmaps}
    local_stages = {s['id']: s for s in stages}
    stage_keys = {(s['owner'], s['key']): s for s in stages}
    extra_groups = [
        {'id': 'analysis', 'label': 'Analysis, probability and PDE', 'color': '#d8eafe', 'roadmapIds': []},
        {'id': 'topology', 'label': 'Topology, manifolds and Floer theory', 'color': '#d2f1e7', 'roadmapIds': []},
        {'id': 'algebra', 'label': 'Algebra, representation theory and Lie groups', 'color': '#e7dcfa', 'roadmapIds': []},
    ]
    groups = {g['id']: g for g in data['groups'] + extra_groups}
    for r in roadmaps:
        relative = r['repositoryPath']
        short_name = Path(r['sourcePath']).parent.name
        GROUP_FOR = {
            'algebra': {'ReductiveGroups', 'CFSGStatement', 'DGAInfinity', 'ZigzagPreprojective', 'StablePeriodicCurved', 'GrothendieckEulerForms', 'ProfiniteProPGroups', 'ProfiniteCohomology'},
            'topology': {'CombinatorialHeegaardFloer', 'GeometricTopology', 'HeegaardFloer', 'UniversalCovers', 'AlgebraicTopology', 'HopfRinow', 'FuchsianOrbifolds'},
            'modular': {'ModularForms', 'ModularCurves'},
            'diophantine': {'JacobianChallenge', 'EllipticCurves', 'AlgebraicCurves', 'StableReduction', 'BelyiMaps'},
            'classical': {'Multiquadratic', 'EffectiveBounds', 'Chebotarev', 'ArithmeticDirichletSeries', 'GlobalNumberFields', 'NumberFieldArithmetic', 'LocalFieldsRamification', 'ClassFieldTheory', 'PolynomialGaloisGroups', 'GlobalQuadraticForms', 'QuadraticFormInvariants', 'IntegralLattices', 'AlgebraicCodingTheory'},
            'cohomology': {'AdicSpaces'},
            'motivic': {'HodgeStructures'},
        }
        if 'RepresentationTheory/' in relative:
            group = 'algebra'
        else:
            group = next((gid for gid, names in GROUP_FOR.items() if short_name in names), 'analysis')
        r['group'] = group
        groups[group]['roadmapIds'].append(r['id'])
    for r in data['roadmaps']:
        r['origin'], r['lifecycle'] = 'campaign', 'proposed'
        r['parentRoadmapId'] = None
    # Campaign anchor suffixes are explicit source substages; containment is
    # deliberately separate from producer/consumer dependencies.
    original_stage_ids = {s['id'] for s in data['stages']}
    for s in data['stages']:
        s['origin'] = 'campaign'
        candidate = s['owner'] + ':' + s['key'].split(':', 1)[0]
        s['parentStageId'] = candidate if ':' in s['key'] and candidate in original_stage_ids and candidate != s['id'] else None
    parent_ids = {s['parentStageId'] for s in data['stages'] if s['parentStageId']}
    for s in data['stages']:
        s['isLeaf'] = s['id'] not in parent_ids

    # Preserve every resolvable document reference as navigation metadata.
    # A cross-reference is not automatically a mathematical prerequisite.
    links, unresolved = [], []
    for r in roadmaps:
        path = Path(r['sourcePath'])
        for match in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', r['readme']):
            url = match.group(2)
            if re.match(r'\w+://', url) or url.startswith('mailto:'):
                continue
            relative, _, anchor = unquote(url).partition('#')
            target_path = (path.parent / relative).resolve() if relative else path.resolve()
            target = by_path.get(target_path)
            line = r['readme'].count('\n', 0, match.start()) + 1
            if target:
                if target['id'] == r['id'] and not anchor:
                    continue
                sid = target['id'] + '#' + anchor
                links.append({'source': r['id'], 'target': target['id'], 'kind': 'reference',
                              'label': plain(match.group(1)), 'anchor': anchor,
                              'targetStageId': sid if sid in local_stages else None,
                              'sourcePath': str(path), 'sourceLine': line, 'href': url,
                              'meaning': 'Document reference; not a claimed prerequisite.'})
            elif relative.endswith('README.md'):
                unresolved.append({'source': r['id'], 'sourceLine': line, 'href': url,
                                   'targetPath': str(target_path), 'exists': target_path.exists(),
                                   'meaning': 'Not an imported canonical roadmap in this local checkout.'})

    # Explicit source prose provides these declared roadmap dependencies.
    # Each entry includes a checked locator and the exact surrounding paragraph.
    # Navigation references and parent/child relationships are never promoted.
    new_edges = {}
    MISSING_EVIDENCE = []
    def evidence(short_name, needle):
        roadmap = by_short[short_name]
        text = roadmap['readme']
        match = re.search(r'\s+'.join(re.escape(part) for part in needle.split()), text)
        index = match.start() if match else -1
        if index < 0:
            # The quoted sentence is no longer in the upstream README: the edge is
            # not asserted, and the change is reported rather than fatal.
            MISSING_EVIDENCE.append(f'{short_name}: {needle}')
            return None
        start = text.rfind('\n\n', 0, index) + 2
        end = text.find('\n\n', index)
        end = len(text) if end == -1 else end
        return {'sourcePath': roadmap['sourcePath'], 'sourceLine': text.count('\n', 0, index) + 1,
                'text': text[start:end].strip(), 'match': needle,
                'verification': 'explicit_readme_statement', 'snapshotHead': snapshot['head']}
    def declare(producer, consumer, source_name, needle):
        p, c = by_short[producer]['id'], by_short[consumer]['id']
        row = new_edges.setdefault((p, c), {'source': p, 'target': c, 'kind': 'declared',
                                         'stageCount': 0, 'origin': 'tauceti', 'evidence': []})
        found = evidence(source_name, needle)
        if found: row['evidence'].append(found)
    declarations = [
        ('ContourIntegration','ModularForms','ModularForms','Consumes the [Contour Integration roadmap]'),
        ('ContourIntegration','ConformalMapping','ConformalMapping','consumes the sibling **ContourIntegration**'),
        ('GeometricTopology','CombinatorialHeegaardFloer','CombinatorialHeegaardFloer','which **consumes** the knot theory'),
        ('CombinatorialHeegaardFloer','GeometricTopology','GeometricTopology','*contributes* homological invariants'),
        ('CombinatorialHeegaardFloer','HeegaardFloer','CombinatorialHeegaardFloer','input the analytic roadmap\'s Lane F4'),
        ('PDE','OptimalTransport','OptimalTransport','The regularity sublayers consume the [PDE roadmap]'),
        ('GeometricTopology','OptimalTransport','OptimalTransport','Layer 7, supplies Riemannian'),
        ('OneParameterSemigroups','OptimalTransport','OptimalTransport','[one-parameter-semigroups roadmap]'),
        ('OneParameterSemigroups','PDE','OptimalTransport','PDE Lane F.26 should consume that theorem'),
        ('SemisimpleAlgebras','CharacterTheory','SemisimpleAlgebras','foundation beneath [character theory'),
        ('SemisimpleAlgebras','ReductiveGroups','SemisimpleAlgebras','and beneath the representation theory used by'),
        ('InductionRestriction','CharacterTheory','RepresentationTheory','Induction/restriction and Schur-Weyl feed character theory'),
        ('SchurWeyl','CharacterTheory','RepresentationTheory','Induction/restriction and Schur-Weyl feed character theory'),
        ('RootSystems','LieHighestWeight','LieHighestWeight','**shares vocabulary with, and depends on,**'),
        ('RootSystems','ClassicalGroups','ClassicalGroups','It rests on two dependencies'),
        ('LieHighestWeight','ClassicalGroups','ClassicalGroups','It rests on two dependencies'),
        ('SchurWeyl','ClassicalGroups','ClassicalGroups','Young symmetrizer'),
        ('LieGroups','LieHighestWeight','RepresentationTheory','Lie groups sit under the Lie-algebra and compact-group theory'),
        ('LieGroups','CompactGroups','RepresentationTheory','Lie groups sit under the Lie-algebra and compact-group theory'),
        ('SpinRepresentations','ClassicalGroups','RepresentationTheory','Spin representations complete the classical groups'),
        ('ClassicalGroups','SpinRepresentations','SpinRepresentations','It rests on [the classical-groups roadmap]'),
        ('LieHighestWeight','SpinRepresentations','SpinRepresentations','on [the highest-weight roadmap]'),
        ('RootSystems','SpinRepresentations','SpinRepresentations','root-systems roadmap'),
        ('OrthogonalL2Bases','CompactGroups','CompactGroups','Hilbert-space completeness machinery this roadmap consumes'),
        ('RootSystems','QuiverRepresentations','QuiverRepresentations','imports the Weyl-group data'),
        ('SemisimpleAlgebras','QuiverRepresentations','QuiverRepresentations','multiplicities and consumes [semisimple algebras]'),
        ('RootSystems','ReductiveGroups','ReductiveGroups','RootSystems/README.md'),
    ]
    for row in declarations:
        declare(*row)

    # Resolved external names retain their original contracts and stage edges;
    # an alias identifies a roadmap owner, not a verified supplying theorem.
    aliases = []
    for contract in data['external']:
        raw = contract['id'].removeprefix('UPSTREAM:')
        candidate = None
        if raw in by_short:
            candidate = by_short[raw]
        else:
            exact = [r for r in roadmaps if r['id'].removeprefix('tauceti:TauCetiRoadmap/') == raw]
            candidate = exact[0] if len(exact) == 1 else None
        if raw == 'ModularForms-finite-index-subgroups':
            candidate = by_short.get('ModularForms')
        if not candidate:
            continue
        alias = {'externalId': contract['id'], 'roadmapId': candidate['id'],
                 'match': 'canonical_repository_path' if raw != 'ModularForms-finite-index-subgroups' else 'named_subscope_of_canonical_ModularForms',
                 'sourcePath': candidate['sourcePath'], 'sourceSha256': candidate['sourceSha256'],
                 'meaning': 'Canonical owner found locally. Exact theorem availability and signature matching remain unverified.'}
        aliases.append(alias)
        contract['canonicalRoadmapId'] = candidate['id']
        consumers = set(contract.get('declared_by_areas', []))
        consumers.update(s['owner'] for s in data['stages'] if contract['id'] in s['requires'])
        for consumer in consumers:
            if consumer not in existing_areas:
                continue
            key = (candidate['id'], consumer)
            record = new_edges.setdefault(key, {'source': key[0], 'target': key[1], 'kind': 'declared',
                                                 'stageCount': 0, 'origin': 'campaign_upstream_alias', 'evidence': []})
            record['evidence'].append({'externalContract': contract['id'], 'alias': alias,
                                      'meaning': 'Campaign-declared prerequisite, resolved to its local canonical roadmap owner.'})

    # Extract only unambiguous named dependencies in the conformal-mapping plan.
    # They are source assertions, with evidence; numerical order is never used.
    new_stage_edges = []
    def stage_dep(owner, producer_key, consumer_key, needle):
        rid = by_short[owner]['id']
        p, c = stage_keys[(rid, producer_key)], stage_keys[(rid, consumer_key)]
        new_stage_edges.append({'source': p['id'], 'target': c['id'], 'origin': 'tauceti',
                                'evidence': evidence(owner, needle)})
    for p, c, needle in [('L1','L3','and normal (L1)'), ('L2','L3','beat it — L2'),
                          ('L4','L5','Uses L4 (reflection)'), ('L4','L6','built on L4 + L5'),
                          ('L5','L6','built on L4 + L5')]:
        stage_dep('ConformalMapping', p, c, needle)
    semirid = by_short['OneParameterSemigroups']['id']
    bochner = next(s for s in stages if s['owner'] == semirid and s['key'] == 'Milestone 1')
    bcr = next(s for s in stages if s['owner'] == semirid and s['key'] == 'Milestone 2')
    new_stage_edges.append({'source': bochner['id'], 'target': bcr['id'], 'origin': 'tauceti',
                            'evidence': evidence('OneParameterSemigroups', 'develop existence (consuming Milestone')})
    for edge in new_stage_edges:
        local_stages[edge['target']]['requires'].append(edge['source'])
        local_stages[edge['source']]['consumers'].append(edge['target'])
    for roadmap in roadmaps:
        roadmap['dependencyExtraction'] = 'Explicit selected source statements; complete mathematical dependency extraction is not certified.'
    for edge in new_edges.values():
        p, c = edge['source'], edge['target']
        pa = local_areas.get(p) or existing_areas[p]
        ca = local_areas.get(c) or existing_areas[c]
        pa['consumers'] = sorted(set(pa['consumers']) | {c})
        ca['prerequisites'] = sorted(set(ca['prerequisites']) | {p})
    data['roadmaps'].extend(roadmaps)
    data['stages'].extend(stages)
    for key in [k for k, row in new_edges.items() if not row['evidence']]:
        del new_edges[key]
    if MISSING_EVIDENCE:
        print('WARNING: dependency evidence no longer present, edges not asserted:', *MISSING_EVIDENCE, sep='\n  ')
    data['edges'].extend(new_edges.values())
    data['stageEdges'].extend(new_stage_edges)
    data['groups'] = list(groups.values())
    data['roadmapLinks'] = links
    data['upstreamAliases'] = aliases
    data['unresolvedRepositoryLinks'] = unresolved
    data['repositoryDocuments'] = [{'id': str(Path(r['sourcePath']).parent / filename),
                                     'repositoryPath': str(Path(r['repositoryPath']).parent / filename),
                                     'markdown': r[field], 'roadmapId': r['id']}
                                    for r in roadmaps for filename, field in [('STATUS.md','statusMarkdown'),('PROGRESS.md','progressMarkdown')]
                                    if r[field]]
    data['meta'].update({'roadmapCount': len(data['roadmaps']), 'stageCount': len(data['stages']),
                         'edgeCount': len(data['edges']), 'stageEdgeCount': len(data['stageEdges']),
                         'groupCount': len(data['groups']), 'campaignRoadmapCount': 152,
                         'repositoryRoadmapCount': len(roadmaps), 'repositoryStageCount': len(stages),
                         'repositorySnapshot': snapshot,
                         'scope': 'Revised number-theory specifications together with all roadmap READMEs in this local TauCetiRoadmap checkout. Maintained progress reports are snapshots; fresh proof verification is not implied.',
                         'repositoryDependencyScope': 'Selected explicit dependency statements and resolved campaign owner contracts. Every resolved document link is also kept separately for navigation; local prose has not received a complete dependency audit.'})
    (OUT / 'REPOSITORY_LINKS.json').write_text(json.dumps({'dependencies': list(new_edges.values()),
                                                         'stageDependencies': new_stage_edges,
                                                         'documentReferences': links,
                                                         'unresolvedReferences': unresolved,
                                                         'aliases': aliases}, ensure_ascii=False, indent=2) + '\n')
    return {'roadmaps': len(roadmaps), 'stages': len(stages), 'addedRoadmapEdges': len(new_edges),
            'addedStageEdges': len(new_stage_edges), 'documentReferences': len(links),
            'unresolvedLocalRoadmapReferences': len(unresolved), 'resolvedUpstreamAliases': len(aliases),
            'snapshot': snapshot}




def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='revised campaign directory')
    parser.add_argument('--graph', type=Path, required=True, help='campaign graph directory')
    parser.add_argument('--repository', type=Path, required=True, help='checkout of TauCetiProject/TauCetiRoadmap to snapshot')
    args = parser.parse_args()
    source, graph = args.source.resolve(), args.graph.resolve()
    edition = read_json(source / 'EDITION.json')
    manifest = read_json(source / 'campaign/MANIFEST.json')
    queue = read_json(source / 'campaign/WORK_QUEUE.json')['tasks']
    catalogue = read_json(source / 'campaign/STAGE_CATALOGUE.json')['stages']
    external = read_json(source / 'campaign/EXTERNAL_CONTRACTS.json')['contracts']
    node_index = read_json(graph / 'NODE_INDEX.json')
    edge_index = read_json(graph / 'EDGE_INDEX.json')
    areas = {area['name']: area for area in manifest['roadmaps']}
    readmes = {area: (source / data['path'] / 'README.md').read_text(encoding='utf-8')
               for area, data in areas.items()}
    group_ids = {label: group_id for group_id, label, _ in GROUPS}
    membership = {node['roadmap']: group_ids[node['group']] for node in node_index}
    prerequisites, consumers = defaultdict(set), defaultdict(set)
    edges = []
    for edge in edge_index:
        src, dst = edge['prerequisite'], edge['consumer']
        prerequisites[dst].add(src)
        consumers[src].add(dst)
        edges.append({'source': src, 'target': dst,
                      'kind': 'stage_supported' if edge['kind'] == 'stage_supported' else 'declared',
                      'stageCount': len(edge['stage_links'])})
    stages = []
    stage_edges = []
    by_owner = defaultdict(list)
    ext_consumers = defaultdict(list)
    for task in queue:
        by_owner[task['owner']].append(task['id'])
        stages.append({
            'id': task['id'], 'owner': task['owner'], 'key': task['stage'],
            'title': stage_title(task, catalogue, readmes[task['owner']]),
            'description': task['target_text'], 'requires': task['requires'],
            'consumers': task['consumers'], 'depth': task['navigation_depth'],
            'sourcePath': str(source / task['target_file']),
            'sourceLine': task['target_line'], 'status': task['status'],
            'sourceReviewStatus': task['source_review_status'],
            'signatureMatchStatus': task['signature_match_status'],
            'implementationStatus': task['implementation_status'],
            'firstAction': task['first_action'],
            'contextStartLine': task['context_start_line'],
            'contextEndLine': task['context_end_line'],
        })
        for producer in task['requires']:
            stage_edges.append({'source': producer, 'target': task['id']})
            if producer not in catalogue:
                ext_consumers[producer].append(task['id'])
    stage_map = {stage['id']: stage for stage in stages}
    roadmaps = []
    for name in sorted(areas):
        markdown = readmes[name]
        title = next((plain(line[2:]) for line in markdown.splitlines() if line.startswith('# ')), name)
        title = re.sub(r'^Roadmap:\s*', '', title)
        title = title[0].upper() + title[1:]
        ids = sorted(by_owner[name], key=lambda key: (stage_map[key]['sourceLine'], key))
        roadmaps.append({
            'id': name, 'title': title, 'group': membership[name],
            'summary': summary_for(markdown, [stage_map[key]['title'] for key in ids]),
            'readme': markdown, 'sourcePath': str(source / areas[name]['path'] / 'README.md'),
            'stages': ids, 'prerequisites': sorted(prerequisites[name]),
            'consumers': sorted(consumers[name]),
            'suggestedPath': str(source / areas[name]['path'] / 'Suggested.lean'),
            'executionPath': str(source / areas[name]['path'] / 'EXECUTION.md'),
        })
    for contract in external:
        contract['consumers'] = sorted(ext_consumers[contract['id']])
        contract['title'] = human_suffix(contract['id'].removeprefix('UPSTREAM:'))
    groups = [{'id': gid, 'label': label, 'color': color,
               'roadmapIds': [r['id'] for r in roadmaps if r['group'] == gid]}
              for gid, label, color in GROUPS]
    data = {
        'meta': {
            'edition': edition['edition'], 'roadmapCount': len(roadmaps),
            'stageCount': len(stages), 'edgeCount': len(edges),
            'stageEdgeCount': len(stage_edges), 'externalCount': len(external),
            'groupCount': len(groups), 'sourceRoot': str(source),
            'direction': 'prerequisite → consumer',
            'scope': 'Mathematical roadmap specifications. Source-proof audits, exact theorem-level dependency matching and formal implementation remain explicit tasks.',
            'sourceProofClosure': edition['source_proof_closure'],
            'formalCompletion': edition['formal_completion'],
            'areaGraphNote': 'Roadmap-level cycles can occur when early and late stages interleave. The stage dependency graph is acyclic.',
        },
        'groups': groups, 'roadmaps': roadmaps, 'stages': stages,
        'edges': edges, 'stageEdges': stage_edges, 'external': external,
    }
    errors = []
    def check(ok: bool, message: str):
        if not ok:
            errors.append(message)
    names = set(areas)
    stage_ids = set(stage_map)
    external_ids = {contract['id'] for contract in external}
    check(len(roadmaps) == 152, 'Expected all 152 roadmaps')
    check(len(stages) == 1312, 'Expected all 1,312 internal stages')
    check(len(edges) == 954, 'Expected all 954 roadmap arrows')
    check(len(stage_edges) == 3502, 'Expected all 3,502 stage handoffs')
    check(set(membership) == names, 'Group membership does not match roadmap set')
    check(len(stage_ids) == len(stages) and stage_ids == set(catalogue), 'Stage IDs are not a complete unique catalogue')
    check(len({(e['source'], e['target']) for e in edges}) == len(edges), 'Duplicate roadmap arrows')
    check(len({(e['source'], e['target']) for e in stage_edges}) == len(stage_edges), 'Duplicate stage handoffs')
    expected_pairs = {(dep, name) for name, area in areas.items()
                      for dep in area['dependencies'] if dep in names and dep != name}
    check({(e['source'], e['target']) for e in edges} == expected_pairs,
          'Roadmap arrows differ from the full campaign dependency set')
    for edge in edges:
        check(edge['source'] in names and edge['target'] in names, f'Unresolved roadmap arrow {edge}')
    for edge in stage_edges:
        check(edge['source'] in stage_ids | external_ids and edge['target'] in stage_ids,
              f'Unresolved stage handoff {edge}')
    computed_consumers = defaultdict(set)
    for edge in stage_edges:
        computed_consumers[edge['source']].add(edge['target'])
    for stage in stages:
        check(stage['owner'] in names, f'Unresolved owner: {stage["id"]}')
        check(bool(stage['title'] and stage['description']), f'Empty stage: {stage["id"]}')
        check(set(stage['consumers']) == computed_consumers[stage['id']], f'Consumer mismatch: {stage["id"]}')
    for roadmap in roadmaps:
        check(bool(roadmap['summary']), f'Empty roadmap description: {roadmap["id"]}')
        check(Path(roadmap['sourcePath']).exists(), f'Missing source file: {roadmap["id"]}')
    # Independently check the internal dependency order with Kahn's algorithm.
    indegree = {sid: 0 for sid in stage_ids}
    adjacency = defaultdict(list)
    for edge in stage_edges:
        if edge['source'] in stage_ids:
            adjacency[edge['source']].append(edge['target'])
            indegree[edge['target']] += 1
    ready = [sid for sid, degree in indegree.items() if not degree]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for dst in adjacency[node]:
            indegree[dst] -= 1
            if not indegree[dst]:
                ready.append(dst)
    check(visited == len(stage_ids), 'Internal stage graph contains a cycle')
    repository_report = extend_with_repository(data, args.repository)
    all_areas = {r['id'] for r in data['roadmaps']}
    all_stages = {s['id'] for s in data['stages']}
    check(len(all_areas) == len(data['roadmaps']), 'Duplicate imported roadmap IDs')
    check(len(all_stages) == len(data['stages']), 'Duplicate imported stage IDs')
    for r in data['roadmaps']:
        check(not r.get('parentRoadmapId') or r['parentRoadmapId'] in all_areas, 'Unresolved parent roadmap: ' + r['id'])
    for s in data['stages']:
        check(not s.get('parentStageId') or s['parentStageId'] in all_stages, 'Unresolved parent stage: ' + s['id'])
    for e in data['edges']:
        check(e['source'] in all_areas and e['target'] in all_areas, 'Unresolved combined roadmap edge')
    for e in data['stageEdges']:
        check(e['source'] in all_stages | external_ids and e['target'] in all_stages, 'Unresolved combined stage edge')
    check(len({(e['source'], e['target']) for e in data['edges']}) == len(data['edges']), 'Duplicate combined roadmap arrows')
    check(len({(e['source'], e['target']) for e in data['stageEdges']}) == len(data['stageEdges']), 'Duplicate combined stage arrows')
    all_stage_map = {s['id']: s for s in data['stages']}
    combined_indegree = {sid: 0 for sid in all_stages}
    combined_adjacency = defaultdict(list)
    combined_consumers = defaultdict(set)
    for e in data['stageEdges']:
        combined_consumers[e['source']].add(e['target'])
        if e['source'] in all_stages:
            combined_indegree[e['target']] += 1
            combined_adjacency[e['source']].append(e['target'])
    combined_ready = [sid for sid, degree in combined_indegree.items() if not degree]
    combined_visited = 0
    while combined_ready:
        node = combined_ready.pop()
        combined_visited += 1
        for dst in combined_adjacency[node]:
            combined_indegree[dst] -= 1
            if not combined_indegree[dst]:
                combined_ready.append(dst)
    check(combined_visited == len(all_stages), 'Combined stage graph contains a cycle')
    for s in data['stages']:
        check(set(s['consumers']) == combined_consumers[s['id']], 'Combined consumer mismatch: ' + s['id'])
        seen, parent = {s['id']}, s.get('parentStageId')
        while parent:
            check(parent not in seen, 'Stage containment cycle: ' + s['id'])
            if parent in seen:
                break
            seen.add(parent)
            parent = all_stage_map[parent].get('parentStageId')
    if (OUT / 'status_overlay.json').exists():
        overlay = read_json(OUT / 'status_overlay.json')
        # Status is embedded separately by the app builder. Validate its IDs here.
        for kind, valid_ids in [('roadmaps', all_areas), ('stages', all_stages)]:
            values = overlay.get(kind, {})
            if isinstance(values, dict):
                for key in values:
                    check(key in valid_ids, 'Unresolved status overlay ID: ' + key)
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n'
    report = {
        'valid': not errors, 'errors': errors, 'repository': repository_report,
        'combinedRoadmaps': len(data['roadmaps']), 'combinedStages': len(data['stages']),
        'combinedRoadmapEdges': len(data['edges']), 'combinedStageEdges': len(data['stageEdges']),
        'edition': edition['edition'], 'roadmaps': len(roadmaps), 'stages': len(stages),
        'roadmapEdges': len(edges), 'stageEdges': len(stage_edges),
        'externalContracts': len(external), 'referencedExternalContracts': sum(bool(ids) for ids in ext_consumers.values()),
        'groups': {group['id']: len(group['roadmapIds']) for group in data['groups']},
        'edgeKinds': dict(Counter(edge['kind'] for edge in edges)),
        'internalStageGraphAcyclic': combined_visited == len(all_stages),
        'campaignStagesRetained': len(stage_ids), 'campaignRoadmapsRetained': len(names),
        'allDescriptionsEmbedded': True, 'dataBytes': len(encoded.encode()),
        'dataSha256': hashlib.sha256(encoded.encode()).hexdigest(),
        'sourceHashes': {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in [source / 'campaign/MANIFEST.json', source / 'campaign/WORK_QUEUE.json',
                                      source / 'campaign/STAGED_DEPENDENCIES.json']},
        'summaryFallbacks': [roadmap['id'] for roadmap in roadmaps if roadmap['summary'].startswith('Stages cover ')],
        'sourceProofClosure': edition['source_proof_closure'],
        'formalCompletion': edition['formal_completion'],
    }
    (OUT / 'DATA_VALIDATION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if errors:
        raise SystemExit('\n'.join(errors))
    (OUT / 'data.json').write_text(encoded, encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
