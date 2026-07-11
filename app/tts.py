"""Nero's local neural voice — turning her words into speech, on your machine.

All synthesis runs locally, so Nero can *talk* while staying fully private —
nothing spoken (or heard) leaves the PC. The module is engine-abstracted:

  - Increment 1 (now): a premium English voice via **Kokoro**, run through
    **ONNX Runtime** (`kokoro-onnx`) — fast, light, **no torch**, and works on
    modern Python (incl. 3.13). The ~310 MB model is downloaded once on first
    use from the kokoro-onnx release.
  - Next: Croatian via **Meta MMS-TTS**, and an expressive/cloning engine
    (**Chatterbox**) — both slide in behind the same `synthesize()` API.

Best-effort and synchronous: returns WAV bytes, or ``None`` if the voice isn't
installed yet (the web layer then tells the browser to use its own fallback
voice, so chat never breaks). The heavy engine is imported + loaded lazily and
cached, so importing this module is cheap and the app runs fine without the
optional voice deps.
"""
from __future__ import annotations

import importlib.util
import io
import logging
import threading
import time
import urllib.request
import wave
from pathlib import Path

from .config import Config

log = logging.getLogger("nero.tts")
ROOT = Path(__file__).resolve().parent.parent

SAMPLE_RATE = 24_000  # Kokoro outputs 24 kHz mono
METRICS: dict[str, float] = {"spoken": 0, "chars": 0, "last_ms": 0.0}

_lock = threading.RLock()
_engine = None  # cached kokoro_onnx.Kokoro instance

# Model files, downloaded once from the kokoro-onnx GitHub release.
_MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
_VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
_MODEL_NAME = "kokoro-v1.0.onnx"
_VOICES_NAME = "voices-v1.0.bin"


def available(cfg: Config) -> bool:
    """Is the configured voice engine installed? Cheap — no model load/download."""
    if not cfg.tts_enabled:
        return False
    engine = (cfg.tts_engine or "kokoro").lower()
    if engine == "kokoro":
        return importlib.util.find_spec("kokoro_onnx") is not None
    return False


def _model_dir(cfg: Config) -> Path:
    d = Path(cfg.tts_model_dir or "models")
    if not d.is_absolute():
        d = ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_file(path: Path, url: str) -> None:
    """Download a model file once (atomically), if it's not already present."""
    if path.exists() and path.stat().st_size > 0:
        return
    log.info("downloading voice model %s (one-time)…", path.name)
    tmp = path.with_name(path.name + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(path)
    log.info("voice model %s ready (%.0f MB)", path.name, path.stat().st_size / 1e6)


def _kokoro(cfg: Config):
    """Load (once) and cache the Kokoro ONNX engine, fetching models if needed."""
    global _engine
    with _lock:
        if _engine is None:
            from kokoro_onnx import Kokoro  # lazy; pulls onnxruntime + numpy

            d = _model_dir(cfg)
            model, voices = d / _MODEL_NAME, d / _VOICES_NAME
            _ensure_file(model, _MODEL_URL)
            _ensure_file(voices, _VOICES_URL)
            _engine = Kokoro(str(model), str(voices))
        return _engine


def _wav_bytes(samples, rate: int) -> bytes:
    """Encode a float32 mono waveform (-1..1) as 16-bit PCM WAV bytes."""
    import numpy as np

    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate) or SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def _synth_kokoro(cfg: Config, text: str) -> bytes | None:
    engine = _kokoro(cfg)
    samples, rate = engine.create(
        text,
        voice=cfg.tts_voice or "af_heart",
        speed=float(cfg.tts_speed or 1.0),
        lang="en-us",
    )
    if samples is None or len(samples) == 0:
        return None
    return _wav_bytes(samples, rate)


def synthesize(cfg: Config, text: str) -> bytes | None:
    """Speak `text` in Nero's local voice. Returns WAV bytes, or None if the
    voice engine isn't available (caller falls back to the browser voice)."""
    text = (text or "").strip()
    if not text or not available(cfg):  # not enabled, or voice deps absent
        return None
    engine = (cfg.tts_engine or "kokoro").lower()
    try:
        started = time.perf_counter()
        if engine == "kokoro":
            data = _synth_kokoro(cfg, text)
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
