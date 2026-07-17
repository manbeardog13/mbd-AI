# NERO Mobile Presence Experience

**Scope:** what "Nero is present" looks and feels like on a phone.
**Not scope:** Flutter/Swift/Kotlin implementation code (belongs to Phase F
in `docs/visual/manbeardog_visual_production.md`).

**Guiding principle:** mobile is not a smaller desktop. It's Nero
manifesting through a different kind of window. Battery, glanceability,
and interruption discipline shape everything.

---

## Core philosophy

The desktop presence exists in a *dedicated window* — Nero can afford
constant animation, particle systems, full character rendering.

Mobile presence exists *in your pocket, on your lock screen, in a widget
strip*. It has to be:

- **Recognizable in one glance** — the wolf-eye emblem is Nero even at
  16×16 pixels
- **Battery-honest** — no continuous 60 fps particle system
- **Interruption-appropriate** — the phone is already interruptive; Nero
  should not add to that noise
- **Instantly identifiable** — same emblem, same color, same behavior
  across states, even at a fraction of desktop fidelity

**One identity. Many manifestations.**

---

## The mobile visual vocabulary (Presence Level L1)

Everything on mobile is L1 by default. Higher levels (L2 portrait, L4
full body) are desktop territory — mobile battery physics don't sustain them.

### The three visual elements

1. **The Wolf-Eye Emblem** — the primary NERO signature on mobile.
   Two pink-magenta glowing dots, small, always visible when Nero is
   "on" for you.

2. **The Mist Puff** — a small, subtle violet-mist particle field
   surrounding the emblem. Not always animated — only when Nero is
   *doing something*.

3. **The Through-Glow Halo** — a soft violet radial gradient behind the
   emblem, at varying intensity depending on state.

That's it. **No character body. No armor. No pauldrons visible. No
hair.** Those are desktop-only per the presence-level compatibility in
`presence/types.py::PresenceLevel`.

### The color palette (subset of Visual Bible §6)

Only three colors are used on mobile:

| Color | Hex | Where |
|---|---|---|
| `nero-black-deep` | `#0A0A10` | Background (widget or full-screen mode) |
| `nero-violet-glow` | `#B85CFF` | Wolf-eye centers + through-glow |
| `nero-violet-mist` | `#7A4CD6` | Mist particles |

No magenta hair. No armor tones. Mobile is a distilled palette.

---

## Presence states on mobile

Each state has a specific visual signature. Behavior differs from
desktop where noted.

### `absent` — Nero is not currently listening / active

- Emblem: **dimmed** wolf eyes at ~20% intensity. Barely visible.
- Mist: **none**.
- Through-glow: **none**.
- Behavior: static. No animation.
- Use: default state when the app is backgrounded or the user hasn't
  activated Nero recently.

### `idle` — Nero is available, waiting

- Emblem: wolf eyes at **~50% intensity**, subtle slow pulse (1 pulse
  every 4-6 seconds).
- Mist: **very subtle**, low density, drifting slowly.
- Through-glow: **~20%** ambient.
- Behavior: extremely calm. The user shouldn't feel watched.
- Battery target: <1% per hour on a mid-range phone.

### `listening` — Nero is capturing user speech

- Emblem: wolf eyes at **~70% intensity**, gentle attention-pulse
  synchronized loosely with audio input level (not full waveform
  visualization — a subtle brightness modulation).
- Mist: **expands slightly**, more visible drift.
- Through-glow: **~40%**.
- Behavior: shows Nero is engaged. Not overactive.
- Alternative for widget mode: a subtle "..." indicator below the emblem.

### `thinking` — Nero is processing

- Emblem: wolf eyes at **~85% intensity**, no pulse — steady bright.
- Mist: **denser**, slower drift.
- Through-glow: **~60%**.
- Additional: subtle rune-pulse effect around the emblem (a faint
  circular gold pulse every 2-3 seconds — the runes-activating cue from
  Visual Bible §14.3). Battery-cheap since it's a single expanding ring
  shader.
- Behavior: shows energy gathering. Communicates that Nero is *working*.

### `speaking` — Nero is producing voice output

- Emblem: wolf eyes at **~75% intensity**, synchronized-with-voice
  cadence (gentle brightness modulation from the voice envelope, sent
  from the server as part of the presence event stream — see multi-device
  strategy).
- Mist: **moderate**, more visible drift.
- Through-glow: **modulates with voice** — 30-60% depending on voice
  intensity.
- Behavior: the visual "confirms" the voice. On lock screen with audio
  playing, this is the primary cue that Nero (not another app) is
  speaking.

### `alert` — important information

- Emblem: wolf eyes at **100% intensity, still**.
- Mist: **subtle** (stillness IS the alert per Bible §9).
- Through-glow: **90%**, very present.
- Optional: gentle haptic (short single tap) on alert-state entry.
- Behavior: the reduction of motion is the alert. The user's eye catches
  the *change from moving to still*.

### `concerned` — negative outcome / caution

- Emblem: wolf eyes at **~40% intensity** (dimmed per Bible §9).
- Mist: **reduced**.
- Through-glow: **35%**, slightly muted.
- Behavior: the "off-note" state. Should feel subtly different from any
  positive state.

### `celebrating` — positive outcome

- Emblem: wolf eyes at **~70% intensity**.
- Mist: **modest bloom**.
- Through-glow: **55%**.
- Additional: brief warm-rim glow around the emblem (the warm exception
  from Visual Bible §12.4 — a subtle orange-gold radial edge for ~1
  second).
- Behavior: the *rare* warmth. Should feel earned.

### `emerging` (manifestation)

