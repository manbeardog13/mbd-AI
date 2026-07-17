---
id: archive.review-voice-stage1-voice-baseline
layer: archival
type: review
status: archived
owner: shared
superseded_by: docs/adr/0009, 0010, 0011
updated: 2026-07-17
---

# Stage 1 Voice Baseline Review

**Date:** 2026-07-13
**Author:** Claude Code (baseline capture for the ADR-0009 workstream)
**Scope:** documentation only — no code, config, dependency, API, or runtime change of any kind.
**Related:** [ADR-0009](../../adr/0009-voice-rendering-and-backend-architecture.md) (Proposed, revised 2026-07-13) · [ADR-0009 Acceptance Review](../../reviews/ADR-0009-acceptance-review.md) (Accepted with implementation gate preserved).

---

## Purpose

This document captures Nero's **current production voice path exactly as it exists today**, before any ADR-0009 migration work begins. It exists to:

- **Freeze the known-good Stage 1 state** in writing, so it does not drift silently while the ADR sits accepted-but-unimplemented.
- **Document current behavior** in one place — code, config, HTTP surface, threading, lifecycle.
- **Record concrete measurements** obtained on the RTX 4070 during Stage 13.5 Phase 1 so future comparisons have real numbers, not remembered impressions.
- **Provide the comparison baseline** every future ADR-0009 migration stage (2 → 3 → 4 → 5) must clear before promotion.

Two rules stated up front:

1. **Stage 1 is the frozen baseline.** Nothing in this document is a change to Stage 1; it only describes it. Any deviation from what is written here — in `app/tts.py`, `app/main.py`, config, or HTTP behavior — is a Stage-1 regression until it is proposed and approved as a Stage 2+ change under ADR-0009 (which itself is currently gated behind a scheduled second engine).
2. **Future migration stages must prove equivalence against this baseline** using the measurements below. "Behaviorally the same" is not enough — Stage promotions require measurement evidence per the ADR-0009 Validation Strategy.

---

## Current Architecture

### Request flow

```
Web frontend / Siri Shortcut / any HTTPS caller
        │
        │  POST /api/speak     { "text": "…" }
        ▼
   app/main.py :: speak(payload: SpeakIn)                   [async handler]
        │   validates text is non-empty (400 on empty)
        │   loads Config via load_config()
        │
        │  asyncio.to_thread(tts.synthesize, cfg, text)     [off event loop]
        ▼
   app/tts.py :: synthesize(cfg, text) -> bytes | None      [synchronous]
        │   short-circuits to None if !available(cfg)
        │   times the call, updates METRICS
        │
        ▼
   app/tts.py :: _synth_kokoro(cfg, text)
        │   engine = _kokoro(cfg)      # lazy + cached under _lock
        │   samples, rate = engine.create(text, voice, speed, lang="en-us")
        │
        ▼
   app/tts.py :: _wav_bytes(samples, rate) -> bytes
        │   float32 → 16-bit PCM → WAV container (mono, 24 kHz)
        │
        ▼
   Response:
     200 audio/wav  (bytes)      on success
     204 No Content              when synthesize() returned None
     400 Bad Request             when text was empty/whitespace
```

### Where synthesis happens

- Real synthesis: **`app/tts.py::_synth_kokoro`** (lines 106–116).
- HTTP entry point: **`app/main.py::speak`** (lines 320–334).
- Status probe (does not synthesize): **`app/main.py::voice_status`** at `GET /api/voice` (lines 308–317), backed by `app/tts.py::available`.
- Metrics: **`app/main.py::metrics`** at `GET /api/metrics` (lines 293–303) surfaces `app/tts.py::METRICS` as `metrics.voice`.

### Where configuration comes from

- File: `config.yaml` (created on first run from `config.example.yaml`), read by `app/config.py::load_config`.
- Live overrides (humor dial, voice preference) at `data/settings.json`.
- **Read on every request** — `load_config()` is called inside `speak()` (line 330 of `app/main.py`), so a config edit takes effect on the next request without a restart.
- Voice-relevant `Config` fields (from `app/config.py` lines 70–74): `tts_enabled`, `tts_engine`, `tts_voice`, `tts_speed`, `tts_model_dir`.

### How the engine is initialized

- **Lazy.** No engine is loaded until the first synthesis request lands.
- **On first call:** `_kokoro(cfg)` (`app/tts.py:77–89`)
  1. imports `kokoro_onnx.Kokoro` (heavy import, done lazily),
  2. resolves the model directory (`cfg.tts_model_dir`, defaults to `<repo>/models`),
  3. `_ensure_file()` downloads `kokoro-v1.0.onnx` (310 MB) and `voices-v1.0.bin` (27 MB) from the kokoro-onnx v1.0 GitHub release if absent,
  4. instantiates `Kokoro(model_path, voices_path)`,
  5. stores the instance in module-global `_engine`.

