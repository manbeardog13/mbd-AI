---
id: host.nero-taught-knowledge
layer: operational
type: reference
status: active
owner: shared
updated: 2026-07-17
---

# Nero — Taught Knowledge (Claude transfer log)

*Human-readable mirror of the durable lessons Claude has written into Nero's
memory store. This is the audit + static-context source; the live copy lives in
`data/memory.db` as rows with **`source = 'claude-teaching'`**.*

**Batch 1 — 2026-07-14 · 16 memories + 4 world-state keys.**
Written natively via `scripts/claude_teach_nero.py` (idempotent; re-running
replaces only `source='claude-teaching'` rows). Embeddings intentionally left
null so no local model/GPU is woken — recall is keyword-based until Nero
re-embeds during normal operation.

---

## Beauty & identity (the non-negotiables)

- **Beauty is the #1 acceptance bar.** Toni's rule: *"she has to be beautiful."*
  An ugly/harsh/masculine/distorted/"piggish" face is an automatic reject no
  matter how correct the armor or signatures are.
- **Mandatory signatures:** twin high perky magenta/burgundy pigtails
  (Harley-Quinn); plain thick **black wayfarer** sunglasses (opaque, no
  ornament); glowing violet eyes; **obsidian black ornate plate** armor (never
  leather); **both** shoulders = snarling black wolf-head pauldrons with glowing
  violet eyes; violet aura; pale freckled pointed-eared elf. Losing the
  sunglasses, pigtails, or wolf pauldrons = complete failure.
- **Character DNA / temperament:** ancient, calm, veteran, composed — quiet
  danger, controlled power. Never smiling/panicked/cute/pin-up; micro-expressions
  only; the violet glow carries emotion. Must match her voice `nero_prime_v1`.
- **Manbeardog is Nero's visual avatar**, not a separate person, and the name
  must never be read as a man/bear/dog creature.

## Locked production recipe

- ComfyUI (`D:\ComfyUI`, RTX 4070) → **Juggernaut-XL_v9** + LoRA
  **`manbeardog_v0.safetensors` @0.85** + VAE `sdxl_vae`, trigger token
  **`manbeardog_person`**, KSampler `dpmpp_2m`/`karras`, 36 steps, cfg 6.5,
  896×1152, **batch ≤ 4**, full beauty prompt + violet cinematic mood.
  **No IPAdapter, no stacked adapters.**
- Drive ComfyUI via its **HTTP API** (`POST /prompt`, poll `/history/{id}`,
  `/queue`, `/free`), not the UI. Long jobs: submit detached, poll. Copy renders
  from `D:\ComfyUI\ComfyUI\output` → `D:\mbd AI\_nero_preview`, then curate
  against the beauty bar before presenting.

## Hard lessons (paid for in mistakes)

- **Never retrain the identity LoRA on AI-generated images.** v1 (retrained on
  generated keepers) stiffened her face; v2 (18 generated "north-star" beauties)
  rotted it into a piggish/doll look — *"WHAT IS THAT A PIG!?"*. Curated
  generations are **reference/approval only, never training data.** v0 is the
  permanent default — **stop retraining the LoRA.**
- **OneTrainer** (`D:\OneTrainer`): launch headless with
  `-WorkingDirectory D:\OneTrainer` or it can't find the relative
  samples/concepts JSON. v0 = SDXL base 1.0, rank 16 / alpha 16, LR 3e-4,
  ~900 total steps. More steps / more data made her **worse**.
- **VRAM (12 GB):** SDXL batch 8 @896×1152 thrashes (~11.9 GB) → batch ≤ 4.
  Don't generate images while a local LLM (qwen3:14b ~9 GB) is loaded. `POST
  /free` before training.

## Architecture

- **Identity is a permanent, model-agnostic asset** (the *Canon*: references +
  identity profile + Character DNA + measurable spec + approved library). The
  LoRA is a **derived, disposable adapter** regenerated from the Canon per
  renderer. Renderer changes → regenerate the adapter; the Canon never dies.
- **Geography:** Nero app = `D:\mbd AI` (modular monolith, local-first; memory in
  `data/memory.db`). Visual production = `D:\NERO_Forge` (Canon, datasets, LoRAs)
  + `D:\ComfyUI` (render engine).

## Roles & boundaries

- **Claude is Nero's hosted mind** (conversation, reasoning, planning, tool
  selection on Anthropic resources). The local PC is a **job-scoped
  execution/render plane** only. **Never** use Ollama/Qwen/local LLM as Nero's
  mind in Claude Host Mode; on failure, fail closed to normal Claude behavior.
  Keep Claude's normal permissions/confirmations — **no security bypass.**
- **Collaboration:** Claude (local execution/rendering) + Codex (Codex-side host
  presence, voice bridge, integrations). Keep claims honest across both — verify
  actual state before trusting a report (e.g. `memory.db` was empty despite a
  "memory #43" claim).

## Toni's preferences

- Concise and direct; **everything designed must be beautiful**; local-first and
  €0 (no cloud image gen, no paid tools); don't wake the GPU/LLM unless asked;
  **verify before claiming** — never overclaim.
- Talks to Nero as a companion ("Hey Nero", sometimes "Nino"); wants her always
  present, warm, calm, fast. Storage: renders → `D:\mbd AI\_nero_preview`, **never
  iCloud** (iCloud `Nero AI\mbd` is the reference library only).

## Current state → next

- v0 identity LoRA ships as the beautiful default; 18-image blessed north-star
  set at `D:\NERO_Forge\00_reference\north_star` (reference only); animated
  "living portrait" companion at `D:\mbd AI\Manbeardog_Companion.html`.
- **Next requested:** a true roaming desktop mascot (full-body cutout + walk/idle
  frames + a small pet engine).

---

### Retrieval caveat (honest)

Recall is currently keyword-overlap only (no embeddings on these rows). It's
strong for distinctive terms (LoRA, beauty, pauldrons, host mode) but can miss
paraphrases — e.g. "where are images saved" may surface the training lesson
before the storage rule because both are dense in the word *images*. Nero's
normal embedding pass (or a future re-embed) will sharpen this. Not yet
"reliably learned" for fuzzy queries — accurate for direct ones.
