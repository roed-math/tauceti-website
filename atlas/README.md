# Tau Ceti Explorer

An interactive atlas of mathematical roadmaps: one universe with Mathlib at its centre, in which subjects are galaxies, roadmaps are constellations, layers are stars and the mathematics itself orbits them as planets.

**[Open the interactive atlas](https://cbirkbeck.github.io/tauceti-explorer/)**

The atlas also runs entirely offline. Download `index.html` and open it in a browser; its roadmap text, data, graph library, and interface are embedded in that single file. No installation, account, or local server is required.

## Explore

- Mathlib is the black hole at the centre. The farther out a subject or roadmap lies, the more theory must be built before its targets can be stated and proved.
- Scroll or pinch toward a **subject** to see its **roadmap constellations**, toward a constellation to read its **layer stars**, and toward a star to discover its **orbiting mathematical planets**.
- Tap or click a roadmap, star or planet to make the same journey directly. Zoom out or use the back control to return to the previous level.
- Formula planets have short plain-text names; clicking them opens the typeset definition, theorem target or construction from the source. The details also list citations from the topic or layer and broader roadmap reading, with links back to the embedded source. Progress belongs to its layer star; planets do not carry independent completion claims.
- The details panel explains the mathematics, tracked progress, prerequisites and consumers. The Links tab exposes the actual stage pairs behind dependencies.
- Search for a subject, roadmap, or individual stage. Open the full roadmap to read its outline and source text.
- Drag to pan and use Fit to recover the current scene. Export the current graph as SVG.
- Open **Mission status** for a progress breakdown by subject. Filter the collection by layer activity, and pin roadmaps for your next visit.
- Use **Browse** on a phone, or **⌘/Ctrl K** on a keyboard to search. Mobile details share the screen with the chart; pinch, tap and back controls remain available. View links preserve the current roadmap and planetary system.
- Mathematics is typeset offline with native MathML; hover a formula to see its source.

The atlas is one continuous universe. Subjects are galaxies, roadmaps are the constellations inside them, layers are the stars of a constellation, and a layer's definitions, theorems and constructions are the planets of its star. Everything sits in a single coordinate system, so zooming is a camera movement rather than a change of page: from the whole universe the areas are named and each roadmap is a point; inside a galaxy the constellations resolve into their stars and figures; inside a constellation the stars show their names and planets; inside a star system the planets are named. The address bar and breadcrumbs follow the camera, and only what the camera can see and resolve is drawn, which keeps zooming quick. Names are placed only where they fit: never across another planet, star or control, and a name with no room waits for more zoom rather than shrinking or overlapping. Clicking an object travels to it; the back control steps out one level. A large roadmap is given room in proportion to its number of layers, and each layer's planetary system is kept clear of its neighbours, so dense roadmaps separate as the camera closes in.

Mathlib sits at the centre of the universe as a small black hole. Each roadmap belongs to one of 28 subject galaxies, chosen from the Mathematics Subject Classification of its principal references, which are looked up in zbMATH. There is one galaxy for each subject cluster of that classification. Two clusters are split by primary subject class: elementary number theory, computational number theory and finite fields; and algebraic K-theory and motives. Each roadmap also has a distance from Mathlib on a scale from 0 to 10: 0 means its targets can be stated and proved from Mathlib now, and 10 means several research-level theories must be built first. A galaxy lies at the mean distance of its roadmaps, and the distance on the map grows faster than the score, so the farthest subjects stand clearly apart. Inside a galaxy, the nearer roadmaps sit on the side facing the centre. Number theory and geometry, which hold most of the roadmaps, branch out from Mathlib together as one fan. Geometry lies on one side of it and number theory on the other, with arithmetic geometry and the arithmetic Langlands programme between them and geometric Langlands at the far tip. Algebra flanks the fan, and the other subjects sit on the far side of the centre, where new roadmaps in those areas will fill the space. The fan points right on a wide screen and up on a tall one. A roadmap's overview gives its distance, its primary subject class and the reason for the distance. Distances come from `data/roadmap-classification.json`, which `scripts/classification.py` generates. Roadmaps whose classification has not finished use provisional estimates, and the overview marks them. The older layout, with areas at fixed anchors and no centre, opens by adding `#layout=areas` to the address.

No links are drawn at rest. Selecting a roadmap shows its prerequisite links to other roadmaps; selecting a star shows the prerequisites and consumers of that layer, prerequisite → consumer; hovering a subject heading shows the routes between subjects, drawn from rim to rim. The faint figure joining a constellation's stars prefers real prerequisite pairs and is a shape, not a claim. Planet orbits express membership in a layer, not additional prerequisites. Planets are meant to be key definitions, named theorems and central constructions; extracted paragraphs that are instructions, checks, scope caveats or bookkeeping are hidden from the map through `data/landmark-hidden.json`, each with a recorded reason, and an editorial pass is replacing the remaining sentence-fragment names with short names drawn from the passages themselves. Related-plan links can be switched on and carry no prerequisite claim. Positions, discs and orbits are visual aids, not astronomical coordinates or mathematical measurements.

On subjects, roadmaps and layers, colour means one thing: recorded progress, shown as brightness. A layer, roadmap or area recorded as not started is red; it warms through salmon as work is recorded and turns white when complete, so a subject's galaxy brightens as its roadmaps fill in. An open ring means no progress has been recorded, and nothing is ever coloured as started or as zero percent to fill the gap. Planets carry no progress of their own. Their shape says what they are: a rounded square is a definition or construction, a circle is a result, and a ringed circle is a named theorem. Their muted blue and lavender tints lie outside the progress ramp, and a legend appears inside a star system. All marks are flat: solid fills and thin strokes, with no gradients, glows or shaded spheres. The page uses system type, one dark palette and no decorative elements; headline statistics live in Mission status. Scene artwork is generated locally as SVG. There are no external fonts or image downloads, transitions are short, and reduced-motion preferences are respected.

## Source-decomposed refinements

Roadmap layers can carry reviewed refinements: constructions, lemmas, theorems and comparisons read from the primary references by the source-expansion programme, each with its statement, hypotheses, proof route, acceptance conditions and source locators. Refinements orbit their layer as planets, drawn with a dashed edge, and open to their statement, sources and dependencies. They are planning detail: they never enter the progress denominators, never inherit a status from their layer, and carry an unchecked implementation status. A refinement added during review, rather than verified in it, says so. Reviewed packets live under `data/decompositions/` and are merged into the immutable snapshot at build time; the snapshot itself is never edited.

## Included snapshot

| Item | Count |
| --- | ---: |
| Subject galaxies | 28 |
| Roadmaps | 212 |
| Recorded stage entries | 1,968 |
| Reviewed source refinements | 482 (35 roadmaps, partial coverage) |
| Mathematical layer stars | 1,902 |
| Source-backed mathematical planets | 3,028 of 3,440 extracted targets shown (412 procedural paragraphs hidden) + 482 refinements |
| Terminal targets counted for progress | 1,896 |
| Roadmap dependency links | 1,044 recorded + 7 from reviewed refinements |
| Stage dependency links | 3,508 recorded + 639 from reviewed refinements |
| Sanitized source Markdown documents | 296 |

The September 2026 edition combines 152 revised number-theory campaign roadmaps with 60 roadmaps from [TauCetiRoadmap](https://github.com/TauCetiProject/TauCetiRoadmap): its `main` branch at commit fa4d030 (14 September 2026), including the four roadmaps the maintainers have archived as complete, plus the modular-curves roadmap from open pull request #81. The source documents are bundled under [`content/`](content/). The 12 companion guides include the campaign execution protocol, conventions and scope. Reference PDFs and extracted book text are not included. [`data/PUBLICATION.json`](data/PUBLICATION.json) records the publication checks; the atlas and status data retain source hashes, reported commit IDs, and dates.

All 212 overview summaries explain the mathematical objects, results and scope for readers of the atlas. Star names and descriptions present mathematics first; curated entries in `data/stage-presentation.json` replace administrative wording without changing source records. Other descriptions use mathematical passages from the source. The 64 duplicate readiness checkpoints and two library/build administration tasks remain in the full source and progress totals, and are accessible under Project tasks in the Layers tab. They do not appear as mathematical stars. Original roadmap texts remain available in full.

The source snapshot includes local working-tree material and older maintained progress reports. It is not a fresh verification of the Tau Ceti code or of every mathematical proof. Roadmap-level cycles can reflect dependencies between different early and late stages; the encoded stage dependency graph is acyclic.

## Progress colours and local updates

Stage colours run from red (not started) through salmon (in progress) to white (complete). Layers without recorded status have no progress label or status colour. For upstream roadmaps, a roadmap the maintainers archived under `Completed/` is complete with all its layers; otherwise layer statuses are mapped from the roadmap's maintained STATUS.md report, sentence by sentence, and each mapped status carries the quoted sentence and its line numbers. A report is a machine-written snapshot of what has landed, not a fresh proof audit. The salmon midpoint is a status category, not a claim that a theorem is half proved.

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
- `data/galaxies.json`: the subject galaxies, with descriptions, topics, subject classes, families and directions from the centre.
- `data/roadmap-classification.json`: each roadmap's galaxy, distance from Mathlib and subject classes, generated by `scripts/classification.py` from the classification results and `data/classification-estimates.json`.
- `data/landmark-labels.json`: short mathematical names for formula planets, separate from their source excerpts.
- `data/landmark-hidden.json`: extracted paragraphs that are not planets (instructions, checks, caveats, bookkeeping), each with a recorded reason.
- `data/roadmap-summaries.json`: edited overview summaries applied over the snapshot at build time.
- `data/stage-status-reports.json`: layer statuses mapped from the maintained STATUS.md reports of upstream roadmaps, each with the quoted sentence and its line numbers.
- `scripts/snapshot/`: the pipeline and procedure that rebuild `data/atlas.json`, `data/status.json` and `content/` from an upstream checkout.
- `data/bibliography.json`: supplied bibliographic identities for common source abbreviations; no local reference files.
- `src/references.js`: extracts cited reading with its topic, layer or roadmap scope.
- `src/landmarks.js`: source-faithful extraction of key definitions, results and constructions.
- `content/`: sanitized source Markdown documents.
- `scripts/build.py`: portable offline builder. `scripts/galaxies.py` regroups roadmaps into the subject galaxies at build time.
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
