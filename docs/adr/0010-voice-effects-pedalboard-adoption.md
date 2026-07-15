# ADR-0010 — Voice effects layer: pedalboard adoption + GPL v3 acceptance

**Status:** Accepted (2026-07-13, Toni) — operational decision made during
the banshee FX buildout on the same day; this ADR retroactively documents an
already-in-effect state.

## Context

Nero's voice work needed a presentation-layer DSP capability: pitch shifting,
parallel voice mixing (`Mix([...])` for the "ghost double" pattern), reverb,
EQ, compression, limiter. The immediate driver was Toni's Banshee FX brief; the
same capability set is what any future voice profile (`nero_late_night`,
`nero_whisper`, future haunted/alert/celebration modes) would draw on.

Three practical options for the DSP framework:

1. **`pedalboard`** (Spotify) — batteries-included Python DSP framework. Native
   C++ audio-plugin runtime with a clean Python surface. Supports parallel
   effect chains via `Mix`, transparent pedalboard-as-callable API
   (`board(samples, sr)`), full mastering toolkit. **License: GPL v3.**
2. **`scipy.signal` + `librosa`** — permissive (BSD-3 / ISC). Together they
   cover most of pedalboard's primitives, but `Mix`-style parallel chains and
   a coherent effects-graph abstraction have to be reimplemented in numpy.
3. **Pure numpy** — no new deps. Every effect implemented from scratch
   (phase-vocoder pitch shift, Schroeder reverb, biquad filters, tanh
   saturation, etc.). Complete license freedom; substantial engineering.

Verification during selection revealed that the third-party spec claiming
pedalboard was "MIT-licensed" was wrong — the `LICENSE` file on the
`spotify/pedalboard` repo is **GNU General Public License v3**, not MIT. This
mattered because every other Nero dependency to date (`fastapi`, `uvicorn`,
`httpx`, `pydantic`, `kokoro-onnx`, `onnxruntime`, `soundfile`, `pyyaml`) is
permissive (MIT / BSD / Apache 2.0). Adopting pedalboard would introduce Nero's
first copyleft dependency.

