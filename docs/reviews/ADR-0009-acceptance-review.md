---
id: reviews.adr-0009-acceptance
title: "ADR-0009 Acceptance Review"
layer: operational
type: review
status: active
owner: shared
created: 2026-07-13
updated: 2026-07-17
---

# ADR-0009 Acceptance Review

**Date:** 2026-07-13
**Reviewer:** Claude Code (acting on Toni's acceptance directive)
**Status:** Accepted with implementation gate preserved

Reviews: [ADR-0009 — Voice Rendering Profiles and Pluggable Voice Backend Architecture](../adr/0009-voice-rendering-and-backend-architecture.md), revised 2026-07-13.

---

## Decision

ADR-0009 is accepted as an architectural direction.

Acceptance means:

- The rendering / casting / backend seam is the approved future architecture.
- The measurement-first philosophy remains binding.
- Migration Stage 1 remains the current operating state.
- No implementation work is authorized by acceptance alone.

---

## Preconditions before migration begins

Migration work cannot begin until **all** of the following are true:

- Croatian MMS-TTS (or another second engine) is scheduled on a phase plan.
- The implementation window is defined.
- A migration PR is separately reviewed.

---

## Confirmed architectural decisions

The following decisions in ADR-0009 are final under this acceptance:

- **Option B `RealKokoroBackend` reuse is temporary** — a migration bridge, not a permanent layering rule.
- **Kokoro lifecycle extraction happens only when the dissolution trigger fires** (at the earlier of Migration Stage 5 or the first requirement for multiple independently configured Kokoro instances).
- **`TTSEngine` v1 is batch synthesis only** — text in, complete WAV bytes out, one utterance at a time.
- **Streaming requires a Phase-4 companion ADR** — the real-time voice loop is out of scope for ADR-0009.
- **Reference-audio engines require a superseding ADR** — Chatterbox-class cloning does not fit the `(text, engine_params)` contract shape.
- **Language routing belongs to the application layer** — the voice layer never runs its own language detection.
- **Existing `/api/metrics.voice` compatibility is preserved** — the `tts.METRICS` dict shape (`spoken`, `chars`, `last_ms`) is unchanged across all migration stages; new metrics may appear only as additional top-level keys.
- **`Config.tts_voice` remains a legacy migration override until Stage 5** — removed on completion of Migration Stage 5 as a documented breaking change.

---

## Implementation prohibition

> **Acceptance of ADR-0009 does not authorize creation of `voice/`, `TTSEngine`, `RenderingProfile`, `VoiceCasting`, backend modules, configuration changes, dependency changes, or API changes.**

Any PR that touches those surfaces requires a separate implementation authorization tied to a fired Migration Stage-2 trigger — i.e., a scheduled second engine with a defined implementation window (see Preconditions above).

---

## Final verdict

**ADR-0009 accepted.**
**Migration Stage 1 remains active.**
**No implementation begins.**
