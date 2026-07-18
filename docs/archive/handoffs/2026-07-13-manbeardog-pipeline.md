---
id: archive.manbeardog-pipeline-handoff
layer: archival
type: handoff
status: archived
owner: shared
superseded_by: docs/visual/ (Manbeardog visual system)
created: 2026-07-13
updated: 2026-07-17
---

> **Archived 2026-07-17:** superseded by the docs/visual/ system. Retained as the founding handoff.

# NERO Presence Initiative

# Manbeardog Character Creation & Animation Pipeline — Claude Code Handoff

Version: 1.0
Date: 2026-07-13

---

# Mission

This document defines the next development phase of NERO:

## Creating Manbeardog — the visual embodiment of NERO.

This is not an avatar project.

This is not a simple image-generation workflow.

This is the beginning of a complete character production pipeline.

The final objective:

A fully animated digital companion character that can:

* appear when NERO is activated
* visually react to conversations
* synchronize with NERO's voice
* express emotional states
* animate naturally
* exist on desktop and mobile
* eventually transition into full 3D real-time rendering

Manbeardog is not decoration.

She is the physical presence layer of NERO.

---

# Current NERO Architecture Status

The following systems already exist and must be preserved.

## Voice

Status: LOCKED

System:

Voice Director

Current identity:

nero_prime_v1

Characteristics:

* calm
* mature
* intelligent
* warm
* protective
* experienced
* never theatrical

The voice represents Manbeardog's personality.

Do not modify the voice architecture during this phase.

---

## Presence System

Status: IMPLEMENTED

Architecture:

```
NERO Brain

↓

Voice Director

↓

Presence Director

↓

Runtime Bridge

↓

Character Runtime
```

Current capabilities:

* state management
* emotional intents
* emergence/dissolution sequences
* voice event synchronization
* runtime abstraction
* WebSocket communication layer

The visual system must connect into this architecture.

Do not create a separate animation system.

---

## Visual Identity

Status: FROZEN

Source:

docs/visual/manbeardog_visual_bible.md

The Visual Bible is the source of truth.

All generated assets must respect:

* character identity
* color palette
* silhouette
* personality
* emotional direction

---

# Character Identity

## Name

Manbeardog

## Personality

She is:

* calm
* emotionally mature
* intelligent
* protective
* quietly humorous
* deeply experienced
* confident without arrogance
* patient
* warm beneath the armor

She does NOT sound or look like:

* a villain
* a generic undead warrior
* a fantasy NPC
* an anime mascot
* a robotic assistant

---

# Visual Signature

Required:

## Hair

* warm magenta / burgundy tone
* twin ponytails

## Eyes

Signature element:

Purple energy presence.

Important:

The sunglasses remain part of her identity.

The eye glow should appear through:

* lens glow
* wolf pauldron eyes
* environmental energy

Not constant exposed glowing eyes.

---

## Armor

Requirements:

* ancient black steel
* battle-worn
* practical
* elegant
* heavy warrior presence

No:

* colorful fantasy armor
* excessive spikes
* neon aesthetics

---

## Wolf Pauldrons

Critical identity feature.

They are one of the strongest visual identifiers.

---

## Atmosphere

Permanent visual language:

* violet mist
* subtle particles
* controlled energy
* cold cinematic lighting
* snowy environment influence

---

# Development Objective

Create a production pipeline that starts with zero-cost tools.

Budget:

€0

Preferred tools:

* ComfyUI
* free/open models
* Blender
* Krita/GIMP
* Live2D free/trial workflow where possible
* open-source tooling

Avoid paid assets.

---

# Primary Task

Build the ComfyUI character creation pipeline.

The goal is to produce real Manbeardog assets.

Not documentation only.

Not theoretical planning.

Actual visual creation.

---

# Required Pipeline

## Phase A — Identity Creation

Create:

### Face

Generate:

* 30-50 exploration candidates
* close-up portraits
* expressions

Select:

