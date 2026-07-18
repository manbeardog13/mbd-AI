"""A/B test the banshee FX pass against a chosen Kokoro blend.

Generates two WAV files from the same blend + same sentence:
    <outdir>/dry.wav       - Kokoro synthesis, no effects
    <outdir>/banshee.wav   - Kokoro synthesis + banshee FX pass

Usage:
    python voice/effects/ab_test.py \\
        --blend "<path to blend.npy>" \\
        --sentence "<path to sentence .txt>" \\
        --outdir "<directory for the two output WAVs>"

The blend .npy is the cached style vector produced by the audition workspace
(see: iCloudDrive/Nero AI/voice_audition/manbeardog_blends/<slug>/blend.npy).
The sentence file is a plain-text UTF-8 file containing one utterance.

This script is a diagnostic tool. It writes only into --outdir; it never
touches the Kokoro voice pack, the model files, or the Nero app state.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

# Ensure the repo root is on sys.path so `voice.effects.banshee` imports work
# when this script is run directly (e.g. `python voice/effects/ab_test.py`).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", required=True, type=Path,
                        help="Path to a cached blend .npy (style vector).")
    parser.add_argument("--sentence", required=True, type=Path,
                        help="Path to a UTF-8 text file containing one utterance.")
    parser.add_argument("--outdir", required=True, type=Path,
                        help="Directory to write dry.wav and banshee.wav.")
    parser.add_argument("--model", type=Path,
                        default=Path("models/kokoro-v1.0.onnx"),
                        help="Path to kokoro-v1.0.onnx (default: models/ in cwd).")
    parser.add_argument("--voices", type=Path,
                        default=Path("models/voices-v1.0.bin"),
                        help="Path to voices-v1.0.bin (default: models/ in cwd).")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Kokoro speed parameter (default 1.0).")
    parser.add_argument("--lang", default="en-us",
                        help="Kokoro lang parameter (default en-us).")
    args = parser.parse_args()

    if not args.blend.exists():
        print(f"ERROR: blend file not found: {args.blend}", file=sys.stderr)
        return 2
    if not args.sentence.exists():
        print(f"ERROR: sentence file not found: {args.sentence}", file=sys.stderr)
        return 2
    if not args.model.exists() or not args.voices.exists():
        print(f"ERROR: kokoro model or voices file missing "
              f"(model={args.model}, voices={args.voices})", file=sys.stderr)
        return 2

    args.outdir.mkdir(parents=True, exist_ok=True)

    text = args.sentence.read_text(encoding="utf-8").strip()
    if not text:
        print(f"ERROR: sentence file is empty: {args.sentence}", file=sys.stderr)
        return 2
    print(f"Sentence ({len(text)} chars): {text[:80]}{'...' if len(text)>80 else ''}")

    # Load blend vector
    blend_vec = np.load(args.blend)
    print(f"Blend vector loaded: shape={blend_vec.shape}, dtype={blend_vec.dtype}")

    # Load Kokoro (lazy — script also works if only the imports fail)
    try:
        from kokoro_onnx import Kokoro
    except ImportError as exc:
        print(f"ERROR: kokoro-onnx not installed: {exc}", file=sys.stderr)
        return 3

    print("Loading Kokoro engine...")
    t0 = time.perf_counter()
    kokoro = Kokoro(str(args.model), str(args.voices))
    print(f"  engine ready in {time.perf_counter()-t0:.2f}s")

    # Synthesize once — same samples feed both outputs
    print(f"Synthesizing (speed={args.speed}, lang={args.lang})...")
    t0 = time.perf_counter()
    samples, sample_rate = kokoro.create(text, voice=blend_vec, speed=args.speed, lang=args.lang)
    synth_s = time.perf_counter() - t0
    audio_s = len(samples) / sample_rate
    print(f"  synth={synth_s:.2f}s  audio={audio_s:.2f}s  rtf={synth_s/audio_s:.3f}")

    # Write dry WAV
    dry_path = args.outdir / "dry.wav"
    sf.write(str(dry_path), samples.astype(np.float32), sample_rate, subtype="PCM_16")
    dry_kb = dry_path.stat().st_size / 1024
    print(f"  wrote dry:     {dry_path}  ({dry_kb:.0f} KB)")

    # Apply banshee FX and write
    from voice.effects.banshee import apply_banshee_fx  # local import

    banshee_cfg = {"enabled": True}  # use defaults, everything on
    t0 = time.perf_counter()
    processed = apply_banshee_fx(samples, sample_rate, banshee_cfg)
    fx_s = time.perf_counter() - t0
    print(f"  banshee fx pass: {fx_s*1000:.0f} ms")

    banshee_path = args.outdir / "banshee.wav"
    sf.write(str(banshee_path), processed.astype(np.float32), sample_rate, subtype="PCM_16")
    banshee_kb = banshee_path.stat().st_size / 1024
    print(f"  wrote banshee: {banshee_path}  ({banshee_kb:.0f} KB)")

    print()
    print("Compare the two files by ear. If the banshee version blurs or")
    print("overshadows the words, reduce ghost.gain_db (make it more negative)")
    print("or reverb.wet_level in your config overrides.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
