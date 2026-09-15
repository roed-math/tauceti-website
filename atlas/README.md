# Tau Ceti Explorer

An interactive atlas of mathematical roadmaps: travel from a field of galaxies to constellations of layer stars, then into planetary systems of mathematical targets.

**[Open the interactive atlas](https://cbirkbeck.github.io/tauceti-explorer/)**

The atlas also runs entirely offline. Download `index.html` and open it in a browser; its roadmap text, data, graph library, and interface are embedded in that single file. No installation, account, or local server is required.

## Explore

- Scroll or pinch toward a **roadmap galaxy** to enter its constellation of **layer stars**. Keep zooming toward a star to discover its **orbiting mathematical planets**.
- Tap or click a galaxy or star to make the same journey directly. Zoom out or use the back control to return to the previous level.
- Formula planets have short plain-text names; clicking them opens the typeset definition, theorem target or construction from the source. The details also list citations from the topic or layer and broader roadmap reading, with links back to the embedded source. Progress belongs to its layer star; planets do not carry independent completion claims.
- The details panel explains the mathematics, tracked progress, prerequisites and consumers. The Links tab exposes the actual stage pairs behind dependencies.
- Outlined galaxies mark **16 areas needing a dedicated roadmap**. They have no stages or completion percentages. Toggle them with Show unmapped areas.
- Search for a subject, roadmap, or individual stage. Open the full roadmap to read its outline and source text.
- Drag to pan and use Fit to recover the current scene. Export the current graph as SVG.
- Open **Mission status** for a progress breakdown by area. Filter the collection by layer activity, and pin roadmaps for your next visit.
- Use **Browse** on a phone, or **⌘/Ctrl K** on a keyboard to search. Mobile details share the screen with the chart; pinch, tap and back controls remain available. View links preserve the current roadmap and planetary system.
- Mathematics is typeset offline with native MathML; hover a formula to see its source.

The outer atlas groups roadmap galaxies into an irregular field of named mathematical areas, with clear space between them. At overview scale each galaxy is a point and only the area headings are written out; a galaxy's name appears once the zoom makes it legible, and hovering or selecting a galaxy shows its full title. Recorded cross-area dependencies influence the areas' placement. Only the strongest links between areas carry ink at rest: hover an area, or select a roadmap, to see its own prerequisite links, with the rest faded. Every link stays in the data and in the Links tab whether or not it is drawn. Each roadmap has one primary home, with thematic links to other relevant areas.

Inside a galaxy, stars name mathematical topics and form an irregular constellation shaped by their recorded dependencies. Prerequisite arrows point **prerequisite → consumer**; the Links tab provides supporting stage pairs. Inside a layer, planetary orbits express membership in that layer, not additional prerequisites. Dotted paths are references to related plans or context for an unmapped area, and carry no prerequisite claim. Positions, galaxy shapes and orbits are visual aids, not astronomical coordinates or mathematical measurements.

Colour on the map means one thing: recorded progress. A green, amber or red core marks a layer or roadmap recorded as complete, in progress or not started; an open ring means no progress has been recorded, and nothing is ever coloured as started or as zero percent to fill the gap. Dashed outlines mark areas without a roadmap. All marks are flat: solid fills and thin strokes, with no gradients, glows or shaded spheres. The page uses system type, one dark palette and no decorative elements; headline statistics live in Mission status rather than above the map. Scene artwork is generated locally as SVG and stays sharp while zooming. There are no external fonts or image downloads, transitions are short, and reduced-motion preferences are respected.

## Included snapshot

| Item | Count |
| --- | ---: |
| Areas with roadmaps | 13 |
| Additional subject regions | 4 |
| Unmapped areas needing a roadmap | 16 |
| Roadmaps | 180 |
| Recorded stage entries | 1,604 |
| Mathematical layer stars | 1,538 |
| Source-backed mathematical planets | 3,440 |
| Terminal targets counted for progress | 1,543 |
| Roadmap dependency links | 1,011 |
| Stage dependency links | 3,508 |
| Sanitized source Markdown documents | 214 |

The September 2026 edition combines 152 revised number-theory campaign roadmaps with 28 roadmaps from [TauCetiRoadmap](https://github.com/TauCetiProject/TauCetiRoadmap). The source documents are bundled under [`content/`](content/). The 12 companion guides include the campaign execution protocol, conventions and scope. Reference PDFs and extracted book text are not included. [`data/PUBLICATION.json`](data/PUBLICATION.json) records the publication checks; the atlas and status data retain source hashes, reported commit IDs, and dates.

All 180 overview summaries explain the mathematical objects, results and scope for readers of the atlas. Star names and descriptions present mathematics first; curated entries in `data/stage-presentation.json` replace administrative wording without changing source records. Other descriptions use mathematical passages from the source. The 64 duplicate readiness checkpoints and two library/build administration tasks remain in the full source and progress totals, and are accessible under Project tasks in the Layers tab. They do not appear as mathematical stars. Original roadmap texts remain available in full. Unmapped areas identify missing dedicated plans in this catalogue, not the absence of formal mathematics in Tau Ceti or mathlib.

The source snapshot includes local working-tree material and older maintained progress reports. It is not a fresh verification of the Tau Ceti code or of every mathematical proof. Roadmap-level cycles can reflect dependencies between different early and late stages; the encoded stage dependency graph is acyclic.

## Progress colours and local updates

Stage colours distinguish not-started, in-progress, and complete statuses. Layers without recorded status have no progress label or status colour. The amber midpoint is a status category, not a claim that a theorem is half proved.

Roadmap and subject percentages count **completed terminal targets divided by all tracked terminal targets**. Unknown targets remain in the denominator; no percentage is shown when an entire roadmap or subject has no status data. A parent stage and its children are never counted twice; collection roadmaps aggregate their child roadmaps. Completing every extracted target does not by itself certify all source-proof, acceptance, or formal-verification requirements. A separately displayed roadmap-level report retains its own provenance.

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
- `src/camera.js`: mouse, touch and button navigation between the three spatial levels.
- `vendor/`: bundled D3, KaTeX, and their licences.
- `data/atlas.json`: roadmap text, stage hierarchy, and graph relationships.
- `data/status.json`: explicitly mapped source-status evidence.
- `data/regions.json`: mathematical area descriptions and thematic links.
- `data/opportunities.json`: additional areas with no dedicated roadmap in this atlas.
- `data/landmark-labels.json`: short mathematical names for formula planets, separate from their source excerpts.
- `data/bibliography.json`: supplied bibliographic identities for common source abbreviations; no local reference files.
- `src/references.js`: extracts cited reading with its topic, layer or roadmap scope.
- `src/landmarks.js`: source-faithful extraction of key definitions, results and constructions.
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
