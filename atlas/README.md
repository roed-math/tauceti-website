# Tau Ceti Explorer

An interactive atlas of mathematical roadmaps: explore the subject branches, inspect a roadmap, then open its internal stage layers and dependencies.

**[Open the interactive atlas](https://cbirkbeck.github.io/tauceti-explorer/)**

The atlas also runs entirely offline. Download `index.html` and open it in a browser; its roadmap text, data, graph library, and interface are embedded in that single file. No installation, account, or local server is required.

## Explore

- Click a node to read its description, progress, prerequisites, and consumers.
- Double-click a node, or use its Open button, to descend from subjects to roadmaps to stage layers.
- Search for a subject, roadmap, or individual stage. Open the full roadmap to read its outline and source text.
- Scroll to zoom, drag to pan, and use Fit to recover the whole view. Export the current graph as SVG.
- Open **Mission status** for a progress breakdown by area. Filter the collection by layer activity, and pin roadmaps for your next visit.
- Use **Browse** on a phone, or **⌘/Ctrl K** on a keyboard to search. View links preserve the current map.
- Mathematics is typeset offline with native MathML; hover a formula to see its source.

Subject branches organize the landscape visually. Dependency arrows point **prerequisite → consumer**. Branches and document-reference links are navigation aids; they do not add mathematical prerequisite claims.

## Included snapshot

| Item | Count |
| --- | ---: |
| Subject groups | 13 |
| Roadmaps | 180 |
| Stage nodes | 1,604 |
| Terminal targets counted for progress | 1,543 |
| Roadmap dependency links | 1,011 |
| Stage dependency links | 3,508 |
| Sanitized source Markdown documents | 214 |

The September 2026 edition combines 152 revised number-theory campaign roadmaps with 28 roadmaps from [TauCetiRoadmap](https://github.com/TauCetiProject/TauCetiRoadmap). The source documents are bundled under [`content/`](content/). The 12 companion guides include the campaign execution protocol, conventions and scope. Reference PDFs and extracted book text are not included. [`data/PUBLICATION.json`](data/PUBLICATION.json) records the publication checks; the atlas and status data retain source hashes, reported commit IDs, and dates.

The source snapshot includes local working-tree material and older maintained progress reports. It is not a fresh verification of the Tau Ceti code or of every mathematical proof. Roadmap-level cycles can reflect dependencies between different early and late stages; the encoded stage dependency graph is acyclic.

## Progress colours and local updates

Stage colours distinguish not-started, in-progress, and complete statuses. Unknown status is explicitly labelled. The amber midpoint is a status category, not a claim that a theorem is half proved.

Roadmap and subject percentages count **completed terminal targets divided by all tracked terminal targets**. Unknown targets remain in the denominator. A parent stage and its children are never counted twice; collection roadmaps aggregate their child roadmaps. Completing every extracted target does not by itself certify all source-proof, acceptance, or formal-verification requirements. A separately displayed roadmap-level report retains its own provenance.

Open a stage to change its status and add an evidence note. A parent-stage update includes its descendants. Your changes are local overrides, stored in the current browser when storage is available; they do not edit the published data or upstream repositories. “Use recorded status” removes the corresponding local override and its descendants.

Use **Progress → Download offline atlas** for a standalone HTML copy.

Use **Progress → Export progress** to save a JSON backup. Import restores a validated local snapshot, replacing the current local overrides. Export before changing browsers or opening the atlas from a different location: browser storage is tied to its origin and may be unavailable or cleared. If storage is blocked, updates remain available during the current page session and can still be exported.

## Rebuild

Requires Python 3.9 or later, using only its standard library:

```sh
python3 scripts/build.py
```

This writes the self-contained `index.html` and a `BUILD.json` report containing counts and input/output hashes. It reads only repository files and makes no network requests. An alternate output location can be supplied with `--output`.

The builder packages the checked-in snapshot. To update the published mathematics or imported reports, update the corresponding documents and data, retain their provenance, and rebuild. Rebuilding does not fetch upstream changes or import anyone's browser-local progress.

### Repository layout

- `src/`: interface, graph, Markdown reader, progress state, and styles.
- `vendor/`: bundled D3, KaTeX, and their licences.
- `data/atlas.json`: roadmap text, stage hierarchy, and graph relationships.
- `data/status.json`: explicitly mapped source-status evidence.
- `content/`: sanitized source Markdown documents.
- `scripts/build.py`: portable offline builder.
- `index.html`: generated entry point for offline use and GitHub Pages.

The GitHub Pages target is [cbirkbeck.github.io/tauceti-explorer](https://cbirkbeck.github.io/tauceti-explorer/).

## Browser validation

The optional browser suite needs Python's `playwright` package and its Chromium browser:

```sh
python3 tests/validate_browser.py
```

It checks navigation, status persistence/import, mathematics rendering, companion links, filters, pins, mobile browsing and the independent offline download. Reports and screenshots are written to a temporary directory. To check the hosted site, pass its URL as the first argument.

## Licence and acknowledgements

This repository uses the [Apache License 2.0](LICENSE), copied from the TauCetiRoadmap source. The roadmap material is derived from Tau Ceti and its contributors; see [NOTICE](NOTICE). Bundled D3 v5.15.0 retains Mike Bostock's copyright and its [BSD-style licence](vendor/D3-LICENSE.txt). KaTeX 0.16.28 is distributed under its [MIT licence](vendor/KaTeX-LICENSE.txt).
