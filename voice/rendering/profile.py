"""voice.rendering.profile — the engine-agnostic RenderingProfile + its data loader.

A RenderingProfile describes **how speech should sound** — voice character + prosody —
never **how a specific engine produces it**. Per the frozen Rendering-Profile Charter:

  > A Voice Profile describes how speech should be rendered. It never contains
  > engine-specific implementation details. Engine bodies translate rendering profiles
  > into engine-native parameters.

It is **identity-blind**: `voice_character` is an ABSTRACT descriptor
(``"authoritative"``, ``"warm"``) — never an engine's native voice id and never a
persona name. The mapping abstract → native voice lives inside each engine body,
nowhere else.

Rendering data lives in its **own** file (`profiles.json`), separate from `cast.json`
(Identity) — the frozen "four concepts, never merged" law. The loader is fail-loud on
a malformed manifest; an *unknown* voice_id resolves to a documented default profile
(never a crash), so a persona without a declared rendering still speaks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_PROFILES_PATH = Path(__file__).resolve().parent / "profiles.json"

PAUSE_STYLES = frozenset({"tight", "natural", "spacious"})
DEFAULT_CHARACTER = "neutral"
DEFAULT_PAUSE = "natural"


class RenderingError(Exception):
    """A malformed rendering-profiles manifest (bad JSON, missing/typed field, invalid
    pause style / number). The one exception callers catch; each message names the
    profile and field. A *missing* profile is NOT an error — it resolves to a default."""


@dataclass(frozen=True)
class RenderingProfile:
    """Engine-agnostic rendering parameters. `voice_character` is abstract — the engine
    body, and only it, maps it to a native voice."""

    voice_character: str = DEFAULT_CHARACTER
    speed: float = 1.0
    pitch: float = 0.0
    energy: float = 0.5
    pause_style: str = DEFAULT_PAUSE
    schema_version: int = SCHEMA_VERSION

    def as_dict(self) -> dict:
        return {
            "voice_character": self.voice_character, "speed": self.speed,
            "pitch": self.pitch, "energy": self.energy,
            "pause_style": self.pause_style, "schema_version": self.schema_version,
        }


class RenderingProfiles:
    """Loaded per-persona base rendering data (Identity → base RenderingProfile)."""

    def __init__(self, profiles: dict) -> None:
        self._profiles = dict(profiles)

    def get(self, voice_id: str) -> RenderingProfile:
        """The persona's base profile, or a default for an unknown voice_id (never
        raises — a persona without a declared rendering still speaks)."""
        return self._profiles.get(voice_id, RenderingProfile())

    def voices(self) -> list[str]:
        return list(self._profiles)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "RenderingProfiles":
        path = Path(path) if path is not None else DEFAULT_PROFILES_PATH
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise RenderingError(f"rendering profiles not found at {path}") from None
        except OSError as exc:
            raise RenderingError(f"rendering profiles at {path} could not be read: {exc}") from None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RenderingError(f"rendering profiles at {path} is not valid JSON: {exc}") from None
        if not isinstance(data, dict):
            raise RenderingError(f"rendering profiles at {path} must be a JSON object")
        raw_profiles = data.get("profiles")
        if not isinstance(raw_profiles, dict):
            raise RenderingError(
                f"rendering profiles at {path}: missing required 'profiles' object"
            )
        built = {
            voice_id: _parse_profile(voice_id, entry, str(path))
            for voice_id, entry in raw_profiles.items()
        }
        return cls(built)


def _parse_profile(voice_id: str, entry: object, source: str) -> RenderingProfile:
    if not isinstance(entry, dict):
        raise RenderingError(f"rendering {source}: profile {voice_id!r} must be an object")

    character = entry.get("voice_character", DEFAULT_CHARACTER)
    if not isinstance(character, str) or not character.strip():
        raise RenderingError(
            f"rendering {source}: {voice_id!r} 'voice_character' must be a non-empty string"
        )
    pause = entry.get("pause_style", DEFAULT_PAUSE)
    if not isinstance(pause, str) or pause not in PAUSE_STYLES:
        raise RenderingError(
            f"rendering {source}: {voice_id!r} 'pause_style' must be one of {sorted(PAUSE_STYLES)}"
        )
    return RenderingProfile(
        voice_character=character.strip(),
        speed=_num(entry.get("speed", 1.0), voice_id, "speed", source, 0.5, 2.0),
        pitch=_num(entry.get("pitch", 0.0), voice_id, "pitch", source, -1.0, 1.0),
        energy=_num(entry.get("energy", 0.5), voice_id, "energy", source, 0.0, 1.0),
        pause_style=pause,
    )


def _num(value: object, voice_id: str, field: str, source: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RenderingError(f"rendering {source}: {voice_id!r} {field!r} must be a number")
    return max(lo, min(hi, float(value)))
