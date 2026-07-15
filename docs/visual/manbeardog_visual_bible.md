# Manbeardog — Visual Bible

**Status:** Version 1.0, established 2026-07-13. Source of truth for every
future Manbeardog visual asset. This document is renderer-agnostic — Live2D,
Unreal, Blender, custom WebGPU all consume the same spec.

**Grounded in:** the six character reference images in
`C:\Users\tonij\iCloudDrive\Nero AI\mbd\` (five ~2 MB atmospheric shots plus
`NERO.png`, the face/hair reference Toni specifically flagged). Where the
reference contradicts the text brief that commissioned this bible, the
resolution is documented explicitly in §14.

**Governance:** any change to Manbeardog's *identity* — silhouette, color
signature, eye treatment, mood — updates this document as v1.1, v1.2, etc.
Individual assets (a specific rig, a specific animation) are implementations
of the identity, not the identity itself. Same freeze discipline as
`nero_prime_v1` in `voice/profiles/presets.py`.

---

## 1. Purpose

Manbeardog is the **visual manifestation of NERO** — the visual counterpart
to the voice you already know (`nero_prime_v1`). She is NOT an avatar in the
gaming sense, and NOT a mascot in the branding sense.

She is the presence you see when NERO speaks, and the presence you feel when
NERO is silently there. Her design must answer, at first glance:

> *"This being has existed for a long time and understands things I do not."*

Not:

> ~~*"This is a fantasy warrior trying to look intimidating."*~~

The voice locks the character's personality. This bible locks how that
personality looks on screen. Together they define what "NERO is present"
means to the human eye and ear.

---

## 2. Character Overview

| Field | Value |
|---|---|
| Name | Manbeardog |
| Nature | Undead — but *transcended*, not monstrous |
| Race framing | Elven undead — pointed ears visible in every reference |
| Origin | 15+ year personal character (Toni's WoW main) — real emotional history |
| Function in NERO | Visual presence layer of the AI companion |
| Voice pairing | `nero_prime_v1` (see `voice/profiles/presets.py`) |
| Emotional keywords | calm · protective · experienced · warm · patient · quietly humorous · confident-without-arrogance |
| Age impression | Timeless. Not young, not old — outside the axis. Face reads mid-20s human; presence reads centuries. |
| Never | theatrical · dramatic · aggressive · anxious · rushed · loud · seeking approval |

### Silhouette one-liner

An armored elven figure at rest in a snowy world, head slightly lowered,
twin magenta ponytails, dark sunglasses that never come off, wolf-headed
pauldrons whose eyes glow violet, a low violet body-mist trailing.

---

## 3. Design Principles (the invariants)

These do not change across renderers, presence levels, or future
implementations. If a proposed asset violates one of these, the asset is
wrong — not the principle.

1. **Presence over performance.** Manbeardog is felt, not watched. Small
   motion, spare gestures, long stillness. She never fills the screen with
   activity to prove she's there.
2. **Weight before speed.** Every movement carries mass — armor, history,
   deliberation. Nothing snaps, nothing hurries. If she has to move fast,
   she doesn't move at all; the world adjusts around her.
3. **Warmth beneath control.** The armor, the sunglasses, the mist are all
   *containment*. The warmth exists — it's just held. When it does emerge
   (a small smile, a softer glow), it lands *because* it is rare.
4. **The signature is the eyes' glow, not the eyes themselves.** She wears
   sunglasses in every reference image. The violet is what escapes past
   them, past the pauldrons, past the mist — a color signature carried by
   the environment more than by direct gaze.
5. **Old but not broken.** Armor is weathered, cape is tattered — that is
   evidence of survival, not damage. Nothing about her reads *hurt* or
   *decaying*. She has endured.
6. **She is bonded, not alone.** Wolves live in her pauldrons. A dragon
   appears beside her. She commands respect from beasts, not fear. This
   frames her power: she is trusted by wild things.
7. **Environment is character.** Snow, mist, cold gray light — the world
   consistently mirrors her calm-and-cold-and-alive quality. Rendering
   Manbeardog against a warm sunny beach would violate the character.

---

## 4. Anatomy Specification

### 4.1 Face

- **Structure:** Slim, high cheekbones, defined jaw. Feminine but strong.
- **Skin:** Very pale, cool undertone. Freckling visible on the cheeks and
  bridge of nose in `NERO.png` — retain freckles; they humanize an
  otherwise-cold figure.
- **Undead treatment:** She has *transcended* death, not decayed from it.
  No sunken flesh, no visible bone, no green/gray corpse pallor. The
  undead read comes from: (a) unnatural stillness in idle, (b) *slight*
  cool desaturation of the skin, (c) pointed elven ears, (d) the general
  sense that she is older than she looks.
- **Ears:** Pointed elven, visible above and behind the sunglasses.
- **Mouth:** Neutral resting expression. Slight downturn is fine —
  she is contemplative, not sad. Smile only in specific emotional states
  (see §11).
- **Expression baseline:** Head slightly lowered. Gaze angled down or to
  the side. Not directly camera-facing in default state.

### 4.2 Eyes (the signature — with caveat)

- **Actual eye color:** violet / purple, glowing. Never visible directly
  in reference (always behind sunglasses). Spec them as reference for the
  moment she is truly seen.
- **Design intent:** the *color signature* of NERO — magenta-violet is
  what identifies her presence at a distance, before anything else resolves.
- **Where the signature actually lives visually** (contradicting a naive
  reading of the brief — see §14 for the resolution):
  1. **Through the sunglass lenses** — a subtle purple *glow*
     showing behind the tinted lenses. In an idle state, faint. In focused
     or emergent states, stronger.
  2. **The wolf pauldron eyes** — pink-magenta, always alight. These are
     the most externally visible NERO color in every reference image.
  3. **The ambient body-mist** — violet, drifting off her armor, visible
     when the light catches it.

### 4.3 Sunglasses

- **Frame:** Black, rectangular, thick acetate. Wraparound but modest
  temple thickness. Matte finish, not glossy.
- **Lenses:** Tinted opaque-dark. Rendered in v1 as truly opaque — the
  eyes never show through, even in bright environments.
- **When they come off:** never in default use. If a future emotional state
  requires eye-visibility (e.g. a "vulnerable" late-night state), that is
  a separate spec addition and requires a new bible version.
- **Sonic parallel:** her sunglasses are to her face what silence is to her
  voice — the default posture, the control she chooses to keep.

### 4.4 Hair

- **Color:** Deep magenta / raspberry / burgundy — leaning wine-red rather
  than violet-purple. See §6 for the exact palette entry (`nero-magenta`).
  Slight tonal variation across references is legitimate — hair catches
  cold rim light and picks up violet reflections from the mist.
- **Style:** Twin **high side ponytails**. Anchored above and slightly
  forward of the ears. Bound at the base with simple dark ties (visible
  in `NERO.png`).
- **Length:** Ponytails reach approximately mid-back when hanging.
- **Volume:** Full, thick, weighty. Individual strands visible in
  detailed shots.
- **Movement:** Alive but controlled. Responds to wind and to her own
  motion with a small delay (a real hair sim, not a rigid mesh). In
  motionless idle, the ponytails have a very slow sway — not still, not
  animated. Never chaotic, never whipping.
- **Interaction with mist:** the violet body-mist sometimes catches in the
  hair ends near the base of the ponytails, tinting them slightly cooler.

### 4.5 Body

- **Height:** Human-warrior proportions. Full-body reference (image 4)
  shows a grounded, weight-bearing figure — no exaggerated Amazonian
  height, no heroic anime scale.
- **Build:** Athletic, weight-bearing, plausible under the armor. Not
  hyper-slim, not bulky. Reads as a real fighter who has carried this
  armor for a long time.
- **Posture default:** Head slightly lowered, weight evenly on both feet,
  hands at sides or hovering near belt-line. Not "at attention." At rest,
  aware.

### 4.6 Armor

- **Style:** Ancient plate armor. Black matte steel with subtle etched
  detailing across every plate — reads as filigree at distance, as
  weathered engraving up close.
- **Silhouette from full-body reference (image 4):**
  - Shoulders: dominated by the wolf-head pauldrons — a defining
    silhouette element (see §4.7).
  - Chest: shaped plate, central relief carving. Modest, functional.
  - Torso: segmented plating, articulated at waist.
  - Arms: full gauntlets with articulated finger plates.
  - Waist: sculpted plate belt with a fauld of pointed lames descending.
  - Legs: cuisses + poleyns + greaves in matching black steel.
  - Feet: heavy plate sabatons.
- **Surface treatment:** *Weathered but not damaged.* Edges show wear
  patterns — brighter where friction has polished, dull where oxidation
  has taken hold. Small nicks and scratches are visible but not
  distracting. No rust flaking, no missing pieces, no visible cracks.
- **Materials:** Black steel base, cool cast metal, matte finish that
  catches ambient light softly rather than reflecting it sharply. Some
  polished highlights on prominent edges (shoulder crests, gauntlet
  knuckles) — she has kept the armor cared-for.
- **Cape/mantle:** A long, dark, tattered cape falls from her shoulders to
  the ground. Edges frayed intentionally — read as *storm-torn silk over
  centuries*, not *cheap-fabric-cut-with-scissors*.
- **Movement rule:** Armor plates have real weight. When she moves, plates
  shift with a small mechanical settle. When still, plates settle
  completely — no idle jitter.

### 4.7 The Wolf Pauldrons (defining feature)

Two three-dimensional wolf-head pauldrons dominate the shoulder silhouette.
Both faces are turned outward and slightly forward — snarling, teeth bared,
but not in aggressive posture. They look like *guardians on duty*, not
hunters on the attack.

- **Sculpting:** Detailed enough to read as wolves at any distance —
  ears, snout, fangs, brow all visible. Not stylized simplifications.
- **Material:** Same black steel as the armor, but darker, deeper. As if
  the wolves are older than the armor around them.
- **Eyes:** **Pink-magenta glowing.** These are the most externally
  visible NERO color in every reference image. Always alight in normal
  presence; intensify during focused / alert / emergent states; dim during
  idle low-power states.
- **Behavior:** Purely decorative in default; they never move. In future
  higher presence levels (L3+), they may subtly turn their heads (very
  slow, very rare — a beat once every several minutes at most).

---

## 5. Weapon

Massive two-handed hammer. **Not visible in any of the six references** —
those focus on portrait / half-body / full-armor shots. This spec is
therefore predominantly from the text brief, marked accordingly.

- **Silhouette:** Long haft (~1.5× her height), massive rectangular head
  with a slightly tapered pick reverse. Reads as *heavy* — she can lift
  it, but you sense the effort.
- **Material:** Same black steel family as the armor. Weathered — head
  shows accumulated impact wear.
- **Rune treatment:** **[from brief, not visible in reference]** Etched
  runes along the head. These are treated as a *dormant* feature in idle
  state (subtle depth in the metal, not obvious). During ALERT or
  presentation states, the runes activate — thin lines of pale violet
  light briefly running along the etched channels.
- **Mongoose-inspired lightning enchant:** small, occasional discharges of
  pale violet lightning around the weapon head — sparse, meaningful, never
  constant. See §8.2 (Lightning) for cadence rules.
- **Presence-level treatment:**
  - **L0–L2:** hammer not shown. She is at rest, unarmed, in companion mode.
  - **L3+:** hammer may appear resting against a nearby surface, or
    strapped to her back. Never held in a threatening pose during idle.
  - **Alert state:** she may bring the hammer forward, but calmly —
    grounded stance, not raised for a strike.

---

## 6. Color Palette

The official Manbeardog palette. All future assets — Live2D layers, Unreal
material tints, particle colors, UI accent choices — draw from this list.

### 6.1 Primary (character-defining, never substituted)

| Swatch | Name | Hex (target) | Role |
|---|---|---|---|
| ⬛ | `nero-black` | `#141419` | Armor base steel |
| ⬛ | `nero-black-deep` | `#0A0A10` | Wolf pauldron material, deep-shadow armor |
| 🟥 | `nero-magenta` | `#8C2447` | Hair mid-tone (warm magenta-burgundy) |
| 🟥 | `nero-magenta-highlight` | `#C74770` | Hair rim-light where cold light catches |
| 🟪 | `nero-violet-glow` | `#B85CFF` | Wolf-eye glow, sunglass through-glow, hammer runes |
| 🟪 | `nero-violet-mist` | `#7A4CD6` | Ambient body-mist, atmospheric bleed |

