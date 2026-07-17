---
id: archive.review-voice-voice-provider-analysis
layer: archival
type: review
status: archived
owner: shared
superseded_by: docs/adr/0009, 0010, 0011
updated: 2026-07-17
---

> **Archived 2026-07-17:** conclusions extracted into ADR-0009/0010/0011.
> Retained as dated evaluation history.


# Voice Provider Analysis — Cloud and Cloning Options

**Date:** 2026-07-13
**Author:** Claude Code (discovery-phase analysis)
**Scope:** documentation only — no code, config, dependency, API, or runtime change of any kind.
**Related:** [Stage 2 Voice Capability Audit](stage2-voice-capability-audit.md) · [MMS-TTS Evaluation](mms-tts-evaluation.md) · [Voice Strategy Recommendation](voice-strategy-recommendation.md) · [ADR-0006 Local-First with Intelligence Escalation](../../adr/0006-local-model-ceiling.md) · [VISION.md](../../VISION.md).

---

## Purpose

The Stage 2 Capability Audit established that the real voice gap is **identity persistence across languages**, not "can Nero speak Croatian." This document analyses whether cloud voice providers — with voice-cloning as a differentiator — could close that gap, at what cost, and under what product framing.

The task brief explicitly reframed the ideological constraint:

> Nero running locally does NOT mean every capability must be offline. Nero is allowed to browse the web, download resources, call external AI services, use cloud APIs when appropriate. Treat voice as a product capability decision, not an ideological restriction.

But this reframing overrides a specific existing product decision recorded in **VISION.md line 338–339**:

> "the same reasoning is why cloud voice was declined: voice stays **100% local** (Piper/Kokoro, not ElevenLabs/OpenAI)."

That declination was written by Toni as part of the vision document. Any adoption of a cloud voice provider is a **product-level reversal of a previously stated decision**, not merely a technical choice. This document analyses the technical picture and, where relevant, flags the product-level implication so nothing is quietly resolved by engineering fiat.

**A related governance point:** [ADR-0006 "Local-First with Intelligence Escalation"](../../adr/0006-local-model-ceiling.md) already established the *pattern* for a cloud escalation: explicit, opt-in, off-by-default, transparent, per-request. That ADR was written for reasoning models (routing hard tasks to Claude/GPT). Whether the same pattern extends to voice output — moving one utterance's text to a cloud TTS API — is a separate decision. ADR-0006 does not automatically authorize cloud voice; it demonstrates a template.

---

## The problem cloud voice is being evaluated against

From the Capability Audit:

- English: Kokoro `af_heart` — this *is* Nero's voice.
- Croatian: OS-shipped voice (Windows 11 default: `Microsoft Gabrijela`) — this is *not* Nero's voice.
- A single bilingual reply switches identities mid-utterance, audibly.

The candidate solution is a voice with two properties:

1. **Multilingual** — must speak both English and Croatian (and eventually any other language the LLM might respond in).
2. **Identity-preserving** — the *same* voice model must speak both, with no perceptible identity switch.

**Voice cloning** is the shortest path to (2): capture Nero's target voice once, then any utterance in any supported language is rendered as that voice.

---

## Providers surveyed

