# Stage 2 Voice Capability Audit

**Date:** 2026-07-13
**Author:** Claude Code (discovery-phase audit)
**Scope:** documentation only — no code, config, dependency, API, or runtime change of any kind.
**Related:** [Stage 1 Voice Baseline](stage1-voice-baseline.md) · [ADR-0009](../adr/0009-voice-rendering-and-backend-architecture.md) (Proposed) · [ADR-0009 Acceptance Review](ADR-0009-acceptance-review.md).

**Filename note:** the "stage2" in this file's name refers to the *discovery phase* of the ADR-0009 evaluation, **not** ADR-0009 Migration Stage 2 (which remains gated and unauthorized). Migration Stage 1 stays the active operating state.

---

## Purpose

The Stage 1 baseline documented what the current voice system *is*. This audit answers the narrower question raised by the reality check: **what does the current voice pipeline actually do across the two languages Nero speaks, and where does voice identity diverge?**

This is not a survey of what could be built. It is a factual reconstruction of the pipeline that ships today, cross-referenced to specific files and line numbers so every claim is checkable.

---

## The voice pipeline, top-to-bottom

The pipeline splits into two paths at the frontend depending on detected language of each *sentence*. Both paths are active in production today.

```
User types (or dictates) a message
        │
        ▼
POST /api/chat   (streaming reply from the LLM)
        │
        │  reply text (possibly bilingual, sentence-by-sentence)
        ▼
Frontend receives reply     [app/static/app.js]
        │
        ▼
speak(text)  (line 401)  — split into sentences, route each
        │
        ├──── sentence in en-US ────► getNeuralAudio(sentence)  (line 378)
        │                                    │
        │                                    │  POST /api/speak  { "text": "…" }
        │                                    ▼
        │                            app/main.py :: speak()  (line 320)
        │                                    │
        │                                    │  asyncio.to_thread(tts.synthesize, cfg, text)
        │                                    ▼
        │                            app/tts.py :: _synth_kokoro()  (line 106)
        │                                    │
        │                                    │  Kokoro.create(text, voice="af_heart",
        │                                    │                speed=1.0, lang="en-us")
        │                                    ▼
        │                            WAV bytes (24 kHz mono) → 200 audio/wav
        │                                    │
        │                                    ▼
        │                            HTMLAudioElement plays Kokoro
        │
        └──── sentence not en-US ───► null returned by getNeuralAudio
                                             │
                                             ▼
                                     speakBrowser(sentence)  (line 333)
                                             │
                                             │  utter.lang = detectLang(text)
                                             │  utter.voice = chooseVoice(lang)
                                             ▼
                                     window.speechSynthesis.speak(utter)
                                             │
                                             ▼
                                     OS/browser TTS speaks the sentence
```

---

## Current English synthesis path

**Entry:** the frontend calls `POST /api/speak` for each sentence where `detectLang(sentence) === "en-US"`.

**Server-side:**
- `app/main.py:320–334` — the `speak(payload: SpeakIn)` route validates the text is non-empty, loads `Config`, and dispatches to `tts.synthesize` on a worker thread via `asyncio.to_thread`.
- `app/tts.py:119–141` — `synthesize(cfg, text)` calls `_synth_kokoro`, times the call, updates `METRICS`, and catches any exception (returning `None` and logging a warning).
- `app/tts.py:106–116` — `_synth_kokoro(cfg, text)` calls `engine.create(text, voice=cfg.tts_voice or "af_heart", speed=float(cfg.tts_speed or 1.0), lang="en-us")`.

**Engine details:**
- Kokoro via `onnxruntime` (CPU wheel, 1.27.0).
- Model: `models/kokoro-v1.0.onnx` (310 MB).
- Voice pack: `models/voices-v1.0.bin` (27 MB) — 54 voices across 10 language prefixes.
- Default voice: `af_heart` — a warm American-English female voice. **This is "Nero's voice."**
- Output: 24 kHz mono 16-bit PCM, wrapped as WAV.
- Measured warm latency: 0.983 s avg for a 3.9 s clip; RTF 0.25.