The decision was surfaced explicitly to Toni ("Option 1 — Personal use only,
accept GPL v3 / Option 2 — Reject pedalboard, use permissive alternatives /
Option 3 — Custom pure-numpy implementation"). Toni chose Option 1.

## Decision

1. **Adopt `pedalboard>=0.9.24`** as an optional voice-effects dependency.
   Declared in a **separate** `requirements-voice-effects.txt` (parallel to the
   existing optional `requirements-voice.txt`), never in the base
   `requirements.txt`.
2. **Accept GPL v3 for personal-use scope.** Toni operates Nero as a personal
   project. Under GPL v3, running the software privately triggers no
   distribution obligation; only *distributing* Nero together with pedalboard
   would trigger the copyleft. If Nero is ever shipped, published, or given to
   another person, this decision must be revisited — either re-license Nero
   under GPL v3 (or a compatible copyleft), or replace pedalboard with
   permissive alternatives (see Alternatives) before shipping.
3. **Pedalboard is imported lazily** inside effect-function bodies (see
   `voice/effects/banshee.py`). Nero's base app runs fine without pedalboard
   installed — any effect module that needs it raises a clear `RuntimeError`
   with the install command on first invocation, never at import time.
4. **The frozen `nero_prime_v1` profile uses only a strict subset** of
   pedalboard: `PitchShift(semitones=-1.9)` + `Limiter`. Every other stage in
   the banshee chain (ghost / shimmer / chorus / highpass / reverb / saturation
   / EQ / compressor) is disabled for `nero_prime_v1`. This is the *escape
   hatch* — if pedalboard ever needs to be dropped, `nero_prime_v1` can be
   reimplemented with `scipy.signal` (biquad limiter) + `librosa.effects.pitch_shift`
   in under 100 lines of pure-permissive Python. See ADR-0009 and
   `voice/profiles/presets.py::NERO_PRIME_V1`.

## Consequences

- ✅ Full presentation-layer DSP capability (Mix, PitchShift, Reverb, Chorus,
  HighpassFilter, LowShelfFilter, HighShelfFilter, PeakFilter, Distortion,
  Compressor, Limiter) with a verified installed API. All parameter names
  cross-checked by Python introspection against pedalboard 0.9.24, not by
  README scraping.
- ✅ Base app is unaffected. Nero installs and runs with `requirements.txt`
  alone; the voice-effects stack is opt-in via
  `pip install -r requirements-voice-effects.txt`.
- ✅ `nero_prime_v1` (the frozen production voice) uses only the trivially
  replaceable subset. If distribution ever forces pedalboard out, the canonical
  voice is safe.
- ⚠️ **First copyleft dependency in the Nero graph.** Nero's future distribution
  story now has an explicit decision to make. Until Nero is distributed, no
  obligation exists — but the decision cannot be quietly deferred forever.
- ⚠️ **Other profiles that lean on the full FX chain** (`nero_late_night`, and
  future haunted / alert modes) are *not* trivially replaceable — reverb,
  chorus, compressor, and EQ shelves would need real DSP work if pedalboard
  is dropped. Those profiles are tied to pedalboard's lifetime in Nero.
- ⚠️ Nero repo currently has no `LICENSE` file, which under default copyright
  is "all rights reserved by the author." Introducing GPL v3 while the project
  is unlicensed is legally ambiguous. Not urgent for personal use; must be
  resolved before any distribution.

## Alternatives considered

- **Option 2 — `scipy.signal` + `librosa` (BSD-3 / ISC).** Rejected in favor of
  pedalboard for the banshee buildout because (a) `Mix([...])` for parallel
  effect chains is a single class in pedalboard vs. a manual numpy assembly
  elsewhere, (b) pedalboard's Reverb + Compressor + shelf-EQ set exists as
  first-class classes rather than requiring impulse-response management or
  custom biquad chains, (c) the full chain reads clearly (`Pedalboard([Mix,
  Chorus, HighpassFilter, Reverb, PitchShift, Limiter])`) — reimplementation
  in scipy loses that legibility. Remains the escape route for a future
  publish-Nero scenario.
- **Option 3 — Pure numpy implementation.** Rejected as premature: substantial
  engineering (~200+ lines of DSP) for a use case (banshee FX) whose eventual
  survival was uncertain when adopted. `nero_prime_v1` later shed the entire
  supernatural layer anyway, but Toni still uses banshee capabilities in other
  profiles.
- **No FX at all.** Would have worked for `nero_prime_v1` (which uses only
  PitchShift + Limiter — both trivially numpy-implementable). Rejected because
  the FX capability is a Voice Director design goal, not a nero_prime_v1
  requirement. The abstraction is intentionally broader than the flagship
  voice.

## Boundary rules

- **No other GPL / copyleft dependency** may be added to Nero without a
  superseding ADR. Pedalboard is the first and, under this ADR, the only one.
- **No pedalboard usage inside `app/`** — voice effects live under `voice/`.
  This preserves the option of dropping the `voice/` package and reverting to
  the legacy `app/tts.py` path with no GPL contamination in the core app.
- **`requirements.txt` never lists pedalboard.** Adding it there would make the
  base install carry the copyleft, defeating the "optional" property.
- **Effect-module lazy imports are mandatory.** Any effect module that imports
  `pedalboard` at module top-level breaks the "base app runs without pedalboard"
  invariant.

## Cross-references

- **ADR-0002** — Speech stays off the GPU. Pedalboard is pure CPU DSP;
  compatible.
- **ADR-0006** — Local-First with Intelligence Escalation. Cloud escalation is
  reasoning-only; voice was explicitly excluded from the cloud escalation grant
  in this session's Kokoro-only reset. Pedalboard's local CPU nature aligns
  with the voice-locality stance.
- **ADR-0009** — Voice rendering / casting / backend architecture. Pedalboard
  lives in the effects sub-layer of the voice package this ADR describes.
- `voice/effects/banshee.py` — the primary consumer.
- `voice/profiles/presets.py::NERO_PRIME_V1` — the frozen profile that uses
  only the PitchShift + Limiter subset.
- `voice/effects/README.md` — module-level docs including tuning guide and
  license note.
- `requirements-voice-effects.txt` — the optional install file with license
  disclosure inline.
