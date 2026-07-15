# voice/effects — presentation-layer audio effects

Pure post-processing on Kokoro-synthesized audio. Each effect module exposes a
single function that takes `(samples, sample_rate, cfg)` and returns processed
`samples` of the same shape. Effects are OFF by default and only run when a
voice profile explicitly requests them.

## Current effects

- **`banshee.py`** — the supernatural undead layer for Manbeardog-mode voice
  profiles. Ghost octave-down doubling, cold shimmer, hollow highpass, moderate
  reverb, output limiter. OFF by default (`enabled: false`).

## Design rules

Every effect module here MUST:

- Be a **pure function**. No side effects, no globals, no I/O. Same numpy shape
  in as out.
- **Preserve intelligibility.** Voice always wins the mix. If a knob can be set
  to values that blur words, document the safe range and clamp the defaults
  inside it.
- **Import heavy deps lazily.** Nero's base app runs fine without
  `pedalboard` / `librosa` / etc. installed. Effect modules import their DSP
  library inside the function body so a missing dep only fails on invocation,
  not on import.
- **Default disabled.** The default config for the effect must have
  `enabled: false` so touching the config is a conscious choice.
- **Fail loudly, not silently.** If the effect can't run (missing dep, bad
  config), raise a clear `RuntimeError` — do not degrade silently to
  passthrough. Passthrough is only the correct behavior when `enabled: false`.

## Banshee tuning guide (per parameter)

| Knob | Default | Sonic effect | If you want more of it | If you want less of it |
|---|---|---|---|---|
| `ghost.gain_db` | −14 dB | The octave-down shadow beneath the voice — the *signature* Undead double. | Raise toward −10 dB (careful, blurs words) | Lower toward −20 dB or disable |
| `ghost.semitones` | −12 | How far below the voice the shadow sits | −7 (fifth down) sounds warmer; −24 (two octaves) sounds subterranean | 0 disables pitch shift, leaving just a slap-back echo |
| `ghost.delay_seconds` | 0.06 | Distance between voice and shadow (60 ms is an audible echo) | 0.09-0.12 for a more separate voice | 0.02-0.04 for a doubled body |
| `shimmer.gain_db` | −20 dB | Cold metallic top layer | Raise toward −14 dB | Disable if it sounds too "chorus pedal" |
| `shimmer.semitones` | +7 | Perfect fifth up — otherworldly | +12 (octave up) sounds more "banshee scream" | Lower / disable if it draws attention |
| `chorus.mix` | 0.35 | How much of the doubled/detuned signal is blended in | 0.5 for stronger metallic doubling | 0.15 for very subtle |
| `chorus.depth` | 0.25 | Amount of modulation | Higher = more warbling | Lower = tighter |
| `highpass.cutoff_frequency_hz` | 120 Hz | Cuts low body — the "drained of life" hollowness | Raise to 180-200 Hz for more skeletal tone | Lower to 80 Hz for warmer body |
| `reverb.room_size` | 0.4 | Room character (0 = anechoic, 1 = cathedral) | 0.5-0.6 for larger crypt | 0.2-0.3 for closet |
| `reverb.wet_level` | 0.2 | How prominent the reverb tail is | 0.3 (careful — words start to smear) | 0.1 for whispered wet |
| `reverb.dry_level` | 0.7 | How present the un-reverbed voice is | Keep at 0.7 — this is the intelligibility anchor | Lower only if you want the voice to feel distant |
| `limiter.threshold_db` | −1.0 dB | Output ceiling — prevents clipping | Rarely change | Rarely change |

### Safe operating range

Keep the following invariants unless you know exactly what you're doing:

- `ghost.gain_db ≤ −10 dB` (never let the ghost approach dry level)
- `shimmer.gain_db ≤ −14 dB` (shimmer stays as texture)
- `reverb.dry_level ≥ 0.6` (dry voice remains dominant)
- `reverb.wet_level ≤ 0.3` (reverb never washes the words)
- `limiter.threshold_db < 0.0` (always leave headroom)

The defaults in `DEFAULT_CONFIG` sit comfortably inside all of these bounds.

## Usage

```python
from kokoro_onnx import Kokoro
import numpy as np

from voice.effects.banshee import apply_banshee_fx

kokoro = Kokoro("models/kokoro-v1.0.onnx", "models/voices-v1.0.bin")

# Load a Manbeardog blend from the audition workspace
blend_vec = np.load("path/to/blend_11_heart_40_bella_30_nicole_30/blend.npy")

samples, rate = kokoro.create(
    "Good evening, Toni. I have been waiting.",
    voice=blend_vec,
    speed=1.0,
    lang="en-us",
)

# Off by default — this is a passthrough
plain = apply_banshee_fx(samples, rate)

# Turn it on with defaults
undead = apply_banshee_fx(samples, rate, {"enabled": True})

# Tune it — deep-merge overrides on top of DEFAULT_CONFIG
gentler = apply_banshee_fx(samples, rate, {
    "enabled": True,
    "ghost": {"gain_db": -18},
    "reverb": {"wet_level": 0.15},
})
```

## A/B test script

Use `ab_test.py` to compare dry vs. banshee output for a chosen blend and
sentence:

```powershell
D:\mbd AI\.venv\Scripts\python.exe voice\effects\ab_test.py `
  --blend  "C:\Users\tonij\iCloudDrive\Nero AI\voice_audition\manbeardog_blends\blend_11_heart_40_bella_30_nicole_30\blend.npy" `
  --sentence "C:\Users\tonij\iCloudDrive\Nero AI\voice_audition\test_sentences\06_long_form_conversation.txt" `
  --outdir "C:\Users\tonij\iCloudDrive\Nero AI\voice_audition\banshee_test"
```

Writes `dry.wav` and `banshee.wav` side by side for direct listening
comparison. Iterate on the banshee config in `banshee.py::DEFAULT_CONFIG` and
re-run the script until the balance is right.

## Dependency + license

- **`pedalboard>=0.9.24`** (Spotify). Install via
  `pip install -r requirements-voice-effects.txt`.
- **License: GPL v3.** This is a copyleft license. Installing pedalboard is
  fine for personal / private use; if Nero is ever distributed together with
  pedalboard, Nero itself must be released under GPL v3 or a compatible
  copyleft license. See the corresponding ADR in `docs/adr/` for the reasoning
  and the accepted trade-off.

## Adding a new effect

1. Create `voice/effects/<name>.py` with a single `apply_<name>_fx(samples,
   sample_rate, cfg)` function following the design rules above.
2. Add a `DEFAULT_CONFIG` dict with `enabled: false`.
3. Add a `<name>.example.yaml` showing the schema with sensible commented
   defaults.
4. Update this README with a tuning guide table for the effect's knobs.
5. If the effect adds a new dependency, add it to a
   `requirements-voice-effects-<name>.txt` file (keep optional deps in
   isolated requirements files so users can choose what to install).
