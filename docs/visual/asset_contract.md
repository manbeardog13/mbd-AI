# Asset Contract

**Purpose:** define the requirements every visual asset must meet before
it enters the production ecosystem. An asset that fails the contract is
sent back for correction, not integrated.

**Applies to:** every asset in `C:\Users\tonij\iCloudDrive\Nero AI\visual\`
that Nero (or a downstream renderer) will consume. Concept sketches in
`source/concepts/` are exempt — the contract kicks in at
`source/approved/` and everywhere downstream.

---

## The eight required fields

Every production asset (or the folder containing a bundle) MUST have a
sidecar `metadata.json` with these fields:

```json
{
  "asset_name": "manbeardog__L1__v1",
  "asset_type": "live2d_model" | "lora" | "blender_scene" | "png_render" | "shader" | "psd" | "motion" | "expression",
  "version": "1.0.0",
  "date_created": "2026-07-15",
  "author": "Toni / GPT-generated / etc.",
  "visual_bible_version": "1.0",
  "source_of_truth": "path or URL of the origin",
  "license_status": "personal-use / MIT / GPLv3 / CC-BY-NC / proprietary",
  "runtime_target": "live2d_cubism_5.x / unreal_5.x / blender_4.x / mobile_shader / etc.",
  "dependencies": ["manbeardog_v1.safetensors", "..."],
  "fallback_behavior": "silent-degrade to L0 / show static emblem / error / etc."
}
```

If any field is unknown, mark it `"unknown"`. Do not leave fields absent
— the presence of a missing field is a bug, `"unknown"` is honest data.

## Field semantics

### `asset_name`
The stable identifier. Follows the naming discipline from
`asset_folder_architecture.md`:
- Frozen versioned: `<char>__<level>__v<n>` (e.g. `manbeardog__L1__v1`)
- LoRAs: `<char>_v<n>` (e.g. `manbeardog_v1`)
- Everything else: descriptive + version

### `asset_type`
One of the enumerated types above. Add new types by extending this doc
first, then using them.

### `version`
Semantic-ish. Major bumps for identity-changing revisions. Minor for
production polish. Patch for bug fixes. **Once released, a version is
frozen** (see [feedback-freeze-versions memory / freeze discipline
established for `nero_prime_v1`]).

### `date_created`
ISO 8601. When the current version was finalized. Not when the file was
last touched.

### `author`
Who / what produced this. Legitimate values:
- `"Toni"` — Toni's own hand
- `"Toni + ComfyUI + <workflow_name>"` — AI-assisted
- `"Toni + Cubism Editor"` — direct authoring
- `"<contributor_name>"` — if ever a real named human contributes
- Never `"unknown"` — trace every asset to its human origin

### `visual_bible_version`
Which version of `docs/visual/manbeardog_visual_bible.md` this asset was
approved against. If the bible advances (v1.1, v2.0), existing assets are
not automatically re-validated — they were correct against their bible
version and remain so until deliberately re-reviewed.

### `source_of_truth`
Where the origin of this asset lives. For a rig: the PSD it was built
from. For a render: the .blend file + camera setup. For a LoRA: the
training set + config. For a concept: the ComfyUI graph + seed. **Every
asset must be reproducible from its source of truth.** If it isn't, this
field is `"IRREPRODUCIBLE"` and that's a red flag.

### `license_status`
One of:
- `"personal-use"` — Nero-only, no distribution
- `"MIT" | "BSD-3" | "Apache-2.0" | "GPLv3"` — standard permissive/copyleft
- `"CC-BY-NC" | "CC-BY-SA"` — Creative Commons variants
- `"proprietary"` — custom terms, must be documented in an ADR
- `"unknown"` — a bug, resolve before promotion

The current Nero project posture (per session-established decisions):
personal-use is fine; `GPLv3` triggers the ADR-0010 posture (adopted
consciously); anything commercial-restricted requires an ADR before use.

### `runtime_target`
Which system will consume this asset at runtime. Multiple runtimes = an
asset per target (with an `exports/` common source) unless the asset is
inherently portable (a PNG works everywhere; a `.moc3` is Cubism-only).

### `dependencies`
Other assets this one depends on. For an L1 Live2D model that uses the
mist particle system: `["effects/mist/violet_mist_v1"]`. Bidirectional —
the mist asset should note its consumers if the graph gets complex.

### `fallback_behavior`
What happens if this asset fails to load at runtime. Concrete cases:
- Live2D model missing: presence degrades to L0 (voice only), no error
  to the user; health endpoint reports `runtime.viewer_hello == null`
- Mobile emblem missing: static icon substituted, notification shown
- LoRA missing: image generation uses base SDXL (identity drift accepted
  for that generation)

## Live2D acceptance requirements (specific)

Per the brief, a Live2D Manbeardog asset is not production-ready until
**all** of the following are true:

| # | Requirement | How to verify |
|---|---|---|
| 1 | Identity matches Visual Bible v1.0 | Visual review against `docs/visual/manbeardog_visual_bible.md` §4 (anatomy), §6 (palette), §7 (materials), §10 (expressions) |
| 2 | Layer separation is documented | `characters/manbeardog/live2d/psd/manbeardog__L1__v1_layers.md` lists every layer + its purpose |
| 3 | Naming conventions consistent | Cubism parameter names match `presence/runtime_bridge/live2d_parameter_map.py::CUBISM_PARAM_MAP` OR the config's `cubism_param_overrides` is populated to bridge |
| 4 | Textures organized | All textures in `characters/manbeardog/live2d/textures/` with consistent power-of-2 dimensions (256, 512, 1024, 2048) |
| 5 | Parameters mapped through the Live2D bridge | Every parameter Nero drives (`ParamNero*`) exists in the model; extras are OK |
| 6 | Idle state exists | Rig has an `idle` motion — breathing + subtle sway per Bible §9 |
| 7 | Emergence state exists | Parameters + motion for `emerge()` (0.15 → 0.35 → 0.60 → 0.85 → 1.0) — see Bible §11.1 |
| 8 | Dissolution state exists | Reverse of emergence, wolf eyes fade last — see Bible §11.2 |
| 9 | Runtime communication verified | Live viewer connects to Nero, receives `hello` + `params` messages, renders visible response |

Assets that fail any of the nine are logged in
`docs/visual/asset_review_checklist.md`'s outstanding-issues section and
sent back.

## Non-Live2D assets — modulated contract

Assets in other categories use the same eight required fields but the
acceptance criteria differ:

### LoRA (`manbeardog_v<n>.safetensors`)
- Trained from a documented image set (`source/lora_training_sets/training_run_<date>/`)
- Config JSON present alongside the .safetensors
- Test gallery: 8+ generations from unseen prompts, all recognizably Manbeardog
- Trigger word documented if any

### Blender master scene
- .blend file opens cleanly in Blender 4.x
- Materials + textures relatively-referenced (no absolute paths)
- Camera bookmarks for canonical front / side / three-quarter views
- Export test: FBX or glTF exports without error

### Mobile shader
- Shader compiles on the target platform (WebGPU / Metal / Vulkan)
- Documented parameter inputs matching the abstract-parameter layer
- Performance measured: fps + battery cost on a real device

### Render (portrait / cinematic / promo)
- Source scene documented (`.blend` file path + frame number)
- Resolution + color space noted
- Approved against the visual bible

## Signing off

A production asset is "signed off" when:
1. Its `metadata.json` has all eight fields populated (no `"unknown"`s).
2. Its category-specific acceptance criteria all pass.
3. Toni marks it approved in `docs/visual/asset_review_checklist.md`.

Until then it lives in a `pending/` subfolder of whatever category it
belongs to. Assets in `pending/` are never consumed at runtime.

## What this contract is NOT

- Not a legal document. `license_status` is informational for future decisions.
- Not enforced by code (there's no schema validator today). Enforcement
  is by process — the review checklist references this contract explicitly.
- Not for pipeline-internal artifacts. Concepts in `source/concepts/`
  don't need a full metadata.json — the whole batch's provenance is in the
  batch folder's `notes.md`.
