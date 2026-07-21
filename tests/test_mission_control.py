"""Offline unit checks for the Mission Control screen.

These read the shipped assets and the backend and assert the *honesty*
invariants the acceptance directive requires — no server, no psutil, no network
— so they run anywhere (incl. CI). Route-level behaviour is exercised by
``verify/verify_mission_control.py`` when FastAPI is present.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"

HTML = (STATIC / "mission-control.html").read_text(encoding="utf-8")
CSS = (STATIC / "mission-control.css").read_text(encoding="utf-8")
JS = (STATIC / "mission-control.js").read_text(encoding="utf-8")
MAIN = (ROOT / "app" / "main.py").read_text(encoding="utf-8")


def test_assets_present_and_linked():
    assert "mission-control.css" in HTML
    assert "mission-control.js" in HTML
    assert '<title>NERO · Mission Control</title>' in HTML


def test_three_disclosures_are_distinct():
    # Core sealed / Companion active / Computer-use simulation must all remain.
    assert "CORE · SEALED" in HTML
    assert "COMPANION · ACTIVE" in HTML
    assert "COMPUTER USE · SIMULATION" in HTML


def test_nine_field_states():
    for state in ["idle", "listening", "thinking", "planning", "reviewing",
                  "executing", "speaking", "waiting", "offline"]:
        assert f'data-state="{state}"' in HTML, state


def test_telemetry_gate_requires_attestation():
    # A gauge renders only when the adapter attests simulated:false.
    assert "d.simulated !== false" in JS


def test_gpu_null_states_a_reason():
    assert "gpuReason" in JS
    assert "No vendor-neutral GPU" in JS


def test_dispatch_contract():
    assert "/api/council/dispatch" in JS
    assert "'claude'" in JS and "'architect'" in JS


def test_dispatch_failure_is_honest_and_retains_files():
    assert "Not sent" in JS
    # Staged files are cleared exactly once, on the success path — which sits
    # textually before the "Not sent" failure branch. The failure branch never
    # clears, so files are retained locally when the adapter is unavailable.
    assert JS.count("app.files = []") == 1
    clear_idx = JS.find("app.files = []")
    fail_idx = JS.find("Not sent: ")  # the code branch (colon); not the doc comment
    assert clear_idx != -1 and fail_idx != -1 and clear_idx < fail_idx


def test_backend_never_fabricates_telemetry():
    # simulated:False is asserted only for measured values; never simulated:True.
    assert '"simulated": False' in MAIN
    assert '"simulated": True' not in MAIN
    # And a genuine 503 fallback exists when no measured source is present.
    assert "status_code=503" in MAIN


def test_backend_routes_registered():
    assert '"/mission-control"' in MAIN
    assert '"/api/host"' in MAIN
    assert '"/api/council/dispatch"' in MAIN


def test_structure_is_grayscale_nero_keeps_color():
    # The operator ramp is present; Nero's cyan lives in the token set.
    for gray in ["#070707", "#0e0f0f", "#141414", "#1c1c1c", "#252525", "#343534"]:
        assert gray in CSS, gray
    assert "--cyan:#58f3ff" in CSS  # Nero keeps her colours


CONNECT = (STATIC / "connect.html").read_text(encoding="utf-8")
MANIFEST = (STATIC / "mission-control.webmanifest").read_text(encoding="utf-8")


def test_pwa_installable_for_phone_tablet():
    # Home-screen icon path: manifest linked + Apple touch meta + orb icons.
    assert 'rel="manifest"' in HTML and "mission-control.webmanifest" in HTML
    assert "apple-touch-icon" in HTML
    assert '"start_url": "/mission-control"' in MANIFEST
    assert "mission-control-512.png" in MANIFEST
    for png in ["mission-control-192.png", "mission-control-512.png", "mission-control-180.png"]:
        assert (STATIC / png).exists(), png


def test_device_connect_page_and_routes():
    assert "/api/connect" in CONNECT and "Add to Home Screen" in CONNECT
    assert '"/connect"' in MAIN and '"/api/connect"' in MAIN
    # Devices link is discoverable from Mission Control.
    assert 'href="/connect"' in HTML
    # QR is optional — the endpoint must not hard-require segno.
    assert "segno is not None" in MAIN


def test_windows_launcher_and_icon_present():
    scripts = ROOT / "scripts"
    for f in ["mission-control.ps1", "install-desktop-icon.ps1",
              "Create Desktop Icon.cmd", "nero-mission-control.ico", "make_icon.py"]:
        assert (scripts / f).exists(), f


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} unit tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
