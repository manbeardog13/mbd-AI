# Visual Asset Folder Architecture

**Location of the workspace:** `C:\Users\tonij\iCloudDrive\Nero AI\visual\`
**Where this document lives:** `D:\mbd AI\docs\visual\asset_folder_architecture.md` (Nero repo)
**Why they're separate:** the workspace holds binaries (potentially many GB); the repo holds decisions.

**Status:** v1.0, established 2026-07-13. Folder skeleton created; no assets present yet.

---

## The layout

Adapted from the structure in the Preparation-Phase brief, with two
additions clearly marked and justified below.

```
visual/
├── source/                      raw inputs into the pipeline
│   ├── references/              canonical Manbeardog reference art (mirror of ../mbd/)
│   ├── concepts/                throwaway AI exploration
│   ├── approved/                selected keepers — the LoRA training seed
│   └── lora_training_sets/      *ADDED* — explicit LoRA-training-ready image sets
│
├── characters/
│   └── manbeardog/              the character
│       ├── master/              long-term 3D master (Blender)
│       │   ├── blender/         .blend files, versioned
│       │   ├── textures/        PBR textures
│       │   ├── materials/       material presets
│       │   └── exports/         FBX / glTF for other tools
│       ├── live2d/              production 2D rig
│       │   ├── psd/             layered PSDs
│       │   ├── model/           .model3.json + .moc3 + .cdi3.json
│       │   ├── textures/        texture atlases
│       │   ├── motions/         .motion3.json (idle, breathing, emerge, dissolve)
│       │   └── expressions/     .exp3.json
│       └── loras/               *ADDED* — Manbeardog SDXL LoRA .safetensors files
│
├── effects/                     reusable non-character visual effects
│   ├── mist/
│   ├── particles/
│   ├── glow/
│   └── runes/
│
├── mobile/                      mobile-specific lightweight assets
│   ├── emblem/
│   ├── shaders/
│   └── lightweight/
│
├── renders/                     final output renders
│   ├── portraits/
│   ├── cinematic/
│   ├── previews/
│   └── promo/                   *ADDED* — wallpapers, splash, promo art
│
└── viewer/                      *ADDED* — the Cubism Web SDK viewer app
    ├── index.html
    ├── assets/
    └── README.md
```

## Adaptations from the brief's example structure

| Addition | Rationale |
|---|---|
| `source/lora_training_sets/` | Separates *approved concepts* (curated for identity approval) from *training-ready image sets* (with augmentation, cropping, captions). Training data is a distinct artifact category with its own version history. |
| `characters/manbeardog/loras/` | The Manbeardog LoRA `.safetensors` file is a first-class asset. It has its own version discipline (`manbeardog_v1.safetensors`, `v2`, etc.) parallel to the model rig versioning. Keeping it under the character it depicts makes ownership clear. |
| `renders/promo/` | Wallpapers, splash screens, and promotional art derive from the character but exist as their own asset class. Separating from `cinematic/` (which implies motion) and `portraits/` (which implies formal composition) keeps discovery clean. |
| `viewer/` | The Live2D viewer (Cubism Web SDK static HTML) is itself an asset — a small runtime that ships alongside the character. Kept top-level rather than nested under `characters/manbeardog/` because a viewer can host multiple characters over time. |

## What each folder holds — precise semantics

### `source/references/`
Copies of (or pointers to) the canonical Manbeardog references at
`C:\Users\tonij\iCloudDrive\Nero AI\mbd\`. Six images at v1. **Read-only in
practice** — do not modify. Any new reference is a new version.

### `source/concepts/`
AI-generated exploration output, organized by session date
(`batch_2026-07-13/`, `batch_2026-07-15/`). Ephemeral — expect to prune
periodically. Contents are throwaway; only approved output graduates.

### `source/approved/`
The 3–5 concepts Toni explicitly signs off as canonical Manbeardog. These
plus the six `mbd/` references form the LoRA training seed set.

### `source/lora_training_sets/`
Fully-prepared training packages: images + caption `.txt` files + optional
augmentations. One subfolder per training run
(`training_run_2026-07-15/`). Reproducible: keep the training config JSON
alongside so a run can be rerun.

### `characters/manbeardog/master/blender/`
The 3D master `.blend` files. Versioned filenames
(`manbeardog_sculpt_v1.blend`, `manbeardog_retopo_v1.blend`,
`manbeardog_rigged_v1.blend`). Each is a milestone snapshot.

### `characters/manbeardog/master/textures/` + `materials/`
PBR textures (albedo, normal, roughness, metallic, emission) and Blender
material `.blend` files. Reusable across renders and export targets.

### `characters/manbeardog/master/exports/`
Format-portable exports for other tools — FBX for Unreal, glTF for web,
Alembic for animation exchange.

### `characters/manbeardog/live2d/`
The 2D production rig, in Cubism Editor's native format. `psd/` holds the
layered source. `model/` holds the exported runtime files
(`.model3.json`, `.moc3`, `.cdi3.json`). `motions/` and `expressions/` are
the animation and expression data.

### `characters/manbeardog/loras/`
Trained LoRA `.safetensors` files. One per version. The current LoRA is
whatever `docs/visual/manbeardog_identity_workflow.md` points at.

### `effects/`
Non-character visual effects — the mist, particle systems, glow bloom
textures, rune atlases. These are *reusable* across characters and
future presence experiences.

### `mobile/`
Mobile-specific downscaled or shader-based variants. See
`docs/mobile/presence_experience.md` for what belongs here.

### `renders/`
Output — not input. Anything here can be regenerated from the sources.

### `viewer/`
The Cubism Web SDK viewer static HTML app. When it exists, it loads the
current `.model3.json` and connects to Nero via WebSocket per
`presence/runtime_bridge/live2d_protocol.md`.

## Naming conventions

The repo enforces one naming discipline consistently:

- **Frozen versioned artifacts:** `<name>__<level>__v<n>.<ext>` — e.g.
  `manbeardog__L1__v1.model3.json`, `manbeardog__L2__v1.blend`. Never edit
  a versioned artifact; changes create `v2`.
- **Unversioned working artifacts:** free-form names in appropriate
  folders. E.g. `concepts/batch_2026-07-15/generation_027.png`.
- **Configuration + metadata:** `.json` sidecar files matching the artifact
  name — e.g. `manbeardog_v1_lora_config.json` alongside
  `manbeardog_v1.safetensors`.
- **Dates:** ISO 8601 (`2026-07-13`), never regional formats.

## Governance

This folder architecture is v1.0. Adding new top-level folders happens
via updating this doc to v1.1+. Do **not** create ad-hoc top-level
folders without documenting the addition here.

Related documents:
- `docs/visual/manbeardog_visual_bible.md` — character identity
- `docs/visual/asset_contract.md` — what makes an asset production-ready
- `docs/visual/asset_review_checklist.md` — the arrival gate
- `docs/visual/manbeardog_visual_production.md` — phased production plan
