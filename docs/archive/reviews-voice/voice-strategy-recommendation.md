---
id: archive.review-voice-voice-strategy-recommendation
layer: archival
type: review
status: archived
owner: shared
superseded_by: docs/adr/0009, 0010, 0011
updated: 2026-07-17
---

# Voice Strategy Recommendation

**Date:** 2026-07-13
**Author:** Claude Code (discovery-phase recommendation)
**Scope:** documentation and recommendation only — no code, config, dependency, API, or runtime change of any kind.
**Depends on:** [Stage 2 Voice Capability Audit](stage2-voice-capability-audit.md) · [Voice Provider Analysis](voice-provider-analysis.md) · [MMS-TTS Evaluation](mms-tts-evaluation.md).
**Related:** [Stage 1 Voice Baseline](stage1-voice-baseline.md) · [ADR-0009](../../adr/0009-voice-rendering-and-backend-architecture.md) (Proposed) · [ADR-0006 Local-First with Intelligence Escalation](../../adr/0006-local-model-ceiling.md) · [VISION.md](../../VISION.md).

---

## Purpose

The three sibling discovery documents established the technical picture. This document does two things:

1. Answers the question **"what problem are we actually trying to solve?"**
2. Recommends the next step from the menu of options given in the task brief.

Neither answer authorises any code change. Recommendations are stopping points for Toni's decision, not to-do items to execute.

---

## What problem are we actually trying to solve?

The task brief offered four candidate framings:

- **A** — Croatian speech generation is missing.
- **B** — Croatian speech exists, but Nero lacks a unified voice identity.
- **C** — Voice quality is insufficient globally.
- **D** — No problem exists yet.

Evaluating each against the evidence in the audit:

### A — Croatian speech generation is missing

**Rejected.** The Capability Audit found a live production Croatian path: `app/static/app.js:378` short-circuits to `null` for non-English sentences, and `speakBrowser(text)` (line 333) uses `SpeechSynthesisUtterance` with the appropriate language and voice. On Windows 11 this resolves to `Microsoft Gabrijela` or `Microsoft Matej` — real speech synthesizers, real audio. This has been shipping and working.

**Verdict:** *not* the problem.

### B — Croatian speech exists, but Nero lacks a unified voice identity

**Accepted.** English (Kokoro `af_heart`) and Croatian (browser voice) are two audibly different women. A single bilingual reply plays as two distinct speakers mid-utterance. The MMS-TTS evaluation confirmed that MMS does not close this gap — it just relocates it. The Provider Analysis confirmed that voice-cloning engines (ElevenLabs, Cartesia, Chatterbox, XTTS) do close it.

**Verdict:** *this is* the problem, insofar as any voice problem exists at all — see D below for the honest counter-question.

### C — Voice quality is insufficient globally

**Rejected.** Measured evidence:
- English via Kokoro `af_heart` — warm, natural, RTF 0.25 on RTX 4070 host, praised in the pipeline design.
- Croatian via Windows 11 `Microsoft Gabrijela` — modern neural voice, not premium but not deficient.
- No user-facing quality complaint recorded anywhere in the repo docs.

Global voice quality is not the pressure point. Identity is.

**Verdict:** *not* the problem.

### D — No problem exists yet

**Partially accepted.** Whether B is a user-visible problem is a **product judgment call, not an engineering one**. Two honest interpretations:

- **B is a real problem** if Toni actually feels the identity break when Nero speaks bilingual replies, or if he expects future users to. The break is objectively real; the *importance* of the break is a taste call.
- **B is not a problem** if Toni finds the current bilingual behavior acceptable — English is warm-and-Nero-like when needed, Croatian is functional. Many production voice assistants (including Siri, Alexa, Google Assistant) have significant per-language voice differences and their users have never treated this as a headline issue.

**Verdict:** D is the null hypothesis and cannot be rejected without evidence Toni can only supply subjectively. Until that judgment is made, treating B as urgent is unjustified.

### Recommended framing

**B, contingent on subjective validation.** The identity gap is technically real and objectively describable, but its *severity as a problem* is unmeasurable from code inspection alone. Any next step should either:

- treat B as "confirmed important" and proceed to solve it (with a cloning engine), or
- treat B as "conditionally important" and run a listening test to promote it to confirmed before doing engineering work.

**"Yes, this bothers me" from Toni after listening to Nero switch identities mid-sentence is the input every downstream decision hinges on.** Nothing in the code produces that input.

---

## Recommendation — the next step

The task brief offered five candidate next steps:

- **1** — Keep Stage 1 unchanged.
- **2** — Revise ADR-0009 trigger.
- **3** — Create a new voice-provider ADR.
- **4** — Create a voice-cloning evaluation phase.
- **5** — Or do nothing.

### Primary recommendation — Option 4 (voice-cloning evaluation phase)

Run a subjective evaluation *before* committing any architectural decision.

**Concrete shape (this is what "voice-cloning evaluation phase" means as a next step, not a plan to implement):**

