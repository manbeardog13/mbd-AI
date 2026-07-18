# ADR-0011 — Single voice production path + Croatian handling

**Status:** Accepted (2026-07-13, Toni) — operational decision applied the
same day; this ADR retroactively records the reasoning.

## Context

Two coupled questions arose after `nero_prime_v1` (see ADR-0010 and the
frozen profile in `voice/profiles/presets.py`) was wired into `/api/speak`:

1. The frontend (`app/static/app.js`) still routed Croatian text — detected
   by a diacritic heuristic — to the browser's built-in `SpeechSynthesis`.
   Croatian utterances therefore played through whichever voice the OS /
   browser happened to ship (Windows: *Microsoft Gabrijela*; Chrome:
   Google's Croatian; iOS: Apple's Croatian). That's a *second voice*,
   different from Nero, showing up mid-conversation whenever Toni's message
   crossed into Croatian.
2. There was also a legacy fallback in `app/main.py::speak()` from the
   Voice-Director-wiring step: if the Director raised or produced no audio,
   `app/tts.py::synthesize()` ran as a safety net. Same voice (`af_heart`),
   different code path, but a second production path nonetheless.

Toni's Phase-3 direction was explicit: *"No fallback voices. No browser
speech synthesis. No hidden alternate engines. The user should always hear
the NERO identity voice."*

## Decision

**One production voice path:**

```
User → Brain → Voice Director → nero_prime → Kokoro → banshee → audio
```

The Voice Director is the ONLY code path from text to audio. There is no
browser SpeechSynthesis fallback. There is no legacy `tts.synthesize`
fallback. The frontend does not detect language for routing purposes; the
Voice Director owns that decision.

**Language routing (Croatian handling):** the Voice Director refuses to
synthesize text whose detected language does not match the active
profile's `lang`. When that happens:

- `voice.director.synthesize(...)` returns
  `SynthesisResult(audio=None, reason="unsupported-language",
                   metadata={"detected": "hr-HR", "profile_lang": "en-us"})`
- `voice.events` emits `voice.unsupported_language` for observers (Presence
  Director, telemetry, future logging).
- `POST /api/speak` returns **HTTP 204** with the headers
  `X-Voice-Reason: unsupported-language` and
  `X-Voice-Detected-Language: hr-HR` so the frontend can (optionally) show
  a UI hint like *"no voice for this language yet"* without a second
  round-trip or a body parse.

**Language detection heuristic** (`voice/language.py::detect_language`):
regex on Croatian-only diacritics (`č/ć/đ/š/ž`). Known limitation:
diacritic-free Croatian ("Dobro jutro", "Bok") reads as English and
Kokoro will attempt to voice it, producing an English-phonemized
approximation. This matches the pre-existing frontend behavior and is a
conscious trade — a real LID model would add a dependency for a case Toni
already lives with. Upgradeable in one file if it becomes painful.

**Frontend changes:**
- Removed `detectLang`, `chooseVoice`, `speakBrowser`, `populateVoicePicker`,
  the `FEMALE_HINTS` array, and the voice-picker `<select id="tts-voice">`
  UI element from `index.html`.
- `speak()` now issues `/api/speak` for every sentence unconditionally.
  Sentences that come back 204 are silently skipped — the reply text
  remains visible on screen but produces no audio for that specific
  sentence.
- `fetchSpeech()` records the `X-Voice-Reason` header on 204 responses in
  a module-level `lastVoiceReason` so a future UI hint can consume it
  without more plumbing.
- `stopSpeaking()` no longer calls `window.speechSynthesis.cancel()` —
  there's nothing there to cancel.
- Audio unlock in `unlockAudio()` still primes Web Audio + `<audio>` but
  no longer primes `SpeechSynthesis`.

## Consequences

- ✅ **One voice, one identity.** Users hear Nero or hear nothing. No
  jarring mid-utterance voice switch.
- ✅ **Machine-readable signaling.** `X-Voice-Reason` lets the frontend
  degrade gracefully today and lets future observers (metrics, logs,
  presence) act on synthesis outcomes without parsing bodies.
- ✅ **Voice Director owns language routing.** The brain / HTTP layer
  never inspects text content for language — that's a Voice Director
  concern, per the Phase-3 direction.
- ⚠️ **Croatian without diacritics is misdetected.** Not a regression —
  matches the previous frontend behavior — but the failure mode is now
  "Kokoro speaks garbled Croatian" instead of "browser voice speaks
  Croatian." If this becomes noticeable, upgrade the heuristic in
  `voice/language.py::detect_language` (a small module — the ADR-0010
  escape-hatch reasoning applies: the *detection* is trivially
  replaceable without touching the rest of the voice stack).
- ⚠️ **Croatian is silent in production today.** Nero can chat in
  Croatian (text still comes through the LLM), but Nero can't voice it.
  The 204 + header path is honest about this; a future Croatian voice
  profile (`nero_prime_hr_v1`? — see ADR-0009's persona / cast direction)
  can plug in when a Croatian-capable engine is added, without touching
  any callers.
- ⚠️ **Legacy `app/tts.py` is no longer reachable from `/api/speak`.**
  It still exists in the tree and is still imported by `app.main.py` at
  the module level, but no code path invokes it. Left in place because
  removing it is a separate cleanup unrelated to voice identity; it
  costs nothing while parked.

## Alternatives considered

- **Option A — Lock Nero to English-only in config.** Rejected: violates
  Toni's "preserve architecture for multilingual expansion" requirement.
  Would require re-plumbing the whole stack when a Croatian voice arrives.
- **Option C — Silent no-audio for Croatian (no header, no signal).**
  Rejected: dishonest. The frontend has no way to hint the user, and
  future observability tools can't tell "unsupported language" from
  "engine crashed."
- **Kept the legacy `tts.synthesize` fallback in `/api/speak`.** Rejected:
  the fallback was a migration crutch after ADR-0009 Migration Stage 4;
  migration is now complete. Two paths to the same voice mask bugs
  instead of surfacing them.
- **Cloud TTS for Croatian (ElevenLabs / Cartesia / Azure).** Rejected
  standing per ADR-0006 boundary and this session's Kokoro-only reset.
  Voice stays 100% local. See the memory `feedback-voice-local-only`.

## Cross-references

- ADR-0006 — Local-First with Intelligence Escalation (voice explicitly
  excluded from cloud escalation in the current session)
- ADR-0009 — Voice rendering / casting / backend architecture (the
  eventual home for a `nero_prime_hr_v1` profile)
- ADR-0010 — Voice effects layer (pedalboard adoption)
- `voice/language.py` — the detection heuristic + `profile_supports_text`
- `voice/director.py::SynthesisResult` — the reason enum
- `app/main.py::speak` — the HTTP surface
- `app/static/app.js` — the pared-down frontend
