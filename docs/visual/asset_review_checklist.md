# Asset Arrival Checklist

**Purpose:** the review gate when a Manbeardog asset arrives from
production (from Toni's own hand, from ComfyUI generation, from Cubism
Editor rigging, from Blender sculpting — wherever). Nothing enters the
production ecosystem until it passes this gate.

**Related:** `docs/visual/asset_contract.md` defines the requirements;
this doc is the workflow that enforces them.

---

## The workflow

```
                    Asset received
                          │
                          ▼
              ┌─────────────────────────┐
              │  1. Bible review        │
              │     (identity gate)     │
              └─────────────────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │  2. Contract check      │
              │     (metadata gate)     │
              └─────────────────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │  3. Technical           │
              │     validation          │
              └─────────────────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │  4. Runtime import test │
              └─────────────────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │  5. Presence event test │
              │     (voice+visual sync) │
              └─────────────────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │  6. Device validation   │
              │     (desktop + mobile   │
              │      + web)             │
              └─────────────────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │  7. Production approval │
              └─────────────────────────┘
                          │
                          ▼
                  Asset promoted
```

Every step has a checklist and a fail-fast rule. An asset that fails one
step is sent back with specific feedback; it does NOT proceed with
outstanding issues.

---

## Step 1 — Bible review (identity gate)

The most important step. If identity is wrong, nothing else matters.

Cross-reference against `docs/visual/manbeardog_visual_bible.md`:

- [ ] Hair — magenta / burgundy, twin high side ponytails (Bible §4.4)
- [ ] Sunglasses — black rectangular, opaque lenses (Bible §4.3)
- [ ] Eyes — hidden behind sunglasses; if any glow visible, only through
      the lenses as through-glow (§4.2, §14.1)
- [ ] Wolf pauldrons — present, pink-magenta eye glow (§4.7)
- [ ] Armor — ancient weathered black steel, matte finish (§4.6, §7.1)
- [ ] Cape — tattered but not damaged, dark (§4.6, §7.2)
- [ ] Skin — pale, cool-toned, elven with pointed ears (§4.1)
- [ ] Expression — from the allowed set in §10 (neutral wisdom, warmth,
      focused, concerned, quiet amusement, satisfaction). No forbidden
      expressions (no open smiles, no snarls, no wide-eyed surprise,
      no exposed teeth).
- [ ] Environment (if applicable) — cold palette (snow / mist / cool
      gray-white), never warm sunny (§8.3, §12)
- [ ] Color palette compliance (§6) — no neon, no bubblegum pink, no
      bright fantasy gold outside dormant/activating rune contexts
- [ ] "Feels like Manbeardog" gut check — she reads as *the* Manbeardog,
      not a generic dark-fantasy warrior

**Pass criterion:** ALL checkboxes checked. Any single unchecked = **REJECT**.

**Feedback format for rejection:**
```
Rejected — Bible review, Section [§ number]
Detail: [specifically what's off]
Recommendation: [what to change]
```

---

## Step 2 — Contract check (metadata gate)

Per `docs/visual/asset_contract.md`.

- [ ] `metadata.json` file present adjacent to the asset
- [ ] All 8 required fields populated
- [ ] No field is `"unknown"` (or if it is, an ADR-style justification is
      attached)
- [ ] `asset_name` follows the naming convention (`<char>__<level>__v<n>`
      for versioned artifacts)
- [ ] `visual_bible_version` matches the version this asset was reviewed
      against (typically `"1.0"` at time of writing)
- [ ] `license_status` is one of the acceptable values
- [ ] `dependencies` list is complete — no missing entries
- [ ] `fallback_behavior` is specified (not `"unknown"`)

**Pass criterion:** all fields present and valid. Missing metadata =
**REJECT with clear correction instructions.**

---

## Step 3 — Technical validation

Category-specific. Pick the right sub-checklist:

### 3a — Live2D model

