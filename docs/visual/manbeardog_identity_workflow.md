# Manbeardog Identity Preservation Workflow

**Problem:** AI image generation drifts. A Manbeardog generated today and
another generated three months later must be immediately recognizable as
the same character. Without deliberate identity-preservation techniques,
they won't be.

**Solution:** a specific, reproducible pipeline built on free tools that
combines three complementary identity-lock mechanisms (LoRA, IPAdapter,
ControlNet), with a fallback approval gate for anything they miss.

**Scope of this doc:** the workflow itself. Tool comparisons live in
`docs/visual/manbeardog_visual_production.md` §1. Character definition
lives in `docs/visual/manbeardog_visual_bible.md`.

**Honesty on evidence:** I have not verified the exact current version
numbers or node names against live ComfyUI docs from this environment.
The workflow shape is stable and current-as-of-2025; specific version
numbers and node names should be re-verified against ComfyUI's current
UI when Toni begins Phase A. Marked with **[VERIFY]** below.

---

## The three-layer identity-lock

Character consistency = multiple techniques applied together. Any single
one drifts; the combination is robust.

### Layer 1 — Character LoRA (strongest, requires training)

A LoRA (Low-Rank Adaptation) is a small fine-tuning adapter — 40–200 MB —
that pushes SDXL toward a specific character every time it's active.
Once trained, every generation prompted with the LoRA is on-model without
per-generation conditioning.

**Strength for identity:** highest. Genuinely learns the character.
**Weakness:** requires an initial training pass.

### Layer 2 — IPAdapter (medium, no training required)

IPAdapter conditions each generation on a reference image at inference
time. Feed it an approved Manbeardog reference; it biases the generation
toward that face / hair / silhouette without training. `IPAdapter FaceID`
variants specifically lock facial features.

**Strength for identity:** high for face; moderate for full body/pose.
**Weakness:** each generation has to be conditioned; no persistent model
change.

### Layer 3 — ControlNet (composition-lock, not identity-lock)

ControlNet constrains generation to a specific pose (`OpenPose`),
composition (`Depth`, `Canny`), or lineart. It doesn't preserve identity
but pairs with the two above to lock in pose / camera / silhouette.

**Strength for identity:** none by itself.
**Strength when paired:** essential for producing the canonical front /
side / three-quarter master references (all in the same pose across
generations).

---

## The workflow — end-to-end

### Stage 1: Prepare the seed set

Input: the 6 reference images in `../../mbd/` (from Toni).
Output: `source/references/` (mirrored / copied) + a documented image
inventory.

**Actions:**
1. Copy the 6 PNGs into `source/references/` with descriptive filenames
   (`manbeardog_portrait_snow_v1.png`, etc.). Retain the originals in
   `../mbd/`.
2. Write `source/references/inventory.md` — a table listing each image
   with: which body parts are visible, which angles, what expression,
   what environment.
3. **Do not modify the references.** They are the ground truth.

### Stage 2: Concept exploration (loose identity)

Input: the 6 references.
Output: 30–60 generated variations in `source/concepts/batch_<date>/`.
Purpose: explore the design space *around* the references — different
angles, expressions, lighting — while remaining recognizably Manbeardog.

**ComfyUI workflow:**

```
[Load Checkpoint (SDXL base or JuggernautXL)]  ──▶  [KSampler]
                                                       ▲
[Load Image (reference)] ──▶ [IPAdapter FaceID Plus] ──┘
                              (weight: 0.7-0.85)
                              [VERIFY current node name]
                                                       ▲
[Prompt] "manbeardog, undead elven warrior, magenta ponytails,
         black sunglasses, wolf pauldrons, black steel armor,
         snow environment, calm mature expression, ..."
        ────────────────────────────────────────────────┘

[KSampler] ──▶ [VAE Decode] ──▶ [Save Image]
    ▲
    ├── seed: variable (explore)
    ├── steps: 30-40
    ├── cfg: 6.5-8.0
    ├── sampler: dpmpp_2m_karras
```

**Practical settings that hold up across ComfyUI versions:**
- Reference image weight ~0.75. Higher (0.9+) over-fits pose; lower (<0.5)
  loses identity.
- Prompt-length: keep the identity clauses first, environment clauses
  second, quality tags last.