**Reply audio path in the browser:** WAV bytes are wrapped in an `HTMLAudioElement`, unlocked to iOS Web Audio, played back with barge-in support (a new user input cancels the current playback).

---

## Current Croatian synthesis path

**Entry:** the frontend calls `speakBrowser(sentence)` for each sentence where `detectLang(sentence) !== "en-US"`. `/api/speak` is **not** called for Croatian — the network never leaves the browser.

**Frontend logic (all in `app/static/app.js`):**
- `detectLang(text)` (line 231–233):
  ```js
  return /[čćđšž]/i.test(text) ? "hr-HR" : "en-US";
  ```
  Diacritic-based heuristic. Any Croatian-specific character routes to `"hr-HR"`.
- `getNeuralAudio(sentence)` (line 378): returns `null` short-circuit if `detectLang(sentence) !== "en-US"`. This is the seam that keeps Kokoro out of the Croatian path.
- `chooseVoice(langCode)` (line 255–266): picks the smoothest-female-name browser voice matching the language prefix (e.g. `hr-*`), falling back to any browser voice if none match. Preference is persisted in `localStorage.ttsVoice`.
- `speakBrowser(text)` (line 333–347):
  ```js
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = detectLang(text);
  const voice = chooseVoice(utter.lang);
  if (voice) utter.voice = voice;
  window.speechSynthesis.speak(utter);
  ```
  Uses the platform's built-in speech synthesizer. No network call.