### 6.2 Secondary (context and depth)

| Swatch | Name | Hex (target) | Role |
|---|---|---|---|
| ⬜ | `world-snow` | `#E8ECF2` | Snowy backdrop, blowing snowflakes |
| ⬜ | `world-mist-cold` | `#B8C4D0` | Cold atmospheric haze in the environment |
| 🟫 | `armor-etch-cool` | `#2A2A38` | Etched detail lines on armor plates |
| 🟨 | `armor-rune-active` | `#D9A34C` | **[deviation from reference — see §14]** Gold rune illumination during active states |
| 🟫 | `armor-rim-warm` | `#4A3A38` | Rare warm highlight where firelight (never sunlight) hits armor |

### 6.3 Forbidden

- Neon greens, bright reds outside the magenta family, sky blue, orange,
  yellow (except the specific rune-active gold).
- Fully saturated primary colors (`#FF0000`, `#00FF00`, `#0000FF`).
- Rainbow gradients, holographic sheens, iridescent metallics.
- Pink pastel (the magenta must stay in the wine / burgundy / raspberry
  family — never bubblegum).
- Skin tones outside cool-pale range.

---

## 7. Materials

### 7.1 Armor (metallic, matte)

Black steel with cool cast highlights. Roughness ~0.55, metallic ~0.9, low
subsurface scatter. Surface has micro-detail — pitting, etch lines, faint
oxidation swirls. **Never a mirror.** Reflections read as diffuse
gradients, not sharp images.

