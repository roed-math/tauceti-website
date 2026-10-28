"""The atlas's key definitions as one list page: definitions.html (research/blueprint/PROTOCOL.md, section 19).

scripts/build.py writes it beside the atlas from the promoted key-definition
surveys (data/keydefs/KEYDEF-*.json). Each survey covers one area's share of the
paper catalogue, and an independent review accepted it before it went live.
Every entry is a notion that at least two of the atlas's papers need and that
Mathlib and Tau Ceti do not have. It says what to define, which papers need it,
which layer owns it, what the libraries have, what it depends on and how big it
is, and it gives a sample API that tells a right formalisation from a wrong one.

The page is plain HTML that reads without a script, so it can be shared as a
link; a short script adds search. What the papers use and prove, item by item,
has its own page, items.html (scripts/items.py).
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import urlencode

SIZES = {"M": "one library file: the definition with its basic API",
         "L": "a small project, with one or two missing prerequisites",
         "XL": "several files, probably more than one roadmap"}
API_ORDER = ("example", "counterexample", "theorem", "compatibility")
REQUIRED = ("id", "name", "short", "define", "library", "papers", "owners", "dependsOn", "size", "api")


def load_surveys(root: Path) -> list:
    """[(file stem, survey)] for every promoted survey. Raises ValueError on one the page cannot read."""
    surveys = []
    for path in sorted((Path(root) / "data" / "keydefs").glob("KEYDEF-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"{path.name}: not readable JSON ({exc})")
        if not isinstance(data, dict) or not isinstance(data.get("definitions"), list):
            raise ValueError(f"{path.name}: a key-definition survey lists its definitions")
        for entry in data["definitions"]:
            missing = [key for key in REQUIRED if not isinstance(entry, dict) or key not in entry]
            if missing:
                raise ValueError(f"{path.name}: a definition lacks {', '.join(missing)}")
            if entry["size"] not in SIZES or not isinstance(entry["papers"], list) or not isinstance(entry["api"], list):
                raise ValueError(f"{path.name}: {entry['id']} has a malformed size, papers or api")
        surveys.append((path.stem, data))
    return surveys


def rich(text: str) -> str:
    """Escaped text; Lean names written in backticks become code."""
    return "".join(f"<code>{html.escape(part[1:-1])}</code>" if len(part) > 2 and part[0] == part[-1] == "`" else html.escape(part)
                   for part in re.split(r"(`[^`\n]+`)", str(text or "")))


def plural(n: int, one: str, many: str) -> str:
    return f"{n:,} {one if n == 1 else many}"


def anchor(eid: str) -> str:
    return "kd-" + re.sub(r"[^a-z0-9]+", "-", eid.lower()).strip("-")


def paper_count(entry: dict) -> int:
    return len({paper.get("paper") for paper in entry["papers"] if isinstance(paper, dict)})


def ordered(surveys: list, galaxies: dict) -> list:
    """Every entry with its area, in reading order: field, area, then the number of papers that need it."""
    fields = {field["id"]: n for n, field in enumerate(galaxies.get("fields", []))}
    areas = {galaxy["id"]: (n, galaxy) for n, galaxy in enumerate(galaxies.get("galaxies", []))}
    found = []
    for _, survey in surveys:
        n, galaxy = areas.get(survey.get("area"), (len(areas), {"id": survey.get("area"), "label": survey.get("area"), "field": ""}))
        for entry in survey["definitions"]:
            found.append({**entry, "area": galaxy["id"], "areaLabel": galaxy.get("label", galaxy["id"]), "field": galaxy.get("field", ""),
                          "_order": (fields.get(galaxy.get("field"), len(fields)), n, -paper_count(entry), entry["name"].casefold())})
    found.sort(key=lambda entry: entry["_order"])
    return found


def title_of(rid: str, roadmaps: dict) -> str:
    return re.sub(r"^Roadmap:\s*", "", (roadmaps.get(rid) or {}).get("title", rid), flags=re.I)


def layer_link(layer: str, stages: dict, roadmaps: dict) -> str:
    """The layer as a link into the atlas map: "<roadmap> · <key> <title>"."""
    stage = stages.get(layer)
    if not stage:
        return f"<code>{html.escape(layer)}</code>"
    rid = stage.get("owner", "")
    href = "index.html#" + urlencode({"view": "roadmap", "id": rid, "layer": layer, "selected": layer})
    label = f"{stage.get('key') or ''} {stage.get('title') or layer}".strip()
    return f'<a href="{html.escape(href)}">{html.escape(title_of(rid, roadmaps))} · {html.escape(label)}</a>'


def roadmap_status(entry: dict, stages: dict, roadmaps: dict, assigned: dict, planned: dict) -> tuple:
    """(index cell, entry text, in a roadmap?) for one key definition. assigned: research/blueprint/keydefs/owners.json;
    planned: {node id: layer} of the promoted blueprints, where an owner's reserved node shows that it is planned."""
    layers = list(entry.get("owners") or [])
    owner = assigned.get(entry["id"]) or {}
    if not layers and owner.get("reserved") in planned:
        layers = [planned[owner["reserved"]]]
    if layers:
        names = sorted({title_of(stages[layer]["owner"], roadmaps) for layer in layers if layer in stages} or set(layers))
        return (html.escape(", ".join(names)), "Yes: " + "<br>".join(layer_link(layer, stages, roadmaps) for layer in layers), True)
    if owner.get("owner"):
        title = owner.get("title") or owner.get("roadmap")
        return (f'<span class="gap">Not yet</span> · going to {html.escape(title)}',
                f'<span class="gap">Not yet.</span> It has been given to {html.escape(title)}, whose queued job '
                f'<code>{html.escape(owner["owner"])}</code> plans it as <code>{html.escape(owner.get("reserved") or "")}</code>.', False)
    return ('<span class="gap">Not yet</span>', '<span class="gap">Not yet</span>, and no queued job receives its items: it needs a roadmap.', False)


