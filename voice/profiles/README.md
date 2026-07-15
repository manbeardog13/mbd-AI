# voice/profiles — logical voice identities

The brain requests a voice by name; the profile bundles everything needed to
render it. Adding a new voice character = adding an entry to `presets.py`. No
changes elsewhere in Nero.

## Available profiles

| Name | Character | Blend | Speed | Pitch shift | Banshee |
|---|---|---|---|---|---|
| **`nero_prime`** | Daily-use canonical voice. Calm, mature, present. | Manbeardog blend (heart 40 + bella 30 + nicole 30) | 0.93 | −2 st | v3 tuning, minimal reverb |
| **`nero_whisper`** | Close-mic quiet voice. Late-night / private. | Manbeardog blend (placeholder) | 0.85 | none | off |
| **`nero_late_night`** | Deeper, slower, mildly haunted. | Manbeardog blend | 0.85 | −4 st | v3-derived, slightly more reverb, no shimmer |

## Emotional-expression strategy (honest scope)

Kokoro's engine does not expose emotion / arousal / prosody parameters. The
API is `(text, voice, speed, lang)` — nothing else. Emotional differentiation
in Nero comes from exactly **four** levers that stack:

1. **Blend selection** — a different voice-embedding for a different character.
   (Whisper uses `af_nicole`, late-night uses a deeper-pitched blend, alert
   uses a bright single voice, etc.)
2. **Speed variation** — `speed=0.85` reads as contemplative; `speed=1.05`
   reads as urgent. Kokoro's speed is properly time-stretched, so it doesn't
   also shift pitch — the character stays but the pace changes.
3. **Output pitch shift** — via pedalboard's `PitchShift` in the banshee FX
   chain (`output_pitch_shift.semitones`). Small negative values (−2..−4) sit
   the voice lower without sounding artificial.
4. **Banshee FX profile** — the presentation-layer tuning. `enabled=False`
   for plain speech, gentle values for `nero_prime`, deeper values for
   `nero_late_night`. Different reverb amounts read as different room /
   emotional distance.

Anything more (real prosody, per-word emphasis, breathing, sighs, laughs)
would need either a different engine (Chatterbox, XTTS) or DSP that alters
the voice mid-utterance — both out of scope for this module.

## Usage

```python
from kokoro_onnx import Kokoro
from voice.profiles import get_profile, synthesize_with_profile

kokoro = Kokoro("models/kokoro-v1.0.onnx", "models/voices-v1.0.bin")

# Request by name — the brain never sees blend paths, speed, or FX config
profile = get_profile("nero_prime")
samples, rate = synthesize_with_profile(profile, "Good evening, Toni.", kokoro)

# Different emotional state? Different profile.
alert = get_profile("nero_whisper")
samples, rate = synthesize_with_profile(alert, "Someone is at the door.", kokoro)
```

## Adding a new profile

1. Open `presets.py`.
2. Define a new `VoiceProfile` constant, matching an emotional state
   (e.g. `NERO_THINKING`, `NERO_CELEBRATION`, `NERO_SYSTEM_ALERT`).
3. Add it to the `PRESETS` dict.
4. That's it. No other file needs to change.

## Design decisions worth knowing

- **Blend vectors are loaded on first use, cached per profile instance.**
  `VoiceProfile.load_blend()` memoizes. Restart to pick up a re-generated
  blend file.
- **`banshee_config=None` means no FX.** Callers can request an FX-free
  render without touching the effects module.
- **`text_prep_style` is reserved.** The value is stored but not yet
  consumed — the preprocessor (pause insertion, chunking) will land in a
  later commit.
- **Blends currently point to absolute paths in iCloudDrive.** When the
  winning blend is copied into the Nero repo (Voice Director Phase 3), the
  paths in `presets.py` become repo-relative.
