---
id: visual.phase-a-execution-guide
title: "Phase A — Manbeardog Character Genesis — Execution Guide"
layer: operational
type: reference
status: active
owner: shared
created: 2026-07-13
updated: 2026-07-17
---

# Phase A — Manbeardog Character Genesis — Execution Guide

**Owner:** Toni.
**Date opened:** 2026-07-13.
**Workspace:** `C:\Users\tonij\iCloudDrive\Nero AI\visual\source\concepts\manbeardog_v1\`
**Governance:** [`asset_review_checklist.md`](asset_review_checklist.md) fast-track for `source/concepts/` — Bible review is optional per image, mandatory before **promotion out** of `manbeardog_v1/` into `source/approved/` or training sets.

---

## Purpose

Phase A produces the **first canonical Manbeardog reference package** — the
source of truth for every downstream visual asset (LoRA training set, Live2D
PSD, Blender master, Unreal implementation, mobile emblem, promo renders).

This document is your operator's manual. It does **not** produce images —
Claude cannot generate images. It prepares the workspace, the prompts, the
curation criteria, and the completion audit so your time at ComfyUI goes to
generating and choosing, not planning.

---

## What Claude prepared for this phase

```
D:\mbd AI\docs\visual\phase_a_execution_guide.md   ← this file

C:\Users\tonij\iCloudDrive\Nero AI\visual\source\concepts\manbeardog_v1\
├── README.md                    workspace orientation
├── manifest.template.json       per-folder metadata template
├── phase_a_status.md            living checklist you fill as you go
├── identity/README.md           Stage 1 prompts + curation criteria
├── design/README.md             Stage 2 prompts + curation criteria
├── atmosphere/README.md         Stage 3 prompts + curation criteria
└── production/README.md         Stage 4 prompts + curation criteria
```

Nothing else. No JSON workflow files (ComfyUI node names drift across
versions — safer as text descriptions). No pre-generated images.

---

## Prerequisites

Confirm before starting:

- [ ] **ComfyUI** installed and launching cleanly
- [ ] **Base model** — SDXL 1.0 base + refiner, or a fine-tune (Juggernaut XL v10 /
      RealVisXL v5 / DreamShaper XL are all reasonable starting points).
      **Not FLUX** for Phase A — SDXL has more mature IPAdapter/ControlNet
      ecosystem and the whole prompt system was designed against SDXL.
- [ ] **IPAdapter Plus** custom nodes installed (for identity conditioning from
      the `mbd/` reference images)
- [ ] **ControlNet SDXL** — at minimum OpenPose SDXL (for turnaround control in
      Stage 4)
- [ ] **VAE** — matched to base model (typically bundled)
- [ ] **Reference images** — the 6 PNGs in `C:\Users\tonij\iCloudDrive\Nero AI\mbd\`
      are your IPAdapter conditioning source. `NERO.png` in particular is Toni's
      flagged face/hair reference.
- [ ] **VRAM headroom** — 4070 (12GB) is enough for SDXL + IPAdapter + one
      ControlNet at 1024×1024 or 1536×1536

If any of the above fails, resolve **before** starting Stage 1. Do not
generate on unstable infrastructure — bad seeds get keepable.

---

## Time budget (realistic)

| Stage | Effort | Notes |
|-------|--------|-------|
| Stage 1 — Identity Lock | 1–2 evenings | ~30–50 face generations, 1 approved portrait |
| Stage 2 — Armor Identity | 1 evening | ~15–25 armor/pauldron generations, 1 approved silhouette |
| Stage 3 — Presence Identity | 1 evening | ~10–20 atmosphere generations, 1 approved lighting/mist study |
| Stage 4 — Production Reference Set | 1–2 evenings | 4 views + expression sheet (10 expressions), ControlNet-driven |
| **Total** | **4–6 evenings** | |

Do not compress. Rushing Stage 1 corrupts every downstream stage — because
downstream stages **use Stage 1's approved portrait as IPAdapter reference**.
Get the face right first.

---

## Working principle

> **Every stage is: generate → curate → refine → approve exactly one.**

Not "generate a hundred and keep the best." Not "keep every one you like."

Each folder has a specific target output. When you have the target, you
**stop generating in that folder** and move on. Overproduction is the
enemy — every extra image dilutes attention and risks identity drift.

The pipeline is:

```
face_exploration/   (30-50 candidates)
        │
        │   curation ↓
        ▼