### How caching works

- Single module-global `_engine` (line 39).
- Cached for **process lifetime** — no eviction, no timeout, no explicit release/dispose. Relies on process exit.
- All calls to `_kokoro(cfg)` after the first return the same cached instance.
- The model directory (`models/`) is also cached at the filesystem level — the download is one-time; subsequent process starts skip the network.

### How concurrency is handled

- `_lock = threading.RLock()` at module level (line 38).
- Cache initialization (`_kokoro`) and metrics updates run under `_lock`.
- The actual `engine.create()` call inside `_synth_kokoro` runs **without** holding `_lock` — but because there is exactly one cached engine and Kokoro's `create()` is itself not documented as thread-safe, effective parallelism is bounded by whatever internal locking `kokoro_onnx` performs.
- FastAPI dispatches the sync `synthesize` call via `asyncio.to_thread` (`app/main.py:331`), so the event loop is not blocked; multiple in-flight `/api/speak` requests execute on the default thread-pool executor.

---

## Current Voice Configuration

Defaults come from `app/config.py::load_config` (lines 181–188). All values are override-able via `config.yaml`.

| Config key | Default | Purpose | Notes |
|---|---|---|---|
| `tts_enabled` | `True` | master switch | If False, `available()` returns False, `/api/speak` returns 204. |
| `tts_engine` | `"kokoro"` | engine selector | Currently the only implemented engine; anything else is rejected in `synthesize()` via a warning log. |
| `tts_voice` | `"af_heart"` | Kokoro voice ID | **Engine-specific value stored in top-level config** — the exact coupling ADR-0009 is proposed to break. Live-overridable via `data/settings.json`. |
| `tts_speed` | `1.0` | playback speed | Passed through to `Kokoro.create(speed=…)`. |
| `tts_model_dir` | `"models"` | where to download / find model files | Relative paths resolve under repo root. |

### Fallback behavior

- **Voice deps not installed** → `available()` returns False → `synthesize()` returns None → `/api/speak` returns **204 No Content** → the web frontend falls back to the browser's built-in `SpeechSynthesis` voice. Chat never breaks.
- **Voice deps installed but synthesis raises** → caught in `synthesize()` (lines 139–141), logged as `tts failed (…)`, returns None → same 204 path.
- **Language other than English** → still synthesized by Kokoro with `lang="en-us"` hard-coded (`app/tts.py:112`). The web layer's existing bilingual detection decides at the UI level whether to fall back to the browser voice for Croatian.

---

## Runtime Behavior

### Input format

- HTTP: `POST /api/speak`
- Body: `application/json`, shape `{ "text": "<string>" }` (validated via the `SpeakIn` Pydantic model).
- Empty/whitespace text → **400 Bad Request** with `"Nothing to speak."` detail.

### Output format

- Success → **200 OK**, `Content-Type: audio/wav`, body = 16-bit PCM WAV, mono, 24 kHz.
- Voice unavailable OR synthesis returned None → **204 No Content**, empty body.
- Empty input → **400 Bad Request**.

### Failure behavior

- All engine-side exceptions are caught inside `synthesize()` and translated to a `None` return + a `log.warning` line. Callers never see stack traces from the voice layer.
- The web endpoint distinguishes only success (200 with bytes) vs. graceful-unavailable (204).

### HTTP / threading / async behavior

- FastAPI route is `async def speak(...)`.
- The sync `tts.synthesize` runs on the default thread-pool executor via `asyncio.to_thread` — the event loop is never blocked by synthesis.
- Multiple concurrent `/api/speak` requests are permitted at the HTTP layer; actual synthesis parallelism is bounded by (a) the single cached engine and (b) whatever internal serialization `kokoro_onnx` performs. See Concurrency measurements below.

### Lifecycle behavior

- Engine loads lazily on first request.
- One instance per process, cached for process lifetime.
- No eviction, no idle unload, no explicit `.close()` / `.dispose()`.
- Process exit releases resources implicitly (no cleanup handler registered).

---

## Measurements

Recorded on the RTX 4070 host during Stage 13.5 Phase 1 (2026-07-12). Fresh Python 3.14.5 process in `D:\mbd AI\.venv` with `kokoro-onnx 0.4.7`, `onnxruntime 1.27.0` (CPU wheel), `numpy 2.5.1`, `soundfile 0.14.0`. Model files present at `models/kokoro-v1.0.onnx` (325,532,387 B = 310.4 MB) and `models/voices-v1.0.bin` (28,214,398 B = 26.9 MB) — no download in-loop.