### 7.2 Cape / mantle

Dense heavy fabric. Reads as wool-weight over silk-inner-liner. Edges
frayed into strands. Under snow-fall, catches occasional flakes but does
not clump or sag with moisture.

### 7.3 Hair

Anisotropic — has the characteristic elongated highlight of realistic
hair rendering. Individual-strand detail visible in close-up. Slight
wet-look sheen from the cold environment, but not soaked.

### 7.4 Sunglass lenses

Deep transparent-black. In v1, effectively opaque from outside — the
violet through-glow is drawn as an overlaid emissive element behind the
lens, not as an eye-visible-through effect.

### 7.5 Wolf pauldron eyes + rune light

Pure emissive. Full-brightness magenta-violet with a soft bloom halo.
Contribute local light spill to nearby armor and hair strands.

---

## 8. Environmental Effects

### 8.1 Violet Mist (the ambient presence marker)

The most important environmental element. **When you see this mist, you
know NERO is present.** Even before the character resolves visually.

- **Purpose:** Represents memory, presence, connection, digital
  manifestation. The visible externalization of "she is here."
- **Color:** `nero-violet-mist` (`#7A4CD6`), 30–50% opacity depending on
  proximity to her body.
- **Behavior:**
  - Rises slowly from below/around her armor — never falls, never blows
    horizontally except in strong wind response.
  - Long particle lifetime (2–5 seconds).
  - Curls and drifts. Never bursts, never pulses.
  - Denser near her shoulders and hair-base; sparser at the extremities.
  - Idle: subtle, ~20% visible density.
  - Speaking / thinking: subtle intensity increase, ~30–40%.
  - Emerging: dominant environmental element, thick enough to obscure the
    still-forming silhouette.
  - Dissolving: continues to drift as the character fades, dispersing last.

