#!/usr/bin/env python3
"""Browser checks for the Tau Ceti build (tauceti/index.html): only the roadmaps
Tau Ceti's Progress page reports, its own layer counts as the headline, and each
roadmap's live report."""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
url = next((arg for arg in sys.argv[1:] if not arg.startswith('--')), (REPO / 'tauceti' / 'index.html').as_uri())
checks, errors = [], []


def record(name, ok):
    checks.append(name)
    if not ok:
        print(json.dumps({'failedCheck': name, 'checks': checks, 'pageErrors': errors}, indent=2))
        raise AssertionError(name)


with sync_playwright() as p:
    browser = p.chromium.launch()
    for scope, viewport in (('Desktop', {'width': 1440, 'height': 900}), ('Phone', {'width': 390, 'height': 844})):
        page = browser.new_page(viewport=viewport)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(url)
        page.wait_for_function('window.TauExplorer')
        page.wait_for_timeout(1200)
        record(scope + ' shows only the roadmaps Tau Ceti\'s Progress page reports', page.evaluate("""() => {
          const d=TauExplorer.data, board=Object.keys(d.taucetiProgress.roadmaps);
          return d.variant==='tauceti' && d.roadmaps.length===board.length && d.roadmaps.every(r=>r.origin==='tauceti' && board.includes(r.id))
            && TauExplorer.getUniverse().constellations.filter(c=>!c.unmapped).length===board.length && !d.papers.length; }"""))
        record(scope + ' the headline is the share of the board\'s layers done, with its counts beneath', page.evaluate("""() => {
          const c=TauExplorer.data.taucetiProgress.counts, percent=Math.round(c.done/c.total*100), count=document.getElementById('atlas-count').textContent;
          return document.getElementById('atlas-percent').textContent===percent+'%'
            && count.includes(`${c.done.toLocaleString()} of ${c.total.toLocaleString()} layers done`) && count.includes(`${c.partial.toLocaleString()} partial`)
            && getComputedStyle(document.querySelector('.scale-marker')).display!=='none' && document.getElementById('atlas-marker').style.left===percent+'%'; }"""))
        record(scope + ' the panel says where the data comes from and names roadmaps not yet placed', page.evaluate("""() => {
          const e=document.getElementById('atlas-source'), u=TauExplorer.data.taucetiProgress.unplaced;
          return e.textContent.startsWith("From Tau Ceti's Progress page") && e.textContent.includes(`${u.length} newer roadmap`) && u.every(x=>e.title.includes(x.id.split('/').pop())); }"""))
        if scope == 'Desktop':
            roadmap = page.evaluate("() => Object.entries(TauExplorer.data.taucetiProgress.roadmaps).find(([id,b])=>b.status)[0]")
            page.evaluate("id => TauExplorer.openItem(id)", roadmap)
            page.wait_for_timeout(700)
            record('A roadmap shows its share of layers done, its counts and one segment per layer', page.evaluate("""id => {
              const segments=document.querySelectorAll('#inspector-content .layer-segments i'), leaves=TauExplorer.progress.roadmapLeaves(id);
              const done=leaves.filter(l=>TauExplorer.progress.leafState(l).status==='complete').length;
              return segments.length===leaves.length && document.querySelector('#inspector-content .progress-caption strong').textContent===Math.round(done/leaves.length*100)+'%'; }""", roadmap))
            record('A roadmap links to its live report and progress log', page.evaluate("""() => {
              const links=[...document.querySelectorAll('#inspector-content .report-links a')].map(a=>a.href);
              return [...document.querySelectorAll('#inspector-content .section-label')].some(h=>h.textContent==="Tau Ceti's latest report")
                && links.some(h=>h.endsWith('/STATUS.md')) && links.some(h=>h.endsWith('/PROGRESS.md')); }"""))
            layer = page.evaluate("() => Object.keys(TauExplorer.data.taucetiProgress.remaining)[0]")
            page.evaluate("id => TauExplorer.openStage(id)", layer)
            page.wait_for_timeout(700)
            record('A layer shows what its latest report says is still to do', page.evaluate("""id => [...document.querySelectorAll('#inspector-content .section-label')].some(h=>h.textContent==='Still to do')
              && document.getElementById('inspector-content').textContent.includes(TauExplorer.data.taucetiProgress.remaining[id].slice(0,40))""", layer))
        record(scope + ' has no application errors', not errors)
        page.close()
    browser.close()
print(json.dumps({'url': url, 'checks': checks, 'result': 'PASS'}, indent=2))
