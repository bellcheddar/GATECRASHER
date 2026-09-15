#!/usr/bin/env python3
"""Drive GATECRASHER in a real browser and check what it actually renders.

A screenshot proves the page lays out. It does not prove that Mol* loaded coordinates, that
clicking a residue filters the SAR table, that a copied URL restores the view, or that both
themes are legible. Those need a browser running the JavaScript, so this speaks the Chrome
DevTools Protocol over a real-time session.

Two deliberate choices, both learned the hard way elsewhere in this portfolio:

  * no --virtual-time-budget, which pauses requestAnimationFrame and makes every animation
    and every Mol* draw measure as frozen. The session is real time.
  * no zero-delay synthetic clicks. A press and release in the same millisecond passes tests
    that a real click fails, so every click holds for 120 ms and the target is resolved at
    press time.

    python3 tools/browser_check.py --base http://127.0.0.1:8099
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class Tab:
    """A minimal CDP client: evaluate, click, hover, screenshot."""

    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=40)
        self.n = 0
        self.console: list[str] = []
        self.send("Runtime.enable")
        self.send("Page.enable")

    def send(self, method: str, **params) -> dict:
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("method") == "Runtime.consoleAPICalled":
                args = " ".join(str(a.get("value", a.get("description", "")))
                                for a in msg["params"].get("args", []))
                self.console.append(f"{msg['params']['type']}: {args}")
                continue
            if msg.get("method") == "Runtime.exceptionThrown":
                d = msg["params"]["exceptionDetails"]
                self.console.append(f"EXCEPTION: {d.get('text')} "
                                    f"{d.get('exception', {}).get('description', '')[:300]}")
                continue
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def goto(self, url: str) -> None:
        """Navigate, then wait for the app's own readiness signal.

        document.readyState reaches 'complete' once the markup and modules have loaded,
        which is well before the first data bundle has been fetched and drawn. Against a
        local server that gap is invisible; against the deployed site it is seconds, and
        asserting inside it reports an empty page as a broken one. The app sets
        data-ready on the root element when a paper has finished loading.
        """
        self.send("Page.navigate", url=url)
        for _ in range(300):
            if self.js("document.readyState") == "complete":
                break
            time.sleep(0.1)
        for _ in range(600):                    # up to 60 s for the first bundle
            if self.js("document.documentElement.dataset.ready") == "true":
                return
            time.sleep(0.1)
        # No signal: carry on and let the assertions report what is actually there.
        time.sleep(0.4)

    def js(self, expr: str):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True,
                      awaitPromise=True)
        if "exceptionDetails" in r:
            return None
        return r.get("result", {}).get("value")

    def wait_for(self, expr: str, seconds: float = 20, want=True):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self.js(expr) == want:
                return True
            time.sleep(0.2)
        return False

    def _box(self, selector: str):
        return self.js(f"""(() => {{
            const el = document.querySelector({selector!r});
            if (!el) return null;
            el.scrollIntoView({{block:'center'}});
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return null;
            return {{x: r.left + r.width/2, y: r.top + r.height/2}};
        }})()""")

    def click(self, selector: str, hold_ms: int = 120) -> bool:
        box = self._box(selector)
        if not box:
            return False
        for kind in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", type=kind, x=box["x"], y=box["y"],
                      button="left", clickCount=1,
                      buttons=1 if kind == "mousePressed" else 0)
            if kind == "mousePressed":
                time.sleep(hold_ms / 1000)
        time.sleep(0.25)
        return True

    def hover(self, selector: str) -> bool:
        box = self._box(selector)
        if not box:
            return False
        self.send("Input.dispatchMouseEvent", type="mouseMoved", x=box["x"], y=box["y"])
        time.sleep(0.3)
        return True

    def key(self, text: str) -> None:
        for kind in ("keyDown", "keyUp"):
            self.send("Input.dispatchKeyEvent", type=kind, text=text if kind == "keyDown" else "",
                      key=text, windowsVirtualKeyCode=ord(text.upper()))
        time.sleep(0.4)

    def press(self, key: str, vk: int) -> None:
        """A named key such as Tab, which has no text to type."""
        for kind in ("rawKeyDown", "keyUp"):
            self.send("Input.dispatchKeyEvent", type=kind, key=key,
                      windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)
        time.sleep(0.3)

    def dom_key(self, key: str) -> None:
        """Dispatch a keydown from the focused element, inside the page.

        Escape sent through Input.dispatchKeyEvent flipped document.visibilityState to
        "hidden" (2026-09-14, on SwiftShader and on Metal alike). A hidden page renders no
        frames, so requestAnimationFrame and IntersectionObserver stop, nothing lazy ever
        loads, and every later check fails for a reason that has nothing to do with the app.
        A DOM event reaches the app's own key handler, which is what is being tested.
        """
        self.js("(document.activeElement || document.body).dispatchEvent("
                f"new KeyboardEvent('keydown', {{key: {key!r}, bubbles: true}}))")
        time.sleep(0.3)

    def shot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        r = self.send("Page.captureScreenshot", format="png")
        path.write_bytes(base64.b64decode(r["data"]))

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def launch(port: int, profile: str):
    return subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         # Chrome rejects a CDP WebSocket whose Origin it does not recognise, and
         # websocket-client always sends one.
         "--remote-allow-origins=*",
         # Mol* needs WebGL, which headless Chrome will not provide without this.
         "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         "--window-size=1440,960", "--no-first-run", "--no-default-browser-check",
         "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ws_url(port: int) -> str:
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as r:
                for t in json.load(r):
                    if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                        return t["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError("Chrome did not expose a debugging target")


PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}"
          + (f"\n          {detail}" if not cond and detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8099")
    ap.add_argument("--out", default="docs/screenshots")
    args = ap.parse_args()

    if not Path(CHROME).exists():
        sys.exit(f"no Chrome at {CHROME}")

    out = Path(args.out)
    profile = tempfile.mkdtemp()
    port = free_port()
    proc = launch(port, profile)
    tab = None
    try:
        tab = Tab(ws_url(port))

        # ------------------------------------------------------------- boot
        print("\nboot")
        tab.goto(args.base + "/")
        check("the app booted without the failure box",
              not tab.js("!!document.querySelector('main > .sheet-empty')"))
        check("the paper switcher is populated",
              (tab.js("document.querySelectorAll('#paper-switcher button').length") or 0) >= 1)
        check("the dark theme is the default",
              tab.js("getComputedStyle(document.body).backgroundColor") == "rgb(11, 37, 66)",
              tab.js("getComputedStyle(document.body).backgroundColor"))
        check("the provenance rail names the paper",
              "Hummel" in (tab.js("document.getElementById('rail-paper').textContent") or ""),
              tab.js("document.getElementById('rail-paper').textContent"))
        check("the title block is live, not a placeholder",
              "CDK2" in (tab.js("document.querySelector('.title-block').textContent") or ""),
              tab.js("document.querySelector('.title-block').textContent"))

        # ------------------------------------------------- landing and drawers
        # The Structure sheet is the landing sheet for every paper. What the Story sheet held
        # lives in pull-out drawers over whichever sheet is open.
        print("\nlanding sheet and story drawers")
        check("the structure sheet is the landing sheet",
              not tab.js("document.getElementById('tab-structure').hidden")
              and (tab.js("location.hash") or "").startswith("#cdk2/structure"),
              tab.js("location.hash"))
        check("there is no story tab any more",
              not tab.js("!!document.querySelector(\"#tab-strip button[data-tab='story']\")"))
        check("every drawer starts closed and out of reach",
              tab.js("[...document.querySelectorAll('.drawer')]"
                     ".every(d => getComputedStyle(d).visibility === 'hidden')"))

        tab.click("#drawer-tabs button[data-drawer='campaign']")
        check("the campaign drawer pulls out",
              tab.wait_for("getComputedStyle(document.getElementById('drawer-campaign')).visibility === 'visible'", 5))
        check("the open drawer is in the URL",
              "drawer=campaign" in (tab.js("location.hash") or ""), tab.js("location.hash"))
        check("the one-line summary rendered",
              len(tab.js("document.getElementById('one-line').textContent") or "") > 40)
        check("the graphical abstract strip drew its own depictions",
              tab.wait_for("document.querySelectorAll('#abstract-strip .abstract-panel svg').length >= 3", 10),
              f"panels with svg: {tab.js('document.querySelectorAll(\"#abstract-strip .abstract-panel svg\").length')}")
        check("the abstract is marked as a quotation with its DOI",
              tab.js("!!document.querySelector('#abstract-quote cite a[href*=\"doi.org\"]')"))

        tab.click("#drawer-tabs button[data-drawer='story']")
        check("switching drawers leaves exactly one out",
              tab.wait_for("document.querySelectorAll('.drawer.is-open').length === 1"
                           " && document.getElementById('drawer-story').classList.contains('is-open')", 5))
        check("five story beats rendered",
              tab.js("document.querySelectorAll('#beats .beat').length") == 5,
              f"{tab.js('document.querySelectorAll(\"#beats .beat\").length')} beats")

        # Checked against the beat's own focus block, so this measures the cross-link rather
        # than a guess about what CDK2's second beat happens to point at.
        expected = tab.js("fetch('data/papers/cdk2/story.json').then(r => r.json())"
                          ".then(s => s.beats[1].focus || {})") or {}
        tab.click("#beats .beat:nth-child(2) .beat-show")
        tab.wait_for("location.hash.includes('beat=')", 5)
        landed = tab.js("decodeURIComponent(location.hash)") or ""
        want_res = ",".join(expected.get("residues") or [])
        check("a beat's focus reaches the structure sheet in one step",
              "beat=" in landed
              and (not want_res or f"res={want_res}" in landed)
              and (not expected.get("compound") or f"cmpd={expected['compound']}" in landed),
              f"hash {landed!r}, beat focus {expected}")
        tab.dom_key("Escape")
        check("Escape closes the drawer",
              tab.wait_for("document.querySelectorAll('.drawer.is-open').length === 0", 5))

        # Closing a drawer slides the tabs back from right: 540px. Click one mid-slide and
        # the click lands where the button was a frame ago. That happens while Mol* is still
        # evaluating, when a 0.24 s transition runs at 6 frames a second, so wait for rest.
        tab.wait_for("getComputedStyle(document.getElementById('drawer-tabs')).right === '0px'", 5)
        tab.click("#drawer-tabs button[data-drawer='plot']")
        check("the selectivity drawer draws its plot when it is opened",
              tab.wait_for("!!document.querySelector('#story-plot .main-svg')", 25),
              "no plot in the selectivity drawer")
        tab.dom_key("Escape")
        tab.wait_for("document.querySelectorAll('.drawer.is-open').length === 0", 5)

        # --------------------------------------------------------- register
        print("\nregister toggle")
        # The prose nodes are REPLACED on every register change, so polling their textContent
        # races the re-render: a poll landing mid-render throws, reads as None, and reports a
        # working toggle as broken. The button label is a single node that is only ever
        # rewritten in place, so the wait keys on that and the prose is read afterwards.
        prose = "(document.querySelector('#beats .beat .prose')||{}).textContent||''"
        label = "document.getElementById('register-button').textContent.trim()"
        before = tab.js(prose)
        tab.click("#register-button")
        flipped = tab.wait_for(f"{label} === 'Plain'", 6)
        # If the synthetic pointer click did not land, say so and then drive the control
        # directly, so the rest of the register assertions still mean something and the
        # output distinguishes "the control is unreachable" from "the logic is broken".
        by_pointer = flipped
        if not flipped:
            tab.js("document.getElementById('register-button').click()")
            flipped = tab.wait_for(f"{label} === 'Plain'", 6)
        after = tab.js(prose)
        check("the register control responds to a real pointer click", by_pointer,
              "a direct .click() " + ("did work, so the handler is fine and the synthetic "
                                      "press missed the element" if flipped else "did not work either"))
        check("switching register flips the control", flipped,
              f"button reads {tab.js(label)!r}, hash {tab.js('location.hash')!r}")
        check("switching register rewrites the beat prose",
              bool(after) and before != after,
              f"before={(before or '')[:50]!r} after={(after or '')[:50]!r}")
        check("the plain register really is plainer",
              len(after or "") > 0 and "sp3" not in (after or ""),
              (after or "")[:80])
        tab.click("#register-button")
        tab.wait_for(f"{label} === 'Specialist'", 10)

        # -------------------------------------------------------- structure
        print("\nstructure sheet")
        tab.click("#tab-strip button[data-tab='structure']")
        check("the structure tab is visible",
              not tab.js("document.getElementById('tab-structure').hidden"))
        check("Mol* loaded coordinates into a canvas",
              tab.wait_for("!!document.querySelector('#viewer-target canvas')", 40),
              "no canvas in the viewer host")
        # A deposited entry holds whatever the crystal packed into its asymmetric unit, which
        # for 10PI is two copies of the same kinase. The viewers show the copy the bundle
        # describes. Tested on the real entry, through the module's own exported filter.
        copies = tab.js("""(async () => {
            const module = await import('./js/viewers/molstar.js');
            const text = await (await fetch('https://files.rcsb.org/download/10PI.cif')).text();
            const before = new Set(), after = new Set();
            const chains = (body, into) => {
              const lines = body.split('\\n');
              const start = lines.findIndex((l) => l.startsWith('_atom_site.'));
              const columns = [];
              let i = start;
              // '_atom_site.' is ELEVEN characters. Slicing 12 loses the first letter of
              // every column name, indexOf('auth_asym_id') returns -1, and every row reads
              // as undefined: the check then compares [null] with [null] and calls it a pass.
              while (lines[i].startsWith('_atom_site.')) { columns.push(lines[i].trim().slice(11)); i += 1; }
              const auth = columns.indexOf('auth_asym_id');
              for (; i < lines.length; i += 1) {
                if (!lines[i].trim() || lines[i].startsWith('#')) break;
                into.add((lines[i].match(/'[^']*'|"[^"]*"|\\S+/g) || [])[auth]);
              }
            };
            chains(text, before);
            const filtered = module.oneCopy(text, 'A');
            chains(filtered, after);
            return {before: [...before].sort(), after: [...after].sort(),
                    keptHeader: filtered.includes('_entry.id'), shorter: filtered.length < text.length};
        })()""")
        check("the viewer shows one copy of the protein, not the crystal dimer",
              isinstance(copies, dict) and copies.get("after") == ["A"]
              and len(copies.get("before") or []) > 1 and copies.get("keptHeader"),
              str(copies)[:160])

        # The short-MD row, where a run exists. Written to assert the SUBSTANCE when there is
        # one and to say so when there is not, rather than passing vacuously either way: a
        # check that cannot fail is how the blank twin viewer survived a day.
        md = tab.js("""(async () => {
            const index = await (await fetch('data/papers/cdk2/dynamics.json')).json().catch(() => null);
            if (!index) return {ran: false};
            const run = index['8UV0'];
            if (!run) return {ran: false};
            const host = document.getElementById('structure-dynamics');
            return {
              ran: true,
              verdict: run.verdict,
              chips: host ? host.querySelectorAll('.chip').length : 0,
              claimChips: host ? host.querySelectorAll('.claim-held, .claim-broke').length : 0,
              rmsfCells: document.querySelectorAll('#klifs-ruler .rmsf-cell').length,
              hasPlay: host ? !!host.querySelector('button') : false,
              withheld: host ? host.textContent.includes('withheld') : false,
            };
        })()""") or {}
        if md.get("ran"):
            check("the short MD row says what was run and what it showed",
                  md.get("chips", 0) >= 2 and md.get("claimChips", 0) >= 1,
                  f"{md.get('chips')} chips, {md.get('claimChips')} of them claims")
            check("the ruler carries an RMSF band from that run",
                  md.get("rmsfCells", 0) > 50, f"{md.get('rmsfCells')} RMSF cells")
            # A trajectory ships only where the verdict supports the paper's claim, so the
            # control and the verdict must agree: BUILD_SPEC Stage 4.
            expected_play = md.get("verdict") == "supports"
            check("the trajectory control matches the verdict",
                  md.get("hasPlay") == expected_play and md.get("withheld") != expected_play,
                  f"verdict {md.get('verdict')}, play control {md.get('hasPlay')}, "
                  f"withheld notice {md.get('withheld')}")
        else:
            print("  skip  no MD run bundled for CDK2 yet, so the dynamics row is not asserted")

        check("the pocket ruler drew its cells",
              (tab.js("document.querySelectorAll('#klifs-ruler .ruler-cell').length") or 0) >= 80,
              f"{tab.js('document.querySelectorAll(\"#klifs-ruler .ruler-cell\").length')} cells")
        check("motif chips rendered",
              (tab.js("document.querySelectorAll('#motif-chips .chip').length") or 0) >= 5)
        check("the contact list came from PLIP",
              (tab.js("document.querySelectorAll('#contact-list .contact-row').length") or 0) == 13,
              f"{tab.js('document.querySelectorAll(\"#contact-list .contact-row\").length')} rows")
        check("a water bridge is shown with both legs",
              "/" in (tab.js("""(() => {const rows=[...document.querySelectorAll('#contact-list .contact-row')];
                  const r = rows.find(x => x.textContent.includes('via water'));
                  return r ? r.querySelector('.contact-distance').textContent : '';})()""") or ""),
              tab.js("""(() => {const rows=[...document.querySelectorAll('#contact-list .contact-row')];
                  const r = rows.find(x => x.textContent.includes('via water'));
                  return r ? r.textContent : 'no water bridge row';})()"""))

        check("the PyMOL downloads are offered",
              (tab.js("document.querySelectorAll('#structure-downloads a').length") or 0) >= 2,
              f"{tab.js('document.querySelectorAll(\"#structure-downloads a\").length')} links")
        check("each download points at a real file in this bundle",
              tab.js("[...document.querySelectorAll('#structure-downloads a')]"
                     ".every(a => a.getAttribute('href').includes('figures/'))"))
        check("the download sizes are stated, so nothing large is a surprise",
              tab.js("[...document.querySelectorAll('#structure-downloads a')]"
                     ".some(a => /\\d+\\s*(kB|MB)/.test(a.textContent))"),
              tab.js("[...document.querySelectorAll('#structure-downloads a')].map(a => a.textContent).join(' | ')"))

        # ----------------------------------------------------- cross-links
        print("\ncross-links (BUILD_SPEC section 8)")
        tab.click("#motif-chips .chip.motif-gatekeeper")
        # A colon is percent-encoded in a URL, so the hash is decoded before asserting:
        # the app writes res=A%3A80, which is correct and is not the string "A:80".
        check("a motif chip selects its residues",
              "A:80" in (tab.js("decodeURIComponent(window.location.hash)") or ""),
              tab.js("window.location.hash"))

        tab.click("#klifs-ruler .ruler-cell:nth-of-type(45)")
        check("a ruler cell selects a residue into the URL",
              "res=" in (tab.js("window.location.hash") or ""),
              tab.js("window.location.hash"))

        tab.click("#contact-list .contact-row")
        check("a contact row selects its residue",
              "res=" in (tab.js("window.location.hash") or ""))

        tab.click("#tab-strip button[data-tab='sar']")
        rows = tab.js("document.querySelectorAll('#compound-table tbody tr').length")
        check("the SAR table rendered", (rows or 0) >= 1, f"{rows} rows")
        check("the R-group grid marks combinations that were never made",
              (tab.js("document.querySelectorAll('#rgroup-grid .rgroup-cell.is-empty').length") or 0) >= 1)

        # BUILD_SPEC section 8 says implement every row of the cross-link matrix, and section
        # 11 says walk every row in a test. These five were asserted only for rendering, which
        # proves a thing is drawn and nothing about whether clicking it does anything.
        tab.click("#rgroup-grid .rgroup-cell:not(.is-empty)")
        check("an R-group cell selects its compound",
              "cmpd=" in (tab.js("window.location.hash") or ""),
              tab.js("window.location.hash"))

        # The substituent row header is a lens on the table rather than shared state, so it
        # is asserted on the rows it hides, not on the hash.
        before = tab.js("document.querySelectorAll('#compound-table tbody tr').length")
        tab.click("#rgroup-grid th.is-substituent")
        after = tab.js("document.querySelectorAll('#compound-table tbody tr').length")
        check("a substituent filters the table to the compounds carrying it",
              isinstance(before, int) and isinstance(after, int) and 0 < after < before,
              f"{before} rows before, {after} after")
        check("the filtering substituent says it is pressed",
              tab.js("""document.querySelector('#rgroup-grid th.is-substituent[aria-pressed="true"]') !== null"""))
        # Clicking the same one again is the way back: a filter with no visible off switch
        # strands the reader on a partial table.
        tab.click("#rgroup-grid th.is-substituent[aria-pressed='true']")
        restored = tab.js("document.querySelectorAll('#compound-table tbody tr').length")
        check("clicking the same substituent again clears the filter",
              restored == before, f"{restored} rows, expected {before}")

        # Only 4 of cdk2's 40 cliffs have an edit linking the pair, and none of them is the
        # first row: a cliff is a potency jump, and the paper does not always document the
        # change that made it. Asserting edit= on whatever row came first tested the data's
        # luck rather than the wiring, so the row is chosen by the pair it names.
        cliffs = tab.js("document.querySelectorAll('#cliffs-table tbody tr').length")
        clicked = tab.js("""(() => {
            const want = ['6 \\u2192 7', '2 \\u2192 3', '8 \\u2192 9', '8 \\u2192 13'];
            for (const tr of document.querySelectorAll('#cliffs-table tbody tr')) {
                const text = (tr.textContent || '').replace(/\\s+/g, ' ');
                if (want.some((w) => text.includes(w))) { tr.click(); return text.slice(0, 40); }
            }
            return null;
        })()""")
        if cliffs and clicked:
            cliff_hash = tab.js("window.location.hash") or ""
            check("a cliff pair selects its compound and the edit between them",
                  "cmpd=" in cliff_hash and "edit=" in cliff_hash,
                  f"clicked {clicked!r}, hash {cliff_hash}")
        else:
            check("a cliff pair selects its compound and the edit between them", False,
                  f"{cliffs} cliff rows, none matching a documented pair")
        check("the selectivity matrix rendered folds",
              (tab.js("document.querySelectorAll('#selectivity-matrix .fold').length") or 0) >= 5)
        check("a bound value is marked as a bound, not a number",
              (tab.js("document.querySelectorAll('#compound-table .value-bounded').length") or 0) >= 1)

        tab.click("#compound-table tbody tr")
        check("clicking a compound row selects it everywhere",
              "cmpd=" in (tab.js("window.location.hash") or ""),
              tab.js("window.location.hash"))

        # -------------------------------------------------------- edit log
        print("\nedit log")
        tab.click("#tab-strip button[data-tab='structure']")
        cards = tab.js("document.querySelectorAll('#edit-cards-inline .edit-card').length")
        check("edit cards rendered", (cards or 0) >= 1, f"{cards} cards")
        check("the default filter is isostere",
              tab.js("""(() => {const c=[...document.querySelectorAll('#change-type-filter .chip')]
                  .find(x => x.getAttribute('aria-pressed')==='true');
                  return c ? c.textContent : '';})()""").startswith("isostere"),
              tab.js("""(() => {const c=[...document.querySelectorAll('#change-type-filter .chip')]
                  .find(x => x.getAttribute('aria-pressed')==='true'); return c?c.textContent:'none';})()"""))
        check("each card shows a before and an after depiction",
              (tab.js("document.querySelectorAll('#edit-cards-inline .edit-card .edit-swap svg').length") or 0) >= 2)
        check("property deltas are coloured by gain or loss",
              (tab.js("document.querySelectorAll('#edit-cards-inline .edit-delta.gain, #edit-cards-inline .edit-delta.loss').length") or 0) >= 1)

        # Matrix row: an edit card puts both compounds into a comparison state, highlights the
        # cited residues, and makes the consequence assays the plot axes.
        tab.click("#edit-cards-inline .edit-card")
        card_hash = tab.js("window.location.hash") or ""
        check("an edit card selects the edit and its compound",
              "edit=" in card_hash and "cmpd=" in card_hash, card_hash)

        # Only 5 of cdk2's 17 edits cite a structural basis, and both of the clearest ones are
        # filtered out of the default isostere view, so the first visible card has no residues
        # to highlight and correctly produces no res=. Show every change type, then pick a card
        # that actually carries residue chips.
        tab.js("""(() => {
            const chip = [...document.querySelectorAll('#change-type-filter .chip')]
                .find((c) => (c.textContent || '').startsWith('all'));
            if (chip) chip.click();
        })()""")
        time.sleep(0.4)
        cited = tab.js("""(() => {
            for (const card of document.querySelectorAll('#edit-cards-inline .edit-card')) {
                if (card.querySelector('.sheet-tools .chip')) { card.click(); return true; }
            }
            return false;
        })()""")
        basis_hash = tab.js("window.location.hash") or ""
        check("an edit card highlights the residues it cites",
              bool(cited) and "res=" in basis_hash,
              f"card citing residues found: {bool(cited)}, hash {basis_hash}")

        # ------------------------------------------------------ properties
        print("\nproperties sheet")
        tab.click("#tab-strip button[data-tab='properties']")
        check("the property plot drew an SVG",
              tab.wait_for("!!document.querySelector('#plot-property .main-svg')", 20))
        check("the ligand efficiency plot drew",
              tab.js("!!document.querySelector('#plot-efficiency .main-svg')"))
        check("the PK ladder drew",
              tab.js("!!document.querySelector('#plot-pk .main-svg')"))
        check("the PK sheet states that doses differ per row",
              "dose" in (tab.js("document.getElementById('pk-note').textContent") or "").lower(),
              tab.js("document.getElementById('pk-note').textContent"))

        # Matrix row: a point on any plot selects its compound. Clicked as a real element
        # rather than by calling the handler, because what is being tested is the wiring
        # between Plotly's event and AppState, and calling onPointClick directly would pass
        # even if plotly_click were never bound.
        # The assertion is that the selection CHANGES, not that a cmpd= appears. Clearing the
        # hash first with replaceState looked tidier and was wrong twice over: it does not
        # clear AppState, so the app still held a compound, and clicking the point that was
        # already selected is a no-op that writes no hash at all. Which point that is had come
        # to depend on the edit-card test above, so the result turned on test order.
        # Reached by an explicit URL rather than by whatever the tests above left behind. The
        # edit-card test sets assayX and assayY from that edit's consequences, which re-points
        # this plot at assays most compounds do not carry (compound 2 has 3 measurements,
        # compound 17 has 30), so it can legitimately draw no points at all. Five clicks then
        # land on nothing and the failure reads exactly like broken wiring.
        tab.goto(args.base + "/#cdk2/properties?cmpd=2")
        tab.wait_for("!!document.querySelector('#plot-property .main-svg')", 20)
        time.sleep(1.0)
        points = tab.js("document.querySelectorAll('#plot-property .points path').length")
        selected = "(new URLSearchParams((location.hash.split('?')[1] || ''))).get('cmpd')"
        before = tab.js(selected)
        after, changed = before, False
        for index in range(5):
            box = tab.js(f"""(() => {{
                const p = document.querySelectorAll('#plot-property .points path')[{index}];
                if (!p) return null;
                const r = p.getBoundingClientRect();
                return {{x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2)}};
            }})()""")
            if not box:
                continue
            for kind in ("mousePressed", "mouseReleased"):
                tab.send("Input.dispatchMouseEvent", type=kind, x=box["x"], y=box["y"],
                         button="left", clickCount=1)
            time.sleep(0.5)
            after = tab.js(selected)
            if after and after != before:
                changed = True
                break
        # The point count is in the message on purpose: "no points to click" and "clicked and
        # nothing happened" are different faults and looked identical in the first version.
        check("a point on a plot selects its compound",
              changed, f"{points} points drawn, compound {before} -> {after}")

        # ---------------------------------------------------- linkability
        print("\na copied URL restores the view")
        deep = args.base + "/#cdk2/structure?cmpd=17&res=A:80,A:83"
        tab.goto(deep)
        check("the deep link selected the compound",
              tab.js("document.getElementById('rail-compound').textContent") == "cmpd 17",
              tab.js("document.getElementById('rail-compound').textContent"))
        check("the deep link opened the structure tab",
              not tab.js("document.getElementById('tab-structure').hidden"))
        check("the deep link selected both residues",
              (tab.js("document.querySelectorAll('#klifs-ruler .ruler-cell[aria-selected=\"true\"]').length") or 0) == 2,
              f"{tab.js('document.querySelectorAll(\"#klifs-ruler .ruler-cell[aria-selected=true]\").length')} selected")
        tab.shot(out / "structure-dark.png")

        tab.goto(args.base + "/#cdk2/story")
        check("an old link to the story tab lands on the structure with the story drawer out",
              tab.wait_for("document.getElementById('drawer-story').classList.contains('is-open')", 10)
              and not tab.js("document.getElementById('tab-structure').hidden"),
              tab.js("location.hash"))
        tab.dom_key("Escape")
        tab.wait_for("document.querySelectorAll('.drawer.is-open').length === 0", 5)

        # --------------------------------------------------------- search
        print("\nsearch")
        tab.js("document.getElementById('search-input').focus()")
        tab.js("""(() => {
            const i = document.getElementById('search-input');
            i.value = 'gatekeeper';
            i.dispatchEvent(new Event('input', {bubbles: true}));
        })()""")
        check("searching finds our own writing",
              tab.wait_for("document.querySelectorAll('#search-results .search-hit').length > 0", 15),
              f"{tab.js('document.querySelectorAll(\"#search-results .search-hit\").length')} hits")
        check("each hit says where it came from",
              (tab.js("document.querySelectorAll('#search-results .search-hit .chip').length") or 0) > 0)
        # The honest answer has to look like an answer, not like a failure.
        tab.js("""(() => {
            const i = document.getElementById('search-input');
            i.value = 'zzzqqq nonsense term';
            i.dispatchEvent(new Event('input', {bubbles: true}));
        })()""")
        check("an unanswerable question says so plainly",
              tab.wait_for("!!document.querySelector('#search-results .search-empty')", 10),
              tab.js("(document.getElementById('search-results')||{}).textContent"))
        check("the not-stated answer explains that only our own text is searched",
              "not reproduced here" in (tab.js(
                  "(document.querySelector('#search-results .search-empty p')||{}).textContent") or ""))
        tab.js("""(() => {
            const i = document.getElementById('search-input');
            i.value = ''; i.dispatchEvent(new Event('input', {bubbles: true}));
        })()""")

        # ---------------------------------------------------------- about
        print("\nabout sheet")
        tab.click("#tab-strip button[data-tab='about']")
        # Counted against software.json rather than a literal, which is the whole point of the
        # About sheet being generated from it: adding the dynamics stage broke this assertion
        # while the page was perfectly correct. A test that hard-codes what the data decides
        # fails every time the data is right.
        stages = len(json.loads((Path("web/data/software.json")).read_text())["pipeline"])
        check("the about sheet renders every pipeline stage in software.json",
              tab.wait_for(f"document.querySelectorAll('#about-flow .about-stage').length === {stages}", 15),
              f"{tab.js('document.querySelectorAll(\"#about-flow .about-stage\").length')} drawn, "
              f"{stages} in software.json")
        check("the software table lists what this stands on",
              (tab.js("document.querySelectorAll('#about-software tbody tr').length") or 0) >= 10,
              f"{tab.js('document.querySelectorAll(\"#about-software tbody tr\").length')} rows")
        check("software rows carry a DOI where one exists",
              (tab.js("document.querySelectorAll('#about-software a[href*=\"doi.org\"]').length") or 0) >= 5)
        check("the data sources are named with their DOIs",
              (tab.js("document.querySelectorAll('#about-sources .about-source').length") or 0) >= 3)
        check("the page states what is rendered rather than reproduced",
              "drawn from its SMILES" in (tab.js("document.getElementById('about-statement').textContent") or ""),
              (tab.js("document.getElementById('about-statement').textContent") or "")[:90])
        check("every outgoing link opens safely",
              tab.js("[...document.querySelectorAll('#tab-about a[target]')]"
                     ".every(a => a.rel.includes('noopener'))"))

        # ------------------------------------------------------- keyboard
        print("\nkeyboard")
        # Focus must be visible to a KEYBOARD user, and :focus-visible only matches after a
        # real keyboard interaction: a programmatic .focus() does not match it in Chrome, so
        # testing that way measures nothing and fails on working code.
        tab.js("document.body.focus()")
        for _ in range(6):
            tab.press("Tab", 9)
            if tab.js("document.activeElement && document.activeElement.tagName") == "BUTTON":
                break
        focus_ring = tab.js("""(() => {
            const el = document.activeElement;
            if (!el || el === document.body) return 'nothing focused';
            const s = getComputedStyle(el);
            const visible = (s.outlineStyle !== 'none' && s.outlineWidth !== '0px')
              || s.boxShadow !== 'none';
            return visible ? 'visible' : `${el.tagName}.${el.className}: no ring`;
        })()""")
        check("tabbing to a control shows a focus ring", focus_ring == "visible", str(focus_ring))
        tab.key("r")
        tab.wait_for("document.getElementById('register-button').textContent.trim() === 'Plain'", 5)
        check("'r' switches register",
              (tab.js("document.getElementById('register-button').textContent") or "").strip() == "Plain",
              f"label reads {tab.js('document.getElementById(\"register-button\").textContent')!r}")
        tab.key("r")

        # ------------------------------------------------- all four papers
        # Everything above runs on CDK2. These are the rows of the section 8 matrix that
        # only exist once there is more than one bundle, plus the twin-structure path that
        # only JAK1 has.
        print("\nfour papers")
        tab.goto(args.base + "/")
        # Wait for the first bundle to finish loading before touching the keyboard: the app
        # serialises paper switches, but a key pressed mid-boot still has to queue behind it,
        # and the check should measure the switch rather than the boot.
        tab.wait_for("document.querySelectorAll('#beats .beat').length === 5", 30)
        papers = tab.js("[...document.querySelectorAll('#paper-switcher button')]"
                        ".map(b => b.textContent.replace(/\\d+$/, '').trim())")
        check("all four campaigns are in the switcher",
              isinstance(papers, list) and len(papers) == 4, str(papers))

        for index, slug in ((2, "fgfr"), (3, "kras"), (4, "jak1")):
            tab.key(str(index))
            loaded = tab.wait_for(f"location.hash.startsWith('#{slug}')", 25)
            check(f"keyboard {index} switches to {slug}", loaded, tab.js("location.hash"))
            check(f"{slug}: the provenance rail followed the paper",
                  bool(tab.js("document.getElementById('rail-paper').textContent")),
                  tab.js("document.getElementById('rail-paper').textContent"))
            check(f"{slug}: story beats rendered",
                  (tab.js("document.querySelectorAll('#beats .beat').length") or 0) == 5,
                  f"{tab.js('document.querySelectorAll(\"#beats .beat\").length')} beats")

        # KRAS is not a kinase: the ruler must degrade with no empty pocket affordances.
        tab.key("3")
        tab.wait_for("location.hash.startsWith('#kras')", 25)
        tab.click("#tab-strip button[data-tab='structure']")
        time.sleep(1.0)
        check("kras: the ruler still draws, from the sequence",
              (tab.js("document.querySelectorAll('#klifs-ruler .ruler-cell').length") or 0) > 100,
              f"{tab.js('document.querySelectorAll(\"#klifs-ruler .ruler-cell\").length')} cells")
        check("kras: no KLIFS numbering is claimed anywhere",
              "KLIFS" not in (tab.js("document.getElementById('klifs-ruler')"
                                     ".getAttribute('aria-label')") or ""),
              tab.js("document.getElementById('klifs-ruler').getAttribute('aria-label')"))

        # JAK1 is the only paper with the same ligand in the target and the anti-target.
        tab.key("4")
        tab.wait_for("location.hash.startsWith('#jak1')", 25)
        tab.click("#tab-strip button[data-tab='structure']")
        check("jak1: the target viewer loaded",
              tab.wait_for("!!document.querySelector('#viewer-target canvas')", 40))
        tab.click("#anti-toggle")
        check("jak1: the anti-target viewer opens on demand",
              tab.wait_for("!document.getElementById('viewer-anti').hidden", 15))
        check("jak1: the second structure loaded its own coordinates",
              tab.wait_for("!!document.querySelector('#viewer-anti canvas')", 40),
              "no canvas in the anti-target host")
        # A canvas can exist and be blank. It was: the twin's camera is locked to the
        # target's, and with each entry in its own crystal frame the second viewer pointed 89
        # angstroms away from its own structure and drew nothing, with no error anywhere.
        # Reading the pixels is the only check that would have caught it.
        drawn = """(id) => { const c = document.querySelector('#' + id + ' canvas');
            if (!c) return 0;
            const gl = c.getContext('webgl2') || c.getContext('webgl');
            const px = new Uint8Array(4 * 64 * 64);
            gl.readPixels(Math.floor(c.width / 2) - 32, Math.floor(c.height / 2) - 32, 64, 64,
                          gl.RGBA, gl.UNSIGNED_BYTE, px);
            const seen = new Set();
            for (let i = 0; i < px.length; i += 4) seen.add(px[i] + ',' + px[i + 1] + ',' + px[i + 2]);
            return seen.size; }"""
        for host, label in (("viewer-target", "target"), ("viewer-anti", "anti-target")):
            # Polled, not sampled once: a canvas exists long before it has drawn, and the
            # twin has 766 kB of coordinates to fetch, parse, superpose and render first.
            # Reading immediately measured the loading gap and reported a working viewer as
            # blank.
            colours = 0
            for _ in range(60):
                colours = tab.js(f"({drawn})({host!r})")
                if isinstance(colours, int) and colours > 1:
                    break
                time.sleep(0.5)
            check(f"jak1: the {label} viewer has actually drawn something",
                  isinstance(colours, int) and colours > 1,
                  f"{colours} distinct colours in the centre of the canvas")
        check("jak1: the twin says it was superposed, and by how much",
              "superposed" in (tab.js("document.getElementById('viewer-anti-label').textContent") or ""),
              tab.js("document.getElementById('viewer-anti-label').textContent"))
        check("jak1: the twin is labelled as the anti-target",
              "JAK2" in (tab.js("document.getElementById('viewer-anti-label').textContent") or ""),
              tab.js("document.getElementById('viewer-anti-label').textContent"))
        tab.shot(out / "jak1-twin.png")
        tab.key("1")
        tab.wait_for("location.hash.startsWith('#cdk2')", 25)

        # --------------------------------------------------------- themes
        print("\nthemes")
        tab.click("#theme-button")
        check("the toggle switches to light",
              tab.js("document.documentElement.dataset.theme") == "light",
              tab.js("document.documentElement.dataset.theme"))
        check("the light theme repaints the page ground",
              tab.js("getComputedStyle(document.body).backgroundColor") == "rgb(244, 247, 252)",
              tab.js("getComputedStyle(document.body).backgroundColor"))
        check("the choice persists in localStorage",
              tab.js("localStorage.getItem('gatecrasher.theme')") == "light")
        tab.shot(out / "structure-light.png")
        tab.goto(args.base + "/")
        check("the stored theme survives a reload",
              tab.js("document.documentElement.dataset.theme") == "light")
        tab.js("localStorage.removeItem('gatecrasher.theme')")

        # ------------------------------------------------------- contrast
        # Measured, not assumed, and measured on the grid ground as well as on a sheet,
        # because the grid lines sit behind everything.
        print("\ncontrast")
        contrast = tab.js("""(() => {
          const lum = (c) => {
            const [r,g,b] = c.match(/\\d+/g).slice(0,3).map(Number).map(v => {
              v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4);
            });
            return 0.2126*r + 0.7152*g + 0.0722*b;
          };
          const ratio = (a,b) => {
            const [x,y] = [lum(a), lum(b)].sort((m,n) => n-m);
            return (x + 0.05) / (y + 0.05);
          };
          const body = getComputedStyle(document.body);
          const beat = document.querySelector('#beats .beat .prose');
          const sheet = beat ? getComputedStyle(beat.closest('.sheet')) : body;
          const rail = document.getElementById('rail-paper');
          return {
            prose: ratio(getComputedStyle(beat).color, sheet.backgroundColor),
            onGrid: ratio(body.color, body.backgroundColor),
            rail: ratio(getComputedStyle(rail).color, getComputedStyle(rail.parentElement.parentElement).backgroundColor),
          };
        })()""") or {}
        for name, minimum in (("prose", 4.5), ("onGrid", 4.5), ("rail", 4.5)):
            value = contrast.get(name)
            check(f"{name} contrast at least {minimum}:1 in the light theme",
                  isinstance(value, (int, float)) and value >= minimum,
                  f"{name} = {value}")

        # --------------------------------------------------------- a phone
        print("\nphone (390 x 844)")
        tab.send("Emulation.setDeviceMetricsOverride", width=390, height=844,
                 deviceScaleFactor=3, mobile=True)
        # A phone is a coarse pointer as well as a narrow screen, and setDeviceMetricsOverride
        # supplies only the screen. Measured on this harness: with mobile=True alone,
        # (pointer: coarse) is false and navigator.maxTouchPoints is 0, so anything gated on
        # touch never fires and the test reports the feature broken when it is working. With
        # touch emulation, (pointer: coarse) is true and maxTouchPoints is 5.
        tab.send("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
        tab.goto(args.base + "/")
        time.sleep(1.5)
        # Against clientWidth, not innerWidth. Under mobile emulation an overflowing page
        # widens the layout viewport, and innerWidth grows WITH the overflow: a 413 px page on
        # a 390 px phone reported innerWidth 413 and passed, while the real phone zoomed the
        # whole app out and pushed the drawer tab bar off the bottom of the screen.
        check("nothing overflows the page sideways",
              tab.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"),
              f"scrollWidth {tab.js('document.documentElement.scrollWidth')} "
              f"vs clientWidth {tab.js('document.documentElement.clientWidth')}")
        check("the edit log becomes its own tab below 900px",
              tab.js("""getComputedStyle(document.querySelector("#tab-strip button[data-tab='editlog']")).display""")
              != "none")
        # Measured on the SHEET, not on the padded container: .tab-body's own left edge is 0
        # by definition, because its gutter is padding on the inside.
        gutter = tab.js("""(() => {
            const s = document.querySelector('.tab-body:not([hidden]) .sheet');
            return s ? s.getBoundingClientRect().left : -1;
        })()""")
        check("a side gutter survives at phone width",
              isinstance(gutter, (int, float)) and gutter >= 10,
              f"sheet left edge at {gutter}px")
        check("the drawer tabs become a bar along the bottom",
              tab.js("(() => { const r = document.getElementById('drawer-tabs').getBoundingClientRect();"
                     " return r.bottom >= window.innerHeight - 1 && r.width >= window.innerWidth - 1; })()"),
              str(tab.js("JSON.stringify(document.getElementById('drawer-tabs').getBoundingClientRect())")))

        # Tap to load 3D. Both halves matter and the first is the one worth guarding: a phone
        # test that only checked the viewer works after a tap would pass just as happily if
        # the gate did nothing and 5 MB of Mol* had already been fetched on arrival.
        check("on a phone the viewer waits for a tap instead of loading",
              tab.js("!!document.getElementById('viewer-tap')")
              and not tab.js("!!document.querySelector('#viewer-target canvas')"),
              f"tap target {tab.js('!!document.getElementById(\"viewer-tap\")')}, "
              f"canvas {tab.js('!!document.querySelector(\"#viewer-target canvas\")')}")
        check("Mol* is not fetched before the tap",
              not tab.js("typeof window.molstar !== 'undefined'"))
        tab.shot(out / "phone-tap.png")
        tab.click("#viewer-tap")
        check("tapping loads the viewer",
              tab.wait_for("!!document.querySelector('#viewer-target canvas')", 60),
              "no canvas after the tap")
        # Same polled readPixels probe as the desktop twin check: a canvas exists long before
        # it has drawn anything, and on an emulated phone it has a library and a coordinate
        # file to fetch first.
        colours = 0
        for _ in range(60):
            colours = tab.js(f"({drawn})('viewer-target')")
            if isinstance(colours, int) and colours > 1:
                break
            time.sleep(0.5)
        check("the tapped viewer has actually drawn something",
              isinstance(colours, int) and colours > 1,
              f"{colours} distinct colours in the centre of the canvas")
        tab.shot(out / "phone.png")
        tab.send("Emulation.clearDeviceMetricsOverride")
        # Cleared too: a coarse pointer left switched on would follow into anything added
        # after this block and quietly change what it measures.
        tab.send("Emulation.setTouchEmulationEnabled", enabled=False)

        # --------------------------------------------------------- console
        print("\nconsole")
        errors = [c for c in tab.console if c.startswith("error") or c.startswith("EXCEPTION")]
        check("no console errors or exceptions", not errors,
              "\n          ".join(errors[:6]))

        print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
        for name in FAIL:
            print(f"  FAILED: {name}")
        return 1 if FAIL else 0
    finally:
        if tab:
            tab.close()
        proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
