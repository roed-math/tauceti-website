"""The atlas's definitions and constructions as one list page: definitions.html.

scripts/build.py writes it beside the atlas, from the same data:

- every definition and construction in a promoted blueprint (data/blueprints/),
  with the planets its workers marked as the key items of their layers
  (PROTOCOL.md section 14, at most six a layer);
- the definitions and constructions of the reviewed source decompositions that
  are still drawn, on layers without a blueprint (no one has marked those key).

The page is plain HTML that reads without a script, so it can be shared as a
link; a short script adds search and filters. What the papers use and prove
has its own page, items.html (scripts/items.py).
"""
from __future__ import annotations

import html
import re

from blueprints import planet_name

KINDS = ("definition", "construction")
# src/presentation.js, stageTitle: the atlas shows a layer's title without its "Layer 3:" prefix.
LAYER_PREFIX = re.compile(r"^(?:layer|stage|lane|phase|step|milestone)\s+(?:(?:[A-Z]{1,3}(?:[ .-]?\d+)*|\d+(?:\.\d+)*[a-z]?)\s*)?[:,—–-]\s*", re.I)


def stage_title(stage: dict, presentation: dict) -> str:
    title = (presentation.get(stage["id"]) or {}).get("title") or str(stage.get("title") or stage.get("key") or stage["id"])
    title = LAYER_PREFIX.sub("", title)
    return title[:1].upper() + title[1:]


def roadmap_title(roadmap: dict) -> str:
    return re.sub(r"^Roadmap:\s*", "", roadmap.get("title") or roadmap["id"], flags=re.I)


def collect(atlas: dict, packets: list) -> dict:
    """{"blueprints": [item], "decompositions": [item]} in reading order. packets: [(file stem, packet)]."""
    stages = {stage["id"]: stage for stage in atlas["stages"]}
    presentation = atlas.get("stagePresentation") or {}
    roadmaps = {roadmap["id"]: roadmap for roadmap in atlas["roadmaps"]}
    # A blueprint lists each declaration under its layer (scripts/blueprints.py, merge_blueprints).
    layer_of = {}
    for rid, roadmap in roadmaps.items():
        for layer, rows in ((roadmap.get("blueprint") or {}).get("layers") or {}).items():
            for row in rows:
                layer_of[rid + ":" + row[0]] = layer
                layer_of.setdefault(row[0], layer)
    found = {"blueprints": [], "decompositions": []}
    for _, packet in packets:
        for node in packet.get("nodes", []):
            layer = layer_of.get(node["id"])
            if node.get("kind") not in KINDS or layer not in stages:
                continue
            name = planet_name(node)
            title = node.get("title") or node["id"]
            found["blueprints"].append({"layer": layer, "kind": node["kind"], "planet": bool(name), "name": name or title,
                                        "title": title if name and title != name else "", "statement": node.get("statement", ""),
                                        "hypotheses": node.get("hypotheses") or [], "reviewed": not node.get("addedBy"), "id": node["id"]})
    for stage in atlas["stages"]:
        expansion = stage.get("expansion")
        if not expansion or expansion.get("blueprint") or expansion.get("kind") not in KINDS or (presentation.get(stage["id"]) or {}).get("hidden"):
            continue
        layer = stages.get(stage.get("parentStageId"))
        while layer and layer.get("expansion") and layer.get("parentStageId") in stages:
            layer = stages[layer["parentStageId"]]
        if not layer:
            continue
        name, title = stage_title(stage, presentation), expansion.get("title") or ""
        found["decompositions"].append({"layer": layer["id"], "kind": expansion["kind"], "planet": False, "name": name,
                                        "title": title if title != name else "", "statement": expansion.get("statement", ""),
                                        "hypotheses": expansion.get("hypotheses") or [], "reviewed": expansion.get("reviewed", True), "id": stage["id"]})

    def order(item):
        owner = roadmaps[stages[item["layer"]]["owner"]]
        position = owner["stages"].index(item["layer"]) if item["layer"] in owner["stages"] else len(owner["stages"])
        return (roadmap_title(owner).casefold(), owner["id"], position, not item["planet"], KINDS.index(item["kind"]))

    for items in found.values():
        items.sort(key=order)
    return found


def rich(text: str) -> str:
    """Escaped text; Lean names written in backticks become code."""
    return "".join(f"<code>{html.escape(part[1:-1])}</code>" if len(part) > 2 and part[0] == part[-1] == "`" else html.escape(part)
                   for part in re.split(r"(`[^`\n]+`)", str(text or "")))