- Seeds: vary widely in this stage — you want diverse concepts, not
  clones.

**Output volume:** 30–60 generations per session. Prune ruthlessly.

### Stage 3: Approval — the identity gate

Input: 30–60 concept generations.
Output: 3–8 approved images in `source/approved/`.

**Criteria for approval** (from `docs/visual/manbeardog_visual_bible.md`):
- ✅ Twin magenta/burgundy high side ponytails
- ✅ Black rectangular sunglasses
- ✅ Wolf-head pauldrons with pink-magenta eye glow
- ✅ Ancient weathered black steel armor
- ✅ Pale elven face with pointed ears
- ✅ Contemplative / calm expression (no theatrical smiles or snarls)
- ✅ Cool environment (snow, misty)
- ❌ Rejects: bright fantasy colors, cartoon style, uncovered eyes,
  villain snarl, generic anime aesthetic, wrong hair color

**Bar:** all six ✅ criteria met. Any ❌ → reject.

Approval is Toni's judgment call. This document defines the criteria; the
call is his.

### Stage 4: LoRA training

Input: the 8–14 images (6 references + 3–8 approved concepts).
Output: `characters/manbeardog/loras/manbeardog_v1.safetensors` +
`manbeardog_v1_lora_config.json`.

**Tool: Kohya_ss** (free, open-source, standard). **[VERIFY current
version]** — as of last widely-referenced state, kohya-ss/sd-scripts.

**Training approach — SDXL LoRA:**

- Base model: same SDXL checkpoint used for concepts (RealVisXL, JuggernautXL, or SDXL base)
- Network dimensions: 32 rank, 16 alpha (small, focused)
- Learning rate: 1e-4 (text encoder off — SDXL LoRA convention)
- Batch size: 1 or 2 (limited by 12GB VRAM with SDXL — close Ollama during training)
- Steps: 2000–3000 total (roughly 200–300 per image)
- Optimizer: AdamW8bit for VRAM efficiency
- Captioning: **required.** Write short natural-language captions for each
  training image emphasizing the identity features. Example:
  *"a woman with twin magenta ponytails and black rectangular sunglasses,
  wearing ancient black steel armor with wolf-head pauldrons, calm
  expression, in a snowy environment"*

**Trigger word (optional but recommended):**
- Include a unique made-up token like `mnbdgv1` in every caption
- At inference: prompt with `mnbdgv1, ...` to activate the LoRA cleanly
- Without a trigger word, the LoRA leaks into every generation; with one,
  it's opt-in per prompt

**Training config** — save alongside the .safetensors as
`manbeardog_v1_lora_config.json`:

```json
{
  "base_model": "sdxl_base_1.0",
  "network_dim": 32,
  "network_alpha": 16,
  "learning_rate": 1e-4,
  "batch_size": 1,
  "total_steps": 2500,
  "optimizer": "AdamW8bit",
  "text_encoder_lr": 0,
  "trigger_word": "mnbdgv1",
  "training_images": ["ref_001.png", "ref_002.png", "..."],
  "date_trained": "2026-07-XX",
  "trainer_version": "kohya-ss/sd-scripts@<commit>"
}
```

**Validation after training:**
- Generate 8+ images from unseen prompts (locations, poses not in the
  training set) using the LoRA
- All 8 should be recognizably Manbeardog per the Stage-3 criteria
- If less than 6/8 pass, retrain with adjusted settings
- Common failures:
  - Overfitting (Manbeardog in a training pose regardless of prompt) → reduce steps or add regularization images
  - Underfitting (recognizable but drifty) → more steps or higher LR

### Stage 5: Master artwork generation

Input: `manbeardog_v1.safetensors` LoRA.
Output: three canonical reference renders — front, three-quarter, side —
at 2048×2048+ resolution.

**ComfyUI workflow:**

```
[Load Checkpoint (SDXL)]  ──▶  [KSampler]
                                    ▲
[Load LoRA (manbeardog_v1)] ────────┤
   (strength: 0.85-1.0)             │
                                    │
[Prompt] "mnbdgv1, T-pose, front view, character reference sheet,
          full body, neutral expression, ..."                      ─┘
                                    ▲
[Load ControlNet OpenPose]          │
[Load Pose Reference Image] ──▶ [Apply ControlNet]
   (T-pose front)                   │
                                    ▲
[KSampler]                          │
    ├── seed: fixed (2026 for front, 2027 for side, 2028 for 3/4)
    ├── steps: 40+
    ├── cfg: 7.0
    ├── resolution: 1536x1536 base, upscale to 2048+ via SDXL refiner
```

