"""voice.profiles.loader — load & validate the voice cast manifest (Stage 5).

*"The system knows how to load voices. It does not know what a voice is."*

This is a **thin translation layer** and deliberately nothing more. It reads
`cast.json`, validates it, and builds immutable structured objects that feed the
existing machinery: a tuple of `VoiceCapability` (Stage 2, the Voice Capability
Graph) and a `fallback_map` + `emergency_voice` (Stage 4, the Voice Manager).

It **may**: read JSON, validate the schema, build immutable objects, and produce
inputs for Stages 2 and 4.
It **may not**: synthesize audio, select voices, perform fallback decisions,
manage health, create engines, touch GPU/model state, or import any executive
system (Trust Engine, Capability Registry, Action Journal, memory).

Data flows **one way only**:  cast.json → loader → Cast → (graph + manager config).
Nothing flows back.

Every malformed / inconsistent manifest becomes a single, loud, safe
:class:`CastError` — never a leaked ``JSONDecodeError`` / ``FileNotFoundError`` /
``KeyError`` / raw validation exception. Each message names the voice, the field,
and the reason.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..local_tts.voice_capability_graph import (
    QualityLevel, VoiceCapability, VoiceCapabilityGraph,
)

# The shipped manifest ships beside this module.
DEFAULT_CAST_PATH = Path(__file__).resolve().parent / "cast.json"

_VALID_QUALITIES = {q.value for q in QualityLevel}


class CastError(Exception):
    """Any malformed or inconsistent cast manifest — the one exception callers
    catch. Raised for bad JSON, a missing file, a duplicate/undefined voice, a
    dangling or circular fallback, a missing engine binding, or a language a bound
    engine cannot produce. The message always identifies the voice, the field, and
    the reason, so a broken cast fails loudly and safely."""


@dataclass(frozen=True)
class VoiceProfile:
    """One validated cast entry — declarative identity only, never behavior."""

    voice_id: str
    engine: str
    languages: tuple[str, ...]
    features: tuple[str, ...]
    quality: QualityLevel
    fallbacks: tuple[str, ...]

    def capability(self) -> VoiceCapability:
        """The Stage 2 capability this profile declares (identity, not availability)."""
        return VoiceCapability(
            voice_id=self.voice_id, engine=self.engine, languages=self.languages,
            features=self.features, quality=self.quality,
        )


@dataclass(frozen=True)
class Cast:
    """The validated manifest as Stage 2 + Stage 4 inputs — an immutable result.

    - ``profiles``        — ordered, validated voice profiles.
    - ``fallback_map``    — ``{voice_id: (fallback voice_ids…)}`` for the VoiceManager.
    - ``emergency_voice`` — the last-resort voice id (validated to exist), or "" for
      an empty cast.

    The Cast holds no engines and makes no decisions. It only *describes*.
    """

    profiles: tuple[VoiceProfile, ...]
    fallback_map: dict          # {voice_id: tuple[str, ...]}
    emergency_voice: str

    def capabilities(self) -> tuple[VoiceCapability, ...]:
        return tuple(p.capability() for p in self.profiles)

    def populate(
        self, graph: VoiceCapabilityGraph, engines: dict
    ) -> VoiceCapabilityGraph:
        """Register every profile into ``graph`` using the injected engine map
        ``{engine_name: TTSEngine}``.

        This is where **engine-binding** validation happens — the loader never
        creates engines, the caller injects them:
          1. every declared engine must be present in ``engines``;
          2. every declared language must be one the bound engine can actually
             produce (Stage 4 finding — a mis-declared language would otherwise make
             a voice silently vanish at runtime via the manager's language gate).

        Validation runs fully *before* any registration, so a bad cast never leaves
        the graph half-populated. Returns the same ``graph`` for chaining.
        """
        for p in self.profiles:
            engine = engines.get(p.engine)
            if engine is None:
                raise CastError(
                    f"voice {p.voice_id!r}: field 'engine' -> no engine named "
                    f"{p.engine!r} was provided to populate()"
                )
            try:
                supported = set(engine.languages())
            except Exception as exc:  # noqa: BLE001 - a broken engine probe is a cast-wiring failure
                raise CastError(
                    f"voice {p.voice_id!r}: engine {p.engine!r} failed to report "
                    f"languages: {exc}"
                ) from None
            missing = [lang for lang in p.languages if lang not in supported]
            if missing:
                raise CastError(
                    f"voice {p.voice_id!r}: field 'languages' declares {missing!r} "
                    f"but engine {p.engine!r} supports {sorted(supported)!r} — a "
                    f"mis-declared language would silently drop this voice at runtime"
                )

        for p in self.profiles:                 # all valid — now register
            graph.register(p.capability(), engines[p.engine])
        return graph


def load_cast(path: str | Path | None = None) -> Cast:
    """Read, parse, and validate a cast manifest into an immutable :class:`Cast`.

    Structural validation only (no engines needed): JSON shape, required fields,
    unique voice ids, an existing emergency voice, existing fallback targets, and no
    self / circular fallback chains. Engine-binding + language validation happen
    later in :meth:`Cast.populate`, when the caller injects real engines.

    Any failure — bad JSON, missing file, malformed structure — raises
    :class:`CastError`, never a lower-level exception.
    """
    path = Path(path) if path is not None else DEFAULT_CAST_PATH

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise CastError(f"cast manifest not found at {path}") from None
    except OSError as exc:
        raise CastError(f"cast manifest at {path} could not be read: {exc}") from None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CastError(f"cast manifest at {path} is not valid JSON: {exc}") from None

    if not isinstance(data, dict):
        raise CastError(
            f"cast manifest at {path} must be a JSON object, got {type(data).__name__}"
        )
    return _build_cast(data, source=str(path))


# ----------------------------------------------------------------------------- #
# internal builders — pure validation, no behavior                              #
# ----------------------------------------------------------------------------- #
def _build_cast(data: dict, source: str) -> Cast:
    voices_raw = data.get("voices")
    if voices_raw is None:
        raise CastError(f"cast {source}: missing required top-level 'voices' array")
    if not isinstance(voices_raw, list):
        raise CastError(
            f"cast {source}: 'voices' must be an array, got {type(voices_raw).__name__}"
        )

    profiles: list[VoiceProfile] = []
    seen: set[str] = set()
    for i, entry in enumerate(voices_raw):
        p = _parse_profile(entry, i, source)
        if p.voice_id in seen:
            raise CastError(f"cast {source}: duplicate voice_id {p.voice_id!r}")
        seen.add(p.voice_id)
        profiles.append(p)

    ids = {p.voice_id for p in profiles}

    # emergency: any declared emergency must exist; a non-empty cast must declare one.
    emergency = data.get("emergency") or ""
    if not isinstance(emergency, str):
        raise CastError(
            f"cast {source}: 'emergency' must be a voice_id string, got "
            f"{type(emergency).__name__}"
        )
    if emergency and emergency not in ids:
        raise CastError(
            f"cast {source}: 'emergency' voice {emergency!r} is not defined in 'voices'"
        )
    if profiles and not emergency:
        raise CastError(
            f"cast {source}: 'emergency' voice is required when voices are defined"
        )

    # fallback targets: must exist, no self-reference.
    fallback_map: dict[str, tuple[str, ...]] = {}
    for p in profiles:
        for fb in p.fallbacks:
            if fb == p.voice_id:
                raise CastError(
                    f"voice {p.voice_id!r}: field 'fallbacks' references itself"
                )
            if fb not in ids:
                raise CastError(
                    f"voice {p.voice_id!r}: field 'fallbacks' target {fb!r} is not a "
                    f"defined voice"
                )
        if p.fallbacks:
            fallback_map[p.voice_id] = p.fallbacks

    _reject_cycles(fallback_map, source)

    return Cast(
        profiles=tuple(profiles), fallback_map=fallback_map, emergency_voice=emergency
    )


def _parse_profile(entry: object, index: int, source: str) -> VoiceProfile:
    if not isinstance(entry, dict):
        raise CastError(
            f"cast {source}: voices[{index}] must be an object, got "
            f"{type(entry).__name__}"
        )

    voice_id = entry.get("voice_id")
    if not isinstance(voice_id, str) or not voice_id.strip():
        raise CastError(
            f"cast {source}: voices[{index}] missing a required non-empty 'voice_id'"
        )
    voice_id = voice_id.strip()

    engine = entry.get("engine")
    if not isinstance(engine, str) or not engine.strip():
        raise CastError(f"voice {voice_id!r}: missing a required non-empty 'engine'")
    engine = engine.strip()

    languages = _str_tuple(entry.get("languages", []), voice_id, "languages")
    features = _str_tuple(entry.get("features", []), voice_id, "features")
    fallbacks = _str_tuple(entry.get("fallbacks", []), voice_id, "fallbacks")

    quality_raw = entry.get("quality", QualityLevel.STANDARD.value)
    if not isinstance(quality_raw, str) or quality_raw not in _VALID_QUALITIES:
        raise CastError(
            f"voice {voice_id!r}: field 'quality' is {quality_raw!r}, must be one of "
            f"{sorted(_VALID_QUALITIES)}"
        )

    return VoiceProfile(
        voice_id=voice_id, engine=engine, languages=languages, features=features,
        quality=QualityLevel(quality_raw), fallbacks=fallbacks,
    )


def _str_tuple(value: object, voice_id: str, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(x, str) and x.strip() for x in value
    ):
        raise CastError(
            f"voice {voice_id!r}: field {field_name!r} must be an array of non-empty "
            f"strings"
        )
    return tuple(x.strip() for x in value)


def _reject_cycles(fallback_map: dict, source: str) -> None:
    """DFS cycle detection over the declared fallback graph. The VoiceManager walks
    only one level, but a cycle in the *data* is a manifest bug — reject it loudly
    so the boundary stays clean."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> None:
        color[node] = GRAY
        stack.append(node)
        for nxt in fallback_map.get(node, ()):
            state = color.get(nxt, WHITE)
            if state == GRAY:                       # nxt is on the current stack
                start = stack.index(nxt)
                chain = " -> ".join(stack[start:] + [nxt])
                raise CastError(f"cast {source}: circular fallback chain: {chain}")
            if state == WHITE:
                visit(nxt)
        stack.pop()
        color[node] = BLACK

    for node in list(fallback_map):
        if color.get(node, WHITE) == WHITE:
            visit(node)
