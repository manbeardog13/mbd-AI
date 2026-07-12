#!/usr/bin/env python3
"""Verify Nero's local neural voice: synthesize a phrase and save a playable WAV.

Self-contained — it generates its own audio, so no microphone or sample file is
needed. Skips (exit 2) if the voice deps aren't installed yet, since they're
optional. On success it writes a WAV next to this script that you can play to
actually *hear* Nero's new voice.
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import tts  # noqa: E402
from app.config import load_config  # noqa: E402

PHRASE = "Hello, Toni. This is Nero, speaking in my own local voice."
OUT = Path(__file__).resolve().parent / "nero_voice_sample.wav"


def main() -> int:
    cfg = load_config()

    if not cfg.tts_enabled:
        print("  . voice disabled (tts_enabled: false) — skipping.")
        return 2
    if not tts.available(cfg):
        print(f"  . voice engine '{cfg.tts_engine}' not installed — skipping.")
        print("    Install it once:  pip install -r requirements-voice.txt")
        return 2

    print(f"  · engine={cfg.tts_engine}  voice={cfg.tts_voice}  speed={cfg.tts_speed}")
    print("  · synthesizing (first run downloads the model, ~310 MB — hang tight)…")
    audio = tts.synthesize(cfg, PHRASE)

    if not audio:
        print("  XX synthesis returned no audio.")
        print("     Check that kokoro-onnx installed cleanly and the model files")
        print("     downloaded into models/. If it failed on phonemization, install")
        print("     espeak-ng once. See the app/tts.py log line above for the reason.")
        return 1

    # Validate it's a real, non-empty WAV.
    OUT.write_bytes(audio)
    try:
        with wave.open(str(OUT), "rb") as w:
            frames, rate, ch = w.getnframes(), w.getframerate(), w.getnchannels()
    except Exception as exc:  # noqa: BLE001
        print(f"  XX produced bytes aren't a valid WAV: {exc}")
        return 1

    seconds = frames / rate if rate else 0
    ok = frames > 0 and seconds > 0.3
    print(f"  {'OK' if ok else 'XX'} synthesized {len(audio):,} bytes "
          f"({seconds:.1f}s, {rate} Hz, {ch}ch, {tts.METRICS['last_ms']} ms)")
    print(f"     > play it:  {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