def plural(n: int, one: str, many: str) -> str:
    return f"{n:,} {one if n == 1 else many}"


def item_html(item: dict) -> str:
    kind = "def" if item["kind"] == "definition" else "con"
    tags = f'<span class="tag">{item["kind"]}</span>' + ('<span class="tag planet">planet</span>' if item["planet"] else "")
    if not item["reviewed"]:
        tags += '<span class="tag">added in review</span>'
    sub = f'<span class="sub">{rich(item["title"])}</span>' if item["title"] else ""
    body = f'<p class="statement">{rich(item["statement"]) or "No statement recorded."}</p>'
    if item["hypotheses"]:
        body += '<p class="label">Hypotheses</p><ul>' + "".join(f"<li>{rich(h)}</li>" for h in item["hypotheses"]) + "</ul>"
    if not item["reviewed"]:
        body += '<p class="label">Added during review; not yet independently checked</p>'
    body += f'<p class="id">{html.escape(item["id"])}</p>'
    return (f'<details class="item" data-kind="{item["kind"]}" data-planet="{int(item["planet"])}"><summary>'
            f'<span class="dot {kind}{" key" if item["planet"] else ""}" aria-hidden="true"></span><span class="nm">{rich(item["name"])}</span>'
            f'<span class="tags">{tags}</span>{sub}</summary><div class="body">{body}</div></details>')


def source_html(items: list, atlas: dict, planets: bool) -> str:
    stages = {stage["id"]: stage for stage in atlas["stages"]}
    roadmaps = {roadmap["id"]: roadmap for roadmap in atlas["roadmaps"]}
    areas = {group["id"]: group.get("label") or group["id"] for group in atlas.get("groups", [])}
    out, rid, layer = [], None, None
    for item in items:
        owner = stages[item["layer"]]["owner"]
        if owner != rid:
            if rid is not None:
                out.append("</div></div></section>")  # the last layer's list, the layer, the roadmap
            rid, layer = owner, None
            mine = [x for x in items if stages[x["layer"]]["owner"] == rid]
            bits = [areas[roadmaps[rid]["group"]]] if roadmaps[rid].get("group") in areas else []
            for kind, many in (("definition", "definitions"), ("construction", "constructions")):
                n = sum(x["kind"] == kind for x in mine)
                if n:
                    bits.append(plural(n, kind, many))
            if planets:
                bits.append(plural(sum(x["planet"] for x in mine), "planet", "planets"))
            out.append(f'<section class="map"><h3>{html.escape(roadmap_title(roadmaps[rid]))}</h3><p class="map-meta">{html.escape(" · ".join(bits))}</p>')
        if item["layer"] != layer:
            if layer is not None:
                out.append("</div></div>")
            layer = item["layer"]
            key = stages[layer].get("key") or ""
            key_html = '<span class="key">' + html.escape(key) + "</span>" if key else ""
            title = stage_title(stages[layer], atlas.get("stagePresentation") or {})
            out.append(f'<div class="layer"><h4>{key_html}<span>{html.escape(title)}</span></h4><div class="items">')
        out.append(item_html(item))
    if rid is not None:
        out.append("</div></div></section>")
    return "\n".join(out)


def page(atlas: dict, packets: list) -> str:
    found = collect(atlas, packets)
    blueprints, decompositions = found["blueprints"], found["decompositions"]
    stages = {stage["id"]: stage for stage in atlas["stages"]}

    def maps(items):
        return len({stages[item["layer"]]["owner"] for item in items})

    planets = sum(item["planet"] for item in blueprints)
    kinds = {kind: sum(item["kind"] == kind for item in blueprints + decompositions) for kind in KINDS}
    total = len(blueprints) + len(decompositions)
    lede = (f"The reviewed blueprints plan {plural(len(blueprints), 'definition or construction', 'definitions and constructions')} "
            f"across {plural(maps(blueprints), 'roadmap', 'roadmaps')}. Their workers marked {planets:,} of these as planets, "
            f"the key items the atlas map draws around each layer. Another {len(decompositions):,} come from source decompositions "
            f"on layers without a blueprint yet, where nothing has been marked as key.")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Definitions and constructions · Tau Ceti Atlas</title>