**Three master views** — same seed, same LoRA, same prompt (except
"front view" / "side view" / "three-quarter view"), OpenPose reference
locks the pose:

1. `characters/manbeardog/master/exports/manbeardog_master_front_v1.png`
2. `characters/manbeardog/master/exports/manbeardog_master_side_v1.png`
3. `characters/manbeardog/master/exports/manbeardog_master_three_quarter_v1.png`

These become the canonical reference for **everything downstream** —
layer separation for Live2D, retopology reference for Blender, marketing
material for the promo folder. If they're wrong, everything else is wrong.

### Stage 6: Ongoing identity preservation (production life)

Input: `manbeardog_v1.safetensors` + workflow templates.
Output: any future Manbeardog imagery.

**Every new generation MUST:**
1. Include the LoRA (`manbeardog_v1` at strength 0.85–1.0)
2. Include the trigger word (`mnbdgv1`) in the prompt
3. Include IPAdapter conditioned on an approved master reference (weight 0.4–0.6, lower than concept stage since the LoRA is doing the heavy lifting)
4. Pass the identity checklist from Stage 3 before being saved outside a
   `concepts/` folder

**Regenerating the LoRA** (v2, v3):
- Only when the character identity is deliberately evolving (e.g. bible
  goes to v2.0)
- Old LoRAs stay frozen — a `manbeardog_v1.safetensors` from month one
  works forever
- Version bump means: new training set, new LoRA, updated
  `characters/manbeardog/loras/` entry, updated identity workflow doc

---

## Approval workflow — the human gate

Automated identity checks can't catch every drift. A human gate is
mandatory before an asset promotes past `source/concepts/`.

```
Concept generated
      │
      ▼
Auto-check: LoRA active? Trigger word present? Resolution ≥ target?
      │
      ▼ (pass)
Manual review: Stage 3 criteria (6 ✅, 0 ❌)
      │
      ▼ (approved)
Move to source/approved/  → assign metadata.json per asset_contract.md
      │
      ▼ (if canonical reference)
Move to characters/manbeardog/master/exports/  → freeze as versioned reference
```

Rejected concepts stay in `source/concepts/batch_<date>/`. They're not
deleted (useful for post-mortem "why did that concept drift?") but they
never enter production folders.

---

## Tools referenced

- **ComfyUI** — node-based SDXL/FLUX interface. Free, GPLv3. Primary
  generation environment.
- **Kohya_ss** (sd-scripts) — LoRA training scripts. Free, Apache 2.0.
- **IPAdapter Plus for ComfyUI** — reference-image conditioning. Free.
  **[VERIFY]** current node names — the IPAdapter ecosystem has had node
  renames.
- **ControlNet models** — OpenPose, Depth, Canny. Free, various licenses
  (most Apache 2.0 or CreativeML Open RAIL-M).
- **SDXL base 1.0** (or a community fine-tune: JuggernautXL, RealVisXL) —
  the underlying image model. Free, CreativeML Open RAIL-M.

## Uncertainties I explicitly flagged

- **Exact IPAdapter Plus node names** in the current ComfyUI ecosystem —
  verify at Phase A start. The technique is stable; the exact click-path
  in the UI shifts.
- **Optimal LoRA rank/alpha for character preservation** — 32/16 is a
  reasonable default but the community has active debate. Recommendation:
  train one at 32/16 first; if under-fitting, escalate to 64/32.
- **SDXL vs. FLUX for the base model** — FLUX has better prompt adherence
  but heavier VRAM cost. SDXL recommended for the 4070 alongside a
  once-closed Ollama.
- **Regularization images** for LoRA training — improves generalization
  but adds prep work. Start without; add if the LoRA overfits.

## Cross-references

- Character definition: `docs/visual/manbeardog_visual_bible.md`
- Approved-concept prompt library: `docs/visual/manbeardog_prompt_system.md`
- Asset acceptance contract: `docs/visual/asset_contract.md`
- Full pipeline context: `docs/visual/manbeardog_visual_production.md`
