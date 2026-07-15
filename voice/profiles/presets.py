"""Bundled voice profile presets.

Add new profiles by defining a new VoiceProfile constant here and registering
it in PRESETS. Editing this file is a data change; the rest of Nero doesn't
need to know a new profile exists — it requests one by name.

Versioning discipline
---------------------
Concrete versions are frozen: once ``NERO_PRIME_V1`` (or any versioned
profile) is committed, its config is IMMUTABLE. Retuning the voice means:

    1. Define ``NERO_PRIME_V2`` with the new config.
    2. Update the ``NERO_PRIME`` alias below to point at v2.
    3. Leave ``NERO_PRIME_V1`` unchanged — reference recordings, tests,
       and documentation continue to work.

This lets Nero evolve without silently mutating the voice a user has
been listening to for months.
"""
from __future__ import annotations

from dataclasses import replace

from .profile import VoiceProfile


# --- Blend paths -----------------------------------------------------------
# Nero looks for a repo-local copy first (voice/blends/) and falls back to the
# iCloudDrive audition workspace if the repo copy is missing. That keeps the
# code portable — the profile still works on a fresh clone once the blend is
# copied in — but also works during exploration while blends live in iCloud.

from pathlib import Path as _Path

_REPO_BLENDS = _Path(__file__).resolve().parent.parent / "blends"
_WORKSPACE = r"C:\Users\tonij\iCloudDrive\Nero AI\voice_audition"


def _blend_path(repo_name: str, workspace_relpath: str) -> str:
    """Prefer the repo-local blend file; fall back to the iCloudDrive workspace."""
    repo_copy = _REPO_BLENDS / repo_name
    if repo_copy.exists():
        return str(repo_copy)
    return rf"{_WORKSPACE}\{workspace_relpath}"


_BLEND_MANBEARDOG = _blend_path(
    "nero_prime_v1.npy",
    r"manbeardog_blends\blend_11_heart_40_bella_30_nicole_30\blend.npy",
)

# For nero_whisper we want the pure Kokoro af_nicole voice — the audition
# generated its 6 WAVs but not a cached .npy for a single voice. We use the
# Manbeardog blend as a placeholder for MVP; the whisper character comes from
# the config (much slower + heavy pitch shift + banshee off). A future pass
# should cache single-voice style vectors alongside blends.
_BLEND_WHISPER = _BLEND_MANBEARDOG  # TODO: swap for a cached af_nicole vector


# ---------------------------------------------------------------------------
# NERO_PRIME_V1 — FROZEN 2026-07-13.  DO NOT EDIT.
# ---------------------------------------------------------------------------
# The winning voice from the audition + banshee iteration loop:
# - Manbeardog blend (heart 40 + bella 30 + nicole 30)
# - Kokoro speed 0.90
# - Output pitched -1.9 semitones
# - NO ghost / shimmer / chorus / highpass / reverb / saturation / EQ /
#   compressor — the character voice is presented naked. Only PitchShift
#   and Limiter run in the "banshee" chain.
#
# If a future retune is needed, define NERO_PRIME_V2 below and update the
# NERO_PRIME alias — leave V1 unchanged forever. Reference recordings live
# at voice_audition/selected_nero_voice/samples/.
NERO_PRIME_V1 = VoiceProfile(
    name="nero_prime_v1",
    description=(
        "Nero's canonical voice. FROZEN v1 tuning as of 2026-07-13. "
        "Manbeardog blend, pitched -1.9 semitones, spoken at 0.90 speed. "
        "No supernatural layer — just the character voice, tuned."
    ),
    blend_path=_BLEND_MANBEARDOG,
    speed=0.90,
    lang="en-us",
    banshee_config={
        "enabled":  True,
        "ghost":    {"enabled": False},
        "shimmer":  {"enabled": False},
        "chorus":   {"enabled": False},
        "highpass": {"enabled": False},
        "reverb":   {"enabled": False},
        "output_pitch_shift": {"enabled": True, "semitones": -1.9},
        "saturation": {"enabled": False},
        "eq":         {"enabled": False},
        "compressor": {"enabled": False},
        "limiter":  {"threshold_db": -1.0, "release_ms": 100.0},
    },
    text_prep_style="normal",
    notes=(
        "FROZEN 2026-07-13. Selected by Toni after listening to 138+ audition "
        "samples spanning single voices, 12 Manbeardog blends, four banshee "
        "iterations (v1/v2/v3/v4 core/v4 full), and three dry_tuned pitch "
        "variants. The winning direction: keep the blend character, drop the "
        "supernatural layer, sit the voice slightly lower and slightly slower. "
        "Do NOT edit this profile — create NERO_PRIME_V2 for future tuning."
    ),
)


# NERO_PRIME is the current-version pointer. Bumping the version means
# defining a new frozen NERO_PRIME_V<N> above and updating this line.
NERO_PRIME = replace(NERO_PRIME_V1, name="nero_prime")


# ---------------------------------------------------------------------------
# Emotional-state profiles (unfrozen MVPs — subject to tuning)
# ---------------------------------------------------------------------------

NERO_WHISPER = VoiceProfile(
    name="nero_whisper",
    description="Nero speaking quietly, close-mic. Late-night / private mode.",
    blend_path=_BLEND_WHISPER,
    speed=0.85,
    lang="en-us",
    banshee_config=None,  # No FX — the whisper character is naked
    text_prep_style="normal",
    notes=(
        "MVP placeholder — uses the Manbeardog blend at 85% speed with no "
        "banshee FX. Future improvement: swap blend_path for a cached "
        "af_nicole style vector (Kokoro's dedicated whispered voice) for a "
        "truer whisper character."
    ),
)


NERO_LATE_NIGHT = VoiceProfile(
    name="nero_late_night",
    description="Deeper, slower, mildly haunted. For quiet late-night use.",
    blend_path=_BLEND_MANBEARDOG,
    speed=0.85,
    lang="en-us",
    banshee_config={
        "enabled":  True,
        "ghost":    {"delay_seconds": 0.020, "semitones": -5, "gain_db": -14},
        "shimmer":  {"enabled": False},
        "chorus":   {"rate_hz": 0.7, "depth": 0.20, "mix": 0.20},
        "highpass": {"cutoff_frequency_hz": 80.0},
        "reverb":   {"room_size": 0.20, "damping": 0.85, "wet_level": 0.06, "dry_level": 0.85},
        "output_pitch_shift": {"enabled": True, "semitones": -4},
    },
    text_prep_style="normal",
    notes=(
        "MVP — untuned by Toni's ear yet. Uses Manbeardog blend at 85% speed, "
        "pitched -4 semitones (deeper than nero_prime_v1), with a barely-there "
        "ghost + minimal reverb for a 'sitting up with you at 3AM' character. "
        "Re-tune when Toni gets to nighttime testing."
    ),
)


# Registry — the only public API. Callers request profiles by name.
PRESETS: dict[str, VoiceProfile] = {
    NERO_PRIME.name:      NERO_PRIME,       # current-version pointer
    NERO_PRIME_V1.name:   NERO_PRIME_V1,    # frozen concrete version
    NERO_WHISPER.name:    NERO_WHISPER,
    NERO_LATE_NIGHT.name: NERO_LATE_NIGHT,
}


def get_profile(name: str) -> VoiceProfile:
    """Look up a profile by name. Raises KeyError with a helpful message if unknown."""
    if name not in PRESETS:
        available = ", ".join(sorted(PRESETS.keys()))
        raise KeyError(f"unknown voice profile: {name!r}. Available: {available}")
    return PRESETS[name]
