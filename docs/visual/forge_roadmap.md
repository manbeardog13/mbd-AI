---
id: visual.forge-roadmap
title: "NERO Visual Forge — Architecture & Roadmap v0.1"
layer: operational
type: reference
status: active
owner: shared
created: 2026-07-13
updated: 2026-07-17
---

# NERO Visual Forge — Architecture & Roadmap v0.1

**Role:** Technical Art Director · Pipeline Engineer · Character Production Lead.
**Mandate:** a reproducible, versioned, local, €0 character-production *studio* for
Manbeardog on an RTX 4070 (12 GB) — not an image-gen experiment.
**Prime directive:** one permanent identity (`manbeardog_identity_profile.md`),
protected by a closed-loop QA system. Generation is cheap; identity is priceless.

Legend: ✅ done · 🔜 next · 🔬 needs current-version verification before locking
(engineering rule: never invent node names, APIs, or versions).

---

## 0. Storage architecture (honors "outputs local, not iCloud")

| Location | Purpose | Sync |
|---|---|---|
| `C:\…\iCloudDrive\Nero AI\mbd\` | **Canonical reference library** (input, read-only) | iCloud (input only) |
| `D:\mbd AI\` (git repo) | Code, docs, Identity Profile, workflow JSON, **metadata DB** (small, versioned) | git |
| `D:\NERO_Forge\` ✅ | **All heavy output**: raw, review, approved, datasets, LoRA, live2d, blender, marketing, exports, audit | local only, non-git |
| `D:\ComfyUI\` | The generation engine | local only |

Rule: **generated images never go to iCloud.** References never leave it.

---

## 1. Software stack (Deliverable 1)

**Chosen engine — ComfyUI** ✅ (installed, v0.27.0). Node-graph = reproducible,
scriptable via HTTP API, versionable JSON, best ControlNet/IPAdapter ecosystem,
lowest-VRAM scheduler control. Rejected for the *engine* role: **A1111** (slower to
reproduce, weaker graph control), **Forge** (great VRAM economy but less
composable for a multi-workflow studio) 🔬, **InvokeAI** (excellent UX/canvas,
weaker for scripted batch + custom nodes) 🔬. → *Forge/Invoke may still earn a
secondary "artist canvas" role; verify current 2026 state before deciding.*

Supporting tools (roles, not popularity):
- **Krita + Krita AI (acly's `krita-ai-diffusion`, talks to ComfyUI)** 🔬 — human inpaint/paintover canvas.
- **Kohya_ss** 🔬 vs **OneTrainer** 🔬 — LoRA training. Decision pending a head-to-head on 12 GB SDXL LoRA (VRAM, config clarity, resume). Both free.
- **Adobe-free Live2D: Cubism Editor (free tier)** 🔬 — rigging. Verify free-tier export limits for our use.
- **Blender** (free) — future 3D. **GIMP/Krita** — raster. **Inkscape** — vector/logo.
- **Florence-2** 🔬 (captioning) + **Segment Anything (SAM2)** 🔬 (masking/layer separation) + **rembg / InSPyReNet** 🔬 (background removal). All free/local.
- **Upscale:** ComfyUI tiled + ESRGAN/4x-Ultrasharp 🔬.

Each 🔬 is a scheduled verification task (Phase 1) — I confirm current repo, license,
and 4070 fit before it enters the locked stack.

---

## 2. ComfyUI install design (Deliverable 2)

✅ done: portable 0.27.0 at `D:\ComfyUI`, RealVisXL + fp16 VAE + IPAdapter Plus Face
+ CLIP-ViT-H, Manager + IPAdapter_plus. As-built: `comfyui_install_verified.md`.
🔜 add: `comfyui_controlnet_aux`, ControlNet SDXL models (depth/lineart/openpose/softedge),
a stylized checkpoint (§3), reference-only, background-removal + SAM nodes, tiled upscaler,
metadata sidecar node. Freeze policy: no mid-project updates; version every custom node commit.
Workflows exported to `D:\NERO_Forge\10_workflows\` with semantic version names.

---

## 3. Model toolbox (Deliverable 3) — one model per job, not one for all

| Job | Candidate (🔬 verify current best on HF, tokenless) | VRAM |
|---|---|---|
| **Identity / gamified key art** | stylized semi-real SDXL (DreamShaper XL / AlbedoBase XL / Copax) 🔬 — single-file needed | ~6–7 GB |
| Photoreal cross-check | RealVisXL V5 ✅ | ~6–7 GB |
| Armor / material detail | same identity model + detail LoRA 🔬 | +~0.3 |
| Line art / turnaround | control-friendly model + LineArt CN 🔬 | +~1.5 |
| Expressions | identity model + IPAdapter face (approved portrait) | +~1.5 |
| Upscale/refine | tiled SDXL + upscaler 🔬 | +~1–2 |
| Inpaint/outpaint | SDXL inpaint 🔬 | ~6 GB |
| Background/env (promo only) | identity model | ~6 GB |

Every entry gets a why/strength/weakness/VRAM row once verified. **No checkpoint
swaps mid-approved-set** (identity = one model + one LoRA at a time).

---

## 4. Workflow set (Deliverable 4) — one purpose each, no monoliths

`10_workflows/`: 01 Identity Discovery · 02 Identity Refinement · 03 Portrait ·
04 Armor · 05 Wolf-Pauldron · 06 Hair · 07 Material Study · 08 Lighting Study ·
09 Expression · 10 Turnaround · 11 Character Sheet · 12 Poster · 13 Wallpaper ·
14 Live2D-Layer · 15 LoRA-Dataset · 16 LoRA-Validation · 17 Marketing · 18 Upscale ·
19 PSD-Prep. Each stored as ComfyUI API JSON + UI JSON + a `.md` spec (durable vs node drift).

---

## 5. Identity pipeline (Deliverable 5) — minimize drift

Layered conditioning, strongest identity anchor first:
- **IPAdapter** on the **full-figure `9C16`** (carries pigtails + pauldrons), not just the face crop — plus IPAdapter Plus **Face** on the approved portrait once chosen.
- **ControlNet** (reference-only / depth / lineart / openpose / softedge) 🔬 for pose, silhouette, pauldron placement.
- **Regional prompting + attention masking** 🔬 to pin "wolf-head pauldrons" to the shoulders and "glowing eyes" to the lenses.
- The **LoRA (§6)** eventually becomes the primary identity lock; IPAdapter/CN become assist.
- Every approved image feeds back (learning capture) so consistency compounds.

---

## 6. LoRA pipeline (Deliverable 6) → `manbeardog_v1`

Dataset (`40_datasets/manbeardog_v1/`) from **approved** assets only → Florence-2
captions hand-corrected, trigger `mnbdgv1` → Kohya/OneTrainer 🔬 (SDXL LoRA, ~rank 16–32,
12 GB-safe config) → validate via workflow 16 (canary prompts vs Identity Profile) →
version `manbeardog_v1.safetensors`, immutable; improvements become `v2`. Retrain trigger:
≥12 approved, or identity metrics plateau. Guard against catastrophic drift with a held-out
canary set scored by the Audit Director.

---

## 7 / 9 / 10 / 11. Asset-once, many-uses (Deliverables 7, 9, 10, 11)

Every approved asset is produced to serve multiple downstreams:
- **Animation prep (9):** neutral front + symmetric framing + separable layers (hair, pigtails, cape, pauldrons, mist, glow) → Live2D-ready; keyframes for idle/blink/speak/think/emergence/dissolution.
- **Blender prep (10):** clean turnarounds (front/side/back/¾), orthographic feel, even lighting → sculpt/retopo/rig reference.
- **Mobile (11):** same identity, lightweight presentation (emblem/eyes/mist) — never a forked character.
- Feeds NERO's existing **Presence Director** (semantic intent → renderer) — additive, no runtime rewrite.

---

## 8. Visual Asset Database (Deliverable 8)

Per-asset JSON sidecar in `90_metadata/` + a master `index.jsonl`. Schema:
```json
{
  "asset_id":"", "filename":"", "sha256":"", "created":"ISO8601",
  "purpose":"identity|armor|expression|turnaround|marketing|dataset|...",
  "approval_status":"rejected|needs_revision|approved", "version":"",
  "identity_profile_version":"1.0",
  "generation":{"engine":"ComfyUI","checkpoint":"","loras":[],"vae":"",
    "positive":"","negative":"","seed":0,"sampler":"","scheduler":"","steps":0,"cfg":0,"resolution":"",
    "ipadapter":[{"model":"","image":"","weight":0}], "controlnet":[{"model":"","image":"","strength":0}]},
  "source_workflow":"10_workflows/xx.json", "dependencies":[], "audit_report":"91_audit/xxx.json",
  "downstream_uses":[]
}
```
PNGs also keep ComfyUI's embedded workflow (reproducibility ground truth). Nothing is unreproducible.

---

## QA system — Visual Audit Director (2nd brief)

Modular, ComfyUI-independent (scores any image). Pipeline:
`Research → Generate → Auto-Review → Root-Cause → Prompt/Workflow Refine → Regenerate → Director Review → Approve → Archive → Knowledge Capture`.

**Scoring rubric** (weighted; scored against Identity Profile):
- Identity 45% — face, hairstyle (twin pigtails), **sunglasses fidelity**, silhouette, armor, **wolf-pauldron accuracy**.
- Art direction 20% — composition, lighting, atmosphere, emotional read.
- Technical 20% — anatomy, hands, symmetry, textures, artifacts, edges.
- Production 10% — Live2D/Blender suitability, layer separation, dataset quality.
- Overall 5% — "feels like Manbeardog."
Thresholds (draft): Approve ≥ 0.85 and **no signature trait < 0.7**; Needs-revision 0.65–0.85; Reject < 0.65. Any wrong signature trait = auto-reject regardless of total.

**Audit report** (`91_audit/<asset>.json`): overall + category scores, strengths, weaknesses, deviations vs profile/refs, root cause, recommendations, all generation params, review state. **Human approval is final** (Toni = Creative Director; automation assists, never decides).

**Learning capture:** approved images mine successful prompt/workflow/model/CN/IPAdapter patterns into `long_term_character_memory.md` — future gens get more consistent without changing identity.

---

## 12. Performance (RTX 4070, measured ✅ + targets)

Measured: SDXL+IPAdapter, 832×1216, 40 steps, **batch 4 ≈ 45–55 s, peak ~9.5 GB**;
single ~11–14 s resident. Defaults: dpmpp_2m/karras, 40 steps, cfg 7. Targets to
benchmark 🔬: hi-res-fix + tiled upscale VRAM, CN stacks, LoRA-train ceiling, model
unload/lazy-load, fp16/bf16. Rule: don't run gen while Ollama `qwen3:14b` (~9 GB) is loaded.

---

## 13. Folder structure (Deliverable 13) ✅ — `D:\NERO_Forge` tree created.

## 14. Automation (Deliverable 14)
Scripts (`D:\mbd AI\scripts\forge\`, 🔜): auto-write metadata sidecar on save · deterministic naming
`mbd_<purpose>_v<NN>_<seed>.png` · versioning · auto-sort raw→review by heuristic + Audit score ·
approval mover · dataset builder · prompt logger · workflow exporter. Think technical artist, not clicker.

## 15. Future vision (Deliverable 15)
Static refs → LoRA → Live2D (blink/breathe/speak/emerge/dissolve) → Blender/Unreal real-time,
all consuming the **same identity** through the existing Presence Director. Today's structure
makes each next stage additive, never a rebuild.

---

## Phased execution plan

- **Phase 0 ✅** — engine live, workspace up, Identity Profile drafted.
- **Phase 1 (🔜 now)** — (a) Toni approves the Identity Profile; (b) verify 🔬 stack items (stylized checkpoint single-file, ControlNet aux, bg-removal/SAM, Kohya vs OneTrainer); (c) install the identity-pipeline nodes/models.
- **Phase 2** — Workflows 01–03 + identity pipeline; first **on-profile gamified** identity batch conditioned on `9C16`; Audit Director v1 scoring; converge on the approved portrait.
- **Phase 3** — Armor/pauldron/hair/expression workflows; build the LoRA dataset.
- **Phase 4** — Train `manbeardog_v1`; validate; turnarounds; Live2D layer prep.
- **Phase 5** — Marketing/wallpaper; automation scripts; mobile presence.

**Immediate next step:** your approval of the Identity Profile (esp. the glasses),
then I verify + install the stylized-model + control stack and run the first
on-profile pass anchored to `9C16`.