ONE approved identity.

This becomes the reference anchor.

---

### Armor

Generate:

* armor variations
* wolf pauldron studies
* material studies

Lock:

* silhouette
* materials
* design language

---

### Hair

Create:

* front views
* side views
* movement references

---

### Presence Effects

Create:

* violet mist
* emergence effects
* glow studies
* rune activation

---

# Identity Preservation

The biggest risk is identity drift.

The pipeline must support:

## IPAdapter

For visual consistency.

## ControlNet

For:

* poses
* composition
* reference views

## LoRA Training

Future goal:

Create:

manbeardog_v1.safetensors

The LoRA should preserve:

* face
* hair
* armor
* silhouette
* personality

---

# Production Outputs Required

The pipeline should eventually create:

## Character References

* front view
* side view
* back view
* full body
* facial expressions

---

## Animation References

Required states:

Idle:

* breathing
* subtle movement

Listening:

* focused eyes
* head movement

Thinking:

* slight posture change
* rune activity

Speaking:

* mouth animation reference

Emergence:

* mist
* energy
* appearance sequence

Dissolution:

* reverse sequence

---

# Future Runtime Targets

The assets should support:

## Level 1

Visual presence:

* eyes
* mist
* glow

## Level 2

Live2D:

* animated portrait
* blinking
* breathing
* speaking

## Level 3

Half-body:

* gestures
* hands
* armor movement

## Level 4

Full character:

* Blender/Unreal
* real-time rendering

## Level 5

Future:

VR/AR presence

---

# Mobile Requirement

NERO will also be accessed remotely through Tailscale.

The visual system must support multiple devices.

Architecture:

Server sends semantic intent.

Client decides rendering capability.

Example:

Server:

```
state = speaking
emotion = warm
intensity = 0.7
```

Desktop:

Full animated character.

Mobile:

Lightweight presence:

* emblem
* eyes
* mist
* simple animation

Never create separate identities.

One Manbeardog.

Multiple presentations.

---

# Required Claude Code Deliverables

Create:

1. ComfyUI integration documentation

2. Recommended model stack

3. Installation instructions

4. Folder structure

5. Workflow files

6. Prompt system integration

7. Metadata tracking system

8. Identity preservation workflow

9. Asset import pipeline

10. Live2D preparation guidelines

---

# Engineering Rules

Never:

* replace existing NERO architecture
* create a parallel character system
* hardcode assets
* break Presence Director abstraction
* assume a paid tool

Always:

* document decisions
* preserve modularity
* keep runtime-independent design
* prepare for future 3D migration

---

# Final Vision

The end result is not:

"A chatbot with an image."

The end result is:

"A local AI companion with a recognizable identity."

The voice already exists.

The brain already exists.

The presence architecture already exists.

This phase creates the being that connects them.

Create Manbeardog.

---
---

# HANDOFF STATE — Read This Before Doing Anything

The following section is written by the previous Claude Code session for the
next Claude Code session. Everything above this line is Toni's mission
statement. Everything below is the current *ground truth* of the pipeline.

**Read this whole section before making a single decision.** Half of what is
described in the "Required Claude Code Deliverables" list above is already
built. The next agent's job is to advance the pipeline, not restart it.

---

# What Is Already Built

## Voice pipeline — LOCKED