<meta name="description" content="{html.escape(lede)}">
<style>
:root {{ color-scheme: light dark; --bg: #f8f7f4; --surface: #fff; --ink: #1c2025; --muted: #59626c; --faint: #7d858d; --line: #e3e0da;
  --code: #f3f1ec; --accent: #2b6a99; --accent-soft: #e5eef6; --def: #3a78b3; --con: #b0862a; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #0e1114; --surface: #151a1f; --ink: #e5e8eb; --muted: #a5aeb6; --faint: #858e97;
  --line: #252b32; --code: #1a1f25; --accent: #82b6de; --accent-soft: #19293a; --def: #6f9fcf; --con: #d9c391; }} }}
* {{ box-sizing: border-box; }}
[hidden] {{ display: none !important; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
a {{ color: var(--accent); }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .86em; background: var(--code); padding: 0 .25em; border-radius: 3px; overflow-wrap: anywhere; }}
.wrap {{ max-width: 1100px; margin: 0 auto; padding-inline: 16px; }}
header {{ padding-block: 24px 4px; }}
.eyebrow {{ text-transform: uppercase; letter-spacing: 1.4px; font-size: 11.5px; color: var(--faint); margin: 0 0 4px; }}
h1 {{ font-size: 25px; margin: 0 0 8px; letter-spacing: -.3px; }}
.lede {{ color: var(--muted); margin: 0 0 8px; max-width: 72ch; }}
.meta {{ color: var(--muted); font-size: 13.5px; margin: 0; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: 13px; color: var(--muted); margin: 10px 0 0; padding: 0; list-style: none; }}
.legend li {{ display: flex; align-items: center; gap: 7px; }}
.bar {{ position: sticky; top: 0; z-index: 5; background: var(--bg); border-bottom: 1px solid var(--line); margin-top: 14px; }}
.bar-inner {{ display: flex; flex-wrap: wrap; gap: 8px 10px; align-items: center; padding-block: 10px; }}
#search {{ flex: 1 1 300px; min-width: 0; font: inherit; font-size: 16px; padding: 7px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); }}
.chips {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.chips button {{ font: inherit; font-size: 13px; padding: 4px 11px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--muted); cursor: pointer; }}
.chips button[aria-pressed="true"] {{ border-color: var(--accent); color: var(--accent); background: var(--accent-soft); font-weight: 600; }}
#showing {{ color: var(--faint); font-size: 13px; margin: 10px 0 0; font-variant-numeric: tabular-nums; }}
main {{ padding-block: 0 48px; }}
section.source > h2 {{ font-size: 20px; margin: 30px 0 2px; }}
.source-note {{ color: var(--muted); font-size: 14px; margin: 0; max-width: 78ch; }}
section.map {{ margin-top: 22px; }}
section.map h3 {{ font-size: 17px; margin: 0; }}
.map-meta {{ font-size: 13px; color: var(--muted); margin: 2px 0 0; }}
.layer {{ margin-top: 12px; }}
.layer h4 {{ font-size: 13.5px; font-weight: 600; color: var(--muted); margin: 0 0 6px; display: flex; gap: 8px; align-items: baseline; }}
.layer h4 .key {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; color: var(--faint); font-weight: 400; flex: none; }}
.items {{ display: flex; flex-direction: column; gap: 4px; }}
details.item {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px; min-width: 0; }}
details.item:hover, details.item[open] {{ border-color: var(--faint); }}
details.item > summary {{ list-style: none; cursor: pointer; display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; column-gap: 10px; row-gap: 1px; align-items: baseline; padding: 8px 12px; }}
details.item > summary::-webkit-details-marker {{ display: none; }}
.dot {{ width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--def); align-self: center; display: inline-block; }}
.dot.con {{ border-color: var(--con); }}
.dot.key.def {{ background: var(--def); }}
.dot.key.con {{ background: var(--con); }}
.nm {{ font-weight: 500; overflow-wrap: anywhere; min-width: 0; }}
.dot.key + .nm {{ font-weight: 650; }}
.sub {{ grid-column: 2 / -1; font-size: 13px; color: var(--muted); overflow-wrap: anywhere; }}
.tags {{ display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }}
.tag {{ font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; color: var(--faint); white-space: nowrap; line-height: 1.6; }}
.tag.planet {{ color: var(--accent); border-color: currentColor; }}
.body {{ border-top: 1px solid var(--line); padding: 10px 14px 14px 34px; }}
.statement {{ white-space: pre-wrap; overflow-wrap: anywhere; max-width: 82ch; margin: 0; }}
.label {{ font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--faint); margin: 10px 0 2px; }}
.body ul {{ margin: 0; padding-left: 18px; max-width: 82ch; }}
.body li {{ overflow-wrap: anywhere; }}
.id {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; color: var(--faint); overflow-wrap: anywhere; margin: 8px 0 0; }}
footer {{ color: var(--faint); font-size: 13px; padding-block: 0 40px; }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
@media (max-width: 720px) {{
  details.item > summary {{ grid-template-columns: 12px minmax(0, 1fr); }}
  .tags {{ grid-column: 2; justify-content: flex-start; }}
  .body {{ padding-left: 14px; }}
}}
</style>
</head>
<body>
<header class="wrap">
  <p class="eyebrow">Tau Ceti Atlas</p>
  <h1>Definitions and constructions</h1>
  <p class="lede">{html.escape(lede)}</p>
  <p class="meta">{plural(kinds['definition'], 'definition', 'definitions')} · {plural(kinds['construction'], 'construction', 'constructions')} ·
    <a href="index.html">the atlas map</a> · <a href="items.html">the paper catalogue</a>, of everything the papers read so far use and prove</p>
  <ul class="legend" aria-label="Legend">
    <li><span class="dot def key" aria-hidden="true"></span>Definition, planet</li>
    <li><span class="dot con key" aria-hidden="true"></span>Construction, planet</li>
    <li><span class="dot def" aria-hidden="true"></span><span class="dot con" aria-hidden="true"></span>Not marked as key</li>
  </ul>
</header>
<div class="bar" id="bar" hidden><div class="wrap bar-inner">
  <input id="search" type="search" placeholder="Search names and statements" aria-label="Search names and statements" autocomplete="off" spellcheck="false">
  <div class="chips" role="group" aria-label="Kind"><button type="button" data-kind="all" aria-pressed="true">All</button><button type="button" data-kind="definition" aria-pressed="false">Definitions</button><button type="button" data-kind="construction" aria-pressed="false">Constructions</button></div>
  <div class="chips"><button type="button" id="planets" aria-pressed="false">Planets only</button></div>
</div></div>
<main class="wrap">
<p id="showing" aria-live="polite">{total:,} items</p>
<section class="source" id="blueprints">
<h2>Reviewed blueprints</h2>
<p class="source-note">{plural(len(blueprints), 'item', 'items')}, {planets:,} of them planets. Each blueprint was independently reviewed before it entered the atlas. Open an item to read its statement.</p>
{source_html(blueprints, atlas, True)}
</section>
<section class="source" id="decompositions">
<h2>Source decompositions</h2>
<p class="source-note">{plural(len(decompositions), 'item', 'items')} on layers without a blueprint. The map draws all of them, but no one has chosen which are key; a layer's blueprint replaces its decomposition.</p>
{source_html(decompositions, atlas, False)}
</section>
</main>
<footer class="wrap"><p>Written by <code>scripts/build.py</code> with the atlas, from the promoted blueprints (<code>data/blueprints/</code>) and the reviewed source decompositions (<code>data/decompositions/</code>). Every layer without a blueprint also shows up to four landmarks on the map, targets picked out of the roadmap's text; they are not reviewed definitions, so they are not listed here.</p></footer>
<script>
(() => {{
  'use strict';
  const $ = id => document.getElementById(id);
  const fold = t => String(t || '').toLowerCase().normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '').replace(/[-\\u2010-\\u2015\\u2212]/g, ' ').replace(/\\s+/g, ' ').trim();
  const items = [...document.querySelectorAll('details.item')], texts = items.map(d => fold(d.textContent));
  const state = {{ terms: [], kind: 'all', planets: false }};
  function apply() {{
    let shown = 0;
    items.forEach((d, i) => {{
      const ok = (state.kind === 'all' || d.dataset.kind === state.kind) && (!state.planets || d.dataset.planet === '1') && state.terms.every(w => texts[i].includes(w));
      d.hidden = !ok; if (ok) shown++;
    }});
    for (const box of document.querySelectorAll('.layer, section.map, section.source')) box.hidden = !box.querySelector('details.item:not([hidden])');
    document.querySelectorAll('[data-kind]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.kind === state.kind)));
    $('planets').setAttribute('aria-pressed', String(state.planets));
    $('showing').textContent = shown === items.length ? items.length.toLocaleString('en-GB') + ' items' : 'Showing ' + shown.toLocaleString('en-GB') + ' of ' + items.length.toLocaleString('en-GB') + ' items';
  }}
  let timer = null;
  $('search').addEventListener('input', e => {{ clearTimeout(timer); timer = setTimeout(() => {{ state.terms = fold(e.target.value).split(' ').filter(Boolean); apply(); }}, 120); }});
  document.querySelectorAll('[data-kind]').forEach(b => b.addEventListener('click', () => {{ state.kind = b.dataset.kind; apply(); }}));
  $('planets').addEventListener('click', () => {{ state.planets = !state.planets; apply(); }});
  $('bar').hidden = false;
}})();
</script>
</body>
</html>
"""
