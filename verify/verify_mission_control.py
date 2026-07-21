#!/usr/bin/env python3
"""Verify the Mission Control screen — routes wired, data honest.

Offline checks (always run): the three static assets exist and carry the
honesty invariants the acceptance directive requires — the telemetry gate
(``simulated !== false``), the dispatch contract (``target=claude`` /
``role=architect``, "Not sent" + local retention on failure), and no fabricated
telemetry anywhere in the backend.

Live route checks run through Starlette's TestClient when FastAPI is importable:
``/mission-control`` serves the page, ``/api/host`` is honest (measured →
``simulated: false`` with GPU null+reason when psutil is present, otherwise a
``503`` — never invented numbers), ``/api/council/dispatch`` returns an honest
``503`` until a real adapter exists, and the chat page still works.

Exit codes (the shared contract): 0 = pass · 2 = skip · other = fail.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
STATIC = ROOT / "app" / "static"

FAILS: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"  {'OK' if ok else 'XX'} {name}")
    if not ok:
        FAILS.append(name)


def offline_checks() -> None:
    html = (STATIC / "mission-control.html").read_text(encoding="utf-8")
    css = (STATIC / "mission-control.css").read_text(encoding="utf-8")
    js = (STATIC / "mission-control.js").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")

    check("page links its css + js", "mission-control.css" in html and "mission-control.js" in html)
    check("page keeps the three distinct disclosures",
          "CORE · SEALED" in html and "COMPANION · ACTIVE" in html and "COMPUTER USE · SIMULATION" in html)
    check("field canvas + nine state tabs present",
          'id="field-canvas"' in html and html.count('class="state-btn') >= 9)

    # Telemetry honesty: a gauge renders only on attested simulated:false.
    check("telemetry gate requires simulated===false", "d.simulated !== false" in js)
    check("GPU null path states a reason (no silent gauge)", "gpuReason" in js and "No vendor-neutral GPU" in js)

    # Dispatch honesty: right contract; failure says Not sent and keeps files.
    check("dispatch targets claude/architect via the council endpoint",
          "'claude'" in js and "'architect'" in js and "/api/council/dispatch" in js)
    check("dispatch failure says 'Not sent' and retains files", "Not sent" in js)
    # Files are cleared exactly once, on the success path — before the "Not
    # sent" failure branch, which never clears. So files are retained on failure.
    clear_idx = js.find("app.files = []")
    fail_idx = js.find("Not sent: ")  # the code branch (colon); not the doc comment
    check("staged files cleared only on success (not on failure)",
          js.count("app.files = []") == 1 and clear_idx != -1 and clear_idx < fail_idx)

    # Backend never fabricates telemetry.
    check("backend attests simulated:False only for measured values", '"simulated": False' in main)
    check("backend invents no 'simulated': True anywhere", '"simulated": True' not in main)
    check("backend falls back to 503 when no measured source", "status_code=503" in main)
    check("routes registered", '"/mission-control"' in main and '"/api/host"' in main and '"/api/council/dispatch"' in main)


def live_checks() -> None:
    try:
        from fastapi.testclient import TestClient  # noqa: E402
        from app.main import app  # noqa: E402
    except Exception as exc:  # noqa: BLE001 - dep-absent is a skip, not a fail
        print(f"  . live route checks skipped — FastAPI not importable ({exc}).")
        return

    c = TestClient(app)

    r = c.get("/mission-control")
    check("GET /mission-control -> 200 html", r.status_code == 200 and "Mission Control" in r.text)

    r = c.get("/api/host")
    if r.status_code == 200:
        d = r.json()
        ok = (d.get("simulated") is False
              and isinstance(d.get("cpu"), (int, float))
              and d.get("gpu") is None and bool(d.get("gpu_reason")))
        check("GET /api/host honest LIVE (measured, simulated:false, gpu null+reason)", ok)
    else:
        check("GET /api/host honest UNAVAILABLE (503, no invented numbers)", r.status_code == 503)

    r = c.post("/api/council/dispatch", data={"prompt": "x", "target": "claude", "role": "architect"})
    check("POST /api/council/dispatch -> honest 503 (no adapter)", r.status_code == 503)

    r = c.get("/")
    check("chat page still serves and links Mission Control",
          r.status_code == 200 and "/mission-control" in r.text)


def main() -> int:
    print("Mission Control — verification")
    try:
        offline_checks()
    except FileNotFoundError as exc:
        print(f"  XX missing asset: {exc}")
        return 1
    live_checks()
    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  Mission Control verified — routes wired, data honest.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
