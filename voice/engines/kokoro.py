"""voice.engines.kokoro — the Kokoro engine body (a contract adapter).

*"How does NERO turn the abstract engine contract into real local speech?"*

`KokoroEngine` exposes the proven `app/tts.py` (Kokoro) through the sealed
`BaseTTSEngine` interface. It is a **docking adapter, not a rebuild**: `app/tts.py`
is wrapped, never modified, refactored, or moved (strangler-fig). The engine body is
a simple worker — it turns text into audio and reports whether it can, and nothing
more. It never chooses a voice, decides fallback, mutates health, ranks engines, or
learns — those live above it, sealed.

Split (approved):
  * **KokoroEngine** owns contract translation · metadata · backend delegation.
    It does NOT own model loading, GPU, file paths, or downloads.
  * **RealKokoroBackend** owns the `app.tts` bridge + the real Kokoro lifecycle. It
    is the ONLY place that imports `app.tts`, and it does so **lazily** so this
    package stays importable where Kokoro's dependencies do not exist.
  * **FakeKokoroBackend** is a cloud-safe test double (no model, no GPU, no `app`).

The engine implements only `_available()` / `_synthesize()`; the sealed
`BaseTTSEngine` envelope owns timing, exception containment, `AudioResult` creation,
and health bookkeeping — the body never bypasses it.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..local_tts.base import BaseTTSEngine, VoiceRequest

_KOKORO_SAMPLE_RATE = 24_000  # Kokoro outputs 24 kHz mono (see app/tts.py SAMPLE_RATE)

# Abstract voice_character -> native Kokoro voice. This engine-specific table is the
# ONLY place that knows Kokoro voice ids; a RenderingProfile never carries them (the
# frozen Rendering-Profile Charter). Unknown characters fall back to the default voice.
_KOKORO_CHARACTER_VOICES = {
    "balanced": "af_heart",
    "authoritative": "am_michael",
    "commanding": "am_adam",
    "warm": "af_bella",
    "calm": "af_sarah",
    "soft": "af_sarah",
    "alert": "am_adam",
    "intense": "am_michael",
    "gentle": "af_nicole",
    "neutral": "af_heart",
}
_KOKORO_DEFAULT_VOICE = "af_heart"


@runtime_checkable
class KokoroBackend(Protocol):
    """The narrow seam between the engine body and real synthesis. A backend does the
    real work; the engine only translates the contract to it. `voice`/`speed` are the
    engine-native rendering parameters (optional + defaulted, so text-only callers and
    older backends keep working)."""

    sample_rate: int

    def is_ready(self) -> bool: ...
    def synthesize(self, text: str, *, voice: str | None = None, speed: float = 1.0) -> bytes | None: ...


class KokoroEngine(BaseTTSEngine):
    """Kokoro exposed through the sealed contract. Implements only `_available()` and
    `_synthesize()` — no `speak`, `fallback`, `select_voice`, `recover`, or `retry`:
    those belong to the Voice Manager and Engine Health, never to an engine body."""

    name = "kokoro"

    def __init__(
        self,
        backend: KokoroBackend,
        *,
        name: str = "kokoro",
        languages: tuple[str, ...] = ("en",),
        voices: tuple[str, ...] = (),
        voice_map: dict | None = None,
        default_voice: str = _KOKORO_DEFAULT_VOICE,
    ) -> None:
        super().__init__()
        self.name = name                       # must equal the cast's engine name
        self._backend = backend
        self._languages = tuple(languages)
        self._voices = tuple(voices)
        self._voice_map = dict(voice_map or _KOKORO_CHARACTER_VOICES)  # abstract char -> native
        self._default_voice = default_voice

    def _available(self) -> bool:
        # A flashlight, not a lighthouse keeper: delegate to the backend's cheap probe.
        return bool(self._backend.is_ready())

    def _synthesize(self, request: VoiceRequest) -> tuple[bytes, int]:
        # Translate the contract to the backend. The envelope has already guarded empty
        # text and unavailability, and contains any exception raised here. `delivery`
        # carries a RenderingProfile (rendering parameters) when Voice Casting ran; the
        # engine — and ONLY the engine — maps the abstract voice_character to a native
        # Kokoro voice. Semantic intent (emotion/authority) never reaches here.
        native_voice, speed = self._render_params(request.delivery)
        data = self._backend.synthesize(request.text, voice=native_voice, speed=speed)  # bytes | None
        rate = int(getattr(self._backend, "sample_rate", _KOKORO_SAMPLE_RATE) or 0)
        return (data or b"", rate)                          # None/empty -> clean failure

    def _render_params(self, delivery: object) -> tuple[str, float]:
        """Map an (optional) RenderingProfile in `delivery` to native params. Absent or
        unknown -> the engine default voice + neutral speed (honest, never a crash);
        this keeps text-only / pre-casting requests working unchanged."""
        rp = delivery if isinstance(delivery, dict) else {}
        character = rp.get("voice_character")
        native_voice = self._voice_map.get(character, self._default_voice) if character else self._default_voice
        speed = rp.get("speed", 1.0)
        speed = float(speed) if isinstance(speed, (int, float)) and not isinstance(speed, bool) else 1.0
        return native_voice, speed


class FakeKokoroBackend:
    """A cloud-safe test double — no model, no GPU, no `app` import. `audio=None`
    simulates a clean synthesis failure; `raises=True` simulates a backend crash
    (the engine envelope must contain it). Counts calls to expose accidental
    retries."""

    def __init__(self, *, ready: bool = True, audio: bytes | None = b"FAKE-WAV",
                 raises: bool = False, sample_rate: int = _KOKORO_SAMPLE_RATE) -> None:
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
        self.calls += 1                                     # exactly-once is asserted by tests
        self.last_voice, self.last_speed = voice, speed     # proves the RenderingProfile arrived
        if self._raises:
            raise RuntimeError("fake Kokoro backend failure")
        return self._audio


class RealKokoroBackend:
    """Bridges the engine body to the proven `app/tts.py`. This is the ONLY place
    that touches `app.tts`, and the import is **lazy** so the package remains
    importable without Kokoro's dependencies. Functional only where those deps and
    the model exist — the RTX-4070; elsewhere it reports not-ready and never raises.
    """

    def __init__(self, cfg) -> None:
        self._cfg = cfg
        self._checked = False       # has the (relatively expensive) dependency probe run?
        self._ready = False
        self.sample_rate = _KOKORO_SAMPLE_RATE

    def is_ready(self) -> bool:
        # Cache the DEPENDENCY PROBE (not a synthesis success). Dependency presence is
        # stable within a run; reality changes (model unload / GPU fail) surface at
        # synthesize() time, feeding Engine Health — not this flag.
        if not self._checked:
            self._ready = self._probe()
            self._checked = True
        return self._ready

    def _probe(self) -> bool:
        try:
            from app import tts     # lazy — package stays importable without Kokoro deps
        except Exception:  # noqa: BLE001 - no app/tts available -> simply not ready
            return False
        try:
            self.sample_rate = int(getattr(tts, "SAMPLE_RATE", _KOKORO_SAMPLE_RATE)) or _KOKORO_SAMPLE_RATE
            return bool(tts.available(self._cfg))
        except Exception:  # noqa: BLE001 - a broken probe is simply not ready, never a crash
            return False

    def synthesize(self, text: str, *, voice: str | None = None, speed: float = 1.0) -> bytes | None:
        # `voice`/`speed` are accepted so the engine can pass rendering params, but the
        # frozen `app/tts.py` is text-only and MUST NOT be modified, so they are not yet
        # applied here. Honoring them (parameterized Kokoro synthesis) is a NEW method
        # calling kokoro-onnx directly — RTX-4070 work — never an edit to app/tts.py.
        try:
            from app import tts
            return tts.synthesize(self._cfg, text)          # bytes | None (best-effort, text-only for now)
        except Exception:  # noqa: BLE001 - real failures become a clean None -> AudioResult(ok=False)
            return None
