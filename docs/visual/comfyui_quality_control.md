# ComfyUI Quality Control

**Purpose:** the fast-reject and fast-accept criteria applied at the
ComfyUI *output level* — before an image makes it into
`visual/source/concepts/manbeardog_v1/`. This is upstream of the
`asset_review_checklist.md` (which governs the ecosystem-wide gate).

Think of it as: **inbox triage**. Most ComfyUI outputs never deserve a
full Bible review — they should be deleted in seconds. The few that
survive triage go to full Bible review before any promotion.

Related:
- `manbeardog_visual_bible.md` — the character source of truth
- `phase_a_execution_guide.md` — the Phase A plan
- `asset_review_checklist.md` — the ecosystem review workflow
- `comfyui_pipeline.md` — ComfyUI installation + workflow overview

---

## The two-pass rule

Every ComfyUI output goes through:

1. **Pass 1 (this doc):** ~2 seconds of eyeballing. Auto-reject signals.
   Most images fail here and get deleted.
2. **Pass 2 (Bible review):** ~30 seconds of Bible cross-reference.
   Only survivors of Pass 1 reach this pass. See
   `asset_review_checklist.md` § Step 1.

**Rejection at Pass 1 is not a personal failing of the model.** SDXL +
IPAdapter is a stochastic system. Expect 70-90% rejection rate during
Stage 1 exploration. That's healthy.

---

## Pass 1 — auto-reject signals

Delete immediately (~2 seconds each) on any of these:

### Face / identity signals

- [ ] Face reads as **undead** — grey/corpse skin, sunken eyes, wraith features
- [ ] Face reads as **horror** — scary, threatening, menacing (Manbeardog is
      protective, not menacing)
- [ ] **Sunglasses missing** or **transparent** (must be opaque black)
- [ ] Eyes **directly visible / glowing** (not through-glow on the lens
      surface — actual visible glowing eyeballs where the sunglasses
      should be)
- [ ] **Wolf/dog features on the face itself** (Manbeardog's wolf iconography
      lives on the pauldrons, never on her face)
- [ ] Face **doesn't match** Stage 1's approved portrait (only applicable
      from Stage 2 onward)

### Hair signals

- [ ] Hair color drifted — anything other than warm magenta/burgundy
- [ ] Hair style drifted — not twin high side ponytails (loose, single
      braid, buns, short cut, etc.)
- [ ] Hair covers the **wolf pauldrons** entirely

### Armor signals (Stages 2, 3, 4)

- [ ] Armor is **any color other than** black steel / dark iron / patinated
- [ ] Armor is **shiny / polished** (must be matte weathered)
- [ ] Armor is **spiky / exaggerated fantasy**
- [ ] **Wolf pauldrons missing** or replaced with generic shoulder plates
- [ ] Rune glow visible in **default state** (runes are DORMANT at
      baseline; glow is a state, not a texture)
- [ ] Armor is **too damaged** (post-apocalyptic ruin rather than
      well-maintained veteran)
- [ ] **Sexualized armor cut** — bikini plate, exposed midriff, cleavage
      window

### Color / atmosphere signals

- [ ] **Neon / cyberpunk** palette
- [ ] Bright fantasy pink or bubblegum accents
- [ ] Warm sunny lighting dominating (Manbeardog's world is cold —
      warmth is only used as counter-point, not primary)
- [ ] Mist looks like **smoke** (curls fast, dissipates like fire smoke)
      when the workflow was targeting the water-slow violet mist

### Composition signals

- [ ] Cartoon / anime proportions (unless explicitly testing style)
- [ ] Wrong pose — the workflow requested T-pose but got action pose
- [ ] Character not centered when the workflow requested reference-sheet framing

### Metadata signals

- [ ] Image was generated with **wrong seed** (not matching the fixed seed
      you intended)
- [ ] Image was generated with **wrong IPAdapter reference** (should be
      the Stage 1 approved portrait for Stages 2-4; you accidentally
      pointed it at `NERO.png`)

**One checked box = delete.** Do not spend time debating a Pass-1
reject. There will be more images.

---

## Pass 2 — Bible review triggers

Images that survive Pass 1 go to full Bible review. Cross-reference
against `manbeardog_visual_bible.md`:

- Bible §4 — character (skin tone, ear shape, face maturity)
- Bible §6 — color palette compliance
- Bible §7 — armor material language
- Bible §10 — expression allowed set
- Bible §11 — presence manifestation
- Bible §14 — divergences from brief (already resolved decisions)