def dependency_html(ref: str, names: dict) -> str:
    if ref in names:
        return f'<a href="#{anchor(ref)}">{html.escape(names[ref])}</a>'
    match = re.match(r"^tauceti:TauCetiRoadmap/([^#]+)(?:#(.+))?$", ref)
    if match:
        layer = (match.group(2) or "").replace("-", " ")
        return html.escape(f"Tau Ceti {match.group(1)}" + (f", {layer}" if layer else ""))
    return f"<code>{html.escape(ref)}</code>"


def papers_html(entry: dict, papers: dict) -> str:
    out = []
    for paper in entry["papers"]:
        record = papers.get(paper.get("paper"), {})
        short = record.get("short") or paper.get("paper", "")
        label = short.split(": ", 1)[0]
        items = ", ".join(paper.get("items") or [])
        text = html.escape(label)
        if record.get("link"):
            text = f'<a href="{html.escape(record["link"])}" target="_blank" rel="noopener">{text}</a>'
        out.append(f'<li title="{html.escape(short)}">{text} <span class="items">{html.escape(items)}</span></li>')
    return "<ul class=\"papers\">" + "".join(out) + "</ul>"


def entry_html(number: int, entry: dict, status: str, names: dict, papers: dict) -> str:
    depends = ", ".join(dependency_html(ref, names) for ref in entry.get("dependsOn") or []) or "none of the other key definitions"
    library = entry.get("library") or {}
    has = library.get("has") or []
    has_html = (" ".join(f"<code>{html.escape(ref)}</code>" for ref in has)) if has else "nothing that provides it"
    api = sorted(entry["api"], key=lambda item: API_ORDER.index(item.get("kind")) if item.get("kind") in API_ORDER else len(API_ORDER))
    api_html = "".join(f'<li><span class="kind">{html.escape(item.get("kind", ""))}</span> {rich(item.get("statement", ""))}</li>' for item in api)
    return f"""<article class="entry" id="{anchor(entry['id'])}">
<h3><span class="num">{number}</span> {rich(entry['name'])}</h3>
<dl class="facts">
<dt>Area</dt><dd>{html.escape(entry['areaLabel'])}</dd>
<dt>Papers needing it</dt><dd><b>{paper_count(entry)}</b>{papers_html(entry, papers)}</dd>
<dt>In a roadmap</dt><dd>{status}</dd>
<dt>Depends on</dt><dd>{depends}</dd>
</dl>
<h4>What to define</h4>
<p class="prose">{rich(entry.get('define'))}</p>
<h4>What the libraries have</h4>
<p class="prose">{has_html}.</p>
<p class="prose"><span class="label">Missing:</span> {rich(library.get('missing'))}</p>
<h4>Sample API</h4>
<p class="prose muted">A formalisation should be able to state these, and ideally prove them. A plausible wrong definition fails one of them.</p>
<ol class="api">{api_html}</ol>
</article>"""


