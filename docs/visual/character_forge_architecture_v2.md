---
id: visual.character-forge-architecture-v2
title: "Character Forge — Architecture v2 (Design Review Outcome)"
layer: operational
type: reference
status: active
owner: shared
created: 2026-07-13
updated: 2026-07-17
---

# Character Forge — Architecture v2 (Design Review Outcome)

**Supersedes the structural assumptions in `forge_roadmap.md`.**
Status: proposed redesign — awaiting Toni ratification of the challenge points (§2).
Author role: Technical Art Director / Principal Graphics Engineer / Character Pipeline Architect.

---

## 1. Prime axiom

**Identity is a permanent, model-agnostic engineered asset. Rendering technology is
disposable.** Every system either (a) *owns* identity, (b) *presents* it, or (c)
*renders* it — and never confuses the three.

---

## 2. The assumption I'm challenging (ratify this first)

Your brief calls the **LoRA the "permanent carrier" of identity.** I'm pushing back,
because it quietly re-couples identity to a rendering technology:

> An SDXL LoRA is a projection of identity **into SDXL's weight space.** It cannot be
> loaded by Flux, SD-next, a 3D engine, or whatever replaces diffusion in 3 years.
> If the LoRA is the identity, then when SDXL dies, **Manbeardog dies with it.** That
> is exactly the failure mode you want to prevent.

**Correction:** split identity into two things.

- **Identity Canon (permanent, model-agnostic):** the references, the descriptive
  Identity Profile, the *measurable* Identity Spec, the Character DNA, the approved
  asset library, the audit history, and (future) the 3D model/textures. This is the
  source of truth. It never contains a `.safetensors`.
- **Identity Adapters (derived, disposable, versioned):** the SDXL LoRA, IPAdapter
  embeddings, textual inversions, and tomorrow's Flux LoRA / 3D-rig / neural-avatar.
  Each is **regenerated from the Canon** for whatever renderer is current.

So the LoRA becomes *the most important derived artifact of the SDXL era* — not the
identity itself. When the renderer changes, we run **Identity Regeneration**: rebuild
the adapter from the Canon + approved library. That is the concrete mechanism by which
"she is recognizable in 5 years under different tech." The LoRA is still central to how
we *work today* — it just isn't allowed to *be* her.

---

## 3. The three layers

| Layer | Owns | Contents | Mutability |
|---|---|---|---|
| **1 · Identity** | *Who she is* | Canon: references · Identity Profile · **Measurable Identity Spec** · **Character DNA** · approved assets · audit history · future 3D | Immutable except by explicit Toni approval → version bump |
| **2 · Art Direction** | *How she's presented* | Named **Render Targets**: Blizzard-key-art, Diablo-cinematic, LoL-splash, poster, bust, full-body, turnaround, character-sheet — each = composition + lighting + framing + style intent | Freely editable; may never alter Layer 1 |
| **3 · Rendering** | *What draws the pixels* | Checkpoint + **style LoRA** + **identity adapter** (derived from Layer 1) + sampler/CN/upscale | Fully disposable; swap freely |

**Boundary rules (enforced):**
- Layer 3 may never be the source of an identity trait. If an image only looks like her
  because IPAdapter/prompt guessed well, that is a **bug**, not a success.
- A technically beautiful image that loses a signature trait is a **failure** (auto-reject, §Measurement).
- Style lives in Layer 2/3 only. Identity lives in Layer 1 only.

---

## 4. Keeping identity and style *actually* separated at the model level

Training the identity LoRA on stylized images risks **baking style into identity** —
re-coupling the two you just separated. Mitigations, in order:
1. **Caption the style out.** During dataset captioning, describe the style explicitly
   (e.g., "blizzard key art, dramatic lighting") so the LoRA attributes it to those
   tokens, not to her.
2. **Diversify style in the dataset** so no single look correlates with her identity.
3. **Two-adapter stack at render time:** `identity_LoRA` (who) + `style_LoRA` (how),
   composed in Layer 3. The AAA-key-art look is a *style* adapter, not part of her.
4. Prefer **lower rank** for the identity LoRA (captures identity, resists memorizing scenes).

> Reality check on the AAA look: base SDXL (even DreamShaper) will not reliably produce
> "Blizzard/Diablo key art" from prompt alone. That look is a **Layer-3 style adapter**
> (a key-art/splash-art style LoRA or a checkpoint in that lane) — to be sourced/verified,
> not assumed. This keeps 85/15 stylization a *rendering* decision, never an identity one.

