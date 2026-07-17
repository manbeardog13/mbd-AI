---
id: visual.manbeardog-identity-profile
title: "Manbeardog — Identity Profile v1.0"
layer: operational
type: reference
status: active
owner: shared
created: 2026-07-13
updated: 2026-07-17
---

# Manbeardog — Identity Profile v1.0

**Status:** DRAFT — awaiting Creative Director (Toni) approval.
**Source of truth:** the 6 canonical reference images in
`C:\Users\tonij\iCloudDrive\Nero AI\mbd\` (read-only input library).
**Role:** this is the machine-readable identity contract. Every generation
assembles from it; the Visual Audit Director scores every candidate against it.
It evolves ONLY by explicit Toni approval (v1.1, v1.2, …). Never edited silently.

> **Recognition test (the only test that matters):** *"Would Toni instantly say
> 'that's Manbeardog'?"* If any of the six signature traits below is wrong, it fails —
> no matter how good the image looks.

---

## Render register (this is "gamify her")

Semi-realistic **stylized AAA game-character key art** — the register of a
high-end game cinematic/render. **North-star reference: `9C16…png`** (full-body,
dark background). NOT photoreal portrait photography. NOT anime/cel-shaded.
Think polished 3D character render / painterly game splash art.

- Idealized-but-grounded proportions, clean readable silhouette.
- Cinematic rim/edge lighting, subtle subsurface, crisp material definition.
- She must read as a **designed character**, not a photographed cosplayer.

---

## The six signature traits (all mandatory)

### 1. Hair — twin high perky pigtails
Two **high, perky pigtails** set high on the head (Harley-Quinn placement),
voluminous and wavy, falling long past the shoulders. Vivid **magenta** at the
crown transitioning toward deep **burgundy** in the lengths.
- ✅ prompt: `two high perky pigtails, twin-tails high on the head, voluminous wavy magenta-to-burgundy hair, symmetrical pigtails`
- ⛔ negative: `single ponytail, one ponytail, low ponytail, side ponytail, braid, fishtail, intertwined hair, loose hair only, short hair, bald`
- evidence: 9C16, A4C0, NERO (all show the twin high pigtails)

### 2. Sunglasses — plain black wayfarers
**Simple, clean, thick-framed BLACK wayfarer/rectangular sunglasses.** Flat top
edge, slightly rounded lower corners, solid **near-black opaque lenses** (an
occasional faint violet reflection is OK). They are ordinary cool sunglasses.
- ✅ prompt: `plain black wayfarer sunglasses, thick black rectangular frames, solid dark lenses, simple classic sunglasses`
- ⛔ negative: **`ornate glasses, sci-fi visor, fantasy frames, cat-eye, pointed frames, metal filigree frames, rimless, round glasses, wire frames, transparent lenses, see-through tinted lenses, mirrored lenses, decorated temples`**
- evidence: NERO, 9C16, A4C0 — all plain black wayfarers. *This trait has been the #1 drift source; enforce hard.*

### 3. Eyes — glowing violet magic
The eyes/pupils **glow vivid violet-magenta**, visible as two luminous points
**through/behind the dark lenses**. The glow is her supernatural "tell."
- ✅ prompt: `glowing violet eyes, luminous magenta-violet glow behind the dark lenses, magical glowing pupils`
- ⛔ negative: `dull eyes, normal human eyes, no glow, exposed bare eyes without glasses`
- evidence: 9C16, A4C0, NERO

### 4. Armor — obsidian black plate
**Obsidian black metal PLATE armor** — glossy/weathered black steel with ornate
etched filigree; feminine cuirass/corset silhouette; segmented gauntlets, tassets,
greaves. Battle-worn but elegant. **Never leather, cloth, brown, or studded-leather.**
- ✅ prompt: `obsidian black metal plate armor, polished black steel, ornate etched filigree, feminine cuirass, battle-worn elegant plate`
- ⛔ negative: **`leather armor, studded leather, brown armor, cloth, fabric armor, fur, bright armor, gold armor, silver shiny armor`**
- evidence: 9C16, A4C0, 9500, 9A63

### 5. Pauldrons — wolf heads with glowing violet eyes (THE signature)
Both shoulders bear **large sculpted BLACK wolf heads** (obsidian metal), snarling
with open maws and bared fangs, **eyes glowing violet-magenta**. They are *armor
sculpture*, not live animals.
- ✅ prompt: `large shoulder pauldrons sculpted as snarling black wolf heads, obsidian wolf-head spaulders on both shoulders, glowing violet wolf eyes, open fanged maws`
- ⛔ negative: **`live wolf, real wolf animal, wolf companion, dog, husky, pet, holding an animal, plain pauldrons, wolf ears on head`**
- evidence: 9C16 (clearest), A4C0, 9500, 9A63

### 6. Aura — violet energy
Violet **mist and faint crackling energy arcs** around her; cool desaturated
surroundings when present. For production she is **background-independent** —
render on plain/void so she can be composited and animated.
- ✅ prompt: `faint violet energy mist, subtle crackling violet arcs`
- ⛔ negative (production): `busy background, snowy landscape, mountains, forest, scenery`

---

## Face & body

- **Face:** youthful-mature elven woman; **pale cool skin with light freckles**;
  calm, composed, quietly serious; defined cheekbones, soft jaw, **mauve/plum lips**.
- **Ears:** **pointed elven ears** (visible past the pigtails).
- **Build:** athletic warrior; confident, grounded stance; not sexualized.
- ⛔ negative: `oversexualized, cleavage-exposing armor, bikini armor, doll skin, uncanny valley`

---

## Palette (approximate targets)

| Role | Color | Hex (approx) |
|---|---|---|
| Armor base | obsidian black | `#0A0A0D` |
| Hair root | magenta | `#C21E6A` |
| Hair tips | burgundy | `#5E1330` |
| Magic glow | violet | `#9A46FF` / `#B673FF` |
| Skin | pale cool | `#E7DCDD` |
| Lips | plum | `#7C3A5A` |
| Steel highlight | cold gray | `#3A3D45` |

