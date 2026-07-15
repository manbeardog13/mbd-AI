# Manbeardog — Measurable Identity Spec + Measurement Harness v0.1

**Status:** DRAFT — targets/tolerances are **uncalibrated** until measured against the 6
canonical refs (calibration is the first harness run). Method design is real now.
**Purpose:** the machine twin of `manbeardog_identity_profile.md`. Turns subjective
descriptions into **numbers the Audit Director compares**, so identity drift is *measured*,
not eyeballed. This is how "losing her sunglasses = complete failure" becomes an
enforceable gate rather than an opinion.

---

## 1. Measurement philosophy

- **Objective first.** Prefer computable metrics (color, geometry, luminance, embeddings)
  over adjectives.
- **Hard gates over soft scores for signatures.** A signature trait is a *boolean gate*:
  present-and-correct, or **auto-reject** — no averaging it away with a pretty background.
- **Honesty about maturity.** Some traits are measurable today with off-the-shelf CV;
  some (material gloss, "edge wear", wolf-jaw fidelity) need a **learned scorer** trained
  later on approved/rejected labels. Each trait below is tagged `NOW` or `LEARNED`.
- **Calibrated from the Canon.** Targets come from measuring the 6 references, not from
  my guesses. Tolerances are set so all 6 refs pass by construction.

---

## 2. Measurement stack (all free, local, ComfyUI-independent)

| Concern | Tool (🔬 verify current) | Output |
|---|---|---|
| Face identity | InsightFace / ArcFace | 512-d face embedding |
| Face geometry | MediaPipe FaceMesh / dlib | 468 landmarks |
| Region masks (hair, lenses, pauldrons, armor, silhouette) | SAM2 + point/box prompts; hair-parsing net | binary masks |
| Semantic presence | open-vocab check (CLIP / OWL-ViT) | "wolf-head pauldron" present? |
| Color / luminance / geometry | OpenCV + NumPy | Lab colors, ratios, bboxes, histograms |

The harness is a standalone Python module in `engine\audit\` → input image → output
`identity_report.json`. It scores **any** image from any renderer (SDXL today, Flux/3D
later), which is why it lives in the Canon layer, not in ComfyUI.

---

## 3. Measurable traits

Format: **trait — measured quantity — method — maturity.** Targets `T` / tolerance `±` filled at calibration.

### Face (identity anchor)
- `face.embedding_distance` — cosine distance of ArcFace embedding to the **canonical
  face centroid** (mean of the 6 refs) — `NOW`. *Primary objective identity metric.*
- `face.proportions` — inter-ocular / nose-length / jaw-width ratios from landmarks — `NOW`.
- `face.skin_L`, `face.freckle_density` — mean lightness of skin mask; blob count — `NOW/LEARNED`.

### Hair (twin pigtails)
- `hair.pigtail_count` — count of distinct high hair masses above crown line — `NOW` → **gate: == 2**.
- `hair.mount_height` — pigtail-base height / head-height (high mount) — `NOW`.
- `hair.symmetry` — L/R mass + position ratio (perky, even) — `NOW`.
- `hair.root_color_Lab`, `hair.tip_color_Lab` — sampled root vs tip regions; ΔE vs magenta/burgundy targets — `NOW`.
- `hair.volume`, `hair.length_ratio` — mask area / silhouette; tip-y vs shoulder-y — `NOW`.

### Sunglasses (hard gate cluster)
- `glasses.present` — detection in the eye band — `NOW` → **gate: true**.
- `glasses.lens_luminance` — mean L in lens mask (opaque-dark) — `NOW` → **gate: ≤ T (dark)**.
- `glasses.frame_thickness` — frame stroke px / face width (blocky) — `NOW` → **gate: ≥ T (thick)**.
- `glasses.shape` — lens aspect + top-edge straightness (rectangular wayfarer, not round/cat-eye) — `NOW/LEARNED` → **gate: rectangular**.
- `glasses.ornamentation` — extra hardware/filigree score around temples — `LEARNED` → **gate: low**.

### Eyes (violet glow)
- `eyes.glow_luminance`, `eyes.glow_hue` — bright violet-hue energy within/behind lens region — `NOW`.

### Armor (obsidian plate)
- `armor.base_color` — dominant torso hue/lightness (near-black, low sat) — `NOW` → **gate: black**.
- `armor.is_plate_not_leather` — material classifier — `LEARNED` → **gate: plate**.
- `armor.gloss`, `armor.metal_roughness`, `armor.edge_wear`, `armor.reflection` — specular-highlight + high-frequency stats now (proxy), learned scorer later — `NOW-proxy/LEARNED`.

### Wolf pauldrons (THE signature — hard gate)
- `pauldron.present_left`, `pauldron.present_right` — open-vocab "wolf-head pauldron" on each shoulder — `NOW-approx/LEARNED` → **gate: both true**.
- `pauldron.size_ratio` — pauldron bbox / shoulder width (large, readable) — `NOW`.
- `pauldron.jaw_open_angle` — maw geometry — `LEARNED`.
- `pauldron.eye_glow` — violet glow points in pauldron masks — `NOW`.

### Aura
- `aura.violet_density` — violet-hue pixel fraction in the silhouette halo — `NOW`.

### Off-DNA / art-direction checks (from Character DNA)
- `dna.expression_restraint` — no broad smile/teeth/fear (mouth-openness + brow via landmarks) — `NOW-approx` → cap score if violated.
- `dna.framing_dignity` — no comedic Dutch/pin-up framing — `LEARNED`.

---

## 4. Hard signature gates (any fail ⇒ auto-reject)

`glasses.present ∧ glasses.dark ∧ glasses.thick ∧ glasses.rectangular ∧
hair.pigtail_count==2 ∧ pauldron.present_left ∧ pauldron.present_right ∧
armor.base_color==black`.

This is the machine form of: *"A beautiful image that loses her sunglasses, wolf
pauldrons, or silhouette is a complete failure."*

---

## 5. Identity score (feeds Audit Director "Identity 45%")

```
identity_score = 0.35 * face_similarity            # 1 - normalized ArcFace distance
              + 0.30 * signature_presence          # gated booleans (must all pass)
              + 0.20 * measurable_trait_match       # 1 - normalized Σ weighted ΔE/geom error vs spec
              + 0.15 * clip_ref_similarity          # CLIP image sim to approved ref set
