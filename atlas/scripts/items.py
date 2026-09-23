#!/usr/bin/env python3
"""The catalogue of what the papers use and prove, as a page.

  python3 scripts/items.py

Every paper extraction (research/blueprint/papers/*.result.json, PROTOCOL.md
section 16) lists the definitions, constructions and theorems the paper uses or
proves, each with its statement, where it is in the paper, and whether the
libraries have it, a roadmap plans it, or nothing covers it yet. This writes
that catalogue as items.html, with a search index the page loads first
(data/items/index.json) and one file per paper read when it is opened
(data/items/<n>.json).
"""
from __future__ import annotations

import glob
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("definition", "construction", "theorem")
STATUSES = ("missing", "planned", "library")
DETAIL = ("id", "kind", "name", "statement", "locator", "status", "planned", "library", "note", "prerequisites", "api", "uses")


def summary(statement: str, limit: int = 160) -> str:
    """A statement's first sentence, in plain text."""
    text = " ".join(str(statement or "").split())
    text = re.sub(r"`([^`]*)`", r"\1", text)
    first = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text, maxsplit=1)[0]
    return first if len(first) <= limit else first[:limit].rsplit(" ", 1)[0] + " …"


def catalogue(results: list, papers: dict) -> dict:
    """One row per item: its name, kind, status and paper, with a sentence each."""
    known = {p["id"]: p for p in papers.get("papers", [])}
    out = {"papers": [], "names": [], "kinds": list(KINDS), "statuses": list(STATUSES), "rows": [], "summaries": [],
           "counts": {"items": 0, "papers": 0}}
    for result in results:
        pid = result.get("paper") or ""
        paper = known.get(pid, {})
        out["papers"].append({"id": pid, "short": paper.get("short") or pid, "citation": paper.get("citation") or pid,
                              "link": paper.get("link") or ""})
        index = len(out["papers"]) - 1
        for item in result.get("items", []):
            kind, status = item.get("kind", "theorem"), item.get("status", "missing")
            if kind not in out["kinds"]:
                out["kinds"].append(kind)
            if status not in out["statuses"]:
                out["statuses"].append(status)
            out["names"].append(item.get("name", ""))
            out["rows"].append([len(out["names"]) - 1, out["kinds"].index(kind), out["statuses"].index(status), index])
            out["summaries"].append(summary(item.get("statement", "")))
            out["counts"][kind] = out["counts"].get(kind, 0) + 1
            out["counts"][status] = out["counts"].get(status, 0) + 1
    out["counts"]["items"] = len(out["rows"])
    out["counts"]["papers"] = len(out["papers"])
    return out


def shard(result: dict) -> dict:
    """One paper's items in full, read when a reader opens it."""
    return {"paper": result.get("paper", ""), "summary": result.get("summary", ""), "status": result.get("status", ""),
            "items": [{key: item[key] for key in DETAIL if key in item} for item in result.get("items", [])]}