---

## 5. Multi-character Forge (engine vs characters)

Split shared machinery from per-character data so new characters need **zero
architectural redesign**:

```
D:\NERO_Forge\
  engine\                     # SHARED across all characters
    workflows\                # the 19 one-purpose ComfyUI graphs
    trainers\                 # LoRA training configs (kohya/onetrainer)
    audit\                    # Measurement Harness + Audit Director (character-agnostic)
    model_toolbox\            # checkpoint/style-LoRA/CN registry + notes
    scripts\                  # metadata, naming, sorting, lineage automation
  characters\
    manbeardog\               # one self-contained character package
      canon\                  # references, identity_profile, identity_spec, character_dna
      adapters\               # identity LoRA versions (+ future non-SDXL adapters)
      approved\  review\  rejected\
      datasets\               # per-adapter-version training sets (+ lineage)
      animation\              # Live2D/keyframe libraries
      audit\                  # per-asset audit reports + drift history
      prompts\  render_targets\
      character.json          # manifest (see below)
    nero\  ragusa_npcs\  ...  # future characters, same shape
```

**`character.json` manifest** binds a character's whole system-of-record:
```json
{
  "name":"manbeardog", "status":"active",
  "identity":{"profile":"canon/identity_profile.md","spec":"canon/identity_spec.json","dna":"canon/character_dna.md","profile_version":"1.0"},
  "adapters":{"sdxl_lora":"adapters/manbeardog_v1.safetensors","current_renderer":"sdxl"},
  "voice_profile":"nero_prime_v1", "presence_level":"L0-L5",
  "approved_count":0, "audit_history":"audit/", "knowledge_graph":null
}
```

**Cross-system unification:** a "character" in this Forge is the union of *visual
identity* (this Forge), *voice identity* (`nero_prime_v1`, already frozen), *behavior*
(Character DNA), *knowledge* (future graph), and *presence* (the existing Presence
Director L0–L5). NERO's runtime **consumes** the character package; it never owns
identity. Manbeardog is the first character; Nero-self and Ragusa NPCs slot in unchanged.

---

## 6. Provenance / lineage (true reproducibility)

- Approved assets are **content-addressed** (sha256) and immutable.
- Every derived artifact records its exact inputs: a LoRA stores *which approved image
  hashes + which caption set + which trainer config + which base* produced it.
- Result: any adapter is **regenerable** from the Canon, and any image traces back to a
  workflow + seed + adapter lineage. Nothing is a mystery file; nothing is unreproducible.

---

## 7. Refactor map — where the current pipeline still lets diffusion own identity

| Current assumption (v1) | Fix (v2) |
|---|---|
| "LoRA becomes the primary identity lock" (identity_profile §root-cause) | LoRA = derived adapter; **Canon** owns identity |
| Model toolbox implied identity varies with checkpoint | Identity is checkpoint-agnostic; checkpoint = Layer-3 render only |
| Workflows used IPAdapter/prompt *as* identity | Those are Layer-3 assists + dataset tooling; identity enforced by the Measurement Harness gates |
| "Approval" was subjective aesthetic | Approval gated by **objective identity distance + hard signature gates** |
| "Generate then hope it's her" | **Measure-and-gate**: every candidate scored vs the measurable spec before a human ever sees it |
| Keepers stored in iCloud scaffold | Local character package; iCloud = references only |

---

## 8. Revised phased plan

- **P0 ✅** engine live, workspace up, descriptive profile drafted.
- **P1 (now)** — build the **Canon**: measurable Identity Spec + Character DNA (this review),
  then the **Measurement Harness** (objective audit) and calibrate its targets against the 6 refs.
- **P2** — dataset prep from refs → **bootstrap identity LoRA (v0)**; source/verify the AAA style adapter + trainer (🔬).
- **P3** — audited generation loop: v0 → hundreds of candidates → harness scores → keep top → retrain → **production LoRA v1**.
- **P4** — Render Targets (AAA looks) · turnarounds · expression sheets · Live2D layer prep.
- **P5** — marketing/wallpaper · automation scripts · mobile presence · second character onboarding test.

**This turn is design only** — no training/generation, per your "design review, not implementation."