Mobile emergence is shorter than desktop (mobile users are impatient) —
target ~1.2 seconds total instead of desktop's ~2.0 s.

Sequence:
1. `0.0–0.2 s` — background dim / attention drawn
2. `0.2–0.5 s` — mist appears
3. `0.5–0.8 s` — wolf-eye pinpoints appear (this is the "Nero is here" moment)
4. `0.8–1.0 s` — through-glow appears
5. `1.0–1.2 s` — settle to idle intensity

### `dissolving`

Reverse of emergence. Wolf eyes fade last, ~1.2 s total.

---

## Mobile manifestation modes

The same visual vocabulary appears in three different mobile *containers*:

### Mode 1 — Notification / Live Activity / Widget

- **Container:** OS-provided widget slot (Android home screen widget,
  iOS Live Activity).
- **Size:** small — typically 64x64 to 128x128 pixels.
- **Detail level:** emblem + minimal mist. No rune pulses. No warm-rim.
  Just the two wolf eyes with intensity + through-glow modulation.
- **Refresh cadence:** Android widgets update at OS-controlled rate (5-15
  min minimum on modern Android). Live Activities have more freedom but
  still not real-time.
- **Practical:** state changes are **discrete** here — the widget shows
  "Nero is listening" as a static-with-recent-update, not a continuous
  animation.
- **Battery:** near-zero. This is the always-on manifestation.

### Mode 2 — Full-screen presence mode

- **Container:** dedicated app screen when the user opens Nero for a
  conversation.
- **Size:** full display.
- **Detail level:** emblem large + full mist particle system + through-glow
  + rune pulses when thinking + warm-rim when celebrating.
- **Refresh cadence:** 30-60 fps (60 on high-refresh displays).
- **Practical:** this is where mobile Nero *feels alive*. Real-time
  presence state changes drive real-time visual changes.
- **Battery:** moderate — target <5% for a 30-minute conversation session.

### Mode 3 — Voice-only lock screen

- **Container:** lock screen media session (Nero speaking via headphones
  while phone is locked).
- **Size:** lock-screen media widget.
- **Detail level:** static emblem + text ("Nero speaking").
- **Refresh cadence:** static.
- **Practical:** you're not looking at the screen anyway. Emblem is
  identification.

---

## Interaction patterns

### Tap the emblem widget

- If Nero was `absent`: transition to `listening`, open the app to
  full-screen presence mode.
- If Nero was `idle`: transition to `listening`, activate microphone.
- If Nero was `speaking`: interrupt (barge-in), transition to `listening`.

### Long-press the emblem widget

- Show quick actions menu: mute Nero, stop current voice, quick memory
  note.

### Full-screen presence mode gestures

- Tap: barge-in / interrupt.
- Swipe down: dismiss to widget mode.
- Swipe up: reveal text transcript below the emblem.

---

## Offline / weak-connection state

Mobile connectivity is inconsistent. Nero must behave predictably when
disconnected.

### Weak signal (occasional drop)

- Emblem: unchanged — still shows current state.
- **Small offline indicator dot** (single dim yellow pixel) beside the
  emblem when a request has been queued locally but not delivered.
- Widget shows "syncing..." on next refresh.

### Fully offline

- Emblem: **desaturated** — wolf eyes shift to gray-violet instead of
  pink-magenta. Recognizably Nero, visibly *not currently reachable*.
- Voice unavailable — no audio playback attempts.
- User taps produce a "Nero is unreachable" static message.
- **Zero animation** when offline — battery-safe stillness.

### Reconnection

- Emblem returns to normal color.
- Brief "reconnected" pulse (1 second warm-rim glow).
- Queued state changes since disconnect play through in order (fast-forwarded).

---

## Notifications discipline

Nero should never notify unless it has something to say. Push
notifications from Nero should be:

- **Rare** — the goal is presence, not attention theft
- **Consented** — user opts in per notification type
- **Character-appropriate** — a Nero notification is a Manbeardog-cool
  sentence, not marketing copy
- **Actionable** — every notification has a clear "why now?"

The emblem itself provides ambient presence. Notifications are for
Nero-initiated moments (a reminder Toni set, a proactive insight — those
are Phase 4+ features per the roadmap).

---

## Implementation approach (deferred to Phase F)

Not building this now, but recording the intended stack so it's not
re-litigated later:

- **Cross-platform framework:** Flutter (BSD-3, single codebase for
  Android + iOS + optional desktop).
- **Emblem rendering:** custom shader (Skia via Flutter's `CustomPainter`
  or `FragmentShader`). Reasons: full battery control, no Live2D runtime
  overhead, sub-1% CPU for the widget-mode emblem.
- **Voice playback:** platform-native audio APIs. Voice comes from the
  Nero server as .wav bytes over the WebSocket presence stream — same
  audio format as desktop `POST /api/speak`.
- **Presence event stream:** WebSocket connection to Nero's forthcoming
  `/api/presence/subscribe` endpoint (part of the multi-client broadcast
  service — Phase E in the roadmap). Client sends `client.hello` with
  its capabilities per `docs/visual/manbeardog_visual_production.md` §5.
- **Widget refresh:** Android AppWidget provider + iOS WidgetKit.
  Widget renders a snapshot of the emblem, updated on OS refresh
  intervals.

---

## Cross-references

- Character visual identity: `docs/visual/manbeardog_visual_bible.md`
- Presence Levels + capabilities: `presence/types.py::PresenceLevel`
- Multi-device asset strategy: `docs/visual/multi_device_asset_strategy.md`
- Full roadmap (mobile is Phase F): `docs/visual/manbeardog_visual_production.md`
- Client capability protocol: `docs/visual/manbeardog_visual_production.md` §5
