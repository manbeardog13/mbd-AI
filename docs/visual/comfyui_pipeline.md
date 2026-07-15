# ComfyUI Pipeline for NERO

**Owner:** Toni.
**Date opened:** 2026-07-13.
**Status:** installation manual + workflow overview.
**Scope:** local ComfyUI as the generation forge for the Manbeardog
Phase A → Phase B → future asset pipeline.

Related:
- `phase_a_execution_guide.md` — the character-side plan (what to make)
- `manbeardog_prompt_system.md` — the prompt library (what to say to the model)
- `manbeardog_identity_workflow.md` — the LoRA training pipeline (Phase B)
- `visual/comfyui/` — the metadata mirror in the iCloud workspace
- `comfyui_quality_control.md` — the QC criteria before promotion

---

## Capability disclosure

I cannot install ComfyUI on your machine, verify against your live
custom-node ecosystem, or benchmark on your 4070. This document is a
recipe — you execute. Anywhere the specific fact could go stale
(package names, filenames, download URLs, ComfyUI-internal node
names, VRAM tuning numbers), I mark it `[VERIFY]` and point at the
authoritative source.

Follow the pattern: **read the recipe → verify against the current
upstream doc → install**.

---

## 1. Where to install

**Recommended:** `D:\ComfyUI\` (fast local disk, plenty of headroom).

**Do NOT install into:**
- iCloud-synced paths (`iCloudDrive`, `OneDrive`, `Dropbox`) — model
  files corrupt during sync
- `C:\Program Files\` — permission surprises
- Any path with spaces — some Python tools fumble spaces
- Any path with non-ASCII characters — Windows codepage issues

The `visual/comfyui/` folder in iCloud is documentation only — it is
not the install location.

---

## 2. Base installation

### Option A — ComfyUI Portable (recommended for Windows)

- **Source:** `github.com/comfyanonymous/ComfyUI` releases page
  [VERIFY current release]
- Download `ComfyUI_windows_portable_nvidia.7z` (or the current
  equivalent for NVIDIA GPUs) [VERIFY exact filename]
- Extract to `D:\ComfyUI\`
- **First run:** `D:\ComfyUI\run_nvidia_gpu.bat`
- Browser opens to `http://127.0.0.1:8188` — the ComfyUI UI

**Pros:** self-contained Python + PyTorch. No conflict with system Python.
**Cons:** larger download (~2 GB); embedded Python can't be upgraded easily.

### Option B — Manual install (advanced)

- Clone: `git clone https://github.com/comfyanonymous/ComfyUI D:\ComfyUI`
- Install PyTorch with CUDA per the current PyTorch install matrix
  [VERIFY latest recommendation for CUDA 12.x + Windows]
- Install ComfyUI dependencies: `pip install -r requirements.txt`
- Run: `python main.py`

**Only use Option B** if you have specific reason to (existing Python
env you want to reuse, dev on ComfyUI itself, etc.). Otherwise Portable
is simpler.

---

## 3. Custom nodes install

After ComfyUI is running, install:

1. **ComfyUI-Manager** first (dependency manager, enables everything else)
2. **ComfyUI_IPAdapter_plus** (identity conditioning)
3. **comfyui_controlnet_aux** (ControlNet preprocessors)

Full list + install instructions: `visual/comfyui/custom_nodes/README.md`

`[VERIFY]` all package repos + versions at install time. Custom-node
ecosystem changes weekly.

---

## 4. Models install

Required for Phase A workflows:
1. One SDXL checkpoint (Juggernaut XL v10 recommended [VERIFY])
2. IPAdapter Plus Face SDXL
3. CLIP Vision H
4. ControlNet OpenPose SDXL

Full list + sizes + sources: `visual/comfyui/models/README.md` and
the sub-folder READMEs.

**Total install size:** ~13 GB. Install all models to
`<ComfyUI>/models/<subfolder>/` (fast local disk).

---

## 5. Hardware optimization for RTX 4070 (12 GB VRAM)

### What the 4070 handles comfortably [VERIFY on your machine]

- SDXL base checkpoint at 1024×1024, no LoRA: ~4-6 GB VRAM used
- SDXL + IPAdapter Plus Face: +~1.5 GB
- SDXL + IPAdapter + ControlNet OpenPose: +~2 GB
- **Peak for the full production workflow:** ~9-10 GB. Fits with headroom.
- **1024×1536 portrait aspect:** adds ~1 GB. Still fits.

### What pushes the 4070 into swap [VERIFY]

- 1536×1536 or higher resolutions with all conditioning active
- Multiple LoRAs stacked at once
- Some FLUX + LoRA combinations
- Running Ollama's `qwen3:14b` (uses ~9 GB) alongside ComfyUI — Nero's
  brain model. Don't run ComfyUI generations while chatting with Nero.

### VRAM-saving flags

If you hit VRAM issues, ComfyUI has command-line flags:

