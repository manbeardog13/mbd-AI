---
id: spec.voidbound-codex
title: "Voidbound Codex v1 contract"
layer: core
type: spec
status: active
owner: toni
created: 2026-07-18
updated: 2026-07-18
---

# Voidbound Codex v1.1 contract

## 1. Product

Voidbound Codex is an original Nero-world top-down action RPG. It provides a
complete Journey across eight domains and an endless Survival mode. The three
oaths differ mechanically: Vanguard uses broad melee arcs, Lancer uses precise
reach and a charge, and Arcanist uses projectiles and seeking magic.

## 2. Gameplay invariants

- Movement and combat remain responsive at a 960×540 internal resolution.
- Passive enemies retaliate only after proximity or damage; aggressive enemies
  engage automatically. Elites and bosses are visually and mechanically clear.
- Health, stamina, XP, levels, upgrade choices, class arts, pickups, tonics,
  mastery, score, and character details are visible and deterministic.
- Journey domains end in a named keeper and a gate. Survival escalates by time
  and produces periodic bosses without a terminal domain.
- A dead player has exactly zero HP and one honest end-state transition.
- A selected companion follows without blocking movement, earns Bond levels,
  persists with the run, and exposes one mechanically distinct ability. Iskra
  marks and attacks, Nero guards and staggers, and Mia heals or projects light.

## 3. Input and accessibility

Keyboard, controller, and touch inputs are first-class. Gameplay controls have
visible help; dialogs are labelled; canvas focus is visible; motion honors
`prefers-reduced-motion`; color is never the sole carrier of vital status.

## 4. Persistence and privacy

The only persistent record is `nero.voidbound.v1` in browser localStorage.
Validation rejects malformed ranks and saved runs. No browser code performs a
network request, invokes a Nero API, reads `data/memory.db`, or publishes a
ranking. The loopback server is read-only and blocks path traversal.

Companion sprites are immutable local project copies with SHA-256 provenance.
Mia's copy must remain labelled provisional until her source build publishes a
validated package; the game must never alter that source build.

## 5. Mechanism

- Runtime assets: `app/static/adventure/`
- Loopback host: `scripts/serve_voidbound.py`
- Launcher: `adventure/Start-VoidboundCodex.ps1`
- Deterministic verifier: `verify/verify_voidbound_codex.py`
- Companion provenance: `app/static/adventure/assets/provenance.json`

## 6. Acceptance criteria

1. The verifier reports every required product, privacy, and packaging check as
   passing, and `node --check` accepts the runtime.
2. A real browser can select an oath, begin Journey, render the world, receive
   keyboard input, open the Codex, and persist a resumable run without errors.
3. Desktop and narrow mobile layouts preserve the game viewport and expose the
   appropriate controls without horizontal document scrolling.
4. The HTTP host binds only to `127.0.0.1`, serves only approved static roots,
   emits a restrictive CSP, and never starts Nero's standalone runtime.
5. All three companion cards render from their actual atlases, can start and
   resume a run, appear in the HUD and Codex, and execute their abilities without
   browser errors or network calls.