STYLE = """
:root { color-scheme: light dark; --bg: #f8f7f4; --surface: #fff; --ink: #1c2025; --muted: #59626c; --faint: #8b939b; --line: #e3e0da;
  --code: #f3f1ec; --accent: #2b6a99; --missing: #b3261e; --planned: #8a6d1f; --library: #2f7d4f; }
@media (prefers-color-scheme: dark) { :root { --bg: #0e1114; --surface: #151a1f; --ink: #e5e8eb; --muted: #a5aeb6; --faint: #7b848d;
  --line: #252b32; --code: #1a1f25; --accent: #82b6de; --missing: #f2a29c; --planned: #e0c368; --library: #6fcf97; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
a { color: var(--accent); }
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }
header { max-width: 1280px; margin: 0 auto; padding: 22px 16px 6px; }
.eyebrow { text-transform: uppercase; letter-spacing: 1.4px; font-size: 11.5px; color: var(--faint); margin: 0 0 4px; }
h1 { font-size: 24px; margin: 0 0 6px; letter-spacing: -.3px; }
.lede { color: var(--muted); margin: 0 0 4px; max-width: 70ch; }
.meta { color: var(--faint); font-size: 13px; margin: 0; }
.bar { position: sticky; top: 0; z-index: 5; background: var(--bg); border-bottom: 1px solid var(--line); }
.bar-inner { max-width: 1280px; margin: 0 auto; padding: 12px 16px 10px; display: flex; flex-wrap: wrap; gap: 8px 10px; align-items: center; }
#search { flex: 1 1 360px; min-width: 0; font: inherit; font-size: 16px; padding: 9px 12px; border-radius: 8px; border: 1px solid var(--line); background: var(--surface); color: var(--ink); }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chips button, select { font: inherit; font-size: 13px; padding: 5px 11px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--muted); cursor: pointer; }
.chips button[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, var(--surface)); font-weight: 600; }
select { border-radius: 8px; max-width: 320px; }
.layout { max-width: 1280px; margin: 0 auto; padding: 10px 16px 60px; display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: 18px; align-items: start; }
.status { color: var(--faint); font-size: 13px; margin: 4px 0 8px; }
.results { display: flex; flex-direction: column; gap: 6px; }
.item { display: block; width: 100%; text-align: left; font: inherit; color: inherit; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 8px 11px; cursor: pointer; }
.item:hover { border-color: var(--faint); } .item[aria-current="true"] { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
.item .name { font-weight: 600; overflow-wrap: anywhere; }
.item .line2 { display: flex; gap: 8px; align-items: baseline; margin-top: 2px; font-size: 12.5px; color: var(--muted); min-width: 0; }
.item .sum { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag { flex: none; font-size: 10.5px; text-transform: uppercase; letter-spacing: .7px; border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; color: var(--faint); }
.tag.missing { color: var(--missing); border-color: currentColor; } .tag.planned { color: var(--planned); border-color: currentColor; }
.tag.library { color: var(--library); border-color: currentColor; }
.panel { position: sticky; top: 70px; max-height: calc(100vh - 86px); overflow: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; }
.panel h2 { font-size: 17px; margin: 6px 0 4px; }
.panel .where { color: var(--faint); font-size: 13px; margin: 0 0 8px; }
.panel .statement { white-space: pre-wrap; background: var(--code); border-radius: 6px; padding: 10px 12px; margin: 10px 0; font-size: 14px; }
.panel .sub { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: var(--faint); margin: 14px 0 4px; }
.panel ul { margin: 4px 0; padding-left: 20px; } .panel li { margin: 2px 0; }
.more { font: inherit; font-size: 13px; margin: 6px 0; padding: 6px 12px; border-radius: 6px; border: 1px solid var(--line); background: var(--surface); color: var(--accent); cursor: pointer; }
.empty { color: var(--muted); }
footer { max-width: 1280px; margin: 0 auto; padding: 0 16px 40px; color: var(--faint); font-size: 13px; }
@media (max-width: 860px) { .layout { grid-template-columns: minmax(0, 1fr); } .panel { position: static; max-height: none; } }
"""

