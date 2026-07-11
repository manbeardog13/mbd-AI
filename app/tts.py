"""Nero's local neural voice — turning her words into speech, on your machine.

All synthesis runs locally, so Nero can *talk* while staying fully private —
nothing spoken (or heard) leaves the PC. The module is engine-abstracted:

  - Increment 1 (now): a premium English voice via **Kokoro** (fast, light,
    Apache-2.0, real-time even on CPU).
  - Next: Croatian via **Meta MMS-TTS**, and an expressive/cloning engine
    (**Chatterbox**) — both slide in behind the same `synthesize()` API.

Best-effort and synchronous: returns WAV bytes, or ``None`` if the voice isn't
installed yet (the web layer then tells the browser to use its own fallback
voice, so chat never breaks). The heavy model is imported lazily and cached, so
importing this module is cheap and the app runs fine without the voice deps.
"""
from __future__ import annotations

import importlib.util
import io
import logging
import threading
import time
import wave

from .config import Config

log = logging.getLogger("nero.tts")

SAMPLE_RATE = 24_000  # Kokoro outputs 24 kHz mono
METRICS: dict[str, float] = {"spoken": 0, "chars": 0, "last_ms": 0.0}

_lock = threading.RLock()
_pipelines: dict[str, object] = {}  # cached KPipeline per language code


def available(cfg: Config) -> bool:
    """Is the configured voice engine installed? Cheap — no model load."""
    if not cfg.tts_enabled:
        return False
    engine = (cfg.tts_engine or "kokoro").lower()
    if engine == "kokoro":
        return importlib.util.find_spec("kokoro") is not None
    return False


def _wav_bytes(samples, rate: int) -> bytes:
    """Encode a float32 mono waveform (-1..1) as 16-bit PCM WAV bytes."""
    import numpy as np

    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _kokoro_pipeline(lang_code: str = "a"):
    """Load (once) and cache Kokoro's pipeline. 'a' = American English."""
    with _lock:
        pipe = _pipelines.get(lang_code)
        if pipe is None:
            from kokoro import KPipeline  # heavy import — pulls torch

            pipe = KPipeline(lang_code=lang_code)
            _pipelines[lang_code] = pipe
        return pipe


def _synth_kokoro(text: str, voice: str, speed: float) -> bytes | None:
    import numpy as np

    pipe = _kokoro_pipeline("a")
    chunks = [audio for _, _, audio in pipe(text, voice=voice, speed=speed)]
    if not chunks:
        return None
    return _wav_bytes(np.concatenate(chunks), SAMPLE_RATE)


def synthesize(cfg: Config, text: str) -> bytes | None:
    """Speak `text` in Nero's local voice. Returns WAV bytes, or None if the
    voice engine isn't available (caller falls back to the browser voice)."""
    text = (text or "").strip()
    if not cfg.tts_enabled or not text:
        return None
    engine = (cfg.tts_engine or "kokoro").lower()
    try:
        started = time.perf_counter()
        if engine == "kokoro":
            data = _synth_kokoro(text, cfg.tts_voice or "af_heart", cfg.tts_speed)
        else:
            log.warning("unknown tts engine: %s", engine)
            return None
        if data:
            with _lock:
                METRICS["spoken"] += 1
                METRICS["chars"] += len(text)
                METRICS["last_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return data
    except Exception as exc:  # noqa: BLE001 - voice is best-effort, never break chat
        log.warning("tts failed (%s): %s", engine, exc)
        return None