---

## Production composition defaults

- **Framing:** front, symmetrical, character fills frame; **both pigtails + both
  wolf pauldrons visible**; head-to-mid-thigh for identity, full-body for turnarounds.
- **Background:** plain flat neutral / void (for clean cutout + animation). Snow
  scenes are promo-only, never for identity/production references.
- **Aspect:** SDXL-native buckets (832×1216 portrait, 1024×1024 bust, 896×1152).

---

## Machine block (for prompt assembly + audit scoring)

```json
{
  "identity_profile_version": "1.0",
  "render_register": "stylized_AAA_game_key_art",
  "signature_traits": {
    "hair": {"desc": "two high perky pigtails, magenta-to-burgundy, voluminous wavy", "weight": 0.18},
    "sunglasses": {"desc": "plain thick black wayfarer, opaque dark lenses, no ornamentation", "weight": 0.18},
    "eyes": {"desc": "glowing violet-magenta through the lenses", "weight": 0.12},
    "armor": {"desc": "obsidian black metal plate, ornate etched, feminine cuirass", "weight": 0.16},
    "pauldrons": {"desc": "snarling black wolf-head spaulders both shoulders, glowing violet eyes", "weight": 0.24},
    "aura": {"desc": "violet mist and crackling arcs", "weight": 0.06},
    "face": {"desc": "pale freckled elven woman, calm serious, pointed ears, plum lips", "weight": 0.06}
  },
  "hard_negatives": ["ornate/sci-fi/round/cat-eye glasses","transparent lenses","leather armor","live wolf","single ponytail","braid","snow/landscape background","anime","photoreal photograph"],
  "palette": {"armor":"#0A0A0D","hair_root":"#C21E6A","hair_tip":"#5E1330","glow":"#9A46FF","skin":"#E7DCDD","lips":"#7C3A5A"},
  "canonical_reference": "9C16 (north-star), A4C0, NERO, 9500, 9A63, 8F05"
}
```

---

## Why prior passes drifted (root cause, logged)

1. **Glasses** rendered ornate/sci-fi because the checkpoint + IPAdapter reinterpreted
   "rectangular sunglasses." → Fix: explicit "plain black wayfarer" + hard negatives above.
2. **Photoreal checkpoint** (RealVisXL) can't "gamify." → Fix: stylized game-art checkpoint (model toolbox, roadmap Del. 3).
3. **IPAdapter anchored on `NERO.png`** (a photoreal face crop) dragged realism + loose hair + snow, and never carried the pauldrons. → Fix: condition identity on the **full-figure `9C16`** (shows pigtails + pauldrons) via IPAdapter + reference/ControlNet, and reduce style bleed.
4. **Pigtails/pauldrons** need reference conditioning, not text alone.

---

## Version history
- **v1.0 (DRAFT, 2026-07-13):** initial profile from the 6-image reference library. Awaiting Toni approval → then becomes the frozen contract.