SCRIPT = r"""
const $ = id => document.getElementById(id);
const PAGE = 60;
let index = null, lower = [], sums = [], state = {q: '', kind: 'all', status: 'all', paper: ''}, shown = PAGE, results = [], chosen = -1;
const cache = new Map();
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

function passes(i) {
  const [, k, s, p] = index.rows[i];
  if (state.kind !== 'all' && index.kinds[k] !== state.kind) return false;
  if (state.status !== 'all' && index.statuses[s] !== state.status) return false;
  if (state.paper !== '' && p !== +state.paper) return false;
  return true;
}
function search() {
  const tokens = state.q.toLowerCase().split(/\s+/).filter(Boolean);
  const found = [];
  for (let i = 0; i < index.rows.length; i++) {
    if (!passes(i)) continue;
    if (!tokens.length) { found.push([0, i]); continue; }
    let score = 0;
    for (const t of tokens) {
      const name = lower[i], sum = sums[i];
      const s = name.startsWith(t) ? 60 : name.includes(t) ? 40 : sum.includes(t) ? 10 : 0;
      if (!s) { score = -1; break; }
      score += s;
    }
    if (score >= 0) found.push([score, i]);
  }
  if (tokens.length) found.sort((a, b) => b[0] - a[0]);
  return found.map(x => x[1]);
}
function itemHtml(i) {
  const [n, k, s, p] = index.rows[i];
  return '<button class="item" data-i="' + i + '"' + (chosen === i ? ' aria-current="true"' : '') + '><div class="name">' + esc(index.names[n]) + '</div>' +
    '<div class="line2"><span class="tag ' + esc(index.statuses[s]) + '">' + esc(index.statuses[s]) + '</span><span class="tag">' + esc(index.kinds[k]) + '</span>' +
    '<span class="sum">' + esc(index.summaries[i] || index.papers[p].short) + '</span></div></button>';
}
function render() {
  results = search();
  const n = results.length;
  $('status').textContent = n.toLocaleString() + (n === 1 ? ' item' : ' items') + (state.q || state.kind !== 'all' || state.status !== 'all' || state.paper !== '' ? ' match' : '');
  $('results').innerHTML = '<div class="results">' + results.slice(0, shown).map(itemHtml).join('') + '</div>' +
    (n > shown ? '<button class="more" id="more">Show more</button>' : '');
  document.querySelectorAll('[data-kind]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.kind === state.kind)));
}
async function show(i) {
  chosen = i;
  render();
  const [n, , , p] = index.rows[i], paper = index.papers[p];
  const panel = $('panel');
  panel.innerHTML = '<h2>' + esc(index.names[n]) + '</h2><p class="empty">Loading…</p>';
  if (!cache.has(p)) cache.set(p, fetch('data/items/' + p + '.json').then(r => r.json()));
  let data;
  try { data = await cache.get(p); } catch (e) { panel.innerHTML = '<p class="empty">Could not load this paper.</p>'; return; }
  if (chosen !== i) return;
  const item = data.items[index.rows.slice(0, i).filter(r => r[3] === p).length];
  if (!item) { panel.innerHTML = '<p class="empty">Not found.</p>'; return; }
  const list = (label, xs) => xs && xs.length ? '<p class="sub">' + label + '</p><ul>' + xs.map(x => '<li>' + esc(typeof x === 'string' ? x : JSON.stringify(x)) + '</li>').join('') + '</ul>' : '';
  panel.innerHTML = '<h2>' + esc(item.name) + '</h2>' +
    '<p class="where"><span class="tag ' + esc(item.status) + '">' + esc(item.status) + '</span> <span class="tag">' + esc(item.kind) + '</span> · ' +
    esc(item.locator || '') + '</p>' +
    '<p class="where">' + (paper.link ? '<a href="' + esc(paper.link) + '">' + esc(paper.citation) + '</a>' : esc(paper.citation)) + '</p>' +
    (item.statement ? '<div class="statement">' + esc(item.statement) + '</div>' : '') +
    list('Planned by', item.planned) + list('In the libraries', item.library) + list('Uses', item.uses) +
    list('Prerequisites', item.prerequisites) + list('API', item.api) +
    (item.note ? '<p class="sub">Note</p><p>' + esc(item.note) + '</p>' : '');
}
document.addEventListener('click', e => {
  const item = e.target.closest('.item');
  if (item) { show(+item.dataset.i); return; }
  const chip = e.target.closest('[data-kind]');
  if (chip) { state.kind = chip.dataset.kind; shown = PAGE; render(); return; }
  if (e.target.id === 'more') { shown += PAGE * 2; render(); }
});
let timer;
$('search').addEventListener('input', e => { clearTimeout(timer); timer = setTimeout(() => { state.q = e.target.value.trim(); shown = PAGE; render(); }, 120); });
$('status-filter').addEventListener('change', e => { state.status = e.target.value; shown = PAGE; render(); });
$('paper-filter').addEventListener('change', e => { state.paper = e.target.value; shown = PAGE; render(); });

(async () => {
  index = await fetch('data/items/index.json').then(r => r.json());
  lower = index.rows.map(r => index.names[r[0]].toLowerCase());
  sums = index.summaries.map(s => (s || '').toLowerCase());
  $('paper-filter').innerHTML = '<option value="">Every paper</option>' + index.papers.map((p, n) => '<option value="' + n + '">' + esc(p.short) + '</option>').join('');
  window.TauItems = {results: () => results.length, state: () => ({...state}), ready: true};
  render();
})();
"""


