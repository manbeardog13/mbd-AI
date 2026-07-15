# Manbeardog Visual Production Roadmap

**Version:** 1.0 (2026-07-13)
**Purpose:** cover the ten deliverables from the "NERO Presence Initiative —
Production Roadmap" brief in one place, so Toni has a single source of
truth for the next phase.
**Scope:** documentation, not implementation. Where I can't verify
something without deeper research, I mark it clearly and recommend the
follow-up rather than pretend to have decided.

**Prerequisite reading:**
- `docs/visual/manbeardog_visual_bible.md` — the frozen character identity
- `docs/adr/0009-*.md` — voice architecture
- `docs/adr/0011-*.md` — single voice path + Croatian handling
- `presence/README.md` — the runtime interface + Presence Levels
- `presence/runtime_bridge/live2d_protocol.md` — the Live2D WebSocket protocol

**Honest capability boundary:** I cannot rig 2D characters, sculpt in
Blender, run image-generation models, or produce visual assets from this
environment. I can research, spec, plan, and integrate. Actual asset
production is Toni's work. Everything in this document is guidance for
that work, plus the interface glue Nero needs.

---

## Table of Contents

1. Free asset pipeline (tool comparison)
2. Recommended workflow (single justified pipeline)
3. Folder structure
4. Learning roadmap
5. Client capability architecture
6. Multi-device networking review (Tailscale-first)
7. Mobile UX specification
8. Runtime compatibility review
9. Implementation roadmap (phased)
10. Risks + open questions

---

## 1. Free Asset Pipeline — Tool Comparison

### 1.1 Concept generation (2D image AI)

The character design work — generating references, exploring variations,
producing the master artwork.

| Tool | License / Cost | Strength for Manbeardog | Learning curve | Verdict for Toni's stack |
|---|---|---|---|---|
| **Stable Diffusion XL (local)** | Free / open weights (CreativeML Open RAIL-M) | Highest quality free base model; huge LoRA ecosystem; runs locally on the RTX 4070 | Medium — CLI or A1111 UI | **Foundation.** Everything else builds on top. |
| **FLUX.1 [schnell]** | Free / Apache 2.0 | Best-in-class prompt adherence for a free model; single-image consistency is strong | Medium — needs 12+ GB VRAM at fp16, tight on the 4070 alongside Ollama | **Yes**, but only when Ollama is not resident. Use for concept exploration, close Ollama during. |
| **FLUX.1 [dev]** | Non-commercial license | Higher quality than [schnell] | Same hardware constraint | Skip unless Nero goes commercial and license fee is acceptable |
| **ComfyUI** | Free / GPLv3 | Node-based graph over SD/FLUX; enables IPAdapter, ControlNet, LoRAs, character consistency workflows | Steep initial, then very powerful | **Yes.** This is the workhorse for identity-preserving generation. |
| **Automatic1111 (A1111) WebUI** | Free / AGPL | Web UI over SD; friendlier for beginners | Low-medium | Yes for a first-look UI while learning; graduate to ComfyUI when workflows get real. |
| **InvokeAI** | Free / Apache 2.0 | Alternative WebUI, cleaner UX than A1111 | Low-medium | Alternative to A1111. Pick one, not both. |
| **Fooocus** | Free / GPL | Auto-tuned SD wrapper — minimal knobs | Very low | Good for "just generate something" but you'll outgrow it fast. Skip. |
| **Krea / Leonardo / etc. (SaaS)** | Freemium | Ready-made character consistency tools | None | Would work but violates the "no cloud" constraint if the assets are the master identity |
| **Midjourney** | Paid (~$10/mo min) | Best quality overall, but paid → violates budget | Low | **Skip** per €0 constraint. Only relevant if you already have a subscription. |

### 1.2 Character consistency (the hardest problem for AI art)

Making every generated Manbeardog image depict the **same character** is
the load-bearing technique for producing a coherent asset library. Free
approaches, ranked by strength:

