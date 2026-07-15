# Nero Presence Director

The visual counterpart to the Voice Director. Same principle: the brain
communicates *intent*, everything downstream is renderer-agnostic
implementation.

## What lives here

```
presence/
├── director.py                      the Director class — the one API the brain touches
├── types.py                         PresenceState, EmotionState, PresenceLevel, PresenceIntent
├── contracts/                       JSON Schemas — the wire format for out-of-process runtimes
│   ├── presence_intent.schema.json
│   └── voice_events.schema.json
├── runtime_bridge/                  pluggable renderers behind PresenceRuntime
│   ├── base.py                      abstract PresenceRuntime
│   ├── null.py                      NullRuntime — no-op, for tests / headless
│   └── log.py                       LogRuntime — prints intents, no rendering
└── README.md                        you are here
```

## Brain → Presence: the ONLY API

```python
from presence import PresenceDirector, PresenceIntent, PresenceState, EmotionState
from presence.runtime_bridge import LogRuntime

director = PresenceDirector(runtime=LogRuntime())
director.start()

director.emerge()  # never appears — always emerges

director.set_intent(PresenceIntent(
    state=PresenceState.THINKING,
    emotion=EmotionState.FOCUSED,
    intensity=0.4,
))

director.dissolve()  # reverse manifestation
director.stop()
```

The brain never mentions animations, particles, shaders, poses, or engine
names. That is a hard rule. If the brain would have to say
`play_animation("idle_breath")`, the runtime is doing too little.

## Presence Levels (0–5)

Capability tiers, not implementations. Each runtime declares its
`max_presence_level`; the Director caps requests at that ceiling.

| Level | Meaning |
|---|---|
| **L0** | Voice only. No visual manifestation. |
| **L1** | Minimal manifestation — eyes, particles, ambient glow, emergence sequence |
| **L2** | Animated portrait — shoulders-up, breathing, eye movement, idle expression |
| **L3** | Half-body companion — arms, posture, hand gestures, shoulder movement |
| **L4** | Full-body companion — procedural movement, environmental interaction, dynamic lighting |
| **L5** | Immersive — VR / AR / mixed reality, spatial audio, room-scale positioning |

MVP target is **L1** with a Live2D renderer eventually reaching L2. The
architecture supports L0–L5 from day one.

## Emergence — never appears, always emerges

`director.emerge()` walks the runtime through a four-step intensity ramp
(0.15 → 0.35 → 0.60 → 0.85 → 1.0 idle) with configurable per-step delay.
The runtime interprets each step. In an L1 runtime that means:

    0.15 : background darkens subtly
    0.35 : violet mist begins drifting, faint particles
    0.60 : purple eyes appear
    0.85 : silhouette resolves, character materializes
    1.00 : idle breathing begins

`director.dissolve()` runs the same ramp in reverse. Eyes disappear last.

These are intent sequences the Director owns; the *how* is entirely the
runtime's problem. Adding cinematic polish to the emergence is a runtime
change, not a Director change.

## Voice ↔ Presence coordination

The Voice Director emits events during synthesis (`voice.started`,
`voice.speaking`, `voice.finished`, `voice.interrupted`) via
`voice/events.py`. The Presence Director can opt into these:

```python
director.bind_to_voice()
```

After binding, voice events auto-translate to presence intents:

| Voice event | Presence intent |
|---|---|
| voice.started | state=SPEAKING, intensity=0.7 |
| voice.speaking | state=SPEAKING, intensity=0.9 (metadata carries sample_rate) |
| voice.finished | state=IDLE, intensity=1.0 |
| voice.interrupted | state=IDLE, intensity=0.6 |

The Presence Director never modifies voice; it observes. Voice never
imports from `presence/`.

## Adding a new runtime

Subclass `PresenceRuntime` (see `runtime_bridge/base.py`), declare
`max_presence_level` + `supported_capabilities`, implement `start` /
`stop` / `is_running` / `set_intent`. Ship it as a separate module or
package; the Director just needs an instance to hold.

Runtimes MAY run in-process (Null, Log, an embedded Godot loop) or
out-of-process (Live2D via WebSocket, Godot as a subprocess, Unreal via
Remote Control). The Director doesn't know or care — that is entirely
encapsulated in the runtime.

## Design invariants (do not violate)

1. **Brain says intent. Runtime does everything else.** No animation IDs,
   asset paths, or engine names in `PresenceIntent`.
2. **Runtime failures never propagate.** If `set_intent` raises, the
   Director logs and continues. Voice + chat are never blocked by visuals.
3. **Runtimes MUST tolerate unknown enum values.** Adding a new
   `PresenceState` or `EmotionState` should not break existing runtimes —
   they fall back to a sensible default (typically IDLE + NEUTRAL).
4. **`presence/` never imports from `voice/` at module top level.** The
   Voice-events subscription happens inside `bind_to_voice()` with a lazy
   import. This keeps the packages testable in isolation.
5. **No visual assets in this package.** Rigs, models, textures, shaders
   live outside — inside individual runtime implementations or in a
   dedicated asset location. The `presence/` package is contract + logic.