- [ ] `.model3.json` opens without errors in Cubism Editor / Cubism Web SDK
- [ ] `.moc3` file present and referenced by the `.model3.json`
- [ ] All textures present in `characters/manbeardog/live2d/textures/`
- [ ] Cubism parameters exist that match either the default map
      (`presence/runtime_bridge/live2d_parameter_map.py::CUBISM_PARAM_MAP`)
      OR the config's `cubism_param_overrides` (documented in the metadata)
- [ ] Motion files (`.motion3.json`) for at minimum: idle, emerge, dissolve
- [ ] Expression files (`.exp3.json`) for at minimum: neutral (Bible §10)
- [ ] Layer separation documented in
      `characters/manbeardog/live2d/psd/<name>_layers.md`
- [ ] PSD source file archived (so rig can be re-exported)
- [ ] Cubism Editor free-license eligible use (Toni's project qualifies)

### 3b — LoRA

- [ ] `.safetensors` file loads without error in ComfyUI / A1111
- [ ] Config JSON matches the training run
- [ ] Trigger word (if any) documented in metadata
- [ ] Test gallery: 8 generations from unseen prompts all recognizably Manbeardog
- [ ] Base model + version documented

### 3c — Blender master scene

- [ ] `.blend` opens in Blender 4.x without missing-texture warnings
- [ ] All textures relatively-referenced (no absolute paths)
- [ ] Canonical camera bookmarks: front, three-quarter, side
- [ ] Material previews render without errors
- [ ] Test export: FBX + glTF both succeed
- [ ] Poly count reasonable for target runtime (Unreal / real-time)

### 3d — Render (portrait / cinematic / promo)

- [ ] Resolution ≥ target (2048+ for portraits, 3840+ for wallpapers)
- [ ] Color space documented (sRGB standard)
- [ ] Source scene documented in metadata
- [ ] Alpha channel present if character is composited over transparent bg

### 3e — Mobile emblem / shader

- [ ] Emblem PNG has clean alpha channel
- [ ] Shader compiles for target platform (WebGPU / Metal / Vulkan)
- [ ] Shader parameters match the abstract-parameter names
- [ ] Battery / fps benchmarked on real device (or a plausible estimate)

**Pass criterion:** all applicable sub-checkboxes checked. Failures with
clear technical reason = REJECT with fix instructions.

---

## Step 4 — Runtime import test

Actually load the asset into the runtime it's targeted for.

### For Live2D assets

1. Place the model in `characters/manbeardog/live2d/model/`
2. Configure the Cubism Web SDK viewer to load it
3. Start the viewer (browser or Electron window)
4. Confirm: model loads, initial pose visible, no console errors
5. Confirm: viewer sends `hello` message with `params_available` listing
   all expected `ParamNero*` names

### For LoRAs

1. Load the LoRA in a fresh ComfyUI session
2. Generate a canary prompt (Recipe A from prompt system) with default
   settings
3. Confirm: image generates without errors, matches Manbeardog identity

### For Blender masters

1. Open in Blender 4.x
2. Confirm: viewport renders correctly, no missing linked data
3. Test render: single frame at low res confirms materials work

**Pass criterion:** clean import + expected behavior. Import errors =
**REJECT.**

---

## Step 5 — Presence event test (integration)

For rigged assets that will drive live presence — the moment of truth.

1. Start Nero fully (`python run.py`)
2. Confirm `/api/runtime/health` shows `presence` service running with
   configured runtime
3. If Live2D: confirm the viewer connects via WebSocket (check runtime
   health `details.runtime_health.connected: true` and
   `details.runtime_health.viewer_hello` shows the model name)
4. Trigger `PresenceDirector.emerge()` via test hook or fire the app
   startup emergence
5. Confirm visual: wolf-eye glow appears first, mist forms, character
   resolves per Bible §11.1 timing
6. Trigger a `POST /api/speak` with English text
7. Confirm visual: speaking-state animation runs synchronized with voice
   (breathing, subtle motion, through-glow modulates)
8. Confirm audio: voice plays as `nero_prime_v1` — unchanged
9. Trigger `PresenceDirector.dissolve()`
10. Confirm visual: reverse manifestation, wolf eyes fade last per §11.2

**Pass criterion:** all 10 steps observable + no console errors + no
degradation of voice or chat. Regression in voice/chat = REJECT even if
visuals look right (per architectural invariant: presence never breaks
voice).

---

## Step 6 — Device validation

For any asset that will render on multiple devices:

### Desktop
- [ ] Renders correctly in Chromium (via the Cubism Web SDK viewer)
- [ ] Renders correctly if applicable to Windows-native / Electron
- [ ] Frame rate 30-60 fps at target level
- [ ] CPU/GPU load reasonable (~1-5% CPU, minimal GPU for L2)

### Mobile (when mobile asset)
- [ ] Renders on Android device (physical or emulator)
- [ ] Renders on iOS device (if applicable — physical or simulator)
- [ ] Widget mode + full-screen mode both work
- [ ] Battery cost measured for a 30-min session
- [ ] Behavior on network disconnect: emblem desaturates per
      `docs/mobile/presence_experience.md` offline spec

### Web browser
- [ ] Loads in Chromium (Chrome, Edge)
- [ ] Loads in Firefox
- [ ] Loads in Safari (if applicable)
- [ ] Transparent background renders correctly

**Pass criterion:** at least the intended primary device passes. Others
"nice to have" but not required for initial promotion.

---

## Step 7 — Production approval

Human gate. Toni signs off.

1. Review the completed checklist for all prior steps
2. Look at the asset one more time in its production context
3. Read the asset's `metadata.json` end-to-end
4. Decide: promote to production, or send back with specific feedback

**Approval action:**
- Move the asset from its `pending/` folder to its production location
  (e.g. from `characters/manbeardog/live2d/model/pending/` to
  `characters/manbeardog/live2d/model/`)
- Update `metadata.json` with `"approval_date": "2026-07-XX"` and
  `"approved_by": "Toni"`
- Record in this doc's outstanding-approvals section (below) — for the
  audit trail

**Rejection action:**
- Asset stays in `pending/`
- File a rejection note in this doc's rejections section (below) with:
  which step failed, what was wrong, what to change

---

## Outstanding approvals (running log)

Format: `YYYY-MM-DD | asset_name | approver | notes`

*Empty. First entry will be logged when the first Manbeardog asset arrives.*

---

## Rejections + rework (running log)

Format: `YYYY-MM-DD | asset_name | step failed | reason | action`

*Empty. First entry will be logged when the first rejection happens.*

---

## Fast-track exceptions

Some assets can skip specific steps by policy:

- **Concept sketches** in `source/concepts/` — no review required.
  They're throwaway exploration. Skip entire checklist.
- **LoRA training set entries** in `source/approved/` — Step 1 (Bible)
  required. Steps 2-7 skipped (they're training data, not runtime assets).
- **Test renders** in `renders/previews/` — Step 1 (Bible) required.
  Skip everything else.

## Slow-track additions

Some asset types trigger EXTRA scrutiny beyond the standard checklist:

- **New Manbeardog LoRA** (v2, v3, ...) — additional review: does the
  new LoRA meaningfully differ from the old one in a *deliberate* way?
  Or is it drift? Requires Toni's explicit decision to bump.
- **Character skin variants** (alternate armor, alternate outfits) —
  additional review: does the skin still read as Manbeardog?
  Requires a bible-adjacent addendum documenting the variant's rules.
- **Cross-character bundles** (Manbeardog + companion beast) —
  additional review: does the beast follow its own emerging bible
  entry? Currently there's no companion bible, so these are DEFERRED
  until one exists.

---

## Governance

This checklist is v1.0. Bumping requires:
- New checklist items are added additively
- Existing items are never silently removed — if an item is dropped, it's
  documented in the changelog
- Version tracked alongside the Visual Bible version
