---
id: archive.review-voice-mms-tts-evaluation
layer: archival
type: review
status: archived
owner: shared
superseded_by: docs/adr/0009, 0010, 0011
updated: 2026-07-17
---

> **Archived 2026-07-17:** conclusions extracted into ADR-0009/0010/0011.
> Retained as dated evaluation history.


# Meta MMS-TTS Evaluation for Nero

**Date:** 2026-07-13
**Author:** Claude Code (discovery-phase evaluation)
**Scope:** documentation only — no code, config, dependency, API, or runtime change of any kind.
**Related:** [Stage 2 Voice Capability Audit](stage2-voice-capability-audit.md) · [Voice Provider Analysis](voice-provider-analysis.md) · [Voice Strategy Recommendation](voice-strategy-recommendation.md) · [ADR-0009](../../adr/0009-voice-rendering-and-backend-architecture.md).

---

## Purpose

Meta MMS-TTS is the specific engine ADR-0009 named as the "first concrete second engine on the map" and as the load-bearing driver for the entire rendering / casting / backend architecture. The reality check found that Croatian is already served (via the browser fallback) and that the real gap is **voice identity**, not Croatian audio generation.

This document evaluates MMS-TTS strictly on the criterion the audit surfaced: *does it solve the identity gap, or something else, or nothing?*

**Verdict, up front:** MMS-TTS solves *local Croatian synthesis* — a problem Nero does not have. It does not solve voice-identity preservation. It should not be adopted as the driver of a voice-architecture migration.

The rest of this document defends that verdict with specifics.

---

## What Meta MMS-TTS actually is

- Full name: **Massively Multilingual Speech** — a research project released by Meta AI in May 2023, encompassing ASR, LID, and TTS.
- Language coverage: **1,100+ languages**, including Croatian (`hrv` / `hr`).
- License: open weights, permissive research use; MMS-TTS models are released under CC-BY-NC 4.0 (**non-commercial** — worth flagging: any commercial deployment is a license question).
- Architecture: **VITS-based** (Variational Inference Text-to-Speech). VITS is an end-to-end TTS model that combines a text encoder, a flow-based decoder, and a HiFi-GAN vocoder into one model.
- Model size: ~140 MB per language (checkpoints are language-specific — Croatian is its own file).
- Runtime: originally distributed for PyTorch via HuggingFace `transformers` (`facebook/mms-tts-hrv`). ONNX conversion is possible but not officially supported.
- CPU-runnable: yes, at reasonable speed on modern desktop CPUs.

---

## Does MMS-TTS support Croatian?

**Yes — `facebook/mms-tts-hrv` exists as a downloadable checkpoint.**

- Model ID: `facebook/mms-tts-hrv` on HuggingFace.
- Language: Standard Croatian (`hrv` ISO 639-3, mapped to `hr` ISO 639-1).
- Approximately 140 MB.
- Community-tested and reproducible.

Croatian coverage is technically confirmed. This is the *only* MMS-TTS claim that turns out to be straightforwardly true against the reality check.

---

## What quality should realistically be expected?

**Functional but distinctly non-premium.** VITS-based TTS in the MMS release quality tier is:

- Intelligible and grammatically correct for its target language.
- Somewhat robotic compared to modern commercial neural TTS (ElevenLabs Turbo, Cartesia Sonic, Azure Neural).
- **Comparable to or slightly better than mid-tier OS-bundled voices** — the Windows 11 `Microsoft Gabrijela` Croatian voice is arguably in the same quality neighborhood.
- Not as expressive or natural as ElevenLabs Multilingual v2 or Cartesia Sonic.
- Not as warm or breathy as Kokoro's `af_heart` (a very different voice character).

**A realistic listening comparison for Croatian on the current host:**

| Source | Quality tier | Notes |
|---|---|---|
| ElevenLabs Multilingual v2 | Premium | Studio-quality, expressive, prosody strong. |
| Cartesia Sonic | Premium | Fastest cloud, comparable quality to ElevenLabs. |
| Azure `hr-HR-GabrijelaNeural` | High | Solid neural voice, no cloning support here. |
| **MMS-TTS `mms-tts-hrv`** | **Mid** | Functional, occasionally awkward prosody, single voice per language. |
| Windows 11 `Microsoft Gabrijela` | Mid | Already installed, already used by Nero today. |
| Older concatenative browser TTS | Low | Historical fallback; not what modern browsers use. |

**MMS-TTS is not obviously better than the browser voice Nero already uses.** Any adoption pitch that leans on "MMS is higher quality than the browser" needs to be verified by an actual A/B listening test, not assumed.

---

## Does MMS-TTS provide voice identity preservation?

**No. This is the disqualifying property.**