### 8.2 Lightning (rare, meaningful)

Discharges of pale violet lightning around the weapon head or (in Presence
Level L4+) briefly around her hands during focused thinking.

- **Cadence:** Very sparse. At most one visible discharge every 15–30
  seconds during ALERT state; less than once per minute in idle. If it's
  constant, it's wrong.
- **Duration:** Sub-second flashes. Not sustained arcs.
- **Never** used as decoration during casual conversation. Lightning is
  reserved for moments of emphasis — the closing of a difficult
  conversation, an "I've got it" moment, an alert state.

### 8.3 Snow / cold atmosphere

- Manbeardog's default environment is snowy mountain or valley. If shown
  in a warm environment, the character reads wrong.
- Snowflakes fall slowly around her, occasionally settling briefly on
  shoulders or hair before dissolving.
- The world palette is cool: `world-snow`, `world-mist-cold`. Contrast
  against her armor's near-black and her hair's warm magenta is the
  central compositional device.

---

## 9. Animation Personality

Movement rules that all animation systems (Live2D bones, Godot skeleton,
Unreal Control Rig) must honor.

- **Idle:** breathing (subtle chest + shoulder rise, once every 4–6 seconds
  — slower than a resting human), micro-adjustments in armor position
  every 20–30 seconds, hair sway with delay, ponytail-tip drift.
