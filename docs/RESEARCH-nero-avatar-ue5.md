# RESEARCH — NERO as an embodied UE5 avatar (celestial being)

*A source-cited research report + honest asset audit + an opinionated, end-to-end
pipeline for turning NERO — the "celestial energy being" — into a rigged,
animated, real-time Unreal Engine 5 avatar streamed to the web at 60 FPS.*

> **Scope & honesty.** This document is **research and a plan**, not a built
> asset. It was produced from a multi-source, adversarially-verified web study
> (Epic Games documentation + peer-reviewed papers + practitioner sources; 25
> sources fetched, 112 claims extracted, 25 verified, **22 confirmed / 3
> refuted**). The **actual Unreal work** — MetaHuman assembly, materials,
> Niagara, retargeting, and the **measured 60 FPS evidence** — must be created
> and validated on an **Unreal seat** (matching the operator's own stated
> requirement). Where a figure was refuted or unverifiable, this doc says so
> and defers it to measurement rather than inventing a number.

Related repo memory: NERO's nine live states (`idle · listening · thinking ·
planning · reviewing · executing · speaking · waiting · offline`) are already
defined for the Mission Control field (`docs/DESIGN-mission-control.md`). The
avatar is the **embodiment of that same being** — those states map 1:1 onto her
animation/VFX states (see §7).

---

## 0. The reference material (what the operator actually has)

The operator provided a **model sheet / turnaround**, not a single render:

- A **full-body A-pose** turnaround — front, front-¾, both profiles, back-¾, back.
- A **full-body T-pose** turnaround — same angles.
- A **labeled head/bust** turnaround — `FRONT · FRONT ¾ R · RIGHT PROFILE ·
  BACK ¾ R · BACK · BACK ¾ L · LEFT PROFILE · FRONT ¾ L`.
- A **"Stellar Specter" texture package** — twelve 2048×2048 channel panels
  (base color, emissive, normal, ORM, roughness, metallic, AO, height, opacity,
  subsurface, scatter/transmission) + a reference render, and a written
  implementation brief (`Textures.md`). **These are channel-separated *concept
  panels* laid out by body part, not UV-baked maps** — see §2.1.

Design read (consistent across all angles): a **near-human female** figure made
entirely of **white/blue light** with a **constellation/filament "starmap"
pattern** across the skin, **twin high ponytails of light-hair**, **dark
sunglasses** (the single opaque element), and **wolf-head "pauldron" light-forms**
on both shoulders. She **floats** (pointed feet, non-grounded).

Two consequences that shape the whole plan:

1. **Near-human proportions** → a **MetaHuman base is viable** and is the right
   call (the research is explicit that stylized *proportions* break the facial
   rig; see §3.4). Keep the body/face near-human; put the "celestial" entirely
   into **materials + VFX**, not geometry.
2. **A real orthographic turnaround upgrades "concept → 3D" from guesswork to a
   standard modeling task.** Front/side/back drive the blockout; the **T-pose**
   is the rigging/bind reference. This is what artists model *from*.

---

## 1. Concept → 3D: what the images can and cannot give you (the "texture audit" reality)

**Confirmed (high confidence, primary sources).** Reconstructing 3D geometry
from a *single* view is a **fundamentally ill-posed problem**; single-image-to-3D
tools **infer/hallucinate** all unseen geometry and **synthesize** PBR textures
(diffuse/specular/normal) from a **generative prior** — they do **not** lift a
texture set out of the input image. A flat RGB render contains **no separated
diffuse/specular/normal channels**, so "extract the textures from the PNG and
apply them to a mannequin" is a **category error**.
*Sources: MeTTA, arXiv [2408.11465](https://arxiv.org/pdf/2408.11465); Magic123,
arXiv [2306.17843](https://arxiv.org/pdf/2306.17843).* Magic123 also shows the
core tension: only the **reference view** is supervised by the input image while
novel views are driven by 2D/3D diffusion priors, exposed as a single
"exploration ↔ exploitation" trade-off knob — i.e. fidelity to the drawing and
plausible unseen geometry **fight each other** and must be hand-tuned.

**What a turnaround genuinely provides** (the operator now has this):
- **Silhouette / alpha** per view → blockout volumes and proportion matching.
- **Color palette** (white → ice → cyan → spectral blue) → the material/emissive ramp.
- **Emissive stylization masks** — the constellation/filament "starmap" and the
  glowing edges → authored as **emissive/opacity masks**, not photographed PBR.
- **Consistent multi-angle design** → front/side/back modeling reference; the
  **T-pose** as the bind/rig reference.

**What it still does *not* provide** (must be authored, on any number of views):
- **UVs**, a **multi-channel PBR set**, **topology**, a **skeleton/rig**, or true
  depth. Standard character production is a **multi-stage pipeline** (concept →
  model → sculpt → retopo → UV → rig → animate), of which the sheet is stage one.
- **Image-to-3D limits for stylized art:** practitioner tool docs are candid that
  image-to-3D "does not work well for imaginary objects or concept art" and is
  tuned for photoreal references (Scenario KB). So an auto-generated mesh is at
  best a **rough blockout to sculpt over**, never a shippable rigged asset.

> **Refuted / do-not-rely-on (from verification):** a specific 80.lv
> characterization of PBR authoring was refuted 0-3 (the *broader* "PBR is
> multi-channel authoring, not extractable from one flat render" still holds via
> the arXiv sources); and "all MetaHumans share the Manny/Quinn skeleton so
> mocap retargets with minimal setup" was refuted 0-3 — directly contradicted by
> the IK-bone gotcha in §3.2. **Setup is not trivial.**

**Bottom line for NERO:** use the turnaround as a **model sheet** → build a
**near-human MetaHuman** → realize "made of light" in **materials + Niagara**.
Do **not** try to bake the look into a texture pulled from the art.

---

## 2. The ethereal "made of light" look — authored as MATERIALS + VFX

The glow/translucency/starmap is a **shading + VFX** problem, not a texture problem.

**Fresnel rim (the core mechanism, confirmed 3-0, Epic primary).** Epic's Fresnel
node "calculates a falloff based on the dot product of the surface normal and the
direction to the camera" — **0 straight-on, 1 at grazing/silhouette angles** —
and is the documented path for **rim / edge lighting**. Feed Fresnel into
**Emissive** (and Opacity) so the figure **peaks in brightness at her silhouette**
— that's what makes a translucent body still read as a person.
*Source: Epic, [Using Fresnel](https://dev.epicgames.com/documentation/unreal-engine/using-fresnel-in-your-unreal-engine-materials).*

**Material recipe (body):**
- **Translucent or Additive** blend, largely **Unlit/Emissive** to control cost
  (see §5 — translucency is the #1 budget risk).
- **Emissive** = palette ramp × (Fresnel rim + **constellation/filament mask**).
  The starmap is an authored **emissive mask** (hand-painted or derived from the
  turnaround), optionally animated (panning/twinkling) via a second UV or noise.
- **Fresnel** for edge glow; **Depth-Fade** so she doesn't hard-clip against
  geometry; light **refraction/distortion** for the "energy" shimmer;
  **dithered opacity** (or WPO shimmer) for a living surface.
- **Subsurface** where you want soft "flesh-of-light" interior scatter.
- **Sunglasses** stay a normal **opaque** material — a deliberate anchor for the eye.

**VFX (Niagara):** the wolf-shoulder forms, trailing filaments, and the ambient
"energy body" are **Niagara** systems — emissive **ribbon trails** for the
hair/wisps, GPU sprite/mesh emitters for body motes, and a driven **emissive
material** (Particle Color + a Dynamic Parameter into Emissive) so the Brain can
recolor her by state. *Practitioner refs: Epic hologram-shader tutorial; CGHOW
ribbon-trail; halo-aura Niagara guide.*

### 2.1 The "Stellar Specter" texture package (12-channel visual target)

The operator supplied a full channel set as **2K concept panels** with an
implementation brief (`Textures.md`). **Honesty gate (stated by the package
itself):** these were *"extracted and enlarged from a generated visual texture
sheet… not guaranteed to share the target model's UV layout, texel density,
seams, topology, tangent basis, or material-slot arrangement. Do not blindly
assign them."* They are a **visual target and starting source** — you
**reproject / project-paint / bake mesh-specific 2K maps against the final
model's UVs** (Substance Painter / Blender bake), using the panels as the look
reference, and **strip the sheet borders/labels/panel divisions**. This is the
same conclusion as §1, now with a ready-made target for every channel.

**Channels supplied:** `base_color · emissive · normal · orm · roughness ·
metallic · ambient_occlusion · height · opacity · subsurface · scatter/
transmission` + `reference_character`. The **emissive** panel (the branching
white-blue energy-vein network + star clusters) is the richest and most useful —
it *is* the "made of light" signature and drives most of the look.

**Import settings (from the brief + README, standard PBR):**
- **sRGB on:** Base Color, Emissive, Subsurface, Scatter/Transmission.
- **Linear / Non-Color:** Normal, ORM, Roughness, Metallic, AO, Height, Opacity.
- **Normal:** Normalmap compression. **ORM:** `AO=R, Roughness=G, Metallic=B`.
- Body generally **non-metallic**; sunglasses use their own plausible values.

**Material structure (target — build on the Unreal seat):**
`M_StellarSpecter_Master` → instances `MI_Body / MI_Hair / MI_Sunglasses /
MI_Wolves / MI_Wisps`. Separate materials per component (body, hair, opaque
sunglasses, wolf pauldrons, wisps) rather than one über-material. **Expose
parameters** (per the brief): emissive intensity/color, body opacity, edge-glow
intensity, Fresnel exponent/intensity, internal-star brightness, energy-vein
brightness, roughness, refraction (off by default), depth-fade distance,
animation speed, distortion, wisp intensity, bloom response. Add **quality
switches** (`Cinematic / High / Performance`) that shed **wisps → distortion →
secondary noise before silhouette readability**.

**Body treatment (aligns with §2 + §5):** translucent/additive/hybrid-masked
(pick the least expensive that holds up — test the Surface Translucency Volume vs
alternatives), **Fresnel** edge glow, **Depth-Fade** on intersections, **subtle**
emissive animation (panning noise / gentle star flicker — never uniform blink or
strobe, never distort the face), keep the **face readable** under normal
exposure, and **avoid overdraw + full-screen bloom blowout**.

> **Where the assets live:** the 30 MB panel package is UE/DCC production
> material, not repo material — it belongs on the Unreal seat / an asset store
> (or Git LFS), **not** committed into this Python web-app repo. This doc is the
> durable record of *what it is and how to use it*.

---

## 3. Rig & animation — the precise MetaHuman pipeline

### 3.1 Body: runtime retarget of UE5 Mannequin animation onto the MetaHuman body
**Confirmed (3-0, Epic primary).** Drive the MetaHuman **body** from standard
UE5 Mannequin (Manny/Quinn) animation **at runtime**: in the MetaHuman **body**
Anim Blueprint's AnimGraph, add a **`Retarget Pose from Mesh`** node → wire to
**Output Pose** → set its **Retargeter Asset** to **`RTG_Mannequin`**. Epic's doc
walks the exact steps (create `ABM_MHRuntimeRTG` from the `f_med_nrw_body`
skeletal mesh; assign via *Use Animation Blueprint*), so the retarget outputs onto
the **MetaHuman body skeleton** while the **face stays on the separate facial
skeleton** (§3.3).
*Source: Epic, [Retargeting Animations to a MetaHuman at Runtime](https://dev.epicgames.com/documentation/en-US/metahuman/retargeting-animations-to-a-metahuman-at-runtime).*

### 3.2 The retarget gotchas (plan for these first)
- **Missing IK bones (confirmed 3-0, blog primary + independent corroboration):**
  the MetaHuman body skeleton **omits `ik_foot_root`, `ik_foot_l/r`** (and hand IK
  equivalents) by default, so **foot IK breaks** until you **copy those bones in
  from `SKM_Manny_Simple`**. *Refs: [Medium 5.6/5.7 pipeline reference](https://medium.com/@Jamesroha/metahuman-5-6-5-7-pipeline-reference-170d302b078e);
  Epic Dev Community "No IK foot on MetaHumans?"; GitHub
  [droganaida/meta-human-ik-retargeting-guide-ue5](https://github.com/droganaida/meta-human-ik-retargeting-guide-ue5).*
  (For a **floating** NERO who never plants feet on a floor, runtime foot-IK
  matters less — but keep the bones present so the ABP/retarget doesn't error.)
- **Spine mismatch:** MetaHuman body has **5 spine bones**, the Mannequin **3** —
  handle in IK-Rig chain mapping + retarget pose.
- **Deformation artifacts** (arms too-close/forward, twisted fingers, hands
  clipping thighs) are the norm out-of-the-box and need manual IK-Rig/retarget-pose
  correction. *Ref: Epic Dev Community retargeting-deformation threads.*

### 3.3 Face: DNA + RigLogic (confirmed 3-0, Epic primary)
The facial rig runs on **DNA** (Epic's data format encoding the head/body/rigs —
geometry + skeleton in neutral pose across LODs, skin weights per LOD) driven by
**RigLogic** (a runtime operator in UE **and** Maya that maps hundreds of
semantic facial channels → many joint transforms + per-vertex displacement at
LOD0). This keeps NERO's face expressive **independently** of body retargeting.
*Source: Epic, [DNA / Rig Definition & Rig Operation](https://dev.epicgames.com/documentation/metahuman/metahuman-dna-rig-definition-and-rig-operation).*

### 3.4 Real-time face paths (confirmed; one comparison was 2-1)
For a **live web companion**, layer a **real-time facial source** over the
retargeted body:
- **Live Link Face (iPhone/ARKit)** — real-time, rapid iteration.
- **Real-time audio Live Link source** — lip-sync from audio, **but the real-time
  audio solver produces NO head motion** → you must supply head movement
  separately (additive head idle / Control Rig look-at). Epic is explicit that the
  "Realtime Audio Solver … is still an offline process and is not the same as
  generating animation in real time from a MetaHuman Audio Live Link Source," and
  that the real-time path "does not produce head motion" while the **offline**
  solve "can now generate head movement straight onto your MetaHuman."
- **MetaHuman Animator (offline)** — highest fidelity + head motion, for
  pre-baked lines. *Currency note: MHA gained a real-time mode by UE 5.8, so the
  strict "offline-only" label softens; the offline high-fidelity solve remains its
  headline value.*
*Sources: Epic, [Audio-Driven Animation](https://dev.epicgames.com/documentation/metahuman/audio-driven-animation); [nastyrodent MetaHuman breakdown](https://nastyrodent.com/ue5-metahuman/).*

### 3.5 Stylized face limit (confirmed 3-0)
**MetaHuman Creator cannot build a non-human face** — it is bounded by
photographic human plausibility (no enlarged eyes / exaggerated cheekbones /
elongated jaw). A stylized head needs **Mesh-to-MetaHuman** (sculpt in a DCC →
Identity Solve wraps the MetaHuman template topology onto it → derives a **DNA**
for a working rig), but **extreme non-human proportions cause deformation
artifacts at expression extremes** (correctives are calibrated for human range).
**NERO is near-human (per the turnaround), so this is a non-issue** — keep her
proportions human, push the "celestial" into look/VFX.
*Sources: [nastyrodent](https://nastyrodent.com/ue5-metahuman/); Epic,
[Mesh to MetaHuman](https://dev.epicgames.com/documentation/metahuman/mesh-to-metahuman).*

### 3.6 Secondary / procedural motion
Use **Control Rig** for procedural secondary motion (breathing, hair/pauldron
sway, gaze/look-at), layered additively in the body ABP after the retarget.

---

## 4. Movement feel for a floating being

Because NERO **floats** (non-grounded), lean away from grounded locomotion and
into:
- **Additive idle / breathing** and **procedural secondary motion** (Control Rig)
  as the base "alive" layer.
- **Hair + pauldrons as simulated light** (groom/cards + Niagara ribbons; light
  cloth/spring sim) so she drifts.
- **Gaze / look-at** toward the operator and **gesture layering** (additive
  upper-body poses per state) over a slow floating idle.
- **Root motion** optional; **motion warping** only if she ever traverses.
- Since there's no floor contact, **de-prioritize foot-IK** (but keep IK bones,
  per §3.2) and let the lower body trail.

*(This is the section the operator's 69-file handoff — character bible, 60 FPS
state machine, gaze/gesture/dialogue-performance rules — will refine most;
see §7.)*

---

## 5. Performance for 60 FPS + Pixel Streaming 2

**The two biggest 60 FPS threats (both confirmed):**
1. **Translucency overdraw (3-0, Epic primary).** "The cost of rendering
   transparency becomes more and more expensive for each successive layer," and
   "lit transparency can quickly become a performance bottleneck if there are too
   many transparent objects." NERO's translucent body **plus** Niagara
   wisps/filaments stack overdraw — this is the **first** budget to watch. Prefer
   **additive/unlit**, minimize overlapping translucent layers.
   *Source: Epic, [Using Transparency](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-transparency-in-unreal-engine-materials).*
2. **MetaHuman corrective-bone CPU cost (2-1, blog + forum).** The dominant
   per-character CPU cost is the **animation thread evaluating corrective bones**;
   disabling **Body + Neck Correctives** recovers **~40% FPS** — a real
   degradation lever. **Treat the % as directional** (editor-measured,
   scene/hardware/LOD-dependent, not guaranteed in a packaged Pixel Streaming
   build). *Refs: [Medium 5.6/5.7 ref](https://medium.com/@Jamesroha/metahuman-5-6-5-7-pipeline-reference-170d302b078e); [Epic forum "3.0 MetaHumans 40% gains"](https://forums.unrealengine.com/t/the-new-3-0-metahumans-40-performance-gains/1777726).*

**Profiling toolchain (confirmed 3-0, Epic primary)** — the instruments the seat
must use: **Unreal Insights** (launch with **`-StatNamedEvents`** to capture asset
names; has overhead — use to *locate* bottlenecks), the **Niagara Debugger**
(profiling alongside PIE), the **Quad Overdraw View Mode** (particle/translucency
overdraw), and the **Shader Complexity View Mode**.
*Source: Epic, [Measuring Performance in Niagara](https://dev.epicgames.com/documentation/unreal-engine/measuring-performance-in-niagara?lang=en-US).*

**Pixel Streaming 2 (confirmed 3-0, Epic primary).** Run the UE app
**server-side** (desktop or cloud) and stream **rendered frames + audio over
WebRTC** to the browser — this embeds cleanly next to the existing Companion /
Mission Control web approach. It adds **GPU H.264 encoder cost + latency +
bitrate** **on top of** the render budget, all sharing the same GPU.
*Source: Epic, [Pixel Streaming](https://dev.epicgames.com/documentation/en-us/unreal-engine/pixel-streaming-in-unreal-engine).*

> **No assumed numeric budgets.** A specific "~3–6 ms/char, 1–4 heroes on screen"
> figure was **refuted (1-2)** — there is **no verified per-character GPU number**
> here. Particle-count ceilings, translucent-layer limits, Lumen-vs-ray-tracing
> deltas, and PS bitrate/latency **did not survive verification either**. The 60
> FPS target is **measurable, not pre-computable** — capture it on the **actual
> deployment hardware** (§8).

**Sane degradation order (from confirmed mechanisms, tune by measurement):**
translucent layers/overdraw → Niagara particle counts (GPU sim, additive/unlit) →
MetaHuman **correctives** off → strand-hair → LODs → Lumen/HWRT/volumetrics →
stream resolution/bitrate.

---

## 6. Recommended end-to-end pipeline (tool by tool)

0. **Concept audit** — from the turnaround, pull the **palette**, per-view
   **silhouette/alpha**, and the **constellation emissive mask**. No texture
   extraction.
1. **Base identity (MetaHuman)** — build a **near-human** NERO. Face via MetaHuman
   Creator; if custom proportions are needed, **Mesh-to-MetaHuman** (sculpt head in
   Blender/ZBrush against the head turnaround → Identity Solve → DNA). Body from a
   MetaHuman preset matched to the T-pose proportions.
2. **The look (materials)** — **bake mesh-specific 2K maps** against the real UVs
   using the **Stellar Specter** panels as the visual target (§2.1), then build
   `M_StellarSpecter_Master` + `MI_*`: translucent/additive **emissive** body
   (palette ramp × (**Fresnel** rim + baked **emissive/energy-vein** map)) +
   depth-fade + refraction + dithered/WPO shimmer + subsurface; **opaque**
   sunglasses; quality switches `Cinematic/High/Performance`.
3. **VFX (Niagara)** — wolf-shoulder pauldrons, hair/wisps as **emissive ribbon
   trails**, ambient body motes; a **Dynamic Parameter** so the Brain recolors her
   by state.
4. **Body anim** — import a UE5 **Mannequin** animation set; build IK-Rigs +
   **`RTG_Mannequin`** IK Retargeter; **copy the IK bones from `SKM_Manny_Simple`**
   first; drive the body at runtime via **`Retarget Pose from Mesh`** in
   `ABM_MHRuntimeRTG`; fix spine-mismatch + deformation in the retarget pose.
5. **Face** — DNA/RigLogic; real-time via **ARKit Live Link** or a **real-time
   audio Live Link source** (supply **head motion** separately — the real-time
   audio solver gives none); MHA **offline** for hero/pre-baked lines.
6. **Movement** — Control Rig additive idle/breathing, hair/pauldron sway,
   gaze/look-at, gesture layering over a floating idle; de-prioritize foot-IK.
7. **Companion integration** — map NERO's **nine Brain states** to anim/VFX states
   via the Companion↔Unreal **event schema** (this is where the 69-file handoff's
   state machine + schemas slot in; §7).
8. **Delivery** — **Pixel Streaming 2**, UE app server-side, WebRTC to the web UI.
9. **Measure** — profile and capture the §8 evidence before calling it done.

---

## 7. Fit with the existing NERO system

- **State continuity:** the avatar's animation/VFX states are the **same nine
  states** already modeled for Mission Control (`nero-core-states.json`) — idle →
  slow float; thinking → denser internal light; executing → brighter/faster;
  waiting → amber authority cue; offline → dim. One state vocabulary, two
  surfaces (the orb field **and** the embodied avatar).
- **Two independent tracks stay independent:** per the Constitution, the **Brain
  produces a response; the presentation layer presents it.** The avatar is an
  **output/presentation surface** (like Voice) — it must **not** touch the
  executive path (no dispatch/authorize/Journal). It consumes Brain state over an
  event schema; it never acts.
- **The 69-file Unreal/MetaHuman handoff** (character bible · 60 FPS state machine
  · gaze/gesture/dialogue rules · Companion↔Unreal event schemas · perf budgets ·
  acceptance tests) refines §4, §6.7, and §8 specifically. **Attach it and this
  plan aligns to it.**

---

## 8. "Done" gate — the measured evidence an Unreal seat must capture

No claim of 60 FPS is credible without these, captured **on the deployment
hardware** with **Pixel Streaming active**:

- [ ] **Unreal Insights** trace: GPU frame **< 16.6 ms** at target stream
      resolution **with the WebRTC/NVENC encoder running** (encoder shares the GPU).
- [ ] **Quad Overdraw** + **Shader Complexity** captures: translucency + Niagara
      overdraw within budget (no red hotspots over the figure).
- [ ] **CPU animation-thread** cost measured; **correctives on/off** delta recorded.
- [ ] **Niagara** per-system particle counts + cost (GPU vs CPU sim noted).
- [ ] **WebRTC** end-to-end **latency + bitrate** at target resolution.
- [ ] **Retarget QA:** no arm/finger/hand-clipping artifacts; IK bones present;
      spine-mismatch resolved.
- [ ] **Face QA:** real-time path latency acceptable; **head-motion source**
      working alongside audio lip-sync; frame-accurate with body retarget.
- [ ] **Sustained 60 FPS** under representative interaction (state changes,
      speaking, gestures), streamed.
- [ ] **Texture reconstruction QC** (from `Textures.md`): maps **baked to the
      real mesh UVs** (no sheet borders/labels/panel artifacts), no visible
      seams under normal viewing, readable face, correct per-channel sRGB /
      Normalmap / ORM settings, no inverted normal channels.

---

## 9. Honest caveats (carry these forward)

- **Source quality:** the strongest findings (single-view ill-posedness; Fresnel;
  translucency overdraw; runtime retargeting; DNA/RigLogic; audio offline-vs-real-time;
  Niagara profiling; Pixel Streaming) rest on **primary sources** (arXiv + current
  Epic 5.6–5.8 docs), unanimous **3-0**. The IK-bone gotcha, the ~40% correctives
  lever, the Creator stylization limit, and Mesh-to-MetaHuman rest on
  **practitioner blogs corroborated by Epic docs/forums** — treat their **specific
  numbers as directional**.
- **Refuted (do not rely on):** the "~3–6 ms/char, 1–4 heroes" GPU budget (1-2);
  "all MetaHumans share Manny/Quinn → trivial retarget" (0-3, contradicted by the
  IK-bone gotcha); a specific 80.lv PBR characterization (0-3, though the broader
  "PBR is authored, not extracted" holds).
- **Time-sensitivity:** MetaHuman tooling moves fast (MHA real-time mode by 5.8;
  the "3.0 component"/correctives are 5.6/5.7-era; Pixel Streaming 2 specifics
  evolve). The **ill-posedness of single-view reconstruction** and **Fresnel /
  overdraw physics** are version-invariant.
- **Scope gap = the whole numeric budget.** Almost **no measured numbers survived
  verification.** Every ceiling in §5/§8 must be **measured**, not assumed.

---

## 10. Open questions for the Unreal seat

1. Actual per-frame GPU cost on the Pixel Streaming server (MetaHuman render +
   translucency overdraw + Niagara + WebRTC encoder) — headroom under 16.6 ms at
   target resolution?
2. Safe numeric ceilings for the ethereal VFX (overlapping translucent layers;
   Niagara counts; GPU-vs-CPU sim; additive/unlit necessity) with the encoder also
   on the GPU?
3. Concrete Lumen / hardware-ray-tracing / volumetric-fog tradeoff for a starfield
   + volumetric light + glowing translucent character, and where GI sits in the
   degradation order.
4. Which real-time facial path best fits NERO (ARKit Live Link vs real-time audio
   source vs Audio2Face-style), and exactly how head motion is supplied when the
   real-time audio solver produces none — coexisting frame-accurately with body
   retargeting.

---

*Sources are linked inline. Full verification detail (per-claim votes, evidence,
and the 25-source table) is in the research run this doc was compiled from.
This is a plan to be executed and measured on an Unreal seat — not a claim that
any asset has been built.*