```
--lowvram         (aggressive VRAM saving, slower)
--normalvram      (default balance)
--highvram        (assume plenty of VRAM, faster)
--disable-smart-memory   (bypass ComfyUI's smart memory manager)
```

[VERIFY current flag names against `python main.py --help`]

For the 4070 doing Phase A workflows, **default (`--normalvram`) is
correct**. Only use `--lowvram` if you hit OOM.

### Generation time expectations [VERIFY on your machine]

Rough baselines at 1024×1024, 40 steps, dpmpp_2m karras:

| Configuration | Time per image |
|---|---|
| SDXL only | ~8-12 s |
| SDXL + IPAdapter | ~10-15 s |
| SDXL + IPAdapter + ControlNet | ~12-20 s |

**Benchmark on your machine** by running 3 generations with a stopwatch
after install completes. Note the actual numbers in a text file for
future reference — they change with driver updates and PyTorch versions.

### Recommended default settings

```
Sampler: dpmpp_2m
Scheduler: karras
Steps: 40 (30 minimum for good detail, 50 for maximum)
CFG: 7.0 (standard)
Resolution: 1024x1024 (base) or 1024x1536 (portrait aspect)
```

Vary from these only when you know why.

---

## 6. Workflow index

Five workflows for Phase A. Each has a `.md` spec (durable, reassemble
if node names drift) and, after first assembly, a `.json` you export
for one-click reload.

| Workflow | Spec location |
|---|---|
| 01 — Identity Exploration | `visual/comfyui/workflows/manbeardog/stage_1_identity/workflow_01_identity_exploration.md` |
| 02 — Approved Portrait Refinement | `visual/comfyui/workflows/manbeardog/stage_1_identity/workflow_02_approved_portrait_refinement.md` |
| 03 — Armor Development | `visual/comfyui/workflows/manbeardog/stage_2_armor/workflow_03_armor_development.md` |
| 04 — Presence Effects | `visual/comfyui/workflows/manbeardog/stage_3_presence/workflow_04_presence_effects.md` |
| 05 — Production References | `visual/comfyui/workflows/manbeardog/stage_4_production/workflow_05_production_references.md` |

Each spec is standalone: shape of the node graph, custom node
requirements, model requirements, prompt strategy, seed strategy,
IPAdapter/ControlNet configuration, output handling.

Read the corresponding Phase A stage README in
`visual/source/concepts/manbeardog_v1/<stage>/README.md` in parallel —
that has the prompts + curation criteria.

---

## 7. Metadata handling (Phase 5 of the brief)

### Primary mechanism (automatic)

ComfyUI's builtin `Save Image` node **embeds the complete workflow
JSON in the PNG's metadata chunks automatically**. Drag any generated
PNG back into ComfyUI — the full workflow reconstitutes. This is
reproducibility ground truth.

**No custom node install required for this.**

### Secondary mechanism (optional, text sidecar)

If you want grep-friendly text metadata alongside each image, install
one of the metadata-saver custom nodes:

- **`Save Image With Metadata`** from various packages [VERIFY current
  recommended] — writes a `<filename>.json` sidecar with named fields
- Or **`WAS Node Suite`** (large but comprehensive)

Configure it to write:

```json
{
  "name": "<filename>",
  "version": "1.0",
  "workflow": "workflow_01_identity_exploration",
  "checkpoint": "<base model filename>",
  "seed": <integer>,
  "prompt": "<positive prompt>",
  "negative_prompt": "<negative prompt>",
  "date_created": "<ISO date>",
  "status": "candidate"
}
```

This is the minimum set from the brief's Phase 5. `visual/source/concepts/
manbeardog_v1/manifest.template.json` has the full manifest schema for
kept images — more fields, per-folder aggregation.

### Tertiary mechanism (manual, curated)

When an image graduates from raw ComfyUI output into
`visual/source/concepts/manbeardog_v1/<folder>/`, append a manifest
entry to the folder's `manifest.json` per the Phase A execution guide.
This is the *survivorship-biased* record — only kept images.

**All three layers coexist.** PNG embedded workflow = reproducibility
of any image. Optional sidecar = quick grep. Manifest = official keeper
log.

---

## 8. Asset bridge (Phase 6 of the brief)

The generation system stays independent of the runtime:

```
ComfyUI (D:\ComfyUI\)
    │  writes raw output
    ▼
D:\ComfyUI\output\ (local, unsynced)
    │
    │  Toni curates — most rejected + deleted
    │
    ▼
visual\source\concepts\manbeardog_v1\<folder>\  (iCloud, kept only)
    │
    │  Manifest entries appended
    │  Bible review pass (asset_review_checklist.md)
    │
    ▼
visual\source\approved\  (promoted, LoRA training set)
    │
    │  Phase B — Kohya_ss training
    │
    ▼
manbeardog_v1.safetensors  (loaded into ComfyUI for future work)
                            (also available as source for Live2D PSD, Blender modeling)
    │
    ▼
