"""Browser check for the catalogue page (scripts/items.py).

Serves the repository as GitHub Pages would and checks what a reader does:
search, filter, and open items. It opens a spread of items across every paper
and fails if any of them does not render — a field written in an unexpected
shape used to throw while drawing, leaving the reader on "Loading…".

  python3 scripts/items.py
  python3 tests/validate_items_browser.py [sample size]

Prints PASS and exits 0, or names the failed check and exits 1.
"""
from __future__ import annotations

import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

SWEEP = """async (sample) => {
  const total = index.rows.length, bad = [];
  for (let n = 0; n < sample; n++) {
    const i = Math.floor(n * total / sample);
    await show(i);
    const panel = document.getElementById('panel');
    const drawn = panel.querySelector('.where') && panel.querySelector('h2')
      && panel.querySelector('h2').textContent === index.names[index.rows[i][0]];
    if (!drawn) bad.push([i, index.papers[index.rows[i][3]].id, index.names[index.rows[i][0]].slice(0, 60)]);
  }
  return bad;
}"""


def main() -> int:
    sample = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/items.html"
    passed, errors = [], []

    def check(name, value):
        if not value:
            raise AssertionError(name)
        passed.append(name)

    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url, wait_until="load")
            page.wait_for_function("window.TauItems && window.TauItems.ready", timeout=120000)
            check("every item is listed", page.evaluate("TauItems.results()") > 1000)
            page.fill("#search", "perfectoid")
            page.wait_for_timeout(400)
            check("a word finds items", 0 < page.evaluate("TauItems.results()") < page.evaluate("index.rows.length"))
            page.fill("#search", "")
            page.select_option("#status-filter", "missing")
            page.wait_for_timeout(300)
            check("the filter narrows to what nothing covers yet", page.evaluate("TauItems.results()") > 1000)
            page.select_option("#status-filter", "all")
            bad = page.evaluate(SWEEP, sample)
            check(f"every one of {sample} items across the papers opens: {bad[:3]}", not bad)
            check("no errors in the page", not errors)
            browser.close()
    except AssertionError as failure:
        print("FAIL:", failure, "| page errors:", errors[:3])
        return 1
    finally:
        server.shutdown()
    print(f"PASS: {len(passed)} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