- Frozen voice identity: `nero_prime_v1` (Manbeardog blend of af_heart 40% + af_bella 30% + af_nicole 30%, Kokoro speed 0.90, output pitch shift −1.9, no supernatural FX)
- Wired into `/api/speak` in `D:\mbd AI\app\main.py`
- Single production path: brain → Voice Director → nero_prime → Kokoro → audio. No fallbacks.
- Croatian handling: returns HTTP 204 + `X-Voice-Reason: unsupported-language` (ADR-0011)
- Ground truth audio references: `C:\Users\tonij\iCloudDrive\Nero AI\voice_audition\selected_nero_voice\samples\` (6 authoritative WAVs)

**Rule:** Do not touch voice architecture during the visual phase. The voice is done.

---

## Presence Director — IMPLEMENTED and WIRED

- `D:\mbd AI\presence\` package: `types.py`, `director.py`, `runtime_bridge/{base,null,log,live2d}.py`
- Semantic intent API: `PresenceState`, `EmotionState`, `PresenceLevel L0-L5`, `PresenceIntent`
- Voice-side integration: `voice/events.py` pub/sub bus; `PresenceDirector.bind_to_voice()` auto-translates voice events to presence intents
- FastAPI lifespan integration: `D:\mbd AI\app\runtime\` — `RuntimeService` protocol + `LifecycleManager` + `services/presence_service.py`
- Health endpoint: `/api/runtime/health`
- Live2D bridge production-ready: WebSocket client on dedicated background thread, exponential backoff reconnect, drop-oldest queue, `health_snapshot()`
- Semantic → abstract → Cubism 3-layer parameter mapping in `presence/runtime_bridge/live2d_parameter_map.py`

**Rule:** Do NOT create a parallel animation system. When Manbeardog assets exist, they render through this architecture. If you need to add a new runtime (Godot, Unreal, WebGPU), extend `PresenceRuntime` in `presence/runtime_bridge/` — do not touch the Director.

---

## Manbeardog Visual Bible v1.0 — FROZEN

**Path:** `D:\mbd AI\docs\visual\manbeardog_visual_bible.md`
**Size:** ~31 KB, 19 sections
**Grounded in:** the 6 reference PNGs in `C:\Users\tonij\iCloudDrive\Nero AI\mbd\` (particularly `NERO.png` — Toni's flagged face/hair reference)

The Bible is the source of truth. Every visual decision below this point
must be Bible-consistent. If the Bible is wrong, retunes bump the version
number (v1.1+); the Bible is never silently edited.

Key sections referenced downstream:
- §4 — character (skin, ear shape, face maturity)
- §6 — color palette
- §7 — armor material language
- §10 — allowed / forbidden expressions
- §11 — presence manifestation
- §14 — resolved divergences from brief

---

## Phase A Execution Kit — PREPARED (workspace scaffolded, no images yet)

Toni had a session that produced the character-side plan. Location + contents:

### Master guide

`D:\mbd AI\docs\visual\phase_a_execution_guide.md` (~12 KB)

Covers:
- Capability disclosure (previous Claude could not render — same is likely true for you)
- Prerequisites (ComfyUI + SDXL + IPAdapter + ControlNet + reference images)
- 4-stage plan (Identity → Armor → Presence → Production References)
- Time budget: 4-6 evenings realistic
- Curation loop
- Completion criteria

### Workspace scaffold

`C:\Users\tonij\iCloudDrive\Nero AI\visual\source\concepts\manbeardog_v1\`

15 items:
- `README.md` — workspace orientation
- `manifest.template.json` — per-folder metadata template
- `phase_a_status.md` — living completion checklist (Toni fills as he generates)
- 4 stage sub-folders with per-stage READMEs containing ready-to-copy prompts + curation criteria:
  - `identity/` — Stage 1 (face + hair + sunglasses lock)
  - `design/` — Stage 2 (armor + wolf pauldrons + hair + materials)
  - `atmosphere/` — Stage 3 (lighting + mist + emergence keyframes)
  - `production/` — Stage 4 (front/side/back/full_body T-pose refs)

Each stage has explicit sub-folder targets, target counts, prompt kits, and
rename conventions. **The kit is complete — Toni just needs to run ComfyUI.**

---

## ComfyUI Creative Pipeline — PREPARED (docs + workspace, no install yet)

The previous session built the ComfyUI-side pipeline to complement Phase A.

### Documentation in Nero repo

`D:\mbd AI\docs\visual\comfyui_pipeline.md` (~14 KB)

Contains:
- Installation instructions for ComfyUI Portable + custom nodes + models
- Recommended model stack (Juggernaut XL v10 [VERIFY], IPAdapter Plus Face SDXL, ControlNet OpenPose SDXL, CLIP Vision H)
- Hardware optimization for **RTX 4070 12 GB VRAM** (peak ~9-10 GB with all conditioning; headroom OK)
- Workflow index (points at 5 workflow specs in the metadata mirror)
- Metadata handling (three-layer: PNG-embedded workflow / optional sidecar / manifest.json)
- Asset bridge (ComfyUI local output → curator → iCloud keepers → Bible review → LoRA training → Live2D/Blender)
- Troubleshooting
- Update strategy

`D:\mbd AI\docs\visual\comfyui_quality_control.md` (~9 KB)

Contains:
- Two-pass triage (fast reject → Bible review → accept)
- Expected reject rates per stage (Stage 1 face exploration: 70-90% expected)
- Rejection log format
- What NOT to do

### Metadata mirror workspace

`C:\Users\tonij\iCloudDrive\Nero AI\visual\comfyui\`

**Critical design decision:** this is a metadata mirror, NOT an install location.
- Actual ComfyUI install goes to `D:\ComfyUI\` (local disk)
- iCloud sync would murder 6+ GB model files
- Every affected README in this workspace says this explicitly

Contents (16 files):
- `README.md` — workspace orientation + install-location warning
- `workflows/manbeardog/README.md` — index of 5 workflows
- **5 workflow specifications** (Markdown, not JSON — durable across ComfyUI version churn):
  - `workflows/manbeardog/stage_1_identity/workflow_01_identity_exploration.md`
  - `workflows/manbeardog/stage_1_identity/workflow_02_approved_portrait_refinement.md`
  - `workflows/manbeardog/stage_2_armor/workflow_03_armor_development.md`
  - `workflows/manbeardog/stage_3_presence/workflow_04_presence_effects.md`
  - `workflows/manbeardog/stage_4_production/workflow_05_production_references.md`
- Model manifests: `models/README.md` + `checkpoints/` + `loras/` + `controlnet/` + `ipadapter/` + `vae/` + `clip_vision/` READMEs (what to install, from where)
- `custom_nodes/README.md` — required custom nodes (ComfyUI-Manager, cubiq/ComfyUI_IPAdapter_plus, Fannovel16/comfyui_controlnet_aux) — all `[VERIFY]` because ecosystem drifts weekly
- `outputs/README.md` — the flow diagram from ComfyUI local output to iCloud keepers

---

## Governance docs already in place

Previous sessions wrote the ecosystem-wide governance:
- `D:\mbd AI\docs\visual\asset_folder_architecture.md` — the visual/ workspace layout
- `D:\mbd AI\docs\visual\asset_contract.md` — 8-field metadata schema, acceptance criteria per asset type, Live2D 9-point checklist
- `D:\mbd AI\docs\visual\manbeardog_identity_workflow.md` — LoRA training pipeline (Kohya_ss, 32 rank / 16 alpha, 2500 steps, trigger word `mnbdgv1`)
- `D:\mbd AI\docs\visual\manbeardog_prompt_system.md` — Identity Lock + Appearance Lock + Camera Presets + permanent Negatives + Recipes A-D
- `D:\mbd AI\docs\visual\multi_device_asset_strategy.md` — desktop/mobile/web/future VR
- `D:\mbd AI\docs\visual\asset_review_checklist.md` — 7-step gate before any asset enters production
- `D:\mbd AI\docs\mobile\presence_experience.md` — mobile UX spec (widget/full-screen/lock-screen)
- `D:\mbd AI\docs\roadmap\manbeardog_visual_production.md` — 7-stage pipeline, Phase A-G roadmap

---

# What Is NOT Yet Built

**Zero images exist.** No approved portrait, no armor references, no
emergence keyframes. Every folder under `visual/source/concepts/manbeardog_v1/`
is empty. This is intentional — the previous Claude Code sessions could not
render.

**ComfyUI is not installed.** The pipeline documents describe how, but the
actual `D:\ComfyUI\` install has not been created.

**No LoRA exists.** `manbeardog_v1.safetensors` does not exist. That is
Phase B, after Phase A completes.

**No Live2D model exists.** The Live2D runtime bridge is production-ready
but has nothing to render. That is Phase C.

---

# For the Next Agent — Start Here

## Reading order

If you have < 10 minutes:
1. This handoff document (you are here)
2. `D:\mbd AI\docs\visual\manbeardog_visual_bible.md` (the character source of truth)

If you have < 30 minutes, add:
3. `D:\mbd AI\docs\visual\phase_a_execution_guide.md`
4. `D:\mbd AI\docs\visual\comfyui_pipeline.md`

If you have an hour, also read:
5. `D:\mbd AI\docs\visual\comfyui_quality_control.md`
6. `D:\mbd AI\docs\visual\manbeardog_prompt_system.md`
7. `C:\Users\tonij\iCloudDrive\Nero AI\visual\source\concepts\manbeardog_v1\identity\README.md` (Stage 1 prompts + curation)
8. The 5 workflow specs in `C:\Users\tonij\iCloudDrive\Nero AI\visual\comfyui\workflows\manbeardog\stage_N_*/`

Everything is written to be standalone-readable. You should not need to
piece together fragments — each file explains its own purpose and how it
fits into the whole.

---

## Working directories

- **Primary Nero repo:** `D:\mbd AI\` — code + documentation
- **Visual workspace (iCloud):** `C:\Users\tonij\iCloudDrive\Nero AI\visual\` — asset workspace
- **Voice audition workspace (iCloud):** `C:\Users\tonij\iCloudDrive\Nero AI\voice_audition\` — voice ground truth
- **Character references (iCloud):** `C:\Users\tonij\iCloudDrive\Nero AI\mbd\` — 6 PNGs from Toni's own generations, notably `NERO.png`
- **Future ComfyUI install (local disk):** `D:\ComfyUI\` — does not exist yet
- **Cross-session memory:** `C:\Users\tonij\.claude\projects\D--mbd-AI\memory\` — read `MEMORY.md` for the index; contains user profile, feedback rules, project state

---

## The mission is production, not planning

Toni's brief above explicitly says:

> Not documentation only.
> Not theoretical planning.
> Actual visual creation.

**But — honest capability disclosure — every Claude Code session so far has
run in an environment without image generation.** No local SD, no cloud
image APIs (and cloud is against Nero's constraints anyway). The previous
sessions have prepared everything they could — folders, prompts, workflows,
QC criteria, install manuals — but the actual generations have to happen
on Toni's RTX 4070 machine via his own ComfyUI installation.

**If you have image generation tools available that the previous sessions
did not have,** you should use them within the constraints: local models
only, no cloud APIs, Bible-consistent output, curated review. Then Toni
can promote the winners into the workspace directly.

**If you do not have image generation tools,** your job is one or more of:
1. Help Toni install ComfyUI (walk him through, verify against current
   ecosystem, unstick him when custom nodes break)
2. Help Toni tune workflows once he starts generating (adjust IPAdapter
   weights, revise prompts, debug identity drift)
3. Refine the prompt system when he identifies patterns (rejections log
   in `phase_a_status.md` tells you what's failing)
4. Prepare Phase B (LoRA training via Kohya_ss) infrastructure once Phase A
   produces the training set
5. Build the Phase E multi-client presence broadcast server (`PresenceBroadcastService`
   as a new RuntimeService — additive per `docs/visual/manbeardog_visual_production.md` §5)

**Do not treat this as a "make some AI images" task.** This is a character
production pipeline leading to a live animated AI companion. Every prompt,
every workflow, every seed choice needs to serve the identity — not the
spectacle.

---

## The one rule of engagement

> Every generated image must answer: **"Would Toni immediately recognize this as Manbeardog?"** If the answer is no, reject it.

Not "is it a cool image." Not "did the AI do a great job." Not "would
anyone else think this looks good."

**Recognition, not spectacle.**

Manbeardog is a 15+ year WoW character — Toni has an emotional blueprint for
her that is not derivable from the reference images alone. When in doubt,
ask him. When something feels off, ask him. He will redirect faster than
you can drift the pipeline.

---

## The one rule of hardware

Nero's brain is `qwen3:14b` (~9 GB VRAM) running in Ollama. The 4070 has
12 GB VRAM. **Do not run ComfyUI generations while the brain is loaded.**
Options:
- Unload Ollama during a generation session
- Or accept that one or the other is running at a time

This is a practical VRAM constraint, not a design flaw. Toni knows this.

---

## The one rule of files

Everything in `visual/source/concepts/manbeardog_v1/` is either:
- An empty directory (waiting for keepers)
- A README (spec)
- A manifest.template.json (schema)
- A phase_a_status.md (tracker)

When Toni starts generating, kept images appear inside these folders. Each
one must be accompanied by a manifest entry. **Do NOT** let untracked images
accumulate — they become unreproducible mystery files.

---

# Engineering rules (from Toni's brief + memory)

## Never
- Replace existing NERO architecture (voice / presence / runtime are done)
- Create a parallel character system (extend Presence Director instead)
- Hardcode assets (asset selection lives in config, not code)
- Break Presence Director abstraction (semantic intents only; renderer-specific stays in `runtime_bridge/`)
- Assume a paid tool (budget is €0; if a workflow needs a paid tool, drop it or replace)
- Introduce cloud dependencies for the voice or the character (Ollama-local brain, Kokoro-local voice, ComfyUI-local generation)
- Skip Bible review to keep an image you like (Bible wins over aesthetic preference)
- Update ComfyUI or custom nodes mid-Phase-A (reproducibility gate)

## Always
- Document decisions (ADRs for architectural choices; inline for lesser ones)
- Preserve modularity (voice does not know about presence; presence does not know about renderers; renderers do not know about ComfyUI)
- Keep runtime-independent design (NERO consumes finished assets; never invokes ComfyUI directly)
- Prepare for future 3D migration (asset structure supports Live2D → half-body → full 3D → VR/AR)
- Flag capability limits honestly (if you can't do it, say so — do not fabricate results)
- Verify APIs before writing code (see memory `feedback_verify_apis_no_fabrication.md` — pedalboard was claimed MIT, actually GPL v3)
- Freeze versioned artifacts (v1 is immutable; retunes create v2 — see `feedback_freeze_versions.md`)

---

# Cross-session memory context

Toni maintains persistent memory across Claude Code sessions at
`C:\Users\tonij\.claude\projects\D--mbd-AI\memory\`. Key memories relevant
to the visual phase:

- `user_toni.md` — Toni's profile: Windows 11 + RTX 4070, EN/HR bilingual, terse iterator, values honest capability disclosure
- `user_manbeardog_identity.md` — the 15+ year character blueprint informing Manbeardog's emotional identity
- `feedback_verify_apis_no_fabrication.md` — introspect before writing; spec claims aren't ground truth
- `feedback_freeze_versions.md` — v1 immutable, retunes become v2
- `feedback_voice_local_only.md` — Kokoro only, no cloud, no cloning
- `project_nero_voice_state.md` — nero_prime_v1 frozen with specific parameters
- `project_sequence_and_pending_work.md` — the full sequencing history (this is the definitive project state file)
- `project_runtime_lifecycle.md` — the RuntimeService pattern; extend it, do not replace
- `reference_paths.md` — all authoritative filesystem paths

**Read `MEMORY.md` first** for the index, then follow the pointers as needed.

---

# What Toni is likely to ask next

Based on the state of the pipeline and the trajectory of prior sessions,
the natural next requests are (in likely order):

1. **"Help me install ComfyUI"** — walk through Portable install, custom nodes, models. All the recipe is in `comfyui_pipeline.md` § 2-4.

2. **"I generated some faces, help me curate"** — apply `comfyui_quality_control.md` two-pass triage. Ask him to share the images or describe what he's seeing.

3. **"The face keeps drifting"** — Stage 1 identity drift is the most common failure. Increase IPAdapter weight in steps of 0.05. Verify he's using `ip-adapter-plus-face_sdxl_vit-h.safetensors` (face-specific, not general). Verify `NERO.png` is the IPAdapter reference.

4. **"I have an approved portrait, now what?"** — Advance to Stage 2. The IPAdapter reference switches from `NERO.png` to his approved_portrait file. Workflow 03 (armor development).

5. **"Continue"** (without specification) — Per memory `project_sequence_and_pending_work.md`, natural next work is either (a) unstick him on his current stage, or (b) Phase E (`PresenceBroadcastService` — additive multi-client presence broadcast server; does not need visual assets to exist).

---

# The final principle (repeated for emphasis)

> The voice already exists.
> The brain already exists.
> The presence architecture already exists.
> **This phase creates the being that connects them.**
>
> Create Manbeardog.

You are joining an established project mid-flight. Preserve what works.
Extend what needs extending. Do not restart. Do not treat this as
image-generation. Treat this as **technical art direction + pipeline
engineering for a character that will eventually breathe, speak, react,
and manifest across desktop and mobile**.

The forge is prepared. The bellows work. The anvil is set.

Now go help Toni strike.

---
---

# SESSION UPDATE — 2026-07-13 (the forge is now LIT)

**This supersedes "What Is NOT Yet Built" above.** A session with machine
control (Windows PowerShell + ComfyUI HTTP API) executed the install and the
first real generations. State now:

## Now built and working
- **ComfyUI 0.27.0 installed at `D:\ComfyUI\`** on the RTX 4070, running headless
  on `http://127.0.0.1:8188`. Python 3.13.12 bundled.
