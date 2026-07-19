---
id: visual.manbeardog-prompt-system
title: "Manbeardog Prompt System"
layer: operational
type: reference
status: active
owner: shared
created: 2026-07-13
updated: 2026-07-17
---

# Manbeardog Prompt System

**Purpose:** the permanent prompt library. Every AI image generation of
Manbeardog assembles its prompt from these components. Consistency across
sessions, months, and generations depends on **not** freehanding prompts.

**How to use this doc:** copy the "Identity Lock" + "Appearance Lock"
blocks verbatim into every prompt. Add one camera preset. Add one
material/mood tag if desired. Then the specific scene / pose / lighting
you want. Then negatives.

**Assumes:** the Manbeardog LoRA is loaded (`mnbdgv1` trigger word active).
Without the LoRA, no prompt is strong enough alone. See
`docs/visual/manbeardog_identity_workflow.md` for the LoRA workflow.

---

## Prompt assembly template

Every Manbeardog prompt follows this exact structure:

```
[TRIGGER WORD]  [IDENTITY LOCK]  [APPEARANCE LOCK]  [CAMERA PRESET]
[SCENE / POSE]  [MATERIAL / MOOD TAGS]  [QUALITY TAGS]
```

And a corresponding negative prompt from the "Negative Constraints"
section below.

Example:

```
mnbdgv1, undead elven warrior woman, calm mature protective wise,
twin magenta burgundy high side ponytails, black rectangular sunglasses,
ancient weathered black steel plate armor, black wolf-head shoulder pauldrons
with glowing pink-magenta eyes, tattered dark cape, pale skin freckles,
pointed elven ears,
head and shoulders portrait, three-quarter view, cinematic composition,
standing quiet in snow, head slightly lowered, contemplative,
soft violet rim light, cold gray-white palette, snowfall,
photorealistic, detailed textures, 8k
```

---

## 1. Identity Lock (permanent — never omit)

These clauses appear in EVERY Manbeardog prompt. They define who she is,
not what she looks like:

```
undead elven warrior woman,
calm mature protective wise,
centuries of experience,
transcended death not decayed,
never theatrical never intimidating
```

**Rationale:**
- `undead elven warrior woman` — species + role + gender lock
- `calm mature protective wise` — the emotional trait cluster from Bible §3
- `centuries of experience` — the timeless-age quality
- `transcended death not decayed` — critical negative-space clause; keeps
  her from generating as a rotting/monstrous undead per Bible §4.1
- `never theatrical never intimidating` — steers away from fantasy-villain
  aesthetic per Bible §2

---

## 2. Appearance Lock (permanent physical features)

These appear in every prompt describing how she looks:

```
twin magenta burgundy high side ponytails,
black rectangular sunglasses always worn,
ancient weathered black steel plate armor,
black wolf-head shoulder pauldrons with glowing pink-magenta eyes,
tattered long dark cape,
pale cool-toned skin with light freckles,
pointed elven ears
```

**Rationale by clause** (all from Visual Bible v1.0):
- Hair per §4.4 — warm-side magenta, not violet-cool
- Sunglasses per §4.3 — always on, never removed
- Armor per §4.6 — weathered, not damaged
- Wolf pauldrons per §4.7 — the defining silhouette feature + color signature
- Cape per §4.6 — tattered as evidence of survival
- Skin per §4.1 — pale, freckled, elven

**Optional appearance modifiers** (add per scene needs):
- `subtle violet body mist` — invoke for atmospheric shots
- `runes dormant` (default) vs `runes glowing gold` (active state per Bible §14.3)
- `two-handed war hammer` (only for L3+ scenes per Bible §5)

---

## 3. Material Language (physics + surface tags)

Add one or two per prompt depending on emphasis:

| Tag | When to use |
|---|---|
| `ancient weathered steel, matte black, subtle etched engravings, oxidation patina` | Armor-forward shots |
| `cracked leather bindings, storm-torn silk cape edges` | Detail shots that include cape |
| `pink-magenta emissive wolf eyes with soft bloom halo` | Any shot with pauldrons in frame |
| `deep transparent-black lens tint, black acetate frame, matte finish sunglasses` | Face shots (rarely needed if identity lock strong) |
| `thick weighty anisotropic magenta hair with cold violet rim reflections` | Hair-forward shots |
| `subtle violet particulate mist rising from below` | Full-body / atmospheric shots |

---

## 4. Camera Presets

Pick exactly one per generation. Do not mix.

### Portrait (head + shoulders)

```
head and shoulders portrait, three-quarter view, subject slightly off-center,
shallow depth of field, subject fills upper 40% of frame,
eye-level or slight above camera height, cinematic composition,
85mm lens equivalent
```

Use for: character reference, avatar sources, promo close-ups.