Only providers that plausibly meet both criteria. Excluded: single-language providers (e.g. Amazon Polly's non-neural voices), providers without cloning, and providers whose Croatian coverage is unlisted or clearly absent.

### ElevenLabs (Multilingual v2 / Turbo v2.5)

- **Multilingual:** yes — 29+ languages including Croatian.
- **Voice cloning:** yes, instant (from ~30 s of reference audio) and professional (from ~30 min). This is their flagship differentiator.
- **Identity across languages:** strong — a cloned voice speaks all supported languages recognizably as the same person.
- **Streaming:** yes, low-latency streaming API (~300 ms TTFB with Turbo v2.5).
- **Cost:** free tier 10k characters/month; paid $5–$99/mo tiers for higher usage. Pay-as-you-go via API also available. Rough magnitude: ~$0.30 per 1000 characters on typical plans.
- **Terms:** Standard commercial API. Reference audio for voice clones remains under your account. Their terms explicitly prohibit voice-cloning without consent — using a synthesized `af_heart` sample as the cloning reference is a *gray area* worth checking (technically you're cloning a Kokoro voice, which is itself an open-weights model).

### Cartesia (Sonic)

- **Multilingual:** yes — English + 15 additional languages including Croatian.
- **Voice cloning:** yes, few-second reference audio.
- **Identity across languages:** strong, comparable to ElevenLabs Turbo.
- **Streaming:** yes, sub-100 ms TTFB claimed — currently the fastest of the surveyed cloud providers.
- **Cost:** roughly similar order of magnitude to ElevenLabs; volume-based tiers.
- **Terms:** newer entrant, cleaner API.

### Azure Speech (Neural, custom voice)

- **Multilingual:** yes, ~140 languages including Croatian (`hr-HR-GabrijelaNeural`, `hr-HR-SreckoNeural`).
- **Voice cloning:** yes via Azure Custom Neural Voice, but requires application approval (Microsoft gates access due to misuse concerns).
- **Identity across languages:** Custom Neural Voice supports cross-lingual synthesis for the primary voice.
- **Streaming:** yes, low-latency streaming.
- **Cost:** per-character pricing, enterprise-oriented. Custom voice has additional training and hosting fees.
- **Terms:** Microsoft consent/verification workflow for custom voice.

### OpenAI TTS (`tts-1`, `tts-1-hd`)

- **Multilingual:** partially — 6 preset voices trained mostly on English but tested to work on 50+ languages. Croatian is not officially listed but is reported to work with variable quality.
- **Voice cloning:** **no.** OpenAI does not offer voice cloning through the public API today.
- **Identity across languages:** the 6 preset voices maintain identity, but you must pick from those six — you cannot use Nero's `af_heart` timbre.
- **Streaming:** yes.
- **Cost:** $15 per million characters (`tts-1`), $30 per million (`tts-1-hd`) — competitively low.
- **Verdict:** disqualified for this specific goal — no cloning means you're not preserving *Nero's* voice, you're picking from OpenAI's six.

### Google Cloud TTS (Neural2 / Journey)

- **Multilingual:** yes — ~50 languages including Croatian (`hr-HR-Standard-A`).
- **Voice cloning:** Google offers custom voice training via Chirp 3, but access is gated/limited-preview.
- **Identity across languages:** limited — most voices are single-language.
- **Streaming:** yes.
- **Cost:** per-character pricing, comparable to Azure.
- **Verdict:** capable for standard TTS, but weaker for the specific identity-cloning goal than ElevenLabs/Cartesia.

### Summary — best-fit providers for the identity goal

| Provider | Croatian | Cloning | Cross-lang identity | TTFB | Verdict |
|---|---|---|---|---|---|
| **ElevenLabs** | ✅ | ✅ instant | ✅ strong | ~300 ms | **primary candidate** |
| **Cartesia** | ✅ | ✅ instant | ✅ strong | ~100 ms | **primary candidate** |
| Azure Custom Neural | ✅ | ⚠️ gated approval | ✅ good | ~200 ms | fallback candidate |
| Google Chirp 3 | ✅ | ⚠️ limited preview | ⚠️ evolving | ~200 ms | fallback candidate |
| OpenAI `tts-1` | ⚠️ unofficial | ❌ | N/A | ~200 ms | disqualified for cloning goal |

---

## Would cloud voice solve the actual problem?

**Yes — decisively — with a cloning-capable provider.**

The gap identified in the audit is that Nero speaks Croatian in someone else's voice. A cloned voice fed a Croatian utterance produces Croatian audio in Nero's voice. That is exactly the missing capability.

Provider caveats:
- ElevenLabs Multilingual v2 and Cartesia Sonic both handle Croatian at high quality with cloning support today. Either would close the gap.
- OpenAI TTS would not solve the problem — you'd be picking from OpenAI's preset voices, not preserving `af_heart`'s identity.
- Azure/Google would solve it if you clear their custom-voice approval processes.

---

## Engineering implications

**Change surface is smaller than it might appear.** Cloud voice does not require ADR-0009's rendering/casting layer — it can be a targeted addition to the existing single-engine path.

**Minimal-surface integration option (illustrative, not a plan):**
- Add a new backend function `_synth_elevenlabs(cfg, text)` alongside `_synth_kokoro` in `app/tts.py` (or a sibling module).
- Extend `Config` with three fields: `tts_cloud_enabled`, `tts_cloud_api_key`, `tts_cloud_voice_id`.
- Route in `synthesize()`: if cloud is enabled and this utterance benefits from the cloned voice, call cloud; else Kokoro.
- No changes to `POST /api/speak` HTTP contract, no changes to `/api/metrics.voice` shape, no changes to the frontend.

**Routing logic — three plausible strategies:**
1. **Language-based (simplest):** cloud for non-English, Kokoro for English. Preserves Kokoro's zero-cost hot path for the dominant language. Requires either the frontend to send `language` in the request, or a server-side heuristic.
2. **Identity-based:** cloud for everything (English *and* Croatian), so a single cloned voice covers both. Cleanest identity guarantee, but sacrifices Kokoro's local/fast/free English path.
3. **Config-toggle:** an explicit `use_cloud_voice` flag on `Config`. Users choose. Off by default.

Strategy (1) is the pragmatic minimum for the identity goal. Strategy (2) has cleaner semantics but higher cost and network dependency for every utterance.

**Streaming vs. batch:** all serious cloud providers offer streaming. Whether Nero adopts streaming depends on user experience goals — currently `POST /api/speak` is a batch call returning a full WAV. Preserving that contract keeps the change small; adopting streaming is a Phase 4-adjacent decision.

**Error handling:** cloud calls introduce a new failure mode (network / API error). The existing `return None → 204` path already handles unavailable synthesis gracefully; a cloud failure simply falls through to that path, which then falls back to the browser voice. The graceful-degradation ladder becomes:

1. Preferred cloud engine → 2. Local Kokoro (English only) → 3. Browser SpeechSynthesis → 4. No audio (chat still works).

**API key management:** the least-glamorous but genuinely important consideration. Keys need to live somewhere they don't accidentally get committed, get shipped in Docker images, or get logged. Options: an environment variable read at startup, a value in `config.yaml` (gitignored today), or a keyring integration. All plausible; none blocking.

**Additional dependencies:** `httpx` is already installed. No new HTTP client is needed. Provider SDKs (`elevenlabs`, `cartesia-python`, `openai`, `azure-cognitiveservices-speech`) are optional — the API is REST-callable directly if minimising dependency growth matters. This matches the existing lazy-import pattern in `app/tts.py` for Kokoro.

**Compatibility with ADR-0009:** none of this requires ADR-0009 to fire. Cloud voice can ship as a small extension to `app/tts.py` under Migration Stage 1 (i.e. Alternative 1 in ADR-0009 — "keep expanding `app/tts.py`") until enough engines accumulate to warrant the rendering layer. This matters: **it means adopting cloud voice is architecturally cheap and does not force the ADR-0009 migration.**

---

## Privacy / security implications

This is the section that most directly hits VISION.md's declination reasoning.

**What leaves the machine:** the text of every utterance Nero speaks aloud. On a typical bilingual chat, that is the LLM's reply text sent to the cloud provider's TTS endpoint over HTTPS.

**What the cloud provider stores:**
- ElevenLabs: request/response are logged; text history is available in the dashboard. Retention is per their privacy policy — historically 30 days for standard tier, longer for enterprise contracts.
- Cartesia: similar model, cleaner privacy stance in current terms.
- Azure/Google: enterprise-grade privacy controls, per-region data residency options.
- OpenAI: request data is available to abuse-monitoring but not used for training on API endpoints (per current terms).

**What the reference audio for cloning contains:** if you clone `af_heart` from a Kokoro-generated sample, the reference is a synthesized voice — no biometric data of a real human. This side-steps the strongest cloning-consent concerns.

**What is NOT sent:** memories, world model state, conversation history, embeddings — none of these leave. Only the *reply text* about to be spoken.

**Consequences for Nero's privacy pillar (Constitution §2, "nothing leaves the machine"):**
- Under a strict reading, sending reply text to a cloud TTS violates the pillar.
- Under ADR-0006's escalation reading, cloud voice would need to be *explicit, opt-in, off by default, transparent per request*. That is precisely the shape ADR-0006 endorsed for cloud reasoning.
- Whether the same reasoning applies to voice specifically is a **product decision**, not an engineering one. See "Governance / product-level open questions" below.

**Sensitive-content edge case:** if Nero ever handles medical, financial, or personal data in her replies, and those replies get spoken, the reply text goes to the provider. A per-request "speak this locally only" override may be needed to keep the escalation "opt-in per-request" as ADR-0006 requires.

---

## Latency implications

**Baseline (Kokoro warm):** 0.983 s for a 3.9 s clip; RTF 0.25.

**Cloud TTS TTFB (time-to-first-byte-of-audio):**
- Cartesia Sonic: ~100 ms — genuinely faster than local Kokoro for first-audio.
- ElevenLabs Turbo v2.5: ~300 ms.
- Azure/Google: ~200 ms.
- OpenAI: ~200 ms.

**For batch (non-streaming) synthesis** — the current `POST /api/speak` shape — total time = TTFB + generation + network return. For a 3-second Croatian sentence, a cloud provider typically returns full audio in ~500–800 ms. **Cloud voice can actually be faster than local Kokoro for short utterances**, because network overhead beats CPU synthesis time.

**Network dependency:** every synthesized utterance requires a working internet connection. Nero on a plane / in a train tunnel / offline for any reason loses cloud voice. Graceful degradation to Kokoro (English) or browser voice (Croatian) is possible but produces the identity break the whole feature was trying to solve.

**Regional latency:** cloud provider data-center distance matters. If Toni is on Croatian residential internet and the nearest ElevenLabs region is in Frankfurt or London, latency is fine (~30–50 ms round trip). If the app were used from Croatia with US-only cloud infrastructure, TTFB grows.

---

## Would cloud voice conflict with Nero's "local AI OS" concept?

**Not necessarily. Depends on how it's framed.**

Nero is described in VISION.md as a *local companion* whose privacy pillar promises "nothing leaves the machine." The strict reading rules out cloud voice. But:

- **ADR-0006 already re-scoped "local-first" from "local-only" to "local by default, cloud as opt-in escalation."** That was a product-level reversal of the earlier no-cloud stance for reasoning models.
- **The user's Task-brief framing** ("Nero is allowed to browse the web, download resources, call external AI services, use cloud APIs when appropriate") extends the same reasoning to arbitrary capabilities.
- **What is preserved regardless:** local-first as the *default*. Kokoro remains the English hot path; cloud voice is only invoked when the identity gap is actually being solved (Croatian, in the language-based-routing option).
- **What is genuinely lost:** the ability to promise "nothing leaves the machine" without the "unless you opt in to cloud voice" qualifier. That is a product story to update, not an engineering blocker.

**The conflict is not with "local AI OS" as an idea. The conflict is with the specific line in VISION.md that declined cloud voice.** That line needs to be reconciled explicitly — either by adopting a Voice ADR that supersedes it (parallel to how ADR-0006 superseded the earlier no-cloud reasoning stance) or by choosing to keep it and accepting the identity gap.

---

## Governance / product-level open questions

Not decisions this analysis makes. Flagged for Toni's decision before any implementation:

1. **Is cloud voice actually allowed?** VISION.md line 338–339 says no. The task brief seems to say yes. These need to be explicitly reconciled — probably by an ADR ("Voice under the Intelligence Escalation model") that documents the reversal, its opt-in shape, and its transparency requirements.
2. **What escalation shape?** Does cloud voice follow ADR-0006's pattern (explicit, opt-in, off-by-default, per-request, transparent)? Or is it a persistent "cloud voice on" toggle? The per-request pattern is more privacy-preserving; the persistent toggle is more ergonomic. This is a UX/product call.
3. **Which utterances go to cloud?** The three routing strategies above (language-based / identity-based / config-toggle) are all viable. Toni picks based on the balance of identity coherence, cost, and offline reliability he wants.
4. **Which provider?** ElevenLabs and Cartesia are the two primary candidates. A short listening test settles it — Cartesia is faster and cheaper; ElevenLabs has larger voice-cloning ecosystem and more mature multilingual quality.
5. **What is stored?** Setting per-provider data-retention preferences (where offered) is trivial; deciding what your privacy commitments to users should say is not. Nero has one user, but the "one user" is a governance customer of Toni's own past commitments.
6. **What happens to Kokoro if cloud voice is adopted?** Options: (a) Kokoro stays for English (dual-engine hybrid), (b) Cloud for everything (single-identity, higher cost), (c) Cloud for everything, Kokoro as offline fallback. Choice affects the routing strategy above.

---

## Compatibility with existing ADRs

- **ADR-0002 (Model router / VRAM budget):** unaffected. Kokoro stays on CPU regardless. Cloud voice consumes zero local resources.
- **ADR-0005 (Security gate):** voice is a `safe` capability (read-only, no filesystem/network side effects — the read-only side of that changes if network egress is now happening; not a security-gate concern, more a privacy concern).
- **ADR-0006 (Local-First with Intelligence Escalation):** cloud voice fits this pattern if implemented as opt-in, off-by-default, transparent per-request. Fits *the pattern*; does not automatically mean ADR-0006 authorizes it — the pattern is a template, not a blanket authorization.
- **ADR-0009 (Voice rendering/casting/backend):** **not required for cloud voice adoption.** A cloud backend can be added under Migration Stage 1 (Alternative 1 in ADR-0009) as a small extension to `app/tts.py`. ADR-0009's abstractions become interesting *only* when enough engines accumulate to warrant them.

---

## Summary

- **Cloud voice with cloning (ElevenLabs or Cartesia) does solve the identity-persistence problem** the Capability Audit surfaced. Neither Kokoro nor MMS-TTS can.
- **Engineering cost is modest** — a small extension to `app/tts.py`, a couple of new `Config` fields, an API key, one new routing decision. Does not require ADR-0009's abstractions.
- **Latency is fine** — TTFB is comparable to or faster than local Kokoro on short utterances.
- **Privacy trade-off is real** — reply text leaves the machine; this is a product-level reversal of a specific VISION.md decision. Should be documented as a new ADR, not slid in.
- **The technical picture is unblocking. The governance picture is the actual gating item.** Until Toni decides whether cloud voice is allowed and under what escalation shape, no implementation should begin.
- **This is a data document, not a recommendation.** The recommendation lives in `voice-strategy-recommendation.md`.