# any hard gate == fail ⇒ identity_score := 0 (auto-reject)
```
Feeds the weighted rubric in `forge_roadmap.md` (Identity 45% of total). Drift over time =
plot `face_embedding_distance` + `measurable_trait_error` per generation and per LoRA
version → an objective **drift dashboard**.

---

## 6. Maturity roadmap

- **Harness v1 (`NOW`):** face embedding, landmarks, color/geometry/luminance, violet-density,
  presence via SAM+open-vocab. Calibrate targets on the 6 refs. Enough to gate signatures
  and rank candidates objectively.
- **Harness v2 (`LEARNED`):** small classifiers trained on the growing approved/rejected
  set for material (plate vs leather), pauldron fidelity, glasses ornamentation, framing
  dignity. Accuracy compounds as the approved library grows — the system literally gets
  better at recognizing her the more we approve.

---

## 7. Companion JSON (schema stub — values at calibration)
```json
{
  "spec_version":"0.1","calibrated":false,"reference_set":["9C16","A4C0","NERO","9500","9A63","8F05"],
  "traits":{"face.embedding_distance":{"target":null,"tol":null,"maturity":"NOW","gate":false},
            "hair.pigtail_count":{"target":2,"tol":0,"maturity":"NOW","gate":true},
            "glasses.lens_luminance":{"target":null,"tol":null,"maturity":"NOW","gate":true},
            "glasses.frame_thickness":{"target":null,"tol":null,"maturity":"NOW","gate":true},
            "pauldron.present_left":{"target":true,"maturity":"NOW","gate":true},
            "pauldron.present_right":{"target":true,"maturity":"NOW","gate":true},
            "armor.base_color":{"target":"black","maturity":"NOW","gate":true}},
  "hard_gates":["glasses.present","glasses.dark","glasses.thick","glasses.rectangular","hair.pigtail_count==2","pauldron.present_left","pauldron.present_right","armor.base_color==black"]
}
```

---
- **v0.1 (2026-07-13):** method + schema designed; targets pending calibration against the reference library.