Test phrase (see **Golden Phrase** below): *"Hello, Toni. This is Nero, speaking in my own local voice."* (12 words). Voice: `af_heart`. Speed: `1.0`. Language: `en-us`.

### Latency

| Metric | Value | Notes |
|---|---|---|
| Cold start — Python import (`kokoro_onnx`) | **0.447 s** | fresh process, first import |
| Cold start — engine init (`Kokoro(model, voices)`) | **0.886 s** | model files on local SSD |
| Cold start — first synth (post-init) | **1.093 s** | first `create()` call |
| **Cold start — total (import + init + first synth)** | **2.427 s** | fresh process, model already downloaded |
| Warm synthesis — min | **0.972 s** | n=5 identical calls |
| Warm synthesis — max | **1.004 s** | " |
| Warm synthesis — average | **0.983 s** | " |
| Warm-run standard deviation (approx.) | ~12 ms | very stable |

### Real-Time Factor

| Metric | Value | Notes |
|---|---|---|
| Audio duration for the test phrase | **3.925 s** | 24 kHz mono, 94,208 samples |
| **RTF (warm average)** | **0.250** | synth_s ÷ audio_s = 0.983 / 3.925 |
| Meaning | 4× faster than realtime | comfortably real-time capable |

### Memory

| Metric | Value | Notes |
|---|---|---|
| Model file — `kokoro-v1.0.onnx` | **310.4 MB** on disk | one-time download |
| Voice pack — `voices-v1.0.bin` | **26.9 MB** on disk | one-time download |
| Total on-disk footprint | **~337 MB** | in `models/` |
| Resident RAM impact | **Not measured in Stage 1 baseline.** | Left for a future measurement pass. |
| **VRAM impact (idle → loaded → synth → released)** | **0 MiB Δ across all phases** | `nvidia-smi` read constant 1707 MiB on the host, driven entirely by ambient processes (dwm, Chrome, etc.). Kokoro runs on CPU via the CPU-only `onnxruntime` wheel installed here. Consistent with ADR-0002. |
| GPU utilization during synth | ambient only (15–28% from other processes) | Kokoro itself contributes nothing measurable. |

### Concurrency

| Metric | Behavior |
|---|---|
| Locking primitive | `threading.RLock` at module scope (`app/tts.py:38`). |
| What the lock protects | engine init in `_kokoro()`, metrics writes in `synthesize()`. |
| What the lock does **not** protect | the actual `engine.create()` call. |
| Effective synthesis parallelism | Bounded by the single shared `Kokoro` instance and `kokoro_onnx`'s internal thread-safety, not documented externally. Concurrent `/api/speak` requests are technically permitted at the HTTP layer but effectively serialize on the engine. |
| Under measured load | Not stress-tested in Stage 1 baseline — single-request latency and RTF only. Concurrent-load measurements are **Not measured in Stage 1 baseline**. |

### Reliability

| Metric | Behavior |
|---|---|
| Exception handling | All exceptions in `synthesize()` are caught → returns None → HTTP 204. Callers never see tracebacks. |
| Warning log format | `tts failed (<engine>): <exception>` |
| Known failure path — voice deps absent | Correct: `available()` returns False, `/api/speak` returns 204, browser falls back. |
| Known failure path — model download interrupted | `_ensure_file()` uses `urllib.request.urlretrieve` to `.part`, then atomic `replace()`. Partial downloads don't leave a bad model in place. |
| Known cosmetic failure — `verify/verify_tts.py` | Prints `→`, `≈`, `▶` glyphs that fail on Windows cp1250 default encoding under Python 3.14. Synthesis completes successfully **before** the print crashes — no functional impact. Documented, not fixed (script is frozen). Workaround: `python -X utf8`. |
| Known limitation — `lang="en-us"` hard-coded | Croatian input is still passed to Kokoro as `en-us`. The web layer separately decides to route non-English utterances to the browser voice; no server-side language routing today. |

---

## Golden Phrase

**Phrase text:**

> `Hello, Toni. This is Nero, speaking in my own local voice.`

**Origin:** already used by `verify/verify_tts.py:20` as `PHRASE`. Reusing it makes the baseline and the shipped verification script speak the same words.

**Properties:**
- **Short** — 12 words, 60 characters — synthesizes in under 4 seconds of audio.
- **Deterministic** — identical string across runs; Kokoro's ONNX inference is bit-stable modulo threading (byte-exact WAV bytes are *not* guaranteed run-to-run, but audible content is stable).
- **Representative** — normal cadence, contains one comma-pause, one sentence break, and Nero's own name — a plausible sample of what she actually says.

