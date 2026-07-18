#!/usr/bin/env python3
"""Deterministically verify the Nero Void Guardian familiar v2 contract."""
from __future__ import annotations

import json
import hashlib
import os
import re
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "familiar" / "src" / "NeroFamiliar.cs"
CONTRACT = ROOT / "familiar" / "nero_companion_runtime_v2.json"
ATLAS = ROOT / "familiar" / "assets" / "nero" / "nero-voidcaster-v2.png"
ICON = ROOT / "familiar" / "assets" / "nero" / "nero-voidcaster.ico"
BINARY = ROOT / "familiar" / "bin" / "NeroFamiliar.exe"
BUILD_SCRIPT = ROOT / "familiar" / "Build-NeroFamiliar.ps1"
sys.path.insert(0, str(ROOT))


def main() -> int:
    checks: list[dict] = []

    def check(name, fn):
        try:
            detail = fn()
            checks.append({"check": name, "ok": True, "detail": detail})
        except Exception as exc:
            checks.append({"check": name, "ok": False, "error": str(exc)})

    def contract_shape():
        data = json.loads(CONTRACT.read_text(encoding="utf-8"))
        assert data["specVersion"] == "2.0.0"
        assert data["id"] == "nero-voidcaster"
        state_ids = {item["id"] for item in data["states"]}
        event_ids = {item["event"] for item in data["events"]}
        assert len(state_ids) == 19, state_ids
        assert len(event_ids) == 15, event_ids
        assert data["runtime"]["eventQueue"]["maxDepth"] == 32
        assert data["runtime"]["eventQueue"]["coalesceRepeatedEventsWithinMs"] == 750
        assert data["runtime"]["eventChannel"]["maxPending"] == 32
        assert data["runtime"]["eventChannel"]["maxPendingBytes"] == 16384
        assert data["audio"]["enabledByDefault"] is False
        assets = data["assets"]
        asset_root = CONTRACT.parent / assets["basePath"]
        declared = [assets["runtimeAtlas"], *assets["provenance"]]
        for record in declared:
            path = asset_root / record["file"]
            assert path.is_file(), path
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"], path
        assert set(assets["fallbackRegistry"]) <= state_ids
        return "v2 identity, exact event/state sets, shipped asset hashes, bounded queue, and audio-off default"

    def atlas_shape():
        raw = ATLAS.read_bytes()
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
        width, height, _depth, color_type = struct.unpack(">IIBB", raw[16:26])
        assert (width, height) == (1536, 416), (width, height)
        assert (_depth, color_type) == (8, 6), (_depth, color_type)
        chunks, cursor = [], 8
        while cursor < len(raw):
            length = struct.unpack(">I", raw[cursor:cursor + 4])[0]
            kind = raw[cursor + 4:cursor + 8]
            payload = raw[cursor + 8:cursor + 8 + length]
            if kind == b"IDAT":
                chunks.append(payload)
            cursor += length + 12
        scan = zlib.decompress(b"".join(chunks))
        stride, bpp, previous, offset = width * 4, 4, bytearray(width * 4), 0
        alpha_rows, rgba_rows = [], []
        for _y in range(height):
            filter_type, offset = scan[offset], offset + 1
            row = bytearray(scan[offset:offset + stride]); offset += stride
            for x in range(stride):
                left = row[x - bpp] if x >= bpp else 0
                up = previous[x]
                upper_left = previous[x - bpp] if x >= bpp else 0
                if filter_type == 1:
                    row[x] = (row[x] + left) & 255
                elif filter_type == 2:
                    row[x] = (row[x] + up) & 255
                elif filter_type == 3:
                    row[x] = (row[x] + ((left + up) // 2)) & 255
                elif filter_type == 4:
                    estimate = left + up - upper_left
                    pa, pb, pc = abs(estimate - left), abs(estimate - up), abs(estimate - upper_left)
                    predictor = left if pa <= pb and pa <= pc else up if pb <= pc else upper_left
                    row[x] = (row[x] + predictor) & 255
                elif filter_type != 0:
                    raise AssertionError(f"unsupported PNG filter {filter_type}")
            alpha_rows.append(row[3::4]); rgba_rows.append(row); previous = row
        transparent = sum(value == 0 for row in alpha_rows for value in row)
        visible = sum(value > 0 for row in alpha_rows for value in row)
        assert transparent > width * height // 3, transparent
        assert visible > width * height // 10, visible
        chroma_leaks = sum(
            rgba[x + 3] > 20 and rgba[x + 1] > 220 and rgba[x] < 40 and rgba[x + 2] < 40
            for rgba in rgba_rows for x in range(0, stride, 4)
        )
        assert chroma_leaks == 0, chroma_leaks
        for row in range(2):
            for column in range(8):
                cell_rows = [
                    values[column * 192:(column + 1) * 192]
                    for values in alpha_rows[row * 208:(row + 1) * 208]
                ]
                visible_cell = sum(value > 0 for values in cell_rows for value in values)
                assert visible_cell > 5000, (row, column, visible_cell)
                points = [(x, y) for y, values in enumerate(cell_rows)
                          for x, value in enumerate(values) if value > 0]
                box = (min(x for x, _ in points), min(y for _, y in points),
                       max(x for x, _ in points) + 1, max(y for _, y in points) + 1)
                assert box[0] >= 2 and box[1] >= 2 and box[2] <= 190 and box[3] <= 206, (
                    row, column, box)
        cell_hashes = []
        for row in range(2):
            for column in range(8):
                cell = b"".join(
                    bytes(values[column * 192 * 4:(column + 1) * 192 * 4])
                    for values in rgba_rows[row * 208:(row + 1) * 208]
                )
                cell_hashes.append(hashlib.sha256(cell).digest())
        assert len(set(cell_hashes)) == 16, "duplicate atlas cells"
        return "RGBA atlas is 1536x416; transparency, clean edges, and 16 unique crops verified"

    def semantic_bridge():
        from presence.runtime_bridge import FamiliarRuntime
        from presence.types import PresenceIntent, PresenceState
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "command.txt"
            runtime = FamiliarRuntime(path)
            runtime.set_intent(PresenceIntent(PresenceState.THINKING))
            assert not path.exists()
            runtime.start()
            runtime.set_intent(PresenceIntent(
                PresenceState.THINKING,
                metadata={"activity": "heavy", "label": "Void Guardian verification"}))
            spool = path.parent / "command.d"
            envelopes = sorted(spool.glob("*.cmd"))
            assert len(envelopes) == 1
            envelope = json.loads(envelopes[0].read_text(encoding="utf-8"))
            assert envelope == {"event": "agents.dual_active",
                                "label": "Void Guardian verification",
                                "confirmed": False, "provenance": ""}
        return "cold bridge durably spools one exact, bounded v2 event and launches nothing"

    def package_shape():
        icon = ICON.read_bytes()
        reserved, image_type, count = struct.unpack("<HHH", icon[:6])
        assert (reserved, image_type) == (0, 1)
        assert count >= 5, count
        build = BUILD_SCRIPT.read_text(encoding="utf-8-sig")
        assert "NeroFamiliar.exe" in build
        assert "NeroFamiliar-v2.exe" not in build
        assert not (BINARY.parent / "NeroFamiliar-v2.exe").exists()
        if BINARY.exists():
            executable = BINARY.read_bytes()
            assert executable[:2] == b"MZ" and len(executable) > 30000
        return "source-first build path and custom multi-size icon verified; local PE is optional"

    def source_boundary():
        text = SOURCE.read_text(encoding="utf-8")
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        implemented_events = set(re.findall(r'Map\("([^"]+)"', text))
        implemented_states = set(re.findall(r'return "([a-z_]+)";', text))
        assert implemented_events == {item["event"] for item in contract["events"]}
        assert {item["id"] for item in contract["states"]} <= implemented_states
        for token in (
            "MaxQueueDepth = 32", "CoalesceMilliseconds = 750",
            "BitmapScalingMode.NearestNeighbor", "AutomationProperties.SetName",
            'Map("system.critical"', 'Map("task.succeeded"',
            'Map("claude.started"', 'Map("codex.started"',
            'return "critical_alert"', 'return "dual_agent_ascension"',
            '"Nero is hidden"', "MissingArt",
            "Key.Escape", "WS_EX_NOACTIVATE", "_reducedMotion ? _bubbleTarget",
            "(now - previous).TotalMilliseconds < CoalesceMilliseconds",
            "if (pending.Definition.Priority <= _queue[0].Definition.Priority) return;",
            "if (dismiss)", "IsLatchedAlert(_active.State)",
            "next.Definition.Priority < _active.Priority",
            "DrainEventSpool", "Array.Sort(paths, StringComparer.Ordinal)",
            "AutomationEvents.LiveRegionChanged", "new Mutex(true",
            "DispatchEnvelope", "QuarantineEnvelope", "ValidateStateRecords",
            "ValidateEventRecords", "ValidateAssets", "ValidateEventChannel",
        ):
            assert token in text, token
        forbidden = (
            "Process.Start", "HttpClient", "WebClient", "autostart=1",
            "cmd.exe", "powershell", "Ollama", "memory.db",
        )
        assert not any(token in text for token in forbidden)
        assert "LegacyEvent" not in text
        return "event, accessibility, pixel-render, fallback, and no-execution boundaries present"

    def compile_source():
        windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        framework = windir / "Microsoft.NET" / "Framework64" / "v4.0.30319"
        csc, wpf = framework / "csc.exe", framework / "WPF"
        if not csc.exists():
            raise RuntimeError("installed .NET Framework csc.exe not found")
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "NeroFamiliar-v2.exe"
            references = [
                wpf / "WindowsBase.dll", wpf / "PresentationCore.dll",
                wpf / "PresentationFramework.dll", framework / "System.Xaml.dll",
                framework / "System.Windows.Forms.dll", framework / "System.Drawing.dll",
                framework / "System.Web.Extensions.dll",
            ]
            command = [str(csc), "/nologo", "/target:winexe", f"/out:{output}"]
            command += [f"/reference:{item}" for item in references]
            command.append(str(SOURCE))
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stdout + result.stderr
            assert output.exists() and output.stat().st_size > 0
        return "WPF source compiles to a temporary binary; repository binary untouched"

    check("v2 contract", contract_shape)
    check("sprite atlas", atlas_shape)
    check("semantic bridge", semantic_bridge)
    check("package", package_shape)
    check("authority boundary", source_boundary)
    check("source compilation", compile_source)
    ok = all(item["ok"] for item in checks)
    print(json.dumps({"ok": ok, "checks": checks}, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