MMS-TTS ships **one voice per language.** The Croatian checkpoint (`facebook/mms-tts-hrv`) contains a single-speaker VITS model — you get "the Croatian MMS speaker," and there is no dial to change identity.

- **No voice cloning.** MMS-TTS was trained on multi-speaker religious recordings (that's the training corpus). The released models are single-speaker distillations. There is no reference-audio input, no speaker embedding, no cloning capability.
- **No cross-language identity mapping.** The English MMS model (`facebook/mms-tts-eng`) and the Croatian MMS model are two separate networks with two separate speakers. They do not share identity.
- **No prosody transfer.** You cannot make MMS-TTS sound warm-and-breathy like `af_heart`; you get whatever prosody the model learned from its training data.

**Consequence:** if Nero switched from the browser Croatian voice to MMS-TTS Croatian:

- Old identity break: `af_heart` (Kokoro EN) → `Microsoft Gabrijela` (browser HR).
- New identity break: `af_heart` (Kokoro EN) → MMS speaker HRV (MMS HR).

**The break moves; it does not close.** The listener still hears two different people speaking the two languages. The engineering effort to migrate to MMS-TTS buys a change of voice — not a preservation of voice.

---

## Could MMS-TTS make Nero sound like Nero?

**No.** The above section is the full answer, but stated bluntly for the summary:

- MMS-TTS is not a voice-cloning system.
- MMS-TTS cannot be given a reference sample of Kokoro's `af_heart` and asked to render Croatian in that voice.
- MMS-TTS's single-speaker-per-language architecture makes cross-language identity preservation architecturally impossible for it.

Any framing of MMS-TTS as "Nero's Croatian voice" is a misunderstanding of what the model does. It is "Meta's Croatian voice, running locally."

---

## Does MMS-TTS solve the actual problem?

**No.** The identity gap the Capability Audit surfaced is the *only* voice problem Nero currently has, and MMS-TTS does not solve it.

**What MMS-TTS *does* solve:**
- Running Croatian speech generation **on the server**, under Nero's control, without depending on the browser's built-in synthesizer.
- Making Croatian generation *deterministic across hosts* (the browser voice is host-dependent; MMS output is the same file everywhere).
- Preserving strict local-only operation (respects VISION.md's cloud-voice declination as-written).
- Providing a Croatian voice on hosts where the browser has no Croatian TTS installed (rare on modern OSes; possible on stripped-down Linux).

**Are those problems Nero actually has?**

| Problem | Does Nero have it? |
|---|---|
| Server-side control of Croatian generation | No — browser generation works fine. |
| Cross-host determinism of Croatian audio | No — Toni's Nero runs on his one host. |
| Preserving strict local-only stance | Yes, but only *because* it hasn't been reconsidered yet. The task brief reopened this question. |
| Croatian on a browser without HR TTS | No — Windows 11 ships HR voices. |

The only column where MMS-TTS has a point is "preserving strict local-only stance" — and even there, only *if* the local-only stance survives the current reevaluation.

---

## Comparison against the alternatives

Against the identity-preservation criterion:

| Option | Solves identity gap? | Local? | Effort to adopt | Notes |
|---|---|---|---|---|
| **Do nothing (current pipeline)** | ❌ | ✅ (browser is local to the device) | Zero | The identity break already exists. |
| **Kokoro alone** | N/A (single language) | ✅ | N/A | Kokoro has no Croatian voice; not an option. |
| **MMS-TTS Croatian** | ❌ | ✅ | Moderate — new model, likely `transformers` dep or ONNX conversion, integration into `app/tts.py` | Solves nothing user-facing. |
| **ElevenLabs Multilingual v2 with cloned `af_heart`** | ✅ | ❌ (cloud) | Modest — API key, `httpx` calls, routing decision | Solves the identity gap. Requires cloud escalation policy. |
| **Cartesia Sonic with cloned `af_heart`** | ✅ | ❌ (cloud) | Modest | Faster, cheaper than ElevenLabs. Solves the identity gap. |
| **Chatterbox (mentioned in `app/tts.py:11` as future)** | ✅ if cloning works | ✅ | High — engine not yet integrated | Voice-cloning, local. Actual future candidate that would fit ADR-0009's shape, but has its own maturity questions. |
| **XTTS v2 / Coqui** | ✅ | ✅ | High — new engine + dependencies | Voice-cloning, local; Coqui project has had funding/maintenance issues; license terms complicated. |

**Key observation:** every option that solves the identity gap is either a **cloud cloning provider** or a **local cloning engine**. MMS-TTS is the only "second local engine" in the comparison, and it is the only one that *doesn't* address the gap.

---

## Engineering implications *if* MMS-TTS were adopted

Included for completeness, not as a recommendation.

- **New model files:** `mms-tts-hrv` (~140 MB) downloaded once and cached to `models/`.
- **New dependencies:** either `transformers` + `torch` (large — several hundred MB, sizable install) or an ONNX conversion pipeline (moderate, but ongoing maintenance of the converted checkpoint).
- **Server-side language routing:** the frontend's `detectLang` would need to be reproduced or forwarded server-side, since Kokoro currently receives all requests via `/api/speak` with no language field. The `POST /api/speak` contract would either grow a `language` parameter (compatibility-break unless nullable) or the server would have to detect from the text.
- **Voice identity break persists:** English via Kokoro `af_heart`, Croatian via MMS speaker. See above — the break moves rather than closes.
- **`onnxruntime` reuse:** if MMS-TTS is ONNX-converted, it can share the existing `onnxruntime` (1.27.0 CPU wheel) dependency. If it uses `transformers`, that's a large new dependency.
- **Cold start:** loading a ~140 MB VITS model is comparable to Kokoro's ~340 MB — likely 1–2 seconds first-load, sub-second warm.

This is not a hard integration. But it is real work, for a benefit that solves the wrong problem.

---

## Effect on ADR-0009

ADR-0009's Context section, revised 2026-07-13, states the primary driver as:

> "Croatian via **Meta MMS-TTS** is committed in `docs/PROJECT_BRIEF.md` (§4 Voice, §5 Roadmap) and Phase 4 real-time voice work in `docs/ROADMAP.md`. That is the *first* concrete second engine on the map, and it will collide with the current single-file, single-cache, engine-baked-into-config design."

This evaluation contradicts that framing in two ways:

1. **MMS-TTS is not the "first concrete second engine on the map"** because it does not answer any concrete user-facing requirement. The requirement it appears to answer (Croatian) is already met.
2. **When a genuine second engine *does* appear**, it will most likely be a voice-cloning engine — either cloud (ElevenLabs, Cartesia) or local (Chatterbox, XTTS). Voice-cloning engines take a **reference-audio input**, which ADR-0009 itself explicitly places out-of-scope (§ TTSEngine › Reference-audio / cloning engines are out of scope):

   > "Engines that require reference audio as an input (Chatterbox-class cloning) do not fit the `(text, engine_params)` shape and are **not** governed by this ADR. When such an engine is added, a **superseding ADR** must define the payload / reference-audio model."

So the engine ADR-0009 was designed to receive (MMS-TTS) is the one Nero doesn't need; the engine Nero *does* need would supersede ADR-0009 rather than integrate through it.

**This is not a fatal criticism of ADR-0009 as a shape — the rendering/casting/backend seam is still the right shape for a multi-engine future.** But the stated *trigger* (MMS-TTS scheduled) and the load-bearing *justification* (Croatian requires a second engine) are both weaker than the audit implied when ADR-0009 was revised.

The formal recommendation to revise or defer ADR-0009 lives in the sibling document [voice-strategy-recommendation.md](voice-strategy-recommendation.md).

---

## Summary — MMS-TTS scorecard

| Criterion | Result |
|---|---|
| Does it exist? | ✅ Yes, `facebook/mms-tts-hrv` on HuggingFace, ~140 MB. |
| Does it support Croatian? | ✅ Yes. |
| Is the quality significantly better than the browser voice Nero uses? | ⚠️ Unclear. Likely comparable, not obviously better. |
| Does it preserve voice identity across English + Croatian? | ❌ No. Single speaker per language, no cloning. |
| Does it make Nero sound like Nero? | ❌ No. |
| Does it solve the identity gap the audit surfaced? | ❌ No. |
| Is it a good fit for ADR-0009's `(text, engine_params)` contract? | ⚠️ Yes, but that fit is not why we'd want a second engine. |
| Is it commercially licensed for Nero's use case? | ⚠️ CC-BY-NC 4.0 — non-commercial only. Nero is currently a personal project; commercial deployment would need review. |
| Is it worth adopting? | **No.** |

**Bottom line:** MMS-TTS is a real, working, local Croatian TTS engine that fully deserves its research prominence. It is also, specifically for Nero, an answer to a question Nero doesn't need to ask. Adopting it would move an audible break in Nero's voice from browser-space to server-space without closing the break, at real engineering cost, under a non-commercial license.

**Recommendation on MMS-TTS specifically:** do not schedule MMS-TTS as the driver for any voice-architecture migration. If a local Croatian voice ever becomes genuinely useful (e.g. as an offline fallback in a Chatterbox-style architecture), reconsider then — but on its merits at that point, not as the load-bearing case for architecture change today.
