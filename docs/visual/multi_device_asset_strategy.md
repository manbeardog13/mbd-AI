---
id: visual.multi-device-asset-strategy
title: "Multi-Device Asset Strategy"
layer: operational
type: reference
status: active
owner: shared
created: 2026-07-13
updated: 2026-07-17
---

# Multi-Device Asset Strategy

**Principle:** *one identity, many manifestations*. Manbeardog is the
same character on every device. The **presentation** varies to fit each
platform's constraints; the **identity** never does.

**Related docs:**
- `docs/visual/manbeardog_visual_bible.md` — the identity that stays constant
- `docs/mobile/presence_experience.md` — mobile-specific presentation
- `docs/visual/manbeardog_visual_production.md` §5-6 — multi-device architecture
- `presence/types.py::PresenceLevel` — the capability-tier enum this doc maps to

---

## The invariants (never adapt these per device)

These stay identical across every current and future device:

- **Character identity** — Manbeardog is Manbeardog. Same name, same personality, same visual DNA.
- **Voice** — `nero_prime_v1` on server, streamed as WAV bytes. Client never synthesizes locally.
- **Semantic state vocabulary** — `PresenceState` values (`emerging`, `idle`, `listening`, etc.) are identical on desktop, mobile, web, VR.
- **Emotional vocabulary** — `EmotionState` values same everywhere.
- **Color signature** — magenta wolf-eye glow + violet mist + gold rune activation. Same hex values (Visual Bible §6.1) across all devices.
- **Manifestation ritual** — always emerges, never appears. Wolf eyes appear first, dim last. Adapted duration per device but not sequence.
- **Never a foreign voice** — no browser SpeechSynthesis fallback, no cross-device voice substitution (per ADR-0011).

## The variables (adapt these per device)

Everything below is *presentation*, not identity:

- **Presence Level ceiling** — capped per device's rendering budget
- **Frame rate** — desktop can afford 60fps; mobile widget cannot
- **Particle density** — desktop mist has ~500 particles; mobile has 20
- **Emergence duration** — desktop ~2.0s (per Bible §11); mobile ~1.2s
- **Detail level** — full character body vs. emblem-only
- **Interaction affordances** — mouse hover vs. tap vs. eye-tracking (VR)

---

## Device tier matrix

| Device | Presence Level ceiling | Runtime | Asset source | Detail |
|---|---|---|---|---|
| **Desktop (Windows)** | L2 today, L4 target | Live2D via Cubism Web SDK viewer | `characters/manbeardog/live2d/model/manbeardog__L2__v1` | Head-and-shoulders portrait with breathing + subtle motion |
| **Desktop (macOS / Linux)** | Same as Windows | Same viewer | Same asset | Same |
| **Web browser (any OS)** | L2 | Live2D Web SDK embedded in the existing Nero web UI | Same L2 asset | Same |
| **Mobile widget (Android / iOS)** | L1 | Custom shader emblem | `mobile/emblem/wolf_eyes_v1.png` + `mobile/shaders/mist_L1.wgsl` | Wolf-eye emblem + subtle mist |
| **Mobile full-screen** | L1 (upgraded animation) | Same custom shader, richer | Same emblem asset | Emblem + full mist particle system + rune pulses |
| **Mobile lock-screen media** | L0 (voice + static emblem) | OS media session | Static emblem PNG | Emblem-as-icon, no animation |
| **VR headset (future)** | L5 | Unreal or custom WebXR | Full 3D master from `characters/manbeardog/master/exports/*.fbx` | Full body, spatial audio, room-scale positioning |
| **AR overlay (future)** | L2-L3 | Native ARKit / ARCore | 3D master + AR-optimized textures | Half-body, environment-aware |
| **Smart display / TV** | L3-L4 (open question) | Cast-friendly web viewer or native | Same L2 or higher | Portrait or half-body |

## Asset production per device

The character comes from one master, but per-device optimizations happen
downstream:

```
                Manbeardog LoRA
                       │
                       ▼
              Master reference art
                (2048×2048 renders)
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
 Layer-separated  Blender master  Emblem PNG
   PSD for       (Blender master  (mobile:
   Live2D          Blender)       distilled to
                                   wolf-eyes only)
        │              │              │
        ▼              ▼              ▼
    Cubism        Unreal / Blender  Mobile shader
     rig          renders           renders
        │              │              │
        ▼              ▼              ▼
     Desktop     VR / cinematic     Widget / phone
    + web           / promo         full-screen
```