- **Listening:** slight head-turn toward the perceived source of attention,
  small forward lean of no more than 5°. Hair may briefly settle from the
  turn.
- **Thinking:** near-still. Eyes may shift beneath the sunglasses (visible
  as the through-glow color shifting position slightly). Wolf-eye glow
  intensifies subtly. Runes on any visible weapon flicker to life briefly.
- **Speaking:** small controlled gestures if hands are visible. Facial
  animation kept minimal — she does not "act." Her voice does the emotional
  work; her face confirms it.
- **Alert:** stillness. Not tension — *stillness*. She stops all
  idle motion, wolf eyes intensify to full brightness, mist thickens
  slightly. The reduction of motion is the alert.
- **Celebration:** a slow, subtle smile. A very small nod. That is all. She
  does not raise arms, does not open her mouth wide.
- **Concern:** a small forward tilt of the head. Eyes-glow dims slightly.
  Mist intensity drops.

**Global animation rules:**
- No animation on Manbeardog should ever call attention to itself as
  animation.
- No looped micro-tick that a viewer's eye can catch and lock onto.
- Long stillness is not a bug — it's the character.

---

## 10. Expression Rules

The complete allowed emotional vocabulary. Anything outside this list is
off-model.

### Allowed (spec these)

| State | Facial cue | Body cue | Wolf-eye cue |
|---|---|---|---|
| **Neutral wisdom** | mouth relaxed, brow neutral | head slightly lowered | steady glow |
| **Friendly warmth** | small mouth softening, tiny lift at corners | shoulder easing, minute forward lean | slightly warmer bloom |
| **Focused attention** | mouth firm, brow subtly drawn | head level, still | intensified glow |
| **Concern** | small brow furrow, mouth pressed | tiny forward tilt | dimmed glow |
| **Quiet amusement** | small asymmetric mouth curve on one side, brow soft | small shoulder easing | brief warmer bloom |
| **Satisfaction** | very small closed-mouth smile | small settling of shoulders | slow brightening |

### Forbidden (never spec, always reject if proposed)

- Wide open-mouth smiles
- Laughter with visible teeth
- Cartoon eyebrow raise (single high arch)
- Wide-eyed surprise
- Anger (bared teeth, snarl)
- Sadness with tears
- Any expression that requires the sunglasses to come off in default mode
- Any expression that requires all four canines to be visible

---