def page(found: dict) -> str:
    counts = found["counts"]
    kinds = "".join(f'<button data-kind="{k}" aria-pressed="false">{html.escape(k.capitalize())}s</button>' for k in found["kinds"])
    statuses = "".join(f'<option value="{html.escape(s)}">{html.escape(s.capitalize())}</option>' for s in found["statuses"])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What the papers use and prove</title>
<meta name="description" content="Every definition, construction and theorem the atlas's paper extractions found, and whether the libraries have it, a roadmap plans it, or nothing covers it yet.">
<style>{STYLE}</style>
</head>
<body>
<header>
  <p class="eyebrow">Tau Ceti Atlas</p>
  <h1>What the papers use and prove</h1>
  <p class="lede">Every definition, construction and theorem that the atlas's workers found while reading the papers, with the statement, where it is in the paper, and whether Mathlib or Tau Ceti already has it, a roadmap already plans it, or nothing covers it yet.</p>
  <p class="meta">{counts['items']:,} items from {counts['papers']:,} papers ·
    {counts.get('definition', 0):,} definitions · {counts.get('construction', 0):,} constructions · {counts.get('theorem', 0):,} theorems ·
    {counts.get('missing', 0):,} missing · {counts.get('planned', 0):,} planned · {counts.get('library', 0):,} in the libraries ·
    <a href="index.html">the atlas</a></p>
</header>
<div class="bar"><div class="bar-inner">
  <input id="search" type="search" placeholder="Search {counts['items']:,} items: a name, or words from a statement" autocomplete="off" spellcheck="false" aria-label="Search items">
  <div class="chips" role="group" aria-label="Kind"><button data-kind="all" aria-pressed="true">All</button>{kinds}</div>
  <select id="status-filter" aria-label="Status"><option value="all">Anywhere</option>{statuses}</select>
  <select id="paper-filter" aria-label="Paper"><option value="">Every paper</option></select>
</div></div>
<div class="layout">
  <section aria-label="Items"><p class="status" id="status">Loading…</p><div id="results"></div></section>
  <aside class="panel" id="panel" aria-live="polite"><p class="empty">Choose an item to read its statement and where it goes.</p></aside>
</div>
<footer><p>Written by <code>scripts/items.py</code> from the paper extractions (<code>research/blueprint/papers/*.result.json</code>). "Planned" means a roadmap layer already covers it; "missing" means nothing does yet.</p></footer>
<script>{SCRIPT}</script>
</body>
</html>
"""


def write(results: list, papers: dict, out: Path) -> dict:
    found = catalogue(results, papers)
    folder = out / "data" / "items"
    folder.mkdir(parents=True, exist_ok=True)
    compact = {"ensure_ascii": False, "separators": (",", ":")}
    (out / "items.html").write_text(page(found), encoding="utf-8")
    (folder / "index.json").write_text(json.dumps(found, **compact), encoding="utf-8")
    for n, result in enumerate(results):
        (folder / f"{n}.json").write_text(json.dumps(shard(result), **compact), encoding="utf-8")
    return found["counts"]


def main() -> int:
    results = []
    for path in sorted(glob.glob(str(ROOT / "research" / "blueprint" / "papers" / "*.result.json"))):
        try:
            results.append(json.loads(Path(path).read_text(encoding="utf-8")))
        except ValueError as exc:
            print("skipped", Path(path).name, exc)
    papers = json.loads((ROOT / "research" / "blueprint" / "papers" / "papers.json").read_text(encoding="utf-8"))
    counts = write(results, papers, ROOT)
    print(f"items: {counts['items']} from {counts['papers']} papers "
          f"({counts.get('missing', 0)} missing, {counts.get('planned', 0)} planned, {counts.get('library', 0)} in the libraries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
