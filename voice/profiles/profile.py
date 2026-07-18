"""The VoiceProfile dataclass and the synthesize_with_profile helper.

A VoiceProfile is the *logical identity* the brain requests. It bundles the
implementation details (blend, speed, effects) so callers never touch them.

    from voice.profiles import get_profile, synthesize_with_profile
    from kokoro_onnx import Kokoro

    kokoro = Kokoro("models/kokoro-v1.0.onnx", "models/voices-v1.0.bin")
    profile = get_profile("nero_prime")
    samples, rate = synthesize_with_profile(profile, "Good evening.", kokoro)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class VoiceProfile:
    """A logical voice identity — everything needed to render Nero speaking as X.

    Fields
    ------
    name : str
        Stable identifier, e.g. "nero_prime", "nero_whisper".
    description : str
        Human-readable one-liner of what this profile represents.
    blend_path : str | Path
        Path to the cached blend.npy (a Kokoro voice style vector).
        Can be a path to a single-voice pack export or a Manbeardog blend.
    speed : float
        Kokoro speed parameter. 1.0 = natural. Lower = slower.
    lang : str
        Kokoro lang code. Default "en-us".
    banshee_config : dict[str, Any] | None
        Optional banshee FX config override dict. None means no FX.
    text_prep_style : str
        Reserved for future text preprocessing (pause insertion, chunking, etc).
        Currently just a label; the preprocessor is not yet implemented.
    notes : str
        Design notes / character description. Not consumed at runtime — for humans.
    """

    name: str
    description: str
    blend_path: str | Path
    speed: float = 1.0
    lang: str = "en-us"
    banshee_config: dict[str, Any] | None = None
    text_prep_style: str = "normal"
    notes: str = ""

    def load_blend(self) -> np.ndarray:
        """Load the profile's blend vector from disk. Cached across calls."""
        if not hasattr(self, "_cached_blend"):
            self._cached_blend = np.load(str(self.blend_path))
        return self._cached_blend


def synthesize_with_profile(
    profile: VoiceProfile,
    text: str,
    kokoro: Any,
) -> tuple[np.ndarray, int]:
    """Synthesize `text` using `profile` and return (samples, sample_rate).

    Parameters
    ----------
    profile : VoiceProfile
        The logical voice identity to speak as.
    text : str
        Utterance to synthesize.
    kokoro : Kokoro
        An initialized kokoro_onnx.Kokoro instance (typed loosely to avoid
        forcing a heavy import at module load).

    Returns
    -------
    (samples, sample_rate) : tuple[np.ndarray, int]
        Audio samples ready to write / stream / play.
    """
    blend_vec = profile.load_blend()
    samples, sample_rate = kokoro.create(
        text,
        voice=blend_vec,
        speed=float(profile.speed),
        lang=profile.lang,
    )

    if profile.banshee_config:
        # Lazy import so the module is usable even if pedalboard is absent
        # (profile just won't be able to run its effects).
        from voice.effects.banshee import apply_banshee_fx

        samples = apply_banshee_fx(samples, sample_rate, profile.banshee_config)

    return samples, sample_rate