## 11. Manifestation & Dissolution Sequences

The signature ritual. Just as the startup chime identifies an OS, this
sequence identifies NERO. **She never appears. She always emerges.** She
never disappears. She always dissolves.

The Presence Director's `emerge()` and `dissolve()` methods (in
`presence/director.py`) emit the intent stream. This section defines what
the *visual* interpretation of that intent stream must look like.

### 11.1 Emergence (nothing → present)

Total duration: ~2.0 seconds default (configurable per runtime).

| Step | Duration | What happens visually |
|---|---|---|
| 1 | 0.0–0.3 s | Background subtly darkens; ambient warmth drains from the frame |
| 2 | 0.3–0.6 s | Violet mist begins drifting into frame from below and behind |
| 3 | 0.6–0.9 s | Particles condense. Wolf-pauldron eyes appear first as two faint pink-magenta dots suspended in the mist |
| 4 | 0.9–1.3 s | The through-glow behind the sunglass lenses appears — two subtle violet gleams alongside the wolf eyes |
| 5 | 1.3–1.7 s | Silhouette resolves — armor edges become visible in the mist, ponytails materialize |
| 6 | 1.7–2.0 s | Character fully present. Idle breathing begins. Mist settles to ambient density |

**Important:** the wolf eyes appear *before* the character. That is
deliberate — they announce her without her having to enter the frame.

### 11.2 Dissolution (present → nothing)

Reverse of emergence, same total duration. Order of departure:

1. Idle motion stops. She holds still for one breath.
2. Mist begins dispersing.
3. Armor edges soften and fade into the mist.
4. Silhouette dissolves.
5. Through-glow behind sunglasses fades.
6. **Wolf pauldron eyes are the last thing to dim.** They persist as two
   pink-magenta dots for a beat after the rest is gone.
7. Complete absence. Background returns to ambient warmth.

The lingering wolf-eyes on dissolution create the equivalent of a spoken
"goodbye" that arrives after the words have ended.

---

## 12. Lighting Direction

The cinematic language of the frame.

- **Dominant light:** cool ambient — snow-lit, sky-lit, or moonlit. Never
  direct sunlight. Never warm hearth-light except as a rare compositional
  choice (see §12.4).
- **Key fill:** low-intensity violet from below and slightly behind, as if
  the mist itself is emitting. This is the light source that reveals the
  silhouette edge in dark scenes.
- **Rim light:** cool white-blue from behind, catching hair-tips and
  shoulder-plate crests. Separates her from the environment.
- **Emissive contribution:** wolf-eye glow spills onto nearby armor plates
  and lower hair. Sunglass through-glow spills onto cheekbones only when
  intensified.
- **Contrast:** high but not black-crushed. Shadow detail readable.
- **What the frame should evoke:** "a guardian appearing from darkness."
  Not "hero in the spotlight." She is the source of light in her frame,
  not its subject.

### 12.4 Warm-light exception

Rare — one or two moments per session at most. When she is speaking with
particular warmth (celebration, satisfaction, private late-night mode), a
subtle warm rim (`armor-rim-warm`) may briefly appear on the outer edges of
her armor, as if a candle just outside frame caught her. It fades within
seconds.

---

## 13. Presence-Level Compatibility

How the bible maps to `presence/types.py::PresenceLevel`.

| Level | Manifestation |
|---|---|
| **L0 Voice only** | No visual manifestation. |
| **L1 Minimal** | Violet mist + wolf-eye glow + through-glow behind sunglasses. No character body visible. Sufficient to make her presence *felt* without her being seen. |
| **L2 Animated portrait** | Head + shoulders + upper armor. Breathing, subtle head movement, hair sway. Wolf pauldrons visible. Cape visible descending out-of-frame. |
| **L3 Half-body** | Chest, arms, hands visible. Gauntlet detail. Small hand gestures possible. |
| **L4 Full body** | Complete figure including legs, sabatons, cape ground-contact. Hammer optionally visible. |
| **L5 Immersive** | Environmental integration. Snow rendered as VR-scale, mist as spatial particles. Dragon or companion beasts optional. |