**How future migrations should compare against it:**

- Structural parity: sample rate, channel count, bit depth, and duration (within ±50 ms) must match the Stage-1 baseline WAV.
- Latency parity: warm-loop average must stay within **+5%** of 0.983 s (i.e., ≤ ~1.032 s).
- RTF parity: must remain below 0.35 (baseline 0.25 leaves plenty of headroom).
- Byte-exact equality is *not* required (Kokoro on ONNX has minor floating-point run-to-run variance below the audible threshold).
- The comparison is documented here; **no new test infrastructure is added by this document.**

---

## ADR-0009 Migration Baseline Rules

Rules every ADR-0009 migration stage (Stage 2 → 3 → 4 → 5) must preserve when — and only when — the ADR-0009 migration is authorized:

1. **API behavior remains unchanged.** `POST /api/speak` still returns `audio/wav` on success, `204 No Content` when unavailable, `400 Bad Request` on empty input. `GET /api/voice` and `GET /api/metrics` return the same shapes.
2. **Audio quality must remain equivalent.** Structural parity (sample rate, channels, duration) is measured against the golden phrase; audible regression is grounds to block the stage.
3. **Latency must remain within agreed tolerance.** Warm average ≤ +5% of the baseline in this document; RTF < 0.35.
4. **Existing callers must continue working.** The web frontend, Siri Shortcut, and any HTTPS client on the private network are all "existing callers" — none of them may need code changes to continue playing Nero's voice.
5. **Stage transitions require measurement evidence.** Every promotion (Stage N → Stage N+1) must show fresh measurements against this baseline, on the same RTX 4070 host, using the golden phrase. No promotion on inspection alone.
6. **`/api/metrics.voice` shape stays put.** The three keys `spoken`, `chars`, `last_ms` remain unchanged across all stages. Additional metrics may appear only as *additional* top-level keys under `metrics.voice`.
7. **`Config.tts_voice` remains a legacy override** during migration and is removed only on completion of Stage 5, as a documented breaking change per ADR-0009 § Migration Stage 4.

---

## Open Questions

Observations noted here for future consideration. **Not implementation tasks.** No code, config, or dependency change is proposed by any of these — they exist so a future reader knows what was seen and deferred.

- **Resident RAM footprint of the loaded Kokoro engine was not captured** in Stage 13.5 Phase 1. If Migration Stage 3+ ever runs on lower-RAM hardware, a resident-RAM measurement pass would be useful. Not measured today.
- **Concurrent-load synthesis behavior was not stress-tested.** All Stage 1 latency numbers come from single-caller runs. If concurrent `/api/speak` traffic is ever expected (e.g., Phase 2 workspace calls voice while the user also talks), a small concurrent-load probe would tell us whether `kokoro_onnx`'s internal thread-safety serializes at the engine or truly parallelizes.
- **`lang="en-us"` is hard-coded** in `_synth_kokoro` (`app/tts.py:112`). Kokoro supports other language prefixes today (54 voices across 10 language codes were catalogued in Stage 13.5 Phase 1). The web layer's own bilingual detection currently masks this by routing Croatian to the browser voice. When Croatian MMS-TTS is scheduled, this hard-coded `lang` becomes an observable coupling that VoiceCasting will need to address.
- **`onnxruntime` is the CPU wheel.** Kokoro runs on CPU with RTF 0.25 — plenty fast. Switching to `onnxruntime-gpu` would consume VRAM that ADR-0002 explicitly reserved for the primary LLM. Per ADR-0009 Validation Strategy, any ΔVRAM > 0 from Kokoro would require a superseding ADR before landing.
- **`espeak-ng` is not on the system PATH**; the bundled `espeakng-loader` DLL inside the venv satisfies phonemization. If a future engine (e.g., MMS-TTS for Croatian) has different phonemization requirements, this arrangement may need revisiting. Not needed today.
- **No explicit engine release / dispose** on `_engine`. Fine for a long-running server; would matter if the process ever needs to unload voice without restarting.
- **`verify/verify_tts.py` cp1250 crash** on Python 3.14 (Windows default codepage). Synthesis succeeds; the crash is purely in trailing prints (`▶`, `→`, `≈`). Documented as a papercut, not fixed — the verify script is on the frozen list. Workaround: `python -X utf8`.

---

*End of Stage 1 baseline. Nothing in this document changes the running system. Future ADR-0009 migration work — currently gated behind a scheduled second engine — will be measured against these numbers.*
