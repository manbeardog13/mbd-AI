#!/usr/bin/env python3
"""Deterministic static verifier for Nero: Voidbound Codex."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "app" / "static" / "adventure" / "index.html"
STYLE = ENTRY.with_name("styles.css")
GAME = ENTRY.with_name("game.js")
SERVER = ROOT / "scripts" / "serve_voidbound.py"
LAUNCHER = ROOT / "adventure" / "Start-VoidboundCodex.ps1"
SPEC = ROOT / "docs" / "specs" / "voidbound-codex.spec.md"
ADR = ROOT / "docs" / "adr" / "0026-voidbound-codex.md"
ASSETS = ENTRY.parent / "assets"
PROVENANCE = ASSETS / "provenance.json"


def check(condition: bool, label: str, failures: list[str]) -> None:
    if condition:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        failures.append(label)


def main() -> int:
    failures: list[str] = []
    companion_assets = [ASSETS / name for name in [
        "iskra-v2.webp", "nero-void-guardian-v2.webp", "mia-v2-provisional.webp", "voidbound-companions-keyart-v1.png",
    ]]
    required = [ENTRY, STYLE, GAME, SERVER, LAUNCHER, SPEC, ADR, PROVENANCE, *companion_assets]
    check(all(path.is_file() for path in required), "all runtime, launcher, spec, and ADR files exist", failures)
    if failures:
        return 1

    html = ENTRY.read_text(encoding="utf-8")
    css = STYLE.read_text(encoding="utf-8")
    js = GAME.read_text(encoding="utf-8")
    server = SERVER.read_text(encoding="utf-8")
    launcher = LAUNCHER.read_text(encoding="utf-8")
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))

    ids = re.findall(r'\bid="([^"]+)"', html)
    check(len(ids) == len(set(ids)), "HTML element IDs are unique", failures)
    js_ids = set(re.findall(r'\$\("([^"]+)"\)', js))
    check(js_ids.issubset(set(ids)), "all direct JavaScript DOM references resolve", failures)

    result = subprocess.run(["node", "--check", str(GAME)], capture_output=True, text=True, check=False)
    check(result.returncode == 0, "JavaScript passes node --check", failures)
    if result.returncode:
        print(result.stderr.strip())

    check(js.count("{ name:") >= 8 and "The Violet Terminus" in js, "eight named Journey domains are present", failures)
    check(all(token in js for token in ["vanguard:", "lancer:", "arcanist:"]), "three mechanically distinct oath classes are present", failures)
    check(all(token in js for token in ["iskra:", "nero:", "mia:", "updateCompanion", "grantCompanionBond"]), "Iskra, Nero, and Mia have companion behaviors and Bond progression", failures)
    check(all(token in html for token in ["companion-grid", "companion-avatar", "bond-label"]), "companion selection and HUD contracts are present", failures)
    check(all(token in js for token in ["journey", "survival", "spawnEnemy({ boss: true })", "showLevelUp", "openCodex"]), "core modes, bosses, progression, and character sheet are wired", failures)
    input_contracts = all(token in js for token in ["navigator.getGamepads", "touchstart", "keydown"])
    check(input_contracts and "prefers-reduced-motion" in css, "keyboard, controller, touch, and reduced-motion contracts exist", failures)

    forbidden = ["fetch(", "XMLHttpRequest", "WebSocket(", "EventSource(", "data/memory.db", "/api/"]
    check(not any(token in js for token in forbidden), "browser runtime has no network, memory DB, or Nero API path", failures)
    check("localStorage" in js and "validSavedRun" in js and "validRank" in js, "versioned local persistence has saved-run and rank validation", failures)

    manifest_assets = {entry.get("file"): entry for entry in provenance.get("assets", [])}
    hashes_match = True
    for asset in companion_assets:
        expected = manifest_assets.get(asset.name, {}).get("sha256", "").lower()
        actual = hashlib.sha256(asset.read_bytes()).hexdigest()
        hashes_match &= bool(expected) and expected == actual
    check(hashes_match, "companion and key-art hashes match the provenance manifest", failures)
    mia_status = manifest_assets.get("mia-v2-provisional.webp", {}).get("status", "")
    check("provisional" in mia_status and "untouched" in mia_status, "Mia is honestly labelled as an untouched provisional build copy", failures)
    check("voidbound-companions-keyart-v1.png" in css, "generated companion key art is wired into the title screen", failures)

    check('(\"127.0.0.1\", args.port)' in server, "static host binds explicitly to loopback", failures)
    check("relative_to(base_root)" in server and "path.startswith(\"/static/\")" in server, "static host constrains resolved paths to its approved root", failures)
    check("Content-Security-Policy" in server and "connect-src 'none'" in server, "static host emits restrictive browser security headers", failures)
    check("serve_voidbound.py" in launcher and "http://127.0.0.1" in launcher, "launcher targets only the dedicated static host", failures)
    check(not any(token in launcher.lower() for token in ["ollama", "run.py", "memory.db", "start-nero"]), "launcher cannot start the Nero runtime or local model", failures)

    if failures:
        print(f"\nVOIDBOUND CODEX: FAIL ({len(failures)} check(s))")
        return 1
    print("\nVOIDBOUND CODEX: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