| Technique | What it does | Setup effort | Consistency strength |
|---|---|---|---|
| **Character LoRA** (train your own) | Fine-tune SDXL on 15–30 curated Manbeardog images. Result: a small adapter (~40–200 MB) you load into any generation. | High — needs training set + a few hours training on the 4070 | **Highest.** Once trained, every generation is on-model. |
| **IPAdapter FaceID / IPAdapter Plus** | Conditions generation on a reference image without training. Free extension for ComfyUI. | Low — just add nodes to ComfyUI graph | High for face; moderate for full body |
| **ControlNet (OpenPose, Depth, LineArt)** | Constrains generation to a pose/depth/lineart reference. Doesn't preserve identity by itself but pairs with IPAdapter or LoRA. | Low-medium | Constrains composition, not identity |
| **Reference-only conditioning** (A1111 extension) | Weaker cousin of IPAdapter — copies style/features from a reference | Low | Medium |
| **Consistent seed + prompt** | Naive baseline: same seed + same prompt = same-ish character | Zero | Low. Small prompt changes drift. |

**Recommended combination:** train a **Manbeardog LoRA on SDXL** using
the 6 existing reference images as the seed set. Augment with IPAdapter
FaceID during production for extra face-lock. ControlNet for pose control
in specific compositions.

### 1.3 Image editing + layer preparation

Turning a finished piece of AI artwork into animation-ready PSD layers
for Live2D.

| Tool | Cost | Strength | Verdict |
|---|---|---|---|
| **Krita** | Free / GPL | Full raster + layer painting; free PSD export; used by Live2D community | **Recommended primary.** Native PSD, good for painting corrections and creating separate layers. |
| **GIMP** | Free / GPL v3 | Solid raster editor; PSD import/export | Fine alternative to Krita; slightly less painterly. Krita is a better fit for character art. |
| **Photopea** | Free (web) / freemium | Runs in the browser, near-Photoshop UX, PSD-native | Useful as a quick fallback / on-any-device editor. Not for the master workflow (browser-only). |
| **Blender (grease pencil + compositing)** | Free / GPL | Vector-native 2D + 3D combined | Overkill for layer prep; keep for the 3D master work. |
| **Segment Anything (SAM) + AI matting** | Free / Apache 2.0 | Automatic object segmentation — massively speeds up layer separation | **Yes.** ComfyUI has SAM nodes; feed a generated Manbeardog through SAM to get automatic masks for face/hair/armor/pauldrons. |
| **rembg** (background removal) | Free / MIT | Automatic background removal | Yes. Cheap tool for isolating the character from generated backgrounds. |

### 1.4 3D master asset

Long-term Manbeardog lives as a 3D asset that can be re-baked into new
2D poses (via Blender viewport render) and eventually driven in Unreal.

| Tool | Cost | Purpose in the pipeline |
|---|---|---|
| **Blender** | Free / GPL v3 | Sculpting, retopology, UV, rigging, materials, export. The 3D master. Full pipeline in one app. |
| **MakeHuman** | Free / AGPL | Base humanoid mesh generator; useful starting point for retopology | Optional — jump-start the base mesh |
| **VRoid Studio** | Free / proprietary | Anime-style character creator, exports VRM | Skip — the aesthetic doesn't match Manbeardog. Anime-cute is off-model. |
| **Character Creator 4 (Reallusion)** | Paid | Industry-standard | Skip — budget. |
| **MetaHuman Creator** | Free but requires Unreal | Photorealistic humans in Unreal | Skip for MVP — needs Unreal + big VRAM (see ADR-0002). Revisit in Phase 4+. |
| **Substance Painter** | Paid | Texture painting | Skip — Blender's texture painting is sufficient for the aesthetic. |

### 1.5 Live2D specifically