1. **On the current Windows 11 RTX 4070 host, open Nero as she runs today.**
2. **Have Nero produce three bilingual replies** naturally — reply to prompts like *"Reci mi jednu rečenicu na hrvatskom i jednu na engleskom"* — and listen to each with the current pipeline (Kokoro EN + `Microsoft Gabrijela` HR).
3. **Manually generate the same Croatian sentences via ElevenLabs' free demo** with a voice cloned from a ~30 s Kokoro `af_heart` sample. (Zero code — this is done in the ElevenLabs web UI, no integration.)
4. **A/B listen.** Judge whether the cloned-voice Croatian is materially better *for Toni* than the current browser Croatian. Not "better in general" — better *for Toni's actual use of Nero*.
5. **Record the judgment as a one-paragraph decision** in `docs/reviews/`. Something like: *"Listened 2026-07-XX. Voice-identity break in current pipeline is [minor / noticeable / disqualifying]. Cloning is [not worth it / worth it as opt-in / worth it as default]."*

**Cost:** roughly 30 minutes of Toni's time. Zero engineering. Zero commits. Zero VISION.md revisions until a decision is made.

**Why this is the primary recommendation:** every engineering-first option (2, 3) presupposes an answer to a subjective question that hasn't been asked yet. Skipping ahead to architecture work risks producing another ADR that solves the wrong problem — the exact failure mode this discovery phase was created to detect.

### Contingent secondary recommendations, based on the listening outcome

**If listening judgment is "identity break is minor / acceptable":**

Adopt **Option 1 — keep Stage 1 unchanged** plus a documentation update.

- No engineering change.
- Update ADR-0009 language: retitle the exit-trigger as "a demonstrated voice problem the current bilingual router cannot solve," not "Croatian MMS-TTS scheduled." This is Option 2 in the task menu, folded in as bookkeeping.
- Update VISION.md's cloud-voice line to reflect the current state (no change to policy — just acknowledge the escalation model exists as ADR-0006 introduced it).
- Note the listening result in `docs/reviews/` so future sessions know the question was asked and answered.

**If listening judgment is "identity break is disqualifying / worth solving":**

Adopt **Option 3 — create a new voice-provider ADR**.

The new ADR would be, roughly, **ADR-0010: Voice Under Intelligence Escalation** — a product-level decision that:
- Explicitly reverses VISION.md line 338–339's cloud-voice declination.
- Applies ADR-0006's escalation pattern (explicit, opt-in, off-by-default, transparent per-request) to voice.
- Chooses a provider (ElevenLabs vs. Cartesia — a short technical comparison in the ADR itself; either works).
- Chooses a routing strategy (language-based, identity-based, config-toggle — Provider Analysis discussed all three).
- Specifies what leaves the machine (reply text only) and what retention posture the chosen provider is put under.

**Only after ADR-0010 is accepted** would any implementation begin. ADR-0009 would remain relevant but shifted in role — it becomes the abstraction Nero *might* need once ADR-0010's chosen engine plus Kokoro plus potentially a future local cloning engine (Chatterbox) accumulate to the point where an if-tree in `app/tts.py` is no longer the cleanest thing. Not before.

**If listening judgment is inconclusive:**

Repeat Option 4 with more samples, or accept that D ("no problem yet") is the operating stance. Either way, no engineering.

### Options explicitly not recommended as the immediate next step

**Option 2 — revise ADR-0009 trigger, in isolation.** The trigger revision this analysis has already flagged (from "Croatian MMS-TTS scheduled" to "voice-identity engine scheduled") is a real cleanup, but doing it *without* first knowing whether the identity gap matters would be re-arranging an ADR that may or may not ever fire. Fold this into whichever ADR-follow-up direction the listening test picks — don't do it as its own workstream.

**Option 5 — do nothing.** Distinct from Option 1 ("keep Stage 1 unchanged") in intent: Option 5 is refusal to answer the question; Option 1 is an answered "the current state is fine." They produce the same code but different governance stance. Option 5 alone leaves the discovery phase incomplete.

---

## What ADR-0009 status should be after this

**Stay Proposed. Do not change status via this document.**

- ADR-0009's architecture (rendering / casting / TTSEngine / backend seam) remains the correct shape for *some* future — if the future arrives at all.
- Its stated primary driver (Croatian via MMS-TTS scheduled) is contradicted by evidence in the audit and evaluation. That means the ADR's *trigger* is likely wrong even though its *shape* is fine.
- Any revision to ADR-0009 should be done after the listening-test decision, not before, so the revision reflects the actual voice future being planned rather than the aspirational one from the pre-discovery phase.

**Migration Stage 1 remains active.** Nothing here changes that.

---

## Summary — one-page answer to the task

**Problem:** Nero can speak Croatian, but doesn't sound like Nero when she does. That is B in the task menu — a real, technical, describable gap. Whether it is *important* is a subjective call Toni has not yet made.

**MMS-TTS:** does not solve the gap. It just moves the identity break from browser to server. Not a candidate.

**Cloud voice with cloning (ElevenLabs, Cartesia):** does solve the gap. Cost is modest engineering-wise but reverses a VISION.md decision that needs an explicit ADR before adoption. Not automatically blocked; not automatically authorised.

**Local voice cloning (Chatterbox, XTTS):** would solve the gap while preserving 100% local operation. Higher engineering cost; engine maturity is a question mark; ADR-0009's contract explicitly says these engines require a superseding ADR because they need reference-audio input.

**Recommended next step:** Option 4 — a 30-minute subjective listening test on the actual host, comparing current pipeline output against a cloned-voice reference. **Zero engineering.** The outcome of that listening test determines whether Option 1 (accept the gap, keep Stage 1) or Option 3 (draft ADR-0010 for cloud voice under ADR-0006's escalation pattern) is the *actual* next step after this.

**No implementation begins until Toni listens and decides.**