- **Model stack installed & verified:** `RealVisXL_V5.0_fp16` (checkpoint, chosen
  over Juggernaut — ungated on HF, best photoreal), `sdxl_vae` fp16-fix,
  `ip-adapter-plus-face_sdxl_vit-h`, `CLIP-ViT-H-14` image encoder.
- **Custom nodes loaded:** ComfyUI-Manager, cubiq ComfyUI_IPAdapter_plus.
- **Real generations done.** Working API workflow: SDXL + IPAdapterUnifiedLoader
  (PLUS FACE) + IPAdapterAdvanced, `NERO.png` as identity anchor.
- **4 Stage 1 identity candidates** saved + manifested in
  `visual/source/concepts/manbeardog_v1/identity/face_exploration/`. All
  recognizably Manbeardog.
- **As-built record (replaces all `[VERIFY]`):** `docs/visual/comfyui_install_verified.md`
  — exact URLs, versions, node names, the working workflow JSON, benchmarks, lessons.
- Session preview copies (not keepers, gitignored): `D:\mbd AI\_nero_preview\`.

## Key lessons (also in comfyui_install_verified.md)
1. Text-only prompting drifts badly (wolf ears on head) — IPAdapter+NERO.png is mandatory.
2. "Wolf-head pauldrons" → the model paints a *live companion wolf* in scenes;
   shoot identity on a **void background**, and lock the pauldron sculpture in
   Stage 2 via reference/img2img, not text.
3. Twin ponytails still render as one dominant side ponytail — needs a refinement pass.
4. Machine-control calls time out ~25-30s — submit to ComfyUI then poll `/history`; never await inline.

## The immediate next move
Toni reviews the 4 candidates and either (a) approves one into
`identity/approved_portrait/`, or (b) asks for a twin-ponytail refinement pass.
Then Stage 2 (armor + wolf pauldrons) conditioning on the approved face +
a reference image for the pauldron silhouette.