def planned_nodes(atlas: dict) -> dict:
    """{node id: layer} for every declaration of the promoted blueprints (scripts/blueprints.py lists them by layer)."""
    found = {}
    for roadmap in atlas.get("roadmaps", []):
        for layer, rows in ((roadmap.get("blueprint") or {}).get("layers") or {}).items():
            for row in rows:
                found[row[0] if ":" in str(row[0]).split("/")[0] else f"{roadmap['id']}:{row[0]}"] = layer
    return found


def page(atlas: dict, surveys: list, galaxies: dict, papers: dict, enabled: list, assigned: dict | None = None) -> str:
    stages = {stage["id"]: stage for stage in atlas.get("stages", [])}
    roadmaps = {roadmap["id"]: roadmap for roadmap in atlas.get("roadmaps", [])}
    labels = {galaxy["id"]: galaxy.get("label", galaxy["id"]) for galaxy in galaxies.get("galaxies", [])}
    entries = ordered(surveys, galaxies)
    planned = planned_nodes(atlas)
    status = {entry["id"]: roadmap_status(entry, stages, roadmaps, assigned or {}, planned) for entry in entries}
    names = {entry["id"]: entry["name"] for entry in entries}
    published = {survey.get("area") for _, survey in surveys}
    waiting = [labels.get(area, area) for area in enabled if area not in published]
    cited = {paper.get("paper") for entry in entries for paper in entry["papers"] if isinstance(paper, dict)}
    in_roadmap = sum(1 for entry in entries if status[entry["id"]][2])
    lede = ("The definitions that at least two of the atlas's papers need and that Mathlib and Tau Ceti do not have yet. "
            "Each entry says what to define, which papers need it, whether a roadmap plans it yet and which, what the "
            "libraries already have and what it depends on, and gives a sample API that tells a right formalisation from a "
            "wrong one. The atlas's workers write each area's list from the paper catalogue, and an independent review "
            "checks it before it appears here.")
    if entries:
        meta = (f"{plural(len(entries), 'key definition', 'key definitions')} from {plural(len(published), 'area', 'areas')}, "
                f"needed by {plural(len(cited), 'paper', 'papers')}; {in_roadmap:,} of them in a roadmap so far")
    else:
        meta = "No area's list has passed its review yet"
    rows = "".join(f'<tr><td class="n">{n}</td><td><a href="#{anchor(entry["id"])}">{rich(entry["name"])}</a></td>'
                   f'<td>{html.escape(entry["areaLabel"])}</td><td class="n">{paper_count(entry)}</td><td>{status[entry["id"]][0]}</td></tr>'
                   for n, entry in enumerate(entries, 1))
    index = (f"""<section id="index"><h2>Index</h2>
<div class="table"><table><thead><tr><th class="n">#</th><th>Definition</th><th>Area</th><th class="n">Papers</th><th>In a roadmap</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="note">Papers: how many of the atlas's papers need it, counted from their catalogue items. In a roadmap: the roadmap whose plan includes it, or, for one not planned yet, the roadmap it has been given to.</p></section>"""
             if entries else "")
    body, area = [], None
    for n, entry in enumerate(entries, 1):
        if entry["area"] != area:
            area = entry["area"]
            reserve = [item for _, survey in surveys if survey.get("area") == area for item in survey.get("reserve") or []]
            near = "".join(f"<li><b>{rich(item.get('name'))}</b>: {rich(item.get('reason'))}</li>" for item in reserve if isinstance(item, dict))
            body.append(f'<h2 class="area">{html.escape(entry["areaLabel"])}</h2>'
                        + (f'<details class="reserve"><summary>{plural(len(reserve), "near miss", "near misses")}, with why each was left out</summary><ul>{near}</ul></details>' if near else ""))
        body.append(entry_html(n, entry, status[entry["id"]][1], names, papers))
    pending = (f'<p class="pending">Still being surveyed: {html.escape(", ".join(waiting))}. Each area\'s list appears here once its independent review accepts it.</p>'
               if waiting else "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Key definitions · Tau Ceti Atlas</title>
<meta name="description" content="{html.escape(lede)}">
<style>
:root {{ color-scheme: light dark; --bg: #f8f7f4; --surface: #fff; --ink: #1c2025; --muted: #59626c; --faint: #7d858d; --line: #e3e0da;
  --code: #f3f1ec; --accent: #2b6a99; --accent-soft: #e5eef6; --gap: #a3410f; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #0e1114; --surface: #151a1f; --ink: #e5e8eb; --muted: #a5aeb6; --faint: #858e97;
  --line: #252b32; --code: #1a1f25; --accent: #82b6de; --accent-soft: #19293a; --gap: #f0a27a; }} }}
* {{ box-sizing: border-box; }}
[hidden] {{ display: none !important; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
a {{ color: var(--accent); }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .86em; background: var(--code); padding: 0 .25em; border-radius: 3px; overflow-wrap: anywhere; }}
.wrap {{ max-width: 960px; margin: 0 auto; padding-inline: 16px; }}
header {{ padding-block: 26px 4px; }}
.eyebrow {{ text-transform: uppercase; letter-spacing: 1.4px; font-size: 11.5px; color: var(--faint); margin: 0 0 4px; }}
h1 {{ font-size: 27px; margin: 0 0 10px; letter-spacing: -.3px; }}
.lede {{ color: var(--muted); margin: 0 0 10px; max-width: 70ch; }}
.meta {{ color: var(--muted); font-size: 13.5px; margin: 0; }}
.pending {{ margin: 16px 0 0; padding: 10px 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--muted); font-size: 14px; }}
.bar {{ position: sticky; top: 0; z-index: 5; background: var(--bg); border-bottom: 1px solid var(--line); margin-top: 16px; }}
.bar-inner {{ display: flex; gap: 10px; align-items: center; padding-block: 10px; }}
#search {{ flex: 1 1 auto; min-width: 0; font: inherit; font-size: 16px; padding: 7px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); }}
#showing {{ color: var(--faint); font-size: 13px; white-space: nowrap; font-variant-numeric: tabular-nums; }}
main {{ padding-block: 4px 48px; }}
h2 {{ font-size: 20px; margin: 30px 0 8px; }}
h2.area {{ border-top: 1px solid var(--line); padding-top: 22px; }}
.table {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
th {{ font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--faint); font-weight: 600; }}
tr:last-child td {{ border-bottom: 0; }}
td.n, th.n {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.note {{ color: var(--faint); font-size: 13px; margin: 8px 0 0; max-width: 78ch; }}
.gap {{ color: var(--gap); }}
.entry {{ margin: 22px 0 0; padding: 16px 18px 12px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }}
.entry h3 {{ font-size: 18px; margin: 0 0 10px; line-height: 1.3; }}
.num {{ color: var(--faint); font-weight: 500; font-variant-numeric: tabular-nums; margin-right: 4px; }}
.entry h4 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--faint); margin: 14px 0 4px; }}
.facts {{ display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 4px 14px; margin: 0; font-size: 14px; }}
.facts dt {{ color: var(--faint); }}
.facts dd {{ margin: 0; min-width: 0; overflow-wrap: anywhere; }}
.papers {{ margin: 2px 0 0; padding-left: 18px; }}
.papers .items {{ color: var(--faint); font-size: 12px; }}
.prose {{ margin: 0 0 6px; max-width: 78ch; overflow-wrap: anywhere; }}
.muted {{ color: var(--muted); font-size: 13.5px; }}
.label {{ color: var(--faint); }}
.api {{ margin: 4px 0 6px; padding-left: 22px; max-width: 80ch; }}
.api li {{ margin: 4px 0; overflow-wrap: anywhere; }}
.kind {{ font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; color: var(--faint); white-space: nowrap; }}
.reserve {{ color: var(--muted); font-size: 14px; margin: 0 0 6px; }}
.reserve summary {{ cursor: pointer; color: var(--accent); }}
footer {{ color: var(--faint); font-size: 13px; padding-block: 0 40px; }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
@media (max-width: 640px) {{ .facts {{ grid-template-columns: minmax(0, 1fr); }} .facts dt {{ margin-top: 6px; }} }}
</style>
</head>
<body>
<header class="wrap">
  <p class="eyebrow">Tau Ceti Atlas</p>
  <h1>Key definitions</h1>
  <p class="lede">{html.escape(lede)}</p>
  <p class="meta">{html.escape(meta)} · <a href="index.html">the atlas map</a> · <a href="items.html">the paper catalogue</a></p>
  {pending}
</header>
{'<div class="bar" id="bar" hidden><div class="wrap bar-inner"><input id="search" type="search" placeholder="Search the key definitions" aria-label="Search the key definitions" autocomplete="off" spellcheck="false"><span id="showing" aria-live="polite"></span></div></div>' if entries else ''}
<main class="wrap">
{index}
{''.join(body)}
</main>
<footer class="wrap"><p>Written by <code>scripts/build.py</code> from the promoted key-definition surveys (<code>data/keydefs/</code>): each an area's survey of the paper catalogue, checked by an independent review, as <code>research/blueprint/PROTOCOL.md</code> section 19 describes.</p></footer>
<script>
(() => {{
  'use strict';
  const bar = document.getElementById('bar');
  if (!bar) return;
  const fold = t => String(t || '').toLowerCase().normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '').replace(/[-\\u2010-\\u2015\\u2212]/g, ' ').replace(/\\s+/g, ' ').trim();
  const entries = [...document.querySelectorAll('article.entry')], texts = entries.map(e => fold(e.textContent));
  const rows = new Map([...document.querySelectorAll('#index tbody tr')].map(row => [row.querySelector('a').getAttribute('href').slice(1), row]));
  const showing = document.getElementById('showing');
  function apply(terms) {{
    let shown = 0;
    entries.forEach((entry, i) => {{
      const ok = terms.every(w => texts[i].includes(w));
      entry.hidden = !ok; if (ok) shown++;
      const row = rows.get(entry.id); if (row) row.hidden = !ok;
    }});
    showing.textContent = shown === entries.length ? entries.length + ' entries' : shown + ' of ' + entries.length;
  }}
  let timer = null;
  document.getElementById('search').addEventListener('input', e => {{ clearTimeout(timer); timer = setTimeout(() => apply(fold(e.target.value).split(' ').filter(Boolean)), 120); }});
  bar.hidden = false;
  apply([]);
}})();
</script>
</body>
</html>
"""


def render(atlas: dict, root: Path) -> str:
    """The page for the built atlas, from the files under root."""
    root = Path(root)
    galaxies = json.loads((root / "data" / "galaxies.json").read_text(encoding="utf-8"))
    index_path = root / "data" / "items" / "index.json"
    papers = {paper["id"]: paper for paper in json.loads(index_path.read_text(encoding="utf-8")).get("papers", [])} if index_path.exists() else {}
    config = root / "research" / "blueprint" / "keydefs" / "areas.json"
    enabled = json.loads(config.read_text(encoding="utf-8")).get("enabled", []) if config.exists() else []
    owners_path = root / "research" / "blueprint" / "keydefs" / "owners.json"
    assigned = json.loads(owners_path.read_text(encoding="utf-8")).get("definitions", {}) if owners_path.exists() else {}
    return page(atlas, load_surveys(root), galaxies, papers, enabled, assigned)