approved_portrait/  (1 image — the definitive face)
        │
        │   used as IPAdapter reference in every subsequent stage
        ▼
   Stages 2, 3, 4 build on the approved face
```

Approved portrait first. Everything downstream is built on it.

---

## Stage 1 — Identity Lock

**Folder:** `identity/`
**Details:** `C:\Users\tonij\iCloudDrive\Nero AI\visual\source\concepts\manbeardog_v1\identity\README.md` (off-repo)
(open the file at the actual filesystem path — the link above is illustrative)

Goal: find the definitive Manbeardog face and silhouette. No armor
distraction, no complex environment. Head-and-shoulders, neutral pose,
sunglasses present, hair defined.

Output:
- `face_exploration/` — 30–50 candidates + `manifest.json`
- `approved_portrait/` — **exactly 1** chosen from face_exploration
- `expression_sheet/` — 8–10 expressions on the approved face

Do not advance to Stage 2 until `approved_portrait/` has exactly one file.

---

## Stage 2 — Armor Identity Lock

**Folder:** `design/`
**Details:** `C:\Users\tonij\iCloudDrive\Nero AI\visual\source\concepts\manbeardog_v1\design\README.md` (off-repo)

Goal: define the armor language. Ancient weathered black steel, functional
warrior wear, wolf pauldrons, dormant rune placement, hair-armor
integration.

Output:
- `armor_exploration/` — 15–25 candidates, IPAdapter-conditioned on Stage 1's
  approved portrait
- `wolf_pauldron_design/` — 5–10 focused pauldron studies (close-crop shoulder shots)
- `hair_design/` — 5–10 hair-armor integration studies
- `material_studies/` — 5–10 close-up material studies (armor plate detail, rune surface, cape fabric)

Do not advance to Stage 3 until one armor direction is approved.

---

## Stage 3 — Presence Identity Lock

**Folder:** `atmosphere/`
**Details:** `C:\Users\tonij\iCloudDrive\Nero AI\visual\source\concepts\manbeardog_v1\atmosphere\README.md` (off-repo)

Goal: define the NERO manifestation language. Violet mist, purple energy,
through-glow, cinematic cool lighting, emergence atmosphere.

Output:
- `lighting/` — 5–10 lighting studies (cold rim, purple hemisphere, moonlit gray)
- `mist/` — 5–10 mist behavior studies (from wisps to enveloping fog)
- `emergence/` — 5–10 emergence keyframes (uses Recipe D from the prompt system)

---

## Stage 4 — Production Reference Set

**Folder:** `production/`
**Details:** `C:\Users\tonij\iCloudDrive\Nero AI\visual\source\concepts\manbeardog_v1\production\README.md` (off-repo)

Goal: multi-view reference set suitable for downstream production (LoRA
training, Blender modeling, Live2D rigging).

Output — all in ControlNet-locked pose with **the same approved face**:
- `front_reference/` — 1 clean T-pose front view
- `side_reference/` — 1 clean profile view
- `back_reference/` — 1 clean back view
- `full_body_reference/` — 1 full-body neutral pose showing all armor + cape + pauldrons

Consistency across the 4 views is more important than any individual view
looking spectacular. Use ControlNet OpenPose for pose lock. Same IPAdapter
reference for all 4.

---

## Metadata pattern

**Per-folder** `manifest.json`, not per-image sidecar (Phase A is
exploratory — per-image is too heavy).

Template: `manifest.template.json` (top-level in `manbeardog_v1/`). Copy it
into each leaf folder and rename to `manifest.json`, then append an entry
for every kept generation.

Rejected generations do **not** get manifest entries — they get deleted or
moved to a scratch folder outside `manbeardog_v1/`. `manifest.json` is a
record of the survivors.

---

## Curation loop (per-folder)

For each generation:

1. **First-glance rejection** — obvious failures (undead face, missing
   sunglasses, wrong hair color, neon anything) → delete immediately.
2. **Bible spot-check** — cross-reference against
   `docs/visual/manbeardog_visual_bible.md` §4 (character), §6 (colour),
   §10 (expression). Miss on any core identity element → delete.
3. **Comparative review** — after 10–15 generations in a folder, open them
   together. Which are strongest? Delete anything not in the top ~30%.
4. **Batch prompt refinement** — pick your best 3, note what worked in the
   prompt. Adjust the prompt for the next batch. Iterate.
5. **Approval promotion** — when one clearly stands above the rest, rename
   it per the folder's rename convention and add its full metadata to
   `manifest.json`.

---

## Rejection criteria (from the Phase A brief)

Immediate reject on any of these:

- Generic undead warrior appearance
- Exposed glowing eyes replacing sunglasses (glow through lenses is OK; eyes
  visible is not)
- Neon cyberpunk colors
- Excessive spikes
- Random fantasy accessories not in the Bible
- Bright colorful armor (armor stays black steel)
- Sexualized character design
- Cartoon proportions (unless explicitly testing style — Phase A doesn't)
- Inconsistent hair (color or style drift from `NERO.png` reference)
- Missing wolf pauldrons (in any armor shot — pauldrons are non-negotiable)

The prompt system's negative-prompt block already targets most of these;
if they appear anyway, the prompt weight of the identity block is losing to
the negative. Increase Identity Lock weight or IPAdapter strength.

---

## When Phase A is complete

Sign off in `phase_a_status.md` when **all** of these are true:

- [ ] `identity/approved_portrait/` contains exactly 1 image + manifest entry
- [ ] `identity/expression_sheet/` contains ≥6 expressions on the approved face
- [ ] `design/armor_exploration/` has an approved-direction folder or clearly
      marked winning image, referenced in the manifest with `approval_status: "approved"`
- [ ] `design/wolf_pauldron_design/` has ≥3 keeper studies + 1 marked approved
- [ ] `atmosphere/` has ≥1 approved lighting study + ≥1 approved mist study +
      ≥1 approved emergence keyframe
- [ ] `production/` has all 4 views + `expression_sheet` — all showing the
      same face and same armor
- [ ] All approved images have `manifest.json` entries with full metadata
- [ ] `phase_a_status.md` completion checklist ticked

**Success criterion** (from the brief):

> Enough consistent references exist for future LoRA training. Future
> Live2D/Blender production can begin without redesign.

If a downstream production stage would need you to "regenerate a different
face" or "redo the armor" — Phase A is not done.

---

## What comes after Phase A

**Phase B — LoRA training** (from
[`manbeardog_identity_workflow.md`](manbeardog_identity_workflow.md)):

- The `production/` set + `identity/expression_sheet/` + selected keepers from
  `design/` become the training set for `manbeardog_v1.safetensors`
- Trained via Kohya_ss per the identity workflow spec (32 rank / 16 alpha,
  ~2500 steps, trigger word `mnbdgv1`)
- Validation gate: 8/8 unseen prompts recognizably Manbeardog

**Phase C — Live2D rigging** — uses the approved portrait as the source PSD
starting point.

**Phase D — Blender master** — uses the 4-view production references as
modeling reference planes.

**Phase E — PresenceBroadcastService** — the code work Claude can do in
parallel while Toni does asset production.

---

## Governance note

This document is v1.0 for Phase A specifically. It does **not** replace the
[`asset_review_checklist.md`](asset_review_checklist.md) — that checklist
governs asset arrival for the whole ecosystem. This document is the
project-plan for producing the first assets that will then flow through the
review checklist.

`source/concepts/` is fast-tracked in the review checklist ("throwaway
exploration") — but the approved outputs of Phase A are **not** throwaway.
When they move out of `manbeardog_v1/` (into `source/approved/` or into the
LoRA training set), they go through the full 7-step review.
