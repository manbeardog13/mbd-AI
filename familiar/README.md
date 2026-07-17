---
id: familiar.readme
title: Nero Desktop Familiar
layer: operational
type: reference
status: active
owner: shared
created: 2026-07-17
updated: 2026-07-17
---

# Nero Desktop Familiar

A small Windows desktop companion (`bin/NeroFamiliar.exe`) that renders Nero's
presence on the desktop. Source: `src/NeroFamiliar.cs` (C#). Runtime IPC:
`runtime/command.txt` (file-based commands; runs only while launched, no
daemon or autostart).

- **Build from source:** compile `src/NeroFamiliar.cs` with the .NET SDK/`csc`.
  The committed `bin/` artifacts are conveniences.
- **Policy note:** CANONICAL_STRUCTURE discourages binaries in-tree; the exe
  is grandfathered until a build step replaces it.
- Presence behavior and protocols: `../presence/` (Presence Director, Live2D
  bridge) and `../docs/mobile/presence_experience.md`.