Phase C: Live2D rigging in Cubism Editor
Phase D: Static HTML viewer using the Cubism Web SDK
```

**Critical invariant:** NERO's runtime (the FastAPI server, Voice
Director, Presence Director) does NOT know or care that ComfyUI exists.
NERO consumes finished, approved assets from disk (or WebSocket viewer)
— never invokes ComfyUI. ComfyUI is a production tool used offline by
Toni; NERO is the runtime that consumes what Toni produces.

This is why `presence/runtime_bridge/live2d.py` exists but doesn't
speak ComfyUI. Right layering.

---

## 9. Troubleshooting

### ComfyUI won't start / port already in use

- Check for another Python process on port 8188
- Or launch on a different port: `python main.py --port 8189`

### CUDA out of memory

- Reduce resolution: 1024×1024 or lower
- Add `--lowvram` flag
- Disable other GPU processes (close Ollama's `qwen3:14b`, close
  browser windows with WebGL running heavy)
- Watch VRAM usage with `nvidia-smi` in a separate PowerShell window
  before / during / after generation

### Custom node fails to load

- Check ComfyUI's terminal window for the Python stack trace
- Usually a missing dependency: `pip install <package>` in the ComfyUI
  Python environment (portable: `D:\ComfyUI\python_embeded\python.exe -m pip install <package>`)
- If persistent, try uninstalling and reinstalling the custom node via
  ComfyUI-Manager

### Workflow JSON fails to load

- Node was renamed in a recent version. Delete the missing/red node,
  find its current equivalent via ComfyUI-Manager, reconnect edges
- Save-as a new JSON version
- Rebuild from the `.md` spec if too many nodes have drifted

### Face doesn't preserve identity across generations

- Increase IPAdapter weight (in steps of 0.05)
- Verify you're using the **face** IPAdapter model, not general
- Verify the reference image is a clean face crop, not a full-body shot
- Consider training the LoRA sooner (Phase B) — LoRA is stronger than
  IPAdapter for identity

### Colors are washed out / oversaturated

- Check if a separate VAE is loaded and matches the base checkpoint
- Try the reference VAE (`sdxl_vae.safetensors` from stabilityai)

### Everything works but images are boring / generic

- Prompt is too vague. Re-read `manbeardog_prompt_system.md` — use full
  Identity Lock + Appearance Lock blocks, not shortened versions
- Try a higher-quality fine-tuned checkpoint (Juggernaut XL v10 is a
  good baseline; RealVisXL v5 for more photorealism)
- Check CFG — 6.0-7.5 range is typical; anything higher tends to
  over-cook the prompt

---

## 10. Update strategy

**When to update:**
- ComfyUI itself: every ~2 months, when you're between projects
- Custom nodes: only when you have a specific reason (bug affecting you,
  new feature you need)
- Models: **never** mid-project; new checkpoint = new character identity

**When NOT to update:**
- Mid-Phase-A. Do not update anything between Stage 1 and Stage 4.
- Between Phase A and Phase B. The Phase A → LoRA training pipeline
  must be reproducible. Same checkpoint, same custom nodes, same models.
- The day before a big generation session.

**Before updating anything:**
- Note what versions you're on (custom node commits, model filenames)
- Update ONE thing at a time
- Regenerate a canary prompt (Prompt A from Workflow 01) and compare
  against a previous canary — if identity drifts, roll back

---

## 11. What NOT to do (explicit restrictions from the brief)

- Do NOT generate the final Manbeardog character automatically. Every
  approved image is a curated human decision.
- Do NOT train LoRAs automatically. Phase B is a supervised training
  step with a validation gate — not something to trigger from a
  workflow.
- Do NOT modify NERO runtime code from within ComfyUI or its custom
  nodes. NERO and ComfyUI live in separate worlds.
- Do NOT introduce cloud dependencies. Every model, every custom node,
  every workflow runs locally. If a workflow wants to call out to a
  hosted API — replace it with a local equivalent or drop the feature.
- Do NOT create hidden workflows outside `visual/comfyui/workflows/`.
  All workflows are checked in and versioned.

---

## 12. Governance

This document is v1.0.

- **Owner:** Toni.
- **Update trigger:** any of — new workflow added, base checkpoint
  changed, custom node ecosystem change requires spec revisions,
  hardware target changes.
- **Non-goals:** this doc is not an SDXL tutorial or ComfyUI beginner
  guide. Those live upstream (comfyanonymous/ComfyUI wiki, Reddit
  r/StableDiffusion, YouTube). This doc is the specific NERO recipe.

Related governance:
- `asset_review_checklist.md` — Bible review + technical validation gate
  for anything leaving `source/concepts/`
- `comfyui_quality_control.md` — per-workflow QC criteria (fast reject
  signals before full curator review)
- Visual Bible (v1.0) — the character source of truth. If ComfyUI
  output conflicts with the Bible, the Bible wins.
