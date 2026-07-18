# ADR-0022: Nero's textual voice is canon — one bible, engine-agnostic, test-gated

**Status:** Proposed (Toni's directive 2026-07-17: "a voice as rich as Sol — savvy and relaxed"; design pending his review)
**Date:** 2026-07-17

## Context

Nero's voice existed as six capsule adjectives, an app-side humor dial, and
two days of lived behavior Toni repeatedly confirmed — but nothing
operationalized it. Each engine could drift stylistically without any check
noticing, the way the capsules once drifted structurally. Toni's directive:
grow the voice deliberately — pattern recognition, integration, and tests of
all sorts — targeting the register he named savvy and relaxed.

## Decision

1. **The voice is defined in canon, not in engines.**
   `docs/persona/NERO_VOICE_BIBLE.md` is law for prose the way the Visual
   Bible is law for pixels; `VOICE_PATTERNS_MINED.md` (P1–P16) is its cited
   evidence trail from capsules, the live app persona, Sol's demonstrated
   register, the visual temperament, and two days of confirmed behavior.
2. **An eight-invariant fingerprint is the identity plane of prose**
   (calibrated honesty, evidence-borne feeling, protectiveness,
   one-pass declaratives, separate-facts discipline, micro-expressions,
   owned mistakes with same-breath fix, bandwidth respect). Engines style
   within it, never out of it (extends ADR-0020).
3. **Conformance is test-gated.** `docs/persona/voice-goldens.md` (13
   register-tagged probes) is the reference corpus;
   `verify/verify_nero_voice.py` enforces the mechanical layer (lexicon,
   densities, emoji policy, register rules) and lints any candidate text.
   Voice-law changes and golden changes travel together.
4. **Structural integration:** briefs, check-ins, interrupts, and
   engine-handoff artifacts are registers with rules, binding ADR-0021's
   surfaces to the voice; the capsule gains a one-line pointer to the Bible
   in the V3 proposal rather than inlining style into identity text.

## Consequences

- The voice becomes reviewable, diffable, and enforceable — drift gets
  caught by a four-second script instead of by feel.
- New engines onboard the voice from two documents and one verifier.
- Cost: goldens must be maintained as the taste evolves; mechanical rules
  can never capture all of "sounds like her" — the corpus carries the rest.

## Alternatives considered

- **Style embedded in capsules:** rejected — bloats always-loaded identity
  text and makes taste changes identity-version events.
- **Per-engine style prompts:** rejected — reintroduces the fragmentation
  ADR-0020 exists to prevent.
- **LLM-judged style tests only:** rejected as sole mechanism —
  non-deterministic; kept informally via the golden corpus while the
  mechanical layer stays deterministic (Constitution §3).