Every branch draws from the same master. If the master changes (v2), the
branches re-derive. No branch modifies the master.

## Presence-Level upgrade / downgrade

A single connected session may include multiple clients at different
levels simultaneously. The Presence Director broadcasts the same semantic
intent to all of them; each client renders per its own level ceiling:

```
PresenceDirector.set_intent(SPEAKING, WARM, 0.9)
                       │
                       ├──▶ desktop L2 viewer:   full portrait speaking animation + warm-rim
                       ├──▶ mobile widget L1:    wolf-eye pulse, brief warm-tinted rim
                       ├──▶ lock-screen L0:      static emblem, media session shows "Nero speaking"
                       └──▶ future VR L5:        full-body speaking animation, spatial audio positioning
```

**Graceful degradation is client-side.** A mobile client that can only
handle L1 doesn't ask the server to send different intents — it receives
the same intents and renders what it can. This keeps the server simple
and the client fully in control of its own performance envelope.

**Graceful upgrade** works the same. If a mobile client becomes capable
of L2 (e.g. iPad Pro), it upgrades its own renderer to handle L2 intents.
The server has no per-device rendering logic.

## Handling capability mismatches

Some presence intents don't have obvious L1 or L0 equivalents. Rules for
handling them:

| Intent feature | L4 (full body) | L2 (portrait) | L1 (emblem) | L0 (voice-only) |
|---|---|---|---|---|
| Warm-rim (celebrating) | Full-body warm rim on armor edges | Warm rim on visible shoulders | Warm-tinted through-glow, brief | Nothing visual — voice tone conveys |
| Alert (stillness) | Full-body freeze | Portrait freeze + wolf-eyes 100% | Wolf-eyes 100%, mist stops | Nothing visual — voice tone conveys |
| Emergence | Full 5-step ramp with body materialization | Portrait resolves from mist | Emblem appears, wolf eyes first | Voice arrives at fully-ready state |
| Speaking sync | Facial animation + breathing | Head motion + breathing | Emblem pulse synchronized with voice | Voice plays; no visual |
| Thinking (rune pulse) | Runes on visible armor activate | Runes on shoulder plates activate | Gold ring pulse around emblem | Nothing visual |
| Concerned | Slight forward tilt, dimmer wolf-eyes | Same on portrait | Emblem dims | Voice tone conveys |

The pattern: **the visual language degrades, but the intent is always
honored somehow.** Even L0 has a way — the voice itself.

## Asset versioning per device

Each device's asset is versioned independently but tied to a master
reference version:

```
manbeardog_v1 LoRA (2026-07-XX)
├── manbeardog_master_v1.png (front reference)
│   ├── manbeardog__L1__v1.emblem.png     (mobile widget)
│   ├── manbeardog__L2__v1.model3.json    (Live2D)
│   ├── manbeardog__L2__v1.moc3
│   └── manbeardog_master_v1.blend        (Blender master)
│       ├── manbeardog__L4__v1.fbx        (future Unreal)
│       └── manbeardog_promo_wallpaper_v1.png
```

When the LoRA advances to v2 (a deliberate identity evolution):
- Master reference re-renders as v2
- Downstream assets each get a v2 (independently, on their own timeline)
- v1 assets stay frozen — old sessions / cached clients keep working

## Governance

This strategy is v1.0. Adding new device targets:

1. Update the device tier matrix above with the new device's row
2. Decide which existing asset it derives from (usually L1 emblem, L2
   portrait, or L4 master)
3. Note any device-specific optimizations required
4. Update `presence/types.py::LEVEL_CAPABILITIES` only if the new device
   introduces a genuinely new capability (rare — most devices sit in
   existing levels)

## Not in scope for v1

- **Cross-device state sync** — if Toni starts a conversation on desktop,
  should the phone widget reflect Nero's current state? Yes eventually,
  but that's a multi-client server feature (Phase E), not an asset
  strategy question.
- **Per-user variants** — Nero is single-user. If Nero ever becomes
  multi-user (unlikely), per-user Manbeardog skins would live under
  `characters/manbeardog/skins/` — not yet.
- **Localized visual variants** — e.g. a Croatian regional aesthetic
  variant. Not planned; identity is universal.
