# Tau Ceti website

A static site for the [Tau Ceti](https://github.com/TauCetiProject/TauCeti) project, served on
GitHub Pages. Eight pages: home (what Tau Ceti is, how to use it from Lean), what's inside,
contribute, growth, roadmaps (structure and progress), people, acknowledgments, and internal health.

## How it works

- `src/layout.html` is the shared shell (nav, footer); `src/pages/*.html` are the page bodies.
  `scripts/build_site.py` puts them together into `_site/`.
- The pages draw most of their figures in the browser from the data taucetiproject.org already
  publishes every three hours (`progress.json`, `pr-stats.json`, `roadmap-completion.json`,
  `pipeline-health.json` and the chart SVGs), which it serves with `Access-Control-Allow-Origin: *`.
- `scripts/build_data.py` generates the few things that are not published there, into `data/`:
  - `library-loc.json`: lines under `TauCeti/` by day, from TauCeti's git history.
  - `loc-by-topic.json`: net lines per roadmap and per arXiv category, from merged pull requests
    and their `roadmap/<Area>` labels (bors merges included).
  - `examples.json`: the showcase theorems from TauCeti's `web/examples/Examples.lean`.
  - `ci-current.json`: running and queued CI jobs, and the CI service's current chart URLs. The CI
    manifest's CORS policy admits only taucetiproject.org, so it is copied at build time.
- `.github/workflows/pages.yml` regenerates `data/` and deploys every three hours. The pull-request
  walk is cached between runs, so a warm run makes a handful of GraphQL requests (a cold one, about
  210).

Charts are plain SVG drawn by `static/js/common.js`; there are no dependencies.

## Local preview

```bash
git clone https://github.com/TauCetiProject/TauCeti.git /tmp/TauCeti
python3 scripts/build_data.py --tauceti-repo /tmp/TauCeti   # needs an authenticated gh
python3 scripts/build_site.py
python3 -m http.server -d _site 8765
```

`build_data.py --skip-prs` skips the pull-request walk; without `--tauceti-repo` it skips the
line-count history, and the growth page falls back to taucetiproject.org's chart.