| Tool | Cost | Notes |
|---|---|---|
| **Cubism Editor Free** | Free for individuals + small-scale businesses (Toni qualifies — see ADR-related discussion earlier this session) | The rigging tool. Native PSD import. Windows/macOS. **Required.** |
| **Cubism Native SDK** | Free for the same tier | Runtime SDKs for embedding a rigged model in a native viewer. Used by the eventual Live2D viewer process. |
| **Cubism Web SDK** | Free for the same tier | JavaScript / WebGL runtime. Best fit for a **browser-based viewer window** that Nero's WebSocket bridge connects to. |
| **Vtube Studio** | Free / freemium (paid unlock) | Turnkey Live2D viewer — supports webcam face tracking. Overkill for Nero and adds unnecessary features. |
| **PrPrLive** | Free | Simple Live2D viewer | Possible viewer for MVP; less polished than a custom Cubism-Web setup |

**Recommendation on viewer:** for MVP, **build a small custom Cubism-Web
viewer** as a static HTML page that Nero's `Live2DRuntime` connects to via
WebSocket. Runs in a Chromium window (Electron optional). Keeps everything
in the local + free zone.

### 1.6 What we do NOT need for MVP

- Substance Painter (Blender's texture tools suffice for the aesthetic)
- ZBrush (Blender's sculpting suffices)
- Marvelous Designer (cape sim can wait; Cubism handles the L1–L2 movement)
- Any AI voice cloning tool (voice is locked, `nero_prime_v1`)
- Any commercial character asset marketplace

---

## 2. Recommended Workflow (single justified pipeline)

Every choice below is optimized for €0 + long-term ownership + reusability.

```
                       (Visual Bible v1.0)
                              │
                              ▼
  ┌─────────────────────── STAGE 1 ────────────────────────┐
  │ Concept exploration                                    │
  │   ComfyUI + SDXL base + IPAdapter FaceID               │
  │   Reference-conditioned on the 6 mbd/ images           │
  │   Output: 20–40 concept generations to converge on     │
  │   the final face + pauldron design                     │
  └────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────── STAGE 2 ────────────────────────┐
  │ Character approval                                     │
  │   Pick 3–5 best generations                            │
  │   Manual selection by Toni                             │
  │   These become the LoRA training set                   │
  └────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────── STAGE 3 ────────────────────────┐
  │ Train Manbeardog SDXL LoRA                             │
  │   Kohya_ss trainer or ComfyUI + LoRA training node     │
  │   Training set: the 6 mbd/ images + 3–5 approved gens  │
  │   ~2000 training steps on the 4070 (~1 hour)           │
  │   Output: manbeardog_v1.safetensors (~50–200 MB)       │
  │   THIS BECOMES THE IDENTITY-LOCK ASSET                 │
  └────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────── STAGE 4 ────────────────────────┐
  │ Master artwork generation                              │
  │   ComfyUI + SDXL + Manbeardog LoRA + ControlNet        │
  │   T-pose front + T-pose 3/4 view + T-pose side         │
  │   All at 2048×2048+ resolution                         │
  │   Output: 3 canonical reference images                 │
  └────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
  ┌────── STAGE 5A (parallel) ──┐  ┌── STAGE 5B (parallel) ─┐
  │ Layer separation for Live2D│  │ Blender master sculpt   │
  │   Krita + SAM + manual pass│  │   Retopology from front │
  │   Output: manbeardog__L1__ │  │   view. UV. Rig later. │
  │     v1.psd with ~15 layers │  │   Reference: LoRA gens  │
  └────────────────────────────┘  └─────────────────────────┘
                    │                   │
                    ▼                   ▼
  ┌────────── STAGE 6A ─────────┐  ┌───── STAGE 6B ────────┐
  │ Cubism Editor rigging       │  │ Blender rig + weights │
  │   Import PSD                │  │   For future Unreal   │
  │   Set ParamNero* parameters │  │   export              │
  │   Export .model3.json       │  └────────────────────────┘
  │   Output: manbeardog__L1__  │
  │     v1.model3.json          │
  └─────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────── STAGE 7 ────────────────────────┐
  │ Live2D viewer (Cubism Web SDK)                         │
  │   Static HTML page loading manbeardog__L1__v1          │
  │   WebSocket client per live2d_protocol.md              │
  │   Connects to Nero's Live2DRuntime                     │
  │   Output: viewer process the runtime bridge talks to   │
  └────────────────────────────────────────────────────────┘
                              │
                              ▼
                     NERO SPEAKS + APPEARS
```

**Total steady-state effort estimate** (Toni's time, not calendar):
- Stage 1 (concept): 1–2 evenings
- Stage 2 (approval): 30 minutes
- Stage 3 (LoRA training): 2–3 hours including test iterations
- Stage 4 (master artwork): 2–3 evenings iterating on the perfect front/side
- Stage 5A (layer separation): 1 evening, longer if learning Krita from scratch
- Stage 5B (Blender master): 5–20 evenings depending on Blender skill trajectory
- Stage 6A (Cubism rigging): 3–8 evenings — Cubism is the biggest new-skill acquisition
- Stage 7 (viewer): 1–2 evenings once the .model3.json exists

**Real bottleneck: Cubism Editor learning + rigging.** Every other stage
has AI acceleration or is a known skill. Rigging is manual craft. Budget
generously.

---

## 3. Folder Structure

Recommended layout for the asset workspace. Lives alongside the existing
iCloud voice audition workspace so all creative artifacts are co-located
outside the Nero repo:

```
C:\Users\tonij\iCloudDrive\Nero AI\
├── voice_audition\            (existing — voice work)
├── mbd\                       (existing — 6 reference images)
├── memory\                    (auto-memory, if we ever mirror it)
│
└── visual\                    NEW — everything visual lives here
    │
    ├── 00_reference\          canonical references (do not modify)
    │   ├── bible_v1.0.pdf     printable snapshot of the bible
    │   └── mbd_refs\          symlink or copy of iCloud mbd/
    │
    ├── 10_concepts\           STAGE 1 output — throwaway exploration
    │   ├── batch_2026-07-13\
    │   ├── batch_2026-07-15\
    │   └── notes.md
    │
    ├── 20_approved\           STAGE 2 output — the LoRA training set
    │   ├── 001_front_face.png
    │   ├── 002_pauldron_close.png
    │   └── ...
    │
    ├── 30_lora\               STAGE 3 output — the identity-lock asset
    │   ├── manbeardog_v1.safetensors
    │   ├── training_log.txt
    │   └── training_config.json
    │
    ├── 40_masters\            STAGE 4 output — canonical reference art
    │   ├── manbeardog_master_front_v1.png       (2048×2048+)
    │   ├── manbeardog_master_side_v1.png
    │   └── manbeardog_master_three_quarter_v1.png
    │
    ├── 50_live2d\             STAGES 5A + 6A
    │   ├── psd\
    │   │   └── manbeardog__L1__v1.psd
    │   ├── layers_notes.md
    │   └── model3\
    │       ├── manbeardog__L1__v1.model3.json
    │       ├── manbeardog__L1__v1.moc3
    │       └── textures\
    │
    ├── 60_blender\            STAGE 5B
    │   ├── manbeardog_sculpt_v1.blend
    │   ├── manbeardog_retopo_v1.blend
    │   └── exports\
    │
    ├── 70_viewer\             STAGE 7 — the Live2D viewer HTML app
    │   ├── index.html
    │   ├── viewer.js
    │   ├── assets\             ← copies of ../50_live2d/model3/*
    │   └── README.md
    │
    └── 90_derivatives\        wallpapers, promo, avatars, splash screens
        └── ...
```

**Naming rules** (mirror the code side):
- Versioned assets are IMMUTABLE. `manbeardog__L1__v1.model3.json` never
  changes; retunes create `v2`.
- Level-tagged (`L1`, `L2`, ...) matching the Presence Level abstractions.
- Blender files use `.blend` at the top, versioned like the rigs.

**Not in git.** These are large binary assets in iCloud, mirrored via
the existing iCloudDrive path. The Nero repo references paths but never
contains the binaries. Follows the same discipline as the voice audition
workspace.

---

## 4. Learning Roadmap

Optimize for building durable skills while producing Nero. Order matters:

### Week 1–2: ComfyUI + SDXL basics (concept generation)
- **Watch:** any current ComfyUI beginner walk-through on YouTube (search
  "comfyui SDXL basics 2025" or newer).
- **Install:** ComfyUI + SDXL base model + any modern quality checkpoint
  (RealVis, JuggernautXL, etc.).
- **Do:** generate 30–50 Manbeardog concepts using the 6 reference images
  as IPAdapter conditioning. Skill unlock: prompt engineering + IPAdapter.
- **Outcome:** Stage 1 done.

### Week 3: LoRA training
- **Learn:** Kohya_ss trainer OR ComfyUI's LoRA training node.
- **Do:** train `manbeardog_v1.safetensors` on the 6 references + best
  concepts.
- **Outcome:** Stage 2–3 done. Every future generation is on-model.

### Week 4: Krita + layer separation
- **Learn:** Krita layer basics + Segment Anything (SAM) via ComfyUI.
- **Do:** produce `manbeardog__L1__v1.psd` with the 15 target layers.
- **Outcome:** Stage 5A done.

### Weeks 5–7: Cubism Editor
- **Learn:** Cubism Editor official tutorials — mesh warping,
  parameters, deformer hierarchy, physics.
- **Do:** import the PSD, set up the 5 `ParamNero*` parameters, rig
  breathing, pauldron eye glow, mist particle emitter.
- **Outcome:** MVP Live2D asset. First working Manbeardog.

### Weeks 8+: Blender (in parallel with normal Nero use)
- **Learn:** Blender sculpting + retopology + UV + rigging fundamentals.
- **Do:** build the 3D master from the master reference art.
- **Outcome:** Long-term master asset. Prep for future Unreal migration.

### Deferred: Unreal Engine
- **When:** the 4070 gets upgraded to a 24 GB+ GPU, or Ollama moves to a
  smaller / off-GPU model.
- **Why:** MetaHuman + `qwen3:14b` don't coexist on 12 GB VRAM (see
  ADR-0002). Learning Unreal now doesn't unlock anything Nero can use.

---

## 5. Client Capability Architecture

**Contract:** the Presence Director broadcasts *semantic* events. Clients
declare *what they can render*. The Director never adjusts its output
based on which clients are connected — it just broadcasts. Adjustment
happens client-side.

### 5.1 Client hello message (client → Nero)

New endpoint or handshake message. Every client that wants presence
events sends this on connection:

```json
{
  "v": 1,
  "kind": "client.hello",
  "client_id": "toni-desktop",
  "client_type": "windows-desktop",
  "presence_capabilities": {
    "max_presence_level": 2,
    "supports_transparency": true,
    "supports_particles": true,
    "supports_animation": true,
    "supports_audio_streaming": true,
    "screen_dimensions": [1920, 1080]
  }
}
```

### 5.2 Server side: broadcast, don't multicast-decide

Nero sends the SAME presence intents to every client. Each client's
runtime translates according to its own capabilities:

- Desktop with Live2D viewer: full L2 rendering
- Mobile: L1 emblem-only rendering
- Terminal client: L0 (no rendering; voice only)
- VR headset: L5 spatial rendering

The **Director doesn't know** who's connected. The `voice.events` bus
already has this shape — subscribers observe, the emitter is unaware.
Extending this pattern to presence events is a straight generalization.

### 5.3 Client capability negotiation is CLIENT-SIDE

Each client decides:
- Whether to render at all
- Which subset of parameters to honor
- How to translate presence intents to its native rendering
- When to reduce fidelity (e.g. mobile → less mist to save battery)

Nero server has zero device-specific logic. Adding a new client type =
adding a new client. Server unchanged.

---

## 6. Multi-Device Networking Review (Tailscale-first)

### 6.1 Current state

Nero's FastAPI server binds to `0.0.0.0:8080` today (per `config.example.yaml`).
Any device on the same network — or on Tailscale — can reach it.

- **Local LAN:** `http://<local-ip>:8080` from phone / other computer works today.
- **Tailscale:** `http://<tailscale-hostname>:8080` works today if both devices are on the same tailnet.
- **HTTPS:** not yet configured. `tailscale serve` can provide HTTPS termination for free (see docs/REMOTE_ACCESS.md).

### 6.2 What needs to change for multi-device presence

**Server side (small changes):**
- Add a new HTTP endpoint `POST /api/presence/subscribe` (WebSocket
  upgrade) — accepts `client.hello`, returns a persistent event stream
  of `presence.intent` messages.
- Extend `voice.events` bus with a `presence.intent.broadcast` channel
  that mirrors every `PresenceDirector.set_intent()` call for out-of-process
  observers.
- Add client-tracking to the Presence Service (list of subscribed clients,
  for `/api/runtime/health`).

**Client side (per platform):**
- Each client establishes the WebSocket, sends its hello, then renders
  incoming intents per its own capability profile.
- No `localhost` assumptions. Everything URL-based, configurable per client.

### 6.3 Tailscale specifics

- Nero doesn't need to know it's on Tailscale — it's just a network.
- Client apps store the Nero URL (Tailscale hostname or IP) once.
- MagicDNS makes `http://nero-pc.tailnet.ts.net:8080/` work from any device
  on the tailnet.
- For end-to-end encryption over Tailscale, TLS is optional (Tailscale
  itself is encrypted). Adding HTTPS via `tailscale serve` is a
  no-cost hardening step.

### 6.4 Zero-config discovery (optional, later)

- mDNS broadcast: `nero-pc.local` on the LAN — future work, not MVP.
- QR-code pairing: display a QR with the Nero URL, phone scans, done.
  Cheap UX polish, not architecture.

---

## 7. Mobile UX Specification

**Do not replicate the desktop UI.** Mobile presence is a different
experience.

### 7.1 What mobile Nero looks like (v1)

- **Home screen widget** (Android) / **Live Activity** (iOS): a small
  emblem — the two wolf eyes and a violet mist puff — that pulses subtly
  when Nero is thinking or speaking.
- **Full-screen presence mode:** tap widget → dark background, wolf-eye
  emblem centered, mist ambient. This is the "voice-only conversation
  through the presence lens" mode.
- **Notification-driven speaking:** when Nero speaks, the widget/emblem
  glow intensifies. Optional haptic pulse on speaking start.

### 7.2 What the mobile app is NOT (v1)

- Not a full chat replica of the desktop UI (that's later)
- Not a Live2D character render (mobile can't sustain that battery-wise for
  an always-on companion)
- Not a voice recorder (voice → Nero happens elsewhere; presence just
  renders the response)

### 7.3 Presence Levels mapped to mobile

- **L0:** notification / widget with static emblem (no animation)
- **L1:** animated wolf-eye glow + mist particles (recommended default)
- **L2+:** deferred — not viable on mobile without huge battery cost

### 7.4 Recommended stack

- **Flutter** (free / BSD) for cross-platform Android + iOS. Renders
  presence via CustomPainter + a small particle system. Talks to Nero via
  WebSocket.
- Alternative: **React Native** or **native (Swift + Kotlin)** — pick per
  Toni's existing skill preference. Flutter recommended for solo dev.

### 7.5 Animation approach on mobile

- Skip Live2D on mobile in v1 — the Cubism mobile runtime exists but adds
  binary size + battery cost.
- Roll a custom shader-based emblem: two glowing dots + a Perlin-noise
  driven mist texture. ~50 lines of shader code, runs 60fps at negligible
  power.

---

## 8. Runtime Compatibility Review

Does the current architecture (voice/, presence/, app/runtime/) survive
the roadmap? Yes — with three additive extensions, no rewrites.

### 8.1 What's already right

- `PresenceRuntime` abstraction: swappable per-client renderer. Live2D,
  future Godot, future Unreal, mobile-custom — all plug in.
- `voice.events` pub/sub: cleanly broadcast-shaped. Extending to a
  network-broadcast mode (WebSocket subscribers) is a wrapper around
  the existing subscribe/emit.
- Config-driven runtime selection: adding a new runtime = 3 lines in
  `app/runtime/services/presence_service.py::build_runtime()`.
- `RuntimeService` lifecycle pattern: any new subsystem (multi-client
  subscription server, network discovery, remote rendering relay) is a
  new `RuntimeService`.

### 8.2 What needs to be added

1. **Multi-client presence broadcast** — a `PresenceBroadcastService`
   that accepts WebSocket subscribers and forwards every intent.
   Implements `RuntimeService`. Registers next to `PresenceService` in
   `app/main.py` lifespan.
2. **Client capability protocol** — extend the WebSocket protocol
   already spec'd in `live2d_protocol.md` with the `client.hello`
   message. New `contracts/client_capabilities.schema.json`.
3. **Auth / access control** — currently Nero has no auth. On Tailscale
   this is acceptable (tailnet is the auth boundary). For public exposure
   in the future, add a shared-token or OAuth layer. Not urgent.

### 8.3 What must NOT be added

- Server-side rendering of visuals. All rendering is client-side.
- Server-side per-client customization. All clients see the same intents.
- Server-side language / accent per client. Voice is one identity.

---

## 9. Implementation Roadmap (phased)

Sequenced so each phase produces a working, shippable-ish milestone.

### Phase A — Concept validation (Toni, ~1 week)
Goal: prove the visual identity converges under free tools.

- Set up ComfyUI + SDXL locally
- Generate 30+ Manbeardog concepts using the 6 references as IPAdapter conditioning
- Pick 3–5 as the LoRA training set
- **Milestone:** approved concept sheet — Manbeardog looks like Manbeardog in every generation

### Phase B — Identity lock (Toni, ~3 days)
- Train `manbeardog_v1.safetensors` LoRA
- Generate the 3 canonical master references (front / side / 3/4)
- **Milestone:** LoRA + master art. Every future asset derives from here.

### Phase C — First rig (Toni, ~2 weeks)
- Layer-separate the front-view master into a Live2D-ready PSD
- Learn Cubism Editor basics
- Rig the 5 `ParamNero*` parameters (from the parameter map)
- Export `manbeardog__L1__v1.model3.json`
- **Milestone:** a rigged L1 Manbeardog asset

### Phase D — First viewer (Toni + Claude, ~3 days)
- Build a static HTML page using Cubism Web SDK
- Loads `manbeardog__L1__v1`
- Connects to Nero via WebSocket per `live2d_protocol.md` (Claude built the runtime side already)
- **Milestone:** Nero speaks; wolf eyes glow in the browser window as she speaks. First live presence.

### Phase E — Multi-client server (Claude, ~2 days)
- Add `PresenceBroadcastService` as a new `RuntimeService`
- WebSocket endpoint accepting subscriber clients
- Extend protocol with `client.hello`
- **Milestone:** multiple clients can subscribe. Each renders per its capabilities.

### Phase F — Mobile client (Toni + Claude, ~2 weeks)
- Flutter app with the L1 emblem + mist shader
- Talks to Nero over Tailscale
- Widget / Live Activity for glanceable presence
- **Milestone:** Nero on Toni's phone.

### Phase G — Blender master (Toni, ongoing background work)
- Sculpt Manbeardog in 3D from the master references
- Retopologize + UV
- Rig for future Unreal migration
- **Milestone:** 3D asset ready when hardware / project decides Unreal is worth adopting.

**Total calendar estimate:** 6–10 weeks of Toni's evening/weekend time to
reach Phase D (first live presence). Phase E–G can proceed in parallel or
after.

---

## 10. Risks + Open Questions

### 10.1 Technical risks

- **SDXL VRAM contention with Ollama.** Generating art requires ~8–12 GB
  VRAM. Ollama's `qwen3:14b` already uses ~9 GB. Toni will need to
  shut Ollama down during generation sessions. Not a blocker, but a
  workflow constraint to plan around.
- **LoRA training quality.** With only 6 reference images + 3–5 approved
  concepts, the training set is small. LoRA may overfit to specific
  poses / lighting. Mitigations: augment with cropped/mirrored variants,
  train with regularization images, evaluate on held-out prompts.
- **Cubism rigging is manual craft.** No AI shortcuts here. This is the
  learning-curve bottleneck. Realistic budget: 3–8 evenings to first
  working L1 rig, more for L2+.
- **Mobile battery.** Even the custom shader emblem runs continuously.
  Widget-only mode with occasional pulses is the low-power path;
  full-screen presence should be a user-initiated mode, not always-on.

### 10.2 Open questions I cannot answer without deeper research or user input

- **Which Cubism Web SDK version to standardize on?** They ship v4 (Web
  Framework) and v5. Need to pick one before Phase D begins. Recommend v5
  (newest, ongoing support) but verify against the specific `.model3.json`
  spec version.
- **iOS Live Activity vs. widget for the mobile emblem?** iOS 16+ Live
  Activities are more presence-appropriate but come with more Apple
  constraints. Widget is simpler. Recommend widget for v1, migrate to
  Live Activity if iOS is a primary client.
- **Do we want a browser Nero client** (separate from the current
  chat UI) that renders Live2D presence in-browser using Cubism Web SDK?
  This would collapse Phases D + E into one path if yes. Recommend yes;
  the browser already has the chat surface. Add the presence viewer as
  an overlay on the existing web UI.
- **Auth / access control for multi-device.** Tailnet is the auth
  boundary for Toni's own devices. If Nero ever needs to be reachable by
  someone else, a shared-token or OAuth layer is required. Not urgent.

### 10.3 Things I explicitly did NOT do in this document

- **Deep tool-by-tool version-specific research.** SDXL / FLUX / Cubism
  versions change monthly. This roadmap describes the *shape* of the
  pipeline; the specific version numbers should be settled when Toni
  starts Phase A. Ask me then for a version-locked "install this today"
  list.
- **Cubism parameter naming validation against a real rig.** The names
  in `presence/runtime_bridge/live2d_parameter_map.py::CUBISM_PARAM_MAP`
  are conventions. When Toni actually rigs a model, if his rigger uses
  different names, override via the `cubism_param_overrides` config —
  one dict entry, no code change.
- **Actual concept generation, image editing, or rigging.** Not my job.
  Not my capability. This roadmap tells Toni what to do; execution is
  his time.
- **Detailed Flutter / React Native scaffolding.** Referenced but not
  built. Belongs to Phase F when it's time.

---

## Cross-references

- Visual Bible: `docs/visual/manbeardog_visual_bible.md`
- Live2D protocol spec: `presence/runtime_bridge/live2d_protocol.md`
- Live2D runtime code: `presence/runtime_bridge/live2d.py`
- Parameter mapping: `presence/runtime_bridge/live2d_parameter_map.py`
- Presence Director: `presence/director.py`
- Voice events bus: `voice/events.py`
- Runtime lifecycle: `app/runtime/`
- ADR-0002 (GPU discipline): `docs/adr/0002-model-router-sequential-swap.md`
- ADR-0009 (voice architecture): `docs/adr/0009-voice-rendering-and-backend-architecture.md`
- ADR-0010 (pedalboard adoption): `docs/adr/0010-voice-effects-pedalboard-adoption.md`
- ADR-0011 (single voice path): `docs/adr/0011-voice-single-path-croatian-handling.md`

## Governance

Same freeze discipline as elsewhere: this roadmap is v1.0. Revisions
create v1.1, v1.2. Once Phase A begins, expect small edits as reality
reveals what needed to change; those go into a v1.1 rather than silent
mutation.