### Head-and-shoulders (Live2D L2 target)

```
symmetrical head and shoulders framing, direct front view but head slightly
lowered, upper armor and pauldrons visible, no arms in frame,
transparent-friendly composition,
even lighting with soft violet fill from below,
50mm lens equivalent
```

Use for: the Live2D L2 asset source PSD. Symmetry matters for rigging.

### Full body (T-pose reference)

```
full body T-pose reference, front view, arms held slightly out at sides,
neutral standing pose, feet grounded, full armor visible from sabatons
to pauldrons, character sheet composition, plain neutral background,
even flat lighting, orthographic camera feel,
zero perspective distortion
```

Use for: LoRA training data, Blender modeling reference, Live2D L4 planning.

### Cinematic poster

```
cinematic wide shot, snowy mountain valley environment, subject positioned
in lower-third rule-of-thirds, atmospheric perspective with distant peaks,
volumetric snow, key light from behind subject creating rim silhouette,
violet mist gathering around subject's feet, moody dark palette,
35mm anamorphic lens flare optional, movie poster composition
```

Use for: promo art, wallpapers, splash screens.

### Character sheet (multi-angle single image)

```
character reference sheet, three views on one canvas — front, three-quarter,
side — standing at same height, T-pose, flat neutral background,
consistent lighting across all views, orthographic feel,
professional character concept art aesthetic
```

Use for: rigging references (Blender + Live2D). Sometimes hard to
generate cleanly — may need to composite three separate generations.

### Animation reference (specific state)

```
[state-specific description],
minimal environmental detail, character-focused,
soft violet ambient lighting, subject head slightly lowered,
concept art quality, character motion reference
```

Where `[state-specific description]` picks from:
- `at rest breathing calmly` (IDLE)
- `head slightly turned listening intently` (LISTENING)
- `wolf pauldron eyes intensified bright, quiet focused thinking pose` (THINKING)
- `speaking with subtle facial motion, mouth slightly parted` (SPEAKING) —
  use sparingly, tends to over-animate the face
- `still and alert, wolf eyes fully bright` (ALERT)
- `subtle small smile, warm rim highlight edges of armor` (CELEBRATING)
- `head lowered concerned expression, dimmer wolf eyes` (CONCERNED)

---

## 5. Environment Presets

| Preset | Prompt clause |
|---|---|
| Snow default (Bible §8.3) | `snowy mountain valley, cold gray-white palette, snowfall, blowing snow, atmospheric haze` |
| Interior sanctuary | `dark stone hall, cold moonlight from high windows, minimalist ancient architecture` (rare) |
| Void | `deep dark ambient void, subject-focused, black background with subtle violet gradient` (for promo / avatar generation) |
| Warm exception (Bible §12.4) | `distant candlelight just off-camera, subtle warm rim on armor edges, mostly cold palette` — use rarely |

---

## 6. Quality Tags

Standard uplift at the end of every prompt:

```
photorealistic, highly detailed textures, professional character art,
dramatic composition, 8k, masterpiece
```

Or, for stylized-illustration targets:

```
digital painting, concept art, painterly, professional illustration,
Frank Frazetta / Wayne Reynolds mood, detailed textures, 4k
```

Pick one register per generation. Don't mix "photorealistic" with
"digital painting" — the model can't be both.

---

## 7. Negative Constraints (permanent — always include)

This full negative prompt appears in EVERY Manbeardog generation:

```
generic undead, rotting flesh, exposed bone, corpse pallor,
cartoon, anime, chibi, cel-shaded,
excessive neon, rainbow colors, bright fantasy armor,
gold shiny armor, mirror-polished metal, gleaming clean armor,
uncovered eyes, glowing eyes without sunglasses, no sunglasses,
missing sunglasses, exposed eyes glowing,
different hairstyle, blonde hair, black hair, brown hair, red hair
(not magenta), single ponytail, no ponytails, short hair, bald,
theatrical villain expression, evil snarl, bared teeth, angry face,
laughing, wide open smile, crying, tears,
overly sexualized, cleavage-exposing armor, bikini armor, revealing outfit,
random fantasy accessories, unrelated jewelry, floating orbs,
generic dark fantasy warrior, orc, generic knight,
plastic doll skin, uncanny valley, over-smoothed skin, airbrushed,
low quality, blurry, jpeg artifacts, watermark, signature, text
```

**Rationale for each block:**
- Undead-appearance negatives — keeps her from generating as monstrous
- Style negatives — keeps her out of cartoon/anime aesthetics per Bible §2
- Color negatives — enforces the palette from Bible §6
- Armor-appearance negatives — keeps armor weathered per Bible §4.6
- Sunglasses negatives — critical! LoRAs sometimes drop them
- Hair negatives — enforces color + style
- Expression negatives — enforces the allowed set from Bible §10
- Sexualization negatives — keeps the character register serious and adult
- Miscellany negatives — filters common generation garbage