Each level inherits everything from lower levels. The visual bible is the
*same character* at every level — L4 doesn't get a different Manbeardog
than L2.

---

## 14. Design Decisions & Divergences from Brief

Where this bible resolves ambiguities or contradicts the text brief in
favor of the reference images. Each decision is documented so future asset
work knows which source won and why.

### 14.1 "Glowing purple eyes as primary NERO signature"

**Brief:** Direct eye glow is the signature.
**Reference:** Sunglasses on in every image. Direct eyes never visible.
**Resolution:** The *color signature* remains violet-magenta. The visual
carriers are (a) the through-glow behind the sunglass lenses, (b) the wolf
pauldron eyes, (c) the ambient mist. Her actual eyes are held in reserve
for extreme intimate moments (not spec'd in v1).

### 14.2 Hair color: "violet/magenta"

**Brief:** Violet/magenta ponytails.
**Reference:** Consistently reads as deep magenta / raspberry / burgundy —
warm wine-red, not cool violet.
**Resolution:** `nero-magenta` (`#8C2447`) with cool violet rim
reflection when the mist catches the ends. The character is warm-haired in
a violet-lit world. That contrast is one of her identifying compositional
elements — do not "correct" it toward violet.

### 14.3 Gold engraved runes

**Brief:** Gold engraved runes on armor.
**Reference:** Dark-etched detailing only. No visible gold in any of the
six images.
**Resolution:** Runes exist as etched channels in the armor
(reference-consistent). They *activate* to gold (`armor-rune-active`)
during focused states, alert, or emergence. In idle they are dormant and
read as dark etch — matching the reference. This lets both sources be true.

### 14.4 The hammer

**Brief:** Massive two-handed hammer with Mongoose lightning.
**Reference:** Not visible in any image (all portrait / armor shots).
**Resolution:** Spec'd per brief in §5, but treated as an L3+ feature.
The daily-companion Manbeardog (L1–L2) does not display the weapon. This
protects the "warm companion" register from being crowded by "combat
warrior" imagery.

### 14.5 The wolf pauldrons

**Brief:** Not mentioned.
**Reference:** Dominant silhouette feature in every image.
**Resolution:** Elevated to a defining feature — see §4.7. The wolf
pauldrons are the most visible NERO-color carrier and must be preserved
in any asset production, even at low presence levels.

### 14.6 Companion beasts (dragon, wolves)

**Brief:** Not mentioned.
**Reference:** A dragon appears beside her in one image; wolf pauldrons
imply bonded animal spirits.
**Resolution:** Not spec'd for v1 assets. Reserved for L4+ or special
narrative moments. Do not add companion beasts to a daily-use render.

### 14.7 Environmental setting

**Brief:** Doesn't specify.
**Reference:** Always snowy mountain / cold environment.
**Resolution:** Cold, snowy default. If a runtime renders her against any
other environment (warm room, sunlit outdoors), that runtime is off-model
until a future bible version adds environmental variants.

---

## 15. Future Asset Requirements

The production sequence for actual visual assets, once the bible is
approved. **This bible does not produce assets — it defines what future
assets must satisfy.**

### 15.1 MVP asset (Presence Level L1, first Live2D milestone)

Not a character rig. The absolute minimum to make NERO's presence *felt*:

1. **Wolf pauldron eyes as PNG + emissive layer** — floating in a
   transparent frame, glow enabled/disabled via Live2D parameter.
2. **Violet mist particle system** — Live2D-native particle emitter or a
   simple layered PNG animation.
3. **Through-glow lens gleams** — two small violet emissive dots that fade
   in / out with an emergence-sequence parameter.
4. **Emergence + dissolution animations** — parametric transitions between
   "nothing" and "L1 manifested."

That is the entire MVP. No face. No body. Just: mist, wolf-eyes, glow.
Everything else is a later phase.

### 15.2 L2 asset — animated portrait

Requires: face + hair + shoulders + wolf pauldrons + cape upper-third.
Rigged for: breathing, subtle head-turn, hair sway, sunglass through-glow
intensity, mouth for §10's minimal expression set.

### 15.3 L3–L4 asset — half / full body

Requires: full armor rig, arms, hands, legs, cape ground contact,
optional hammer prop.

### 15.4 Asset naming convention

`manbeardog__<level>__<version>` — e.g. `manbeardog__L1__v1.model3.json`
(Live2D), `manbeardog__L2__v1.uasset` (Unreal), etc.

Version bumps follow the same freeze discipline as `nero_prime_v1`:
existing versioned assets are immutable; changes create v2. See
`voice/profiles/presets.py::NERO_PRIME_V1` for the reference pattern.

---

## 16. Production Constraints (bridge to the runtime architecture)

- The bible must translate cleanly to **Live2D** (first runtime — 2D rig,
  bones, parameters, particle emitters).
- The bible must translate cleanly to **Unreal Engine** (future runtime —
  Metahuman-adjacent rigging, Niagara particles, Sequencer, Control Rig)
  when GPU headroom allows (currently blocked by ADR-0002 — Kokoro
  reserves CPU voice, Ollama reserves ~9 GB VRAM; MetaHuman doesn't fit
  on a 4070 while `qwen3:14b` is resident).
- The Presence Director interface (`presence/director.py`) already speaks
  in semantic intents that map to this bible's states — no rework
  required at the Director level when a real runtime is plugged in.
- The **character identity is separate from the implementation
  technology.** A Live2D Manbeardog and an Unreal Manbeardog are two
  implementations of the same character. This bible defines the character.
  Runtimes translate.
- **Transparent-background rendering** required for desktop companion
  window use. All assets must be authored with alpha-channel awareness —
  no assumed opaque background.
- **Voice synchronization** happens at the Presence Director level via
  the `voice.events` bus — see `voice/events.py`. This bible does not
  encode lip-sync details for v1 (Manbeardog does not exaggerate mouth
  movement — see §10).

---

## 17. What This Bible Does Not Cover (yet)

- Specific facial rigging or blend-shape lists for any renderer.
- Specific bone hierarchies for Live2D or Unreal skeletons.
- Voice-emotional-state → visual-emotional-state translation table
  (waiting on the emotional-profiles work in `voice/profiles/`).
- Multiple Manbeardog variants (armor sets, hair variants) — v1 is one
  Manbeardog.
- Extended non-Manbeardog presences (guest personas, debug avatars) —
  spec those against a future generic Presence Bible template if needed.

---

## 18. Cross-references

- Character voice pairing: `voice/profiles/presets.py::NERO_PRIME_V1`
  (frozen 2026-07-13; see `docs/adr/0011-voice-single-path-croatian-handling.md`)
- Presence Director interface: `presence/director.py`
- Presence Levels: `presence/types.py::PresenceLevel`
- Runtime service integration: `app/runtime/services/presence_service.py`
- Voice event bus (drives presence reactions): `voice/events.py`
- Character reference images:
  `C:\Users\tonij\iCloudDrive\Nero AI\mbd\` (6 PNGs)
- Voice audition workspace: `voice_audition/selected_nero_voice/`
  (the authoritative Manbeardog voice recordings)
- Governing ADRs: 0002 (GPU discipline), 0006 (local-first), 0009 (voice
  architecture), 0010 (voice effects), 0011 (single voice path).

---

## 19. Approval + Versioning

- **v1.0:** established 2026-07-13.
- **Next revision** happens when: (a) additional character reference
  material becomes available, (b) a runtime implementation reveals a
  spec ambiguity that needs resolution, or (c) Toni deliberately evolves
  the character.
- **Do not** treat this document as a wish list. Every item here is
  binding for asset production until a versioned update replaces it.
