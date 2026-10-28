# Refreshing the snapshot

The atlas data (`data/atlas.json`, `data/status.json`, `content/`) is a snapshot of
two sources: the revised number-theory campaign (a local directory, not in this
repository) and a checkout of
[TauCetiProject/TauCetiRoadmap](https://github.com/TauCetiProject/TauCetiRoadmap).
To refresh it against upstream `main` (optionally with an open pull request merged):

1. `git clone https://github.com/TauCetiProject/TauCetiRoadmap <checkout>`; for a pull
   request, `git fetch origin pull/<N>/head:pr-<N>` and merge it on a snapshot branch.
2. Copy this directory to a scratch location `<pipeline>` (it writes `data.json`,
   `REPOSITORY_INVENTORY.json`, `DATA_VALIDATION.json` beside itself) and run
   `python3 build_data.py --source <campaign> --graph <campaign graph> --repository <checkout>`
   once without a `status_overlay.json` to produce the inventory.
3. `python3 make_status_overlay.py --repository <checkout> --inventory <pipeline>/REPOSITORY_INVENTORY.json --previous data/status.json --out <pipeline>/status_overlay.json`
   and run `build_data.py` again. A dependency whose quoted README evidence has
   disappeared upstream is dropped and reported, not asserted.
4. `python3 prepare_repository.py <scratch destination>`; copy `data/atlas.json`,
   `data/status.json`, `data/PUBLICATION.json` and `content/` from there into the
   repository (never its `src/`, which is the old app). Replace any scratch path that
   leaked into the two data files with `[local-source]`.
5. Re-key `data/landmark-labels.json`, `data/landmark-hidden.json` and
   `data/stage-presentation.json` for roadmaps that moved into `Completed/`, drop entries
   whose stage no longer exists, then `python3 scripts/build.py` and the browser suite.

Group assignment for upstream roadmaps lives in `GROUP_FOR` inside `build_data.py`;
a roadmap not listed there lands in the analysis area.
