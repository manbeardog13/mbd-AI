---
id: familiar.readme
title: Nero Void Guardian Desktop Familiar
layer: operational
type: reference
status: active
owner: shared
created: 2026-07-17
updated: 2026-07-18
---

# Nero Void Guardian Desktop Familiar

`bin/NeroFamiliar.exe` is the locally built, opt-in Windows desktop pet. It renders the
locked `nero-voidcaster` identity from `assets/nero/nero-voidcaster-v2.png` and
unfolds compact Mission Control in the same transparent WPF surface. It is a
visual renderer, never a model, speaker, gate, approval mechanism, or agent.

## Run and control

Run `Install-NeroFamiliar.ps1` once to build the executable and create the
**Nero - Void Guardian** desktop shortcut. Run the executable or shortcut
explicitly; there is no autostart or daemon. The overlay is topmost, no-activate,
and click-through by default. Use
the tray menu to enable **Interactive**, open **Mission Control**, pause motion,
enable **Reduced motion**, dismiss, or exit.

The cold `presence.runtime_bridge.FamiliarRuntime` writes exact v2 event IDs as
uniquely named, atomically published envelopes under `runtime/command.d/`.
The overlay consumes each structured JSON envelope once in filename order and
deletes it only after UI-thread acceptance. The spool is bounded to 32
envelopes/16 KiB; a stopped consumer produces explicit backpressure instead of
unbounded disk growth. Labels and provenance are display-only, single-line, and
limited to 160 characters. The bridge does not launch the executable. Unknown
or malformed envelopes are quarantined and surfaced in Mission Control.

Examples:

```json
{"event":"nero.thinking","label":"Checking the build","confirmed":false,"provenance":""}
{"event":"task.succeeded","label":"Checks passed","confirmed":true,"provenance":"verify_nero_familiar:exit-0"}
```

`task.succeeded` and `git.push_succeeded` require `confirmed: true` plus bounded
printable provenance from the caller. Generic celebration or activity metadata
never asserts completion, and the renderer never infers gate completion.

## Build and verify

Run `Build-NeroFamiliar.ps1` from this directory to compile the source with the
installed .NET Framework compiler. Source is authoritative; the executable is a
local ignored build artifact and is not a release trust anchor.

```powershell
python -m unittest tests.test_familiar_runtime
python verify/verify_nero_familiar.py
```

The verifier checks the JSON contract, exact atlas geometry and alpha support,
cold bridge, authority boundary, and a clean temporary compilation. Audio is
off by default; the implementation does not provide TTS or local voice.

Contract: `nero_companion_runtime_v2.json`. Human-readable design contract:
`../docs/specs/desktop-familiar.spec.md`. Decision: ADR-0025.
