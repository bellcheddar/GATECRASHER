#!/usr/bin/env python3
"""Measure GATECRASHER's cold load against the BUILD_SPEC Stage 4 budget.

    python3 tools/perf_check.py --base https://gatecrasher.mdeller.com

The budget: first meaningful paint under 2 s on a cold cache, and total initial transfer
under 1.5 MB excluding Mol*. Lighthouse cannot report "excluding Mol*", so this does.

A fresh Chrome profile is a cold cache. "Initial" means everything the page has fetched by
the time the app raises data-ready on the landing view; what the reader fetches later by
clicking (structures, other papers, PyMOL downloads) is lazy by construction and is not
counted. Transfer sizes come from Resource Timing, which reports them for same-origin
requests: every asset here is same-origin, and cross-origin requests are listed separately
so that none can hide.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_check import Tab, free_port, launch, ws_url  # noqa: E402

BUDGET_PAINT_MS = 2000
BUDGET_TRANSFER_B = 1.5 * 1024 * 1024
MOLSTAR = ("molstar.js", "molstar.css")


def measure(base: str) -> dict:
    port = free_port()
    profile = tempfile.mkdtemp(prefix="gc-perf-")
    chrome = launch(port, profile)
    try:
        tab = Tab(ws_url(port))
        start = time.time()
        tab.goto(base.rstrip("/") + "/")
        ready_s = time.time() - start
        time.sleep(1.0)       # let late paint entries land
        data = tab.js("""(() => {
            const origin = location.origin;
            const nav = performance.getEntriesByType('navigation')[0];
            const paints = Object.fromEntries(performance.getEntriesByType('paint')
                .map((p) => [p.name, p.startTime]));
            const lcp = performance.getEntriesByType('largest-contentful-paint');
            const resources = performance.getEntriesByType('resource').map((r) => ({
                url: r.name, type: r.initiatorType, transfer: r.transferSize,
                decoded: r.decodedBodySize, start: r.startTime, same: r.name.startsWith(origin),
            }));
            return { nav: { transfer: nav.transferSize, decoded: nav.decodedBodySize,
                             dcl: nav.domContentLoadedEventEnd, load: nav.loadEventEnd },
                     paints, lcp: lcp.length ? lcp[lcp.length - 1].startTime : null,
                     resources };
        })()""")
        tab.close()
    finally:
        chrome.terminate()
        shutil.rmtree(profile, ignore_errors=True)
    data["ready_s"] = ready_s
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8099")
    ap.add_argument("--top", type=int, default=12, help="largest requests to list")
    args = ap.parse_args()

    d = measure(args.base)
    rows = d["resources"]
    cross = [r for r in rows if not r["same"]]
    same = [r for r in rows if r["same"]]
    molstar = [r for r in same if any(m in r["url"] for m in MOLSTAR)]
    counted = [r for r in same if r not in molstar]
    total = d["nav"]["transfer"] + sum(r["transfer"] for r in counted)
    paint = d["paints"].get("first-contentful-paint")

    print(f"{args.base}  cold cache")
    print(f"  first contentful paint   {paint:.0f} ms" if paint else "  first contentful paint   n/a")
    print(f"  largest contentful paint {d['lcp']:.0f} ms" if d["lcp"] else "  largest contentful paint n/a")
    print(f"  app data-ready           {d['ready_s'] * 1000:.0f} ms")
    print(f"  requests                 {len(rows) + 1} ({len(cross)} cross-origin)")
    print(f"  transfer excl. Mol*      {total / 1024:.0f} kB")
    print(f"  Mol* transfer            {sum(r['transfer'] for r in molstar) / 1024:.0f} kB")
    print("\n  largest same-origin requests (transfer, decoded):")
    for r in sorted(same, key=lambda r: -r["transfer"])[: args.top]:
        path = r["url"].split("/", 3)[-1].split("?")[0]
        print(f"    {r['transfer'] / 1024:7.0f} kB {r['decoded'] / 1024:7.0f} kB  {path}")
    for r in cross:
        print(f"  cross-origin: {r['url']}")

    # A preload whose URL does not exactly match the later request (a ?v= stamp on one and
    # not the other, say) downloads the file twice. That is silent in the page, so count it.
    seen: dict[str, int] = {}
    for r in same:
        key = r["url"].split("?")[0]
        seen[key] = seen.get(key, 0) + 1
    duplicates = {url: n for url, n in seen.items() if n > 1}
    for url, n in duplicates.items():
        print(f"  fetched {n} times: {url.split('/', 3)[-1]}")

    ok_paint = paint is not None and paint < BUDGET_PAINT_MS
    ok_transfer = total < BUDGET_TRANSFER_B
    print(f"\n  {'ok  ' if ok_paint else 'FAIL'}  first paint under {BUDGET_PAINT_MS} ms")
    print(f"  {'ok  ' if ok_transfer else 'FAIL'}  initial transfer under 1.5 MB excluding Mol*")
    print(f"  {'ok  ' if not duplicates else 'FAIL'}  no file fetched twice")
    return 0 if ok_paint and ok_transfer and not duplicates else 1


if __name__ == "__main__":
    sys.exit(main())