**Do not remove negatives.** The negative prompt is as important as the
positive one for identity preservation.

---

## 8. Prompt Recipes (ready-to-copy)

### Recipe A — Live2D L2 source (head-and-shoulders)

```
mnbdgv1, undead elven warrior woman, calm mature protective wise,
centuries of experience, transcended death not decayed,
never theatrical never intimidating,
twin magenta burgundy high side ponytails, black rectangular sunglasses
always worn, ancient weathered black steel plate armor,
black wolf-head shoulder pauldrons with glowing pink-magenta eyes,
tattered long dark cape, pale cool-toned skin with light freckles,
pointed elven ears,
symmetrical head and shoulders framing, direct front view but head slightly
lowered, upper armor and pauldrons visible, no arms in frame,
transparent-friendly composition, even lighting with soft violet fill from
below, 50mm lens equivalent,
ancient weathered steel matte black subtle etched engravings,
pink-magenta emissive wolf eyes with soft bloom halo,
photorealistic, highly detailed textures, professional character art, 8k
```

### Recipe B — Full-body T-pose (LoRA training / Blender ref)

```
mnbdgv1, undead elven warrior woman, calm mature protective wise,
centuries of experience, transcended death not decayed,
never theatrical never intimidating,
twin magenta burgundy high side ponytails, black rectangular sunglasses
always worn, ancient weathered black steel plate armor,
black wolf-head shoulder pauldrons with glowing pink-magenta eyes,
tattered long dark cape, pale cool-toned skin with light freckles,
pointed elven ears,
full body T-pose reference, front view, arms held slightly out at sides,
neutral standing pose, feet grounded, full armor visible from sabatons
to pauldrons, character sheet composition, plain neutral background,
even flat lighting, orthographic camera feel, zero perspective distortion,
photorealistic, highly detailed textures, 8k
```

### Recipe C — Cinematic promo (wallpaper / splash)

```
mnbdgv1, undead elven warrior woman, calm mature protective wise,
centuries of experience, transcended death not decayed,
never theatrical never intimidating,
twin magenta burgundy high side ponytails, black rectangular sunglasses
always worn, ancient weathered black steel plate armor,
black wolf-head shoulder pauldrons with glowing pink-magenta eyes,
tattered long dark cape, subtle violet body mist,
cinematic wide shot, snowy mountain valley, subject positioned in
lower-third rule-of-thirds, atmospheric perspective with distant peaks,
volumetric snow, key light from behind subject creating rim silhouette,
violet mist gathering around subject's feet, moody dark palette,
movie poster composition,
photorealistic, highly detailed, 8k, masterpiece
```

### Recipe D — Emergence sequence keyframe (for animation reference)

```
mnbdgv1, undead elven warrior woman, [emergence state: silhouette barely
resolving from violet mist], pink-magenta wolf pauldron eyes visible as
two pinpoints of light in the fog before the body materializes,
[all appearance locks], animation reference concept art,
soft violet ambient light, cold snowy void background,
[quality tags]
```

The `[emergence state]` clause varies by keyframe:
- Frame 1 (intensity 0.15): `background subtly darker, mist beginning to drift`
- Frame 2 (intensity 0.35): `violet mist filling the frame, wolf pauldron eyes appearing as pinpoints`
- Frame 3 (intensity 0.60): `silhouette beginning to resolve from the mist, subtle purple through-glow behind sunglass lenses`
- Frame 4 (intensity 0.85): `character mostly resolved, armor edges visible, still slightly wreathed in mist`
- Frame 5 (intensity 1.00): `fully present, idle breathing, standard L1 pose`

Use these to generate keyframe references for the Cubism motion designer.

---

## 9. Governance

- **Never edit these prompts casually.** A change to the Identity Lock or
  Appearance Lock text drifts every future generation. If a change is
  needed, version this doc to v1.1 and note what changed.
- **Trigger word (`mnbdgv1`) is tied to the current LoRA.** When the LoRA
  moves to v2, the trigger word becomes `mnbdgv2` (or documented
  equivalent) and this doc bumps.
- **Negative prompt is a floor, not a ceiling.** You can add negatives per
  scene needs (e.g. `crowd, other characters, multiple subjects` for a
  solo composition). Do not remove any.

## Cross-references

- Character identity: `docs/visual/manbeardog_visual_bible.md`
- Workflow that produces the LoRA: `docs/visual/manbeardog_identity_workflow.md`
- Asset acceptance: `docs/visual/asset_contract.md`
- Full pipeline: `docs/visual/manbeardog_visual_production.md`
