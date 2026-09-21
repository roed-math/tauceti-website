"""Browser checks for promoted blueprints (scripts/blueprints.py, src/app.js).

Builds the atlas with the small reviewed blueprint in tests/fixtures/blueprints,
serves it the way the published site serves data/blueprints/, and checks what a
reader sees: the planets its workers chose on their layers, every declaration
listed under its layer, a declaration's details read on demand, the roadmap's
blueprint summary and its document in the reader.

  /Users/mcu22seu/miniforge3/bin/python tests/validate_blueprints_browser.py

Prints PASS and exits 0, or names the failed check and exits 1. The repository's
index.html and BUILD.json are left as they were.
"""
from __future__ import annotations

import functools
import http.server
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "blueprints"
ROADMAP = "ColemanIntegration"
sys.path.insert(0, str(REPO / "scripts"))


def build_page(folder: Path) -> None:
    from build import build
    report = REPO / "BUILD.json"
    kept = report.read_bytes()
    try:
        build(folder / "index.html", FIXTURE)
    finally:
        report.write_bytes(kept)
    (folder / "data" / "blueprints").mkdir(parents=True)
    for path in FIXTURE.iterdir():
        shutil.copyfile(path, folder / "data" / "blueprints" / path.name)


def main() -> int:
    folder = Path(tempfile.mkdtemp(prefix="tau-blueprints-"))
    build_page(folder)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    handler = functools.partial(Quiet, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    site = f"http://127.0.0.1:{server.server_address[1]}/index.html"
    passed, errors = [], []

    def check(name, value):
        if not value:
            raise AssertionError(name)
        passed.append(name)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))

            def open_at(fragment):
                page.goto(site + "#" + fragment, wait_until="load")
                page.wait_for_function("!!window.TauExplorer", timeout=20000)
                page.wait_for_timeout(1200)

            layer = f"{ROADMAP}:L0"
            open_at(f"view=roadmap&id={ROADMAP}&layer={layer}&selected={layer}")
            planets = page.evaluate(f"TauExplorer.getUniverse().planets.filter(p => p.starId === '{layer}').map(p => p.label)")
            check("a layer's planets are the ones its blueprint chose", sorted(planets) == ["Overconvergent power series", "Primitives on residue discs"])
            later = page.evaluate(f"TauExplorer.getUniverse().planets.filter(p => p.starId === '{ROADMAP}:L1').map(p => p.label)")
            check("each layer keeps its own planets", later == ["Coleman's principle of analytic continuation"])
            panel = page.locator("#inspector-content")
            check("the layer lists its blueprint", panel.locator("h3.section-label", has_text="Blueprint").count() == 1)
            check("definitions and theorems are listed, planets first", panel.locator(":scope > button.item-link:has(.landmark-kind)").count() == 2)
            check("lemmas wait behind a summary", panel.locator("details.blueprint-steps > summary").inner_text() == "1 lemma and other steps")
            panel.locator("details.blueprint-steps > summary").click()
            panel.locator("details.blueprint-steps button.item-link").first.click()
            page.wait_for_selector("#inspector-content h3.section-label:has-text('Proof outline')", timeout=10000)
            check("a declaration's details are read on demand", page.locator("#selection-kind").inner_text() == "Lemma · blueprint")
            check("its prerequisites lead to other declarations, a planet by its name",
                  page.locator("#inspector-content .blueprint-link", has_text="Overconvergent power series").count() == 1)

            open_at(f"view=roadmap&id={ROADMAP}&layer={layer}&selected={ROADMAP}:L0/overconvergent-series")
            page.wait_for_selector("#inspector-content h3.section-label:has-text('Unit tests')", timeout=10000)
            check("a planet shows its API and unit tests", page.locator("#selection-kind").inner_text() == "Definition · planet"
                  and page.locator("#inspector-content h3.section-label", has_text="API").count() == 1)

            open_at(f"view=roadmap&id={ROADMAP}&selected={ROADMAP}")
            check("the roadmap says what its blueprint holds",
                  "4 declarations planned" in panel.locator("p.detail-note", has_text="declarations planned").inner_text())
            panel.locator("button", has_text="Read the blueprint").click()
            page.wait_for_function("document.querySelector('#reader-body').textContent.includes('A small document for the blueprint browser test')",
                                   timeout=10000)
            check("the reader shows the reviewed document", True)
            check("no application exceptions", not errors)
            browser.close()
    except AssertionError as failure:
        print("FAIL:", failure, "| page errors:", errors)
        return 1
    finally:
        server.shutdown()
        shutil.rmtree(folder, ignore_errors=True)
    print(f"PASS: {len(passed)} blueprint checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
