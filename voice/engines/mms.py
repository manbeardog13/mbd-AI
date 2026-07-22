"""voice.engines.mms — the MMS Croatian engine body (a second driver).

The second real engine body: Meta **MMS-TTS** for Croatian (`hr`), exposed through the
sealed `BaseTTSEngine` contract exactly like Kokoro. Adding it changes **no** upper
layer — routing to Croatian is pure capability (the Stage-4 language gate on
`VoiceCapability.languages`), never special-case logic.

> **Charter principle:** *The architecture never learns that Croatia exists.* The
> Capability Graph understands `language = "hr"`. It never understands "Croatia",
> "Croatian people", or "Croatian rules". That separation lets NERO grow to dozens of
> languages without accumulating special cases.

**Not a strangler-fig wrap.** Kokoro wrapped the proven `app/tts.py`; **MMS has no
existing code** — so `RealMMSBackend` is a *new integration seam* that lazily wraps a
**future `app/mms_tts.py`** (to be written and validated on the RTX-4070, mirroring
`app/tts.py`'s shape: `available(cfg)`, `synthesize(cfg, text)`, `SAMPLE_RATE`). In
the cloud that module is absent, so `RealMMSBackend` reports not-ready and never
raises. `FakeMMSBackend` proves the contract offline.

**Permanent architectural rule — preprocessing stays in the backend, forever.**
Croatian punctuation, text normalization, abbreviation expansion, and phonemization
belong **inside `RealMMSBackend`** — never in the Voice Manager, Capability Graph,
Startup, or Telemetry. The upper layers remain blissfully ignorant of language-
specific detail.

**No smart fallback.** If Croatian cannot be produced, the system fails honestly
(`text_only`) — it never silently substitutes English. Language substitution is a
future *conversational-layer* decision, never a Voice one; the engine only renders
what it is handed and reports whether it can.

This body, like Kokoro, is deliberately built in *parallel* rather than on a shared
base: two engines are not enough evidence to justify a shared engine base, and MMS
already diverges (16 kHz vs. Kokoro's 24 kHz). A shared `BackendEngine` waits for a
third engine (or proven stable convergence) — good duplication is cheaper than bad
inheritance.

*Note (deferred): once a **third** engine exists, the scattered metadata (name /
languages / voices / sample_rate) should become a first-class immutable
``EngineIdentity`` object rather than more constructor fields — not implemented here.*
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..local_tts.base import BaseTTSEngine, VoiceRequest

_MMS_SAMPLE_RATE = 16_000  # Meta MMS-TTS (VITS) outputs 16 kHz mono; differs from Kokoro's 24 kHz

# Abstract voice_character -> native MMS speaker. MMS-hrv is typically single-speaker,
# so this table is intentionally minimal (personas differ mainly by speed/prosody, not
# timbre). Kept ENGINE-LOCAL and PARALLEL to Kokoro's — deliberately NOT a shared base.
_MMS_CHARACTER_SPEAKERS: dict = {}          # (populated on the 4070 if MMS ever exposes speakers)
_MMS_DEFAULT_SPEAKER = "hrv"


@runtime_checkable
class MMSBackend(Protocol):
    """The narrow seam between the engine body and real MMS synthesis. `voice`/`speed`
    are engine-native rendering parameters (optional + defaulted for backward compat)."""

    sample_rate: int

    def is_ready(self) -> bool: ...
    def synthesize(self, text: str, *, voice: str | None = None, speed: float = 1.0) -> bytes | None: ...


class MMSEngine(BaseTTSEngine):
    """Meta MMS-TTS (Croatian) exposed through the sealed contract. Implements only
    `_available()` / `_synthesize()` — no `speak`, `fallback`, `select_voice`,
    `recover`, or `retry`, and no language branching: it declares `languages` as data
    and delegates, so the architecture routes to it by capability, not by name."""

    name = "mms_hr"

    def __init__(
        self,
        backend: MMSBackend,
        *,
        name: str = "mms_hr",
        languages: tuple[str, ...] = ("hr",),
        voices: tuple[str, ...] = (),
        voice_map: dict | None = None,
        default_voice: str = _MMS_DEFAULT_SPEAKER,
    ) -> None:
        super().__init__()
        self.name = name                       # must equal the cast's engine name
        self._backend = backend
        self._languages = tuple(languages)
        self._voices = tuple(voices)
        self._voice_map = dict(voice_map or _MMS_CHARACTER_SPEAKERS)  # abstract char -> native speaker
        self._default_voice = default_voice

    def _available(self) -> bool:
        return bool(self._backend.is_ready())          # a flashlight, not a lighthouse keeper

    def _synthesize(self, request: VoiceRequest) -> tuple[bytes, int]:
        # Translate the contract to the backend. `delivery` carries a RenderingProfile
        # (rendering parameters) when Voice Casting ran; the engine — and ONLY the engine
        # — maps the abstract voice_character to a native MMS speaker. Semantic intent
        # never reaches here. Language-specific preprocessing lives inside the backend.
        native_voice, speed = self._render_params(request.delivery)
        data = self._backend.synthesize(request.text, voice=native_voice, speed=speed)  # bytes | None
        rate = int(getattr(self._backend, "sample_rate", _MMS_SAMPLE_RATE) or 0)
        return (data or b"", rate)                      # None/empty -> clean failure

    def _render_params(self, delivery: object) -> tuple[str, float]:
        """Map an (optional) RenderingProfile in `delivery` to native params. Absent or
        unknown -> the engine default speaker + neutral speed (honest, never a crash)."""
        rp = delivery if isinstance(delivery, dict) else {}
        character = rp.get("voice_character")
        native_voice = self._voice_map.get(character, self._default_voice) if character else self._default_voice
        speed = rp.get("speed", 1.0)
        speed = float(speed) if isinstance(speed, (int, float)) and not isinstance(speed, bool) else 1.0
        return native_voice, speed


class FakeMMSBackend:
    """A cloud-safe test double — no model, no GPU, no `app`. `audio=None` simulates a
    clean failure; `raises=True` simulates a backend crash (the envelope contains it).
    Counts calls to expose accidental retries."""

    def __init__(self, *, ready: bool = True, audio: bytes | None = b"FAKE-HR-WAV",
                 raises: bool = False, sample_rate: int = _MMS_SAMPLE_RATE) -> None:
        self._ready = ready
        self._audio = audio
        self._raises = raises
        self.sample_rate = sample_rate
        self.calls = 0
        self.last_voice: str | None = None      # records the native params it received
        self.last_speed: float = 1.0

    def is_ready(self) -> bool:
        return self._ready

    def synthesize(self, text: str, *, voice: str | None = None, speed: float = 1.0) -> bytes | None:
        self.calls += 1
        self.last_voice, self.last_speed = voice, speed     # proves the RenderingProfile arrived
        if self._raises:
            raise RuntimeError("fake MMS backend failure")
        return self._audio


class RealMMSBackend:
    """Bridges the engine body to a **future** `app/mms_tts.py` (the RTX-4070's real
    Croatian synthesis). This is a NEW integration seam, not a wrap of existing code —
    `app.mms_tts` does not exist yet, so in the cloud this reports not-ready and never
    raises. The import is lazy so `voice/engines/` stays importable without MMS deps.

    Language-specific preprocessing (normalization, abbreviations, phonemes) belongs to
    that `app/mms_tts.py` layer, never here or above. Expected shape (to be provided on
    the 4070): ``available(cfg) -> bool``, ``synthesize(cfg, text) -> bytes | None``,
    ``SAMPLE_RATE``.
    """

    def __init__(self, cfg, *, language: str = "hr") -> None:
        self._cfg = cfg
        self._language = language
        self._checked = False       # has the (relatively expensive) dependency probe run?
        self._ready = False
        self.sample_rate = _MMS_SAMPLE_RATE

    def is_ready(self) -> bool:
        # Cache the DEPENDENCY PROBE (not a synthesis success); reality changes surface
        # at synthesize() time and feed Engine Health, never this flag.
        if not self._checked:
            self._ready = self._probe()
            self._checked = True
        return self._ready

    def _probe(self) -> bool:
        try:
            from app import mms_tts     # lazy — not present in the cloud (4070 provides it)
        except Exception:  # noqa: BLE001 - no MMS layer available -> simply not ready
            return False
        try:
            self.sample_rate = int(getattr(mms_tts, "SAMPLE_RATE", _MMS_SAMPLE_RATE)) or _MMS_SAMPLE_RATE
            return bool(mms_tts.available(self._cfg))
        except Exception:  # noqa: BLE001 - a broken probe is simply not ready, never a crash
            return False

    def synthesize(self, text: str, *, voice: str | None = None, speed: float = 1.0) -> bytes | None:
        # `voice`/`speed` are accepted so the engine can pass rendering params; honoring
        # them belongs to the future `app/mms_tts.py` (4070). The seam carries them now.
        try:
            from app import mms_tts
            return mms_tts.synthesize(self._cfg, text)      # bytes | None (best-effort)
        except Exception:  # noqa: BLE001 - real failures become a clean None -> AudioResult(ok=False)
            return None