**Engine details:** whatever the browser + OS provide.
- **Windows 11 (Toni's host):** `Microsoft Matej` (male HR) or `Microsoft Gabrijela` (female HR), bundled with the OS. Adequate consumer quality.
- **Chrome desktop:** Google's Croatian voices, higher quality than the OS defaults.
- **Safari iOS/macOS:** Apple's Croatian voices — generally the highest-quality bundled option.
- **No output metadata** available programmatically (sample rate, duration, etc. are not exposed to the browser JS).

**Latency:** not measured explicitly, but browser TTS is typically hundreds of milliseconds to first sound — comparable to Kokoro warm latency for short sentences.

---

## Where language detection happens

There are actually **three separate "language" mechanisms** in the running system, only one of which is real detection code:

| Mechanism | Location | What it does | Purpose |
|---|---|---|---|
| LLM prompt clause | `app/prompt.py:13–24` (`_language_clause`) | *Instructs the LLM* to detect input language and reply in it — no Python code does the detection. | Determines which language the *reply text* is in. |
| Frontend diacritic heuristic | `app/static/app.js:231–233` (`detectLang`) | Regex on `/[čćđšž]/i` picks `hr-HR` vs `en-US` per sentence. | Determines which voice **path** synthesizes the reply (Kokoro or browser). |
| Kokoro `lang` parameter | `app/tts.py:112` | Hard-coded `lang="en-us"` on every Kokoro call. | Tells Kokoro's phonemizer which language to synthesize. **Never varies.** |

**No server-side Python code detects language.** The `_language_clause` clause in the prompt (line 20–24) reads:

> "You are completely fluent in {joined}. Automatically detect which of these languages each message is written in, and always reply in that same language — naturally and idiomatically, like a native speaker. Match the language of each message; never switch unless you're asked to."

The LLM handles the detection semantically. The Python layer is unaware.

**Implication for the ADR-0009 revision language ("existing bilingual detection in app/prompt.py / app/main.py"):** the phrasing is slightly inaccurate. The "bilingual detection" is *delegated to the LLM* via the prompt clause; no code in `app/prompt.py` or `app/main.py` inspects language. If ADR-0009 ever ships and needs a `language` field on a `RenderingProfile`, that value would come from either (a) the frontend's `detectLang()` result already computed for routing, or (b) a new server-side detection step that does not exist today.

---

## Where fallback happens

Two distinct fallbacks exist, in this order:

1. **Kokoro → browser voice (language-driven).**
   - `app/static/app.js:378` — `getNeuralAudio` returns `null` when `detectLang(sentence) !== "en-US"`.
   - Frontend routes null-audio sentences to `speakBrowser`.
   - This is the **production Croatian path**, not a degraded fallback.

2. **Kokoro → browser voice (availability-driven).**
   - `app/main.py:333` — `POST /api/speak` returns HTTP 204 when `tts.synthesize` returns `None`.
   - `tts.synthesize` returns `None` if `available(cfg)` is false (voice deps not installed, or `tts_enabled=false`), or if synthesis raises an exception (caught in `app/tts.py:139–141`).
   - Frontend `getNeuralAudio` catches the 204 (or any fetch error) and returns `null`, again routing to `speakBrowser`.
   - This is a graceful-unavailable fallback: chat never breaks.

**A third failure mode exists (voice-identity failure) but is not treated as a fallback in code:** even when both paths succeed, the *identities* of the two engines are different, so the audio identity of "Nero" changes when the language changes. The pipeline treats this as normal behavior. See below.

---

## Voice identity differences between languages

This is the load-bearing finding of the audit.

| Aspect | English (Kokoro path) | Croatian (browser path) |
|---|---|---|
| Engine | Kokoro ONNX 0.4.7 | OS/browser SpeechSynthesis |
| Default voice | `af_heart` — American, warm, breathy, female | OS-dependent (Win 11: `Microsoft Gabrijela` female or `Microsoft Matej` male) |
| Selected via | `Config.tts_voice` (server) | `chooseVoice(langCode)` → localStorage preference, else first female-named voice for that language (browser) |
| Sample rate | 24 kHz | Browser-controlled (typically 22 kHz or 24 kHz, unspecified in API) |
| Prosody | Kokoro's neural prosody model | Concatenative or older neural, OS-dependent |
| Cadence | Uniform across sessions (deterministic engine) | Uniform per browser session but varies across browsers/OSes |
| Cross-language identity | N/A (English only) | N/A (Croatian only) |
| **Is the same person speaking both languages?** | **No.** The `af_heart` voice and the `Microsoft Gabrijela` voice are two different women, audibly so. | |

**Consequence:** a bilingual reply where Nero says *"Sure, Toni — evo, gotovo je."* (English then Croatian, one utterance) plays as **two different women's voices, mid-utterance.** The switch is audible. The identity break is not a subtle preference issue — it's a clearly perceptible discontinuity.

**No code today attempts to unify these identities.** There is no voice-cloning step, no cross-engine tone matching, no post-processing. The two engines produce audio independently and the browser plays them in sequence.

---

## What the current pipeline does NOT have

For completeness — none of these exist in the code:

- Any TTS engine other than Kokoro on the server.
- Any language other than `en-us` passed to Kokoro's `create()` call.
- Any server-side language detection function.
- Any voice-provider abstraction (no `TTSEngine`, no `VoiceCasting`, no `RenderingProfile`).
- Any voice-cloning capability.
- Any cloud TTS integration (ElevenLabs, Azure, Google, OpenAI, Cartesia — all zero occurrences in code).
- Any Croatian-specific voice model (Kokoro's voice pack has no Croatian voices; `hf_*` and `hm_*` are Hindi).
- Any voice-identity preservation across engines.

---

## Summary — the pipeline as it stands

- **English speech:** high-quality, consistent voice identity, warm & recognizable. Nero sounds like Nero.
- **Croatian speech:** functional, decent quality on modern hosts, voice identity is *not* Nero — it's whichever female Croatian voice the platform ships. On Windows 11 the default is `Microsoft Gabrijela`.
- **The gap** is not "Nero can't speak Croatian." The gap is "Nero doesn't sound like Nero when she speaks Croatian."
- **The gap is fully in code today, not hypothetical.** It's not a design deficiency waiting to happen — it's a live artifact of the pipeline described above.

Whether that gap is worth solving, and if so with what engine, is the subject of the sibling documents in this discovery phase (`voice-provider-analysis.md`, `mms-tts-evaluation.md`, `voice-strategy-recommendation.md`).