If Pass 2 fails any Bible check: **reject with feedback** — write it
in the folder's `manifest.json` rejection log (or in
`phase_a_status.md`'s Rejections log). Feedback like "hair color drifts
warm-magenta → true-red-orange, prompt needs stronger anchor" is useful
for improving the next batch's prompts.

---

## Pass 3 — accept signals (promote to keeper)

An image that survives Pass 1 AND Pass 2 gets promoted to
`visual/source/concepts/manbeardog_v1/<folder>/` as a keeper.

Accept when **all** of these are true:

- [ ] Identity is **recognizable** — you'd know it was Manbeardog even
      shown out of context six months from now
- [ ] All **non-negotiable identity elements** are present and correct:
      sunglasses, twin magenta ponytails, wolf pauldrons (in armor
      shots), the composed mature expression
- [ ] Image is **production-useful** — could serve its purpose in the
      Phase A execution guide (either as reference, as training data,
      or as approved deliverable)
- [ ] No forbidden elements from Pass 1 or Pass 2 present
- [ ] Metadata is captured (PNG embedded workflow + manifest entry)

---

## Reject rate expectations

Rough rates by stage [VERIFY on your actual runs]:

| Stage | Reject rate | Reasoning |
|---|---|---|
| Stage 1 face_exploration | 70-90% | Exploration = high variance |
| Stage 1 portrait refinement | 30-50% | Locked seed + high IPAdapter = tighter |
| Stage 1 expression sheet | 20-40% | Very high IPAdapter weight; small variance |
| Stage 2 armor exploration | 50-70% | Complex composition, more failure modes |
| Stage 2 material studies | 30-50% | Fewer identity constraints |
| Stage 3 lighting/mist | 40-60% | Atmosphere is hard to prompt precisely |
| Stage 3 emergence keyframes | 60-80% | 4-image sequence must feel continuous |
| Stage 4 production references | 40-60% | ControlNet + IPAdapter both must land |

**If you see a much lower reject rate**, either:
- Your prompt is too permissive (you'll get identity drift downstream), or
- Your standards drifted (recalibrate against the Bible)

**If you see a much higher reject rate**:
- Prompt is fighting the model (weight balance is off, IPAdapter is
  too low or too high)
- Reference image is wrong (Stage 1: use `NERO.png`; Stage 2+: use
  Stage 1's approved portrait)
- Model choice is wrong for the aesthetic (try a different SDXL
  fine-tune)

---

## Rejection log format

Track rejections at the folder level (in each folder's
`manifest.json` — add a `rejections` array) OR at the phase level
(in `phase_a_status.md`'s Rejections log).

Format:

```
YYYY-MM-DD | folder | reason | lesson learned
```

Example:

```
2026-07-14 | identity/face_exploration | hair drifted to reddish-orange | need stronger "warm magenta burgundy" anchor in Appearance Lock
2026-07-14 | design/armor_exploration | pauldrons kept generating as generic shoulder plates | may need dedicated wolf-shape reference or a wolf-specific IPAdapter pass
2026-07-15 | atmosphere/mist | mist reads as fire smoke | prompt needs "water-slow" phrasing more prominent; may need negative "smoke, wisps of smoke"
```

The rejection log is your feedback loop — patterns tell you what to
change in the next batch's prompts.

---

## What NOT to do

- **Do NOT keep rejects "just in case."** They accumulate, dilute
  attention, and provide bad reference for downstream stages
- **Do NOT batch-accept a promising direction.** One promising image
  ≠ ten similar promising images. Overproduction weakens curation
- **Do NOT skip Pass 2 for images that "look great."** Great-looking
  images that fail the Bible are the most dangerous — they seduce
  you into building on drift
- **Do NOT rewrite the Bible to match the images.** Bible is the source
  of truth. If ComfyUI won't produce Bible-compliant output, the prompt
  or workflow needs adjustment. The Bible does NOT get retuned to make
  the model happy.

---

## When to escalate

If you're stuck (high reject rate, prompts fighting model, no clear
winner emerging after ~50 candidates in a folder):

1. **Re-read the folder's Phase A README** — you may have drifted from
   the intended target
2. **Compare against the Bible** — has your standard shifted?
3. **Change ONE variable** — different SDXL fine-tune, or different
   IPAdapter weight, or different prompt clause. Don't change everything
4. **Take a break** — decision fatigue makes curation worse

If genuinely stuck for multiple sessions on the same folder, that folder's
target may need re-scoping. Document the difficulty in
`phase_a_status.md` before advancing.

---

## Governance

- **v1.0** — 2026-07-13. Initial for Phase A.
- **Bump when:** thresholds change, new Phase B/C stages need their
  own QC criteria, or the reject rate table needs updating from real data.
