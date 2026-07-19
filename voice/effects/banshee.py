"""Banshee — the supernatural post-processing pass for Manbeardog-mode voice.

Layers an undead / spectral quality on top of a dry Kokoro-synthesized voice.
Pure CPU DSP via Spotify's ``pedalboard`` library. Does not touch the GPU.

Design principles (see docs/reviews and the ADR that governs this module):

1. **Voice always wins the mix.** The dry passthrough sits at 0 dB. Every
   ghost / shimmer chain is attenuated well below the dry signal so
   intelligibility is preserved. The final ``Limiter`` prevents clipping.
2. **OFF by default.** Callers must explicitly opt in via ``cfg["enabled"]
   = True``. With the default config, ``apply_banshee_fx`` is a passthrough.
3. **Pure function.** Same numpy array shape in and out. No side effects on
   Kokoro, no globals, no I/O.
4. **Verified API.** Every ``pedalboard`` class and parameter here has been
   introspected against the installed package. If pedalboard's API drifts,
   this module will fail loudly rather than silently.

Signal chain (matches the spec verbatim):

    input samples
        |
        v
    Mix([
        dry passthrough (Gain=0),
        ghost   (Delay ~0.06s → PitchShift -12 → Gain -14 dB),
        shimmer (Delay ~0.03s → PitchShift  +7 → Gain -20 dB),
    ])
        |
        v
    Chorus (subtle) → HighpassFilter (~120 Hz) → Reverb (~0.4 room, ~0.2 wet)
        |
        v
    Limiter
        |
        v
    output samples

Reference:
- pedalboard parallel-chain pattern:
  https://github.com/spotify/pedalboard#running-pedalboards-in-parallel
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np


# Default configuration. Every knob has a documented sonic effect. See the
# module README for tuning guidance. Callers merge overrides on top of this.
DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,  # master switch — banshee is off unless explicitly turned on
    "ghost": {
        "enabled": True,
        "delay_seconds": 0.06,   # ~60 ms — an audible echo, not a slap-back
        "semitones": -12,        # octave down; the "shadow beneath the voice"
        "gain_db": -14,          # well under the dry signal so it doesn't blur words
    },
    "shimmer": {
        "enabled": True,
        "delay_seconds": 0.03,   # ~30 ms — tight, ethereal
        "semitones": 7,          # perfect fifth up; the "cold metallic glint"
        "gain_db": -20,          # very quiet; contributes texture, not content
    },
    "chorus": {
        "enabled": True,
        "rate_hz": 1.0,          # slow modulation — otherworldly, not seasick
        "depth": 0.25,           # subtle
        "centre_delay_ms": 7.0,
        "feedback": 0.0,
        "mix": 0.35,             # blends into rather than replaces the sound
    },
    "highpass": {
        "enabled": True,
        "cutoff_frequency_hz": 120.0,  # thins body; adds "drained of life" hollowness
    },
    "reverb": {
        "enabled": True,
        "room_size": 0.4,        # moderate — Undercity crypt, not cathedral
        "damping": 0.6,          # cold surfaces, less absorption of highs
        "wet_level": 0.2,        # background presence, not wash
        "dry_level": 0.7,        # dry voice remains dominant in the mix
        "width": 1.0,
    },
    "output_pitch_shift": {
        # Overall pitch shift applied to the final mix (voice + ghost + reverb).
        # Preserves the ghost's internal interval to the dry voice — the ear
        # perceives intervals, not absolute pitch — so the sonic character is
        # unchanged, the whole thing just sits lower or higher.
        # Negative = pitch down. Keep small (-3..0). Below -4 semitones the
        # voice starts to sound artificial.
        "enabled": False,
        "semitones": 0.0,
    },
    # --- v4 polish stages (all off by default). Enable only for profiles
    # where the six-hour-listening bar demands it. If any of these becomes
    # consciously audible, disable it — they exist to be invisible. ---
    "saturation": {
        # Very light tanh waveshaping — adds tiny even/odd harmonics for
        # perceived "warmth" / "analog feel". Pedalboard's Distortion at
        # drive_db=1..3 is the transparent range; the default 25 is heavy.
        "enabled": False,
        "drive_db": 1.5,
    },
    "eq": {
        # Three-band gentle EQ. Sub-1dB moves only. If any band exceeds
        # 1.5 dB you're re-coloring the voice, not polishing it.
        "enabled": False,
        "low_shelf":  {"cutoff_frequency_hz": 200.0,   "gain_db": 0.8,  "q": 0.707},
        "peak":       {"cutoff_frequency_hz": 350.0,   "gain_db": -0.5, "q": 1.0},
        "high_shelf": {"cutoff_frequency_hz": 10000.0, "gain_db": 0.6,  "q": 0.707},
    },
    "compressor": {
        # Transparent long-form compression — very low ratio, slow attack.
        # Do NOT crank ratio > 2:1 or threshold < -30 dB; this is dynamics
        # smoothing for listening comfort, not loudness maximization.
        "enabled": False,
        "threshold_db": -18.0,
        "ratio": 1.5,
        "attack_ms": 15.0,
        "release_ms": 150.0,
    },
    "limiter": {
        "threshold_db": -1.0,    # ceiling just below clipping
        "release_ms": 100.0,
    },
}


def _merge_config(user: dict[str, Any] | None) -> dict[str, Any]:
    """Deep-merge user overrides on top of DEFAULT_CONFIG. Non-destructive."""
    cfg = deepcopy(DEFAULT_CONFIG)
    if not user:
        return cfg
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


def _ensure_mono_float32(samples: np.ndarray) -> tuple[np.ndarray, bool]:
    """Return (audio, was_2d). pedalboard accepts 1-D mono or 2-D (channels,frames)."""
    if samples.dtype != np.float32:
        samples = samples.astype(np.float32)
    return samples, samples.ndim == 2


def apply_banshee_fx(
    samples: np.ndarray,
    sample_rate: int,
    cfg: dict[str, Any] | None = None,
) -> np.ndarray:
    """Apply the banshee post-processing chain to already-synthesized audio.

    Parameters
    ----------
    samples : np.ndarray
        Audio produced by ``kokoro.create(...)`` — 1-D mono float32
        (24 kHz for the current Nero Kokoro path).
    sample_rate : int
        Sample rate in Hz.
    cfg : dict, optional
        Overrides for ``DEFAULT_CONFIG``. If omitted or if ``cfg["enabled"]``
        is falsy, this function is a passthrough and returns ``samples``
        unchanged (same shape, same dtype).

    Returns
    -------
    np.ndarray
        Processed audio, same shape and dtype as the input.
    """
    merged = _merge_config(cfg)

    if not merged.get("enabled"):
        # Passthrough — banshee is off. Return the input untouched.
        return samples

    # Import lazily so the base app runs without pedalboard installed.
    try:
        from pedalboard import (
            Chorus,
            Compressor,
            Delay,
            Distortion,
            Gain,
            HighpassFilter,
            HighShelfFilter,
            Limiter,
            LowShelfFilter,
            Mix,
            PeakFilter,
            Pedalboard,
            PitchShift,
            Reverb,
        )
    except ImportError as exc:  # noqa: BLE001 — surfaced honestly to caller
        raise RuntimeError(
            "banshee fx requested but pedalboard is not installed. "
            "Install with:  pip install -r requirements-voice-effects.txt"
        ) from exc

    # --- Parallel Mix: dry + ghost + shimmer -----------------------------
    parallel: list = [Gain(gain_db=0.0)]  # Chain 1: dry passthrough (always on)

    ghost_cfg = merged["ghost"]
    if ghost_cfg.get("enabled"):
        # Chain 2: the ghost — quiet octave-down shadow
        parallel.append(
            Pedalboard(
                [
                    Delay(delay_seconds=float(ghost_cfg["delay_seconds"]), mix=1.0),
                    PitchShift(semitones=float(ghost_cfg["semitones"])),
                    Gain(gain_db=float(ghost_cfg["gain_db"])),
                ]
            )
        )

    shimmer_cfg = merged["shimmer"]
    if shimmer_cfg.get("enabled"):
        # Chain 3: the shimmer — very quiet ethereal high partial
        parallel.append(
            Pedalboard(
                [
                    Delay(delay_seconds=float(shimmer_cfg["delay_seconds"]), mix=1.0),
                    PitchShift(semitones=float(shimmer_cfg["semitones"])),
                    Gain(gain_db=float(shimmer_cfg["gain_db"])),
                ]
            )
        )

    # --- Serial chain after the parallel mix -----------------------------
    chain: list = [Mix(parallel)]

    # v4 polish: very light saturation on the composite voice for
    # perceived analog warmth. Placed right after the Mix so ghost + dry
    # get the same harmonic treatment.
    sat_cfg = merged["saturation"]
    if sat_cfg.get("enabled"):
        chain.append(Distortion(drive_db=float(sat_cfg["drive_db"])))

    chorus_cfg = merged["chorus"]
    if chorus_cfg.get("enabled"):
        chain.append(
            Chorus(
                rate_hz=float(chorus_cfg["rate_hz"]),
                depth=float(chorus_cfg["depth"]),
                centre_delay_ms=float(chorus_cfg["centre_delay_ms"]),
                feedback=float(chorus_cfg["feedback"]),
                mix=float(chorus_cfg["mix"]),
            )
        )

    # v4 polish: three-band EQ inserted before the highpass so the shelves
    # shape body before we cut the sub-low, and the peak filter can trim
    # muddiness in the 300-400 Hz range without fighting the highpass.
    eq_cfg = merged["eq"]
    if eq_cfg.get("enabled"):
        ls = eq_cfg["low_shelf"]
        chain.append(LowShelfFilter(
            cutoff_frequency_hz=float(ls["cutoff_frequency_hz"]),
            gain_db=float(ls["gain_db"]),
            q=float(ls["q"]),
        ))
        pk = eq_cfg["peak"]
        chain.append(PeakFilter(
            cutoff_frequency_hz=float(pk["cutoff_frequency_hz"]),
            gain_db=float(pk["gain_db"]),
            q=float(pk["q"]),
        ))
        hs = eq_cfg["high_shelf"]
        chain.append(HighShelfFilter(
            cutoff_frequency_hz=float(hs["cutoff_frequency_hz"]),
            gain_db=float(hs["gain_db"]),
            q=float(hs["q"]),
        ))

    hp_cfg = merged["highpass"]
    if hp_cfg.get("enabled"):
        chain.append(
            HighpassFilter(cutoff_frequency_hz=float(hp_cfg["cutoff_frequency_hz"]))
        )

    rev_cfg = merged["reverb"]
    if rev_cfg.get("enabled"):
        chain.append(
            Reverb(
                room_size=float(rev_cfg["room_size"]),
                damping=float(rev_cfg["damping"]),
                wet_level=float(rev_cfg["wet_level"]),
                dry_level=float(rev_cfg["dry_level"]),
                width=float(rev_cfg["width"]),
            )
        )

    # Output pitch shift is applied AFTER all internal FX so the ghost's
    # relative interval to the dry voice is preserved — everything shifts
    # together as a unit.
    op_cfg = merged["output_pitch_shift"]
    if op_cfg.get("enabled") and abs(float(op_cfg.get("semitones", 0))) > 0.001:
        chain.append(PitchShift(semitones=float(op_cfg["semitones"])))

    # v4 polish: gentle transparent compression, placed after pitch shift
    # so it evens out dynamics of the whole processed voice. Keeps long-form
    # listening comfortable by controlling peaks without pumping.
    comp_cfg = merged["compressor"]
    if comp_cfg.get("enabled"):
        chain.append(Compressor(
            threshold_db=float(comp_cfg["threshold_db"]),
            ratio=float(comp_cfg["ratio"]),
            attack_ms=float(comp_cfg["attack_ms"]),
            release_ms=float(comp_cfg["release_ms"]),
        ))

    # Limiter is always last so nothing clips regardless of upstream gain.
    lim_cfg = merged["limiter"]
    chain.append(
        Limiter(
            threshold_db=float(lim_cfg["threshold_db"]),
            release_ms=float(lim_cfg["release_ms"]),
        )
    )

    board = Pedalboard(chain)
    audio, _ = _ensure_mono_float32(samples)
    return board(audio, sample_rate)
