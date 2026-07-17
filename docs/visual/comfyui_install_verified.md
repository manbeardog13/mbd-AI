---
id: visual.comfyui-install-verified
title: "ComfyUI Install — VERIFIED AS-BUILT (2026-07-13)"
layer: operational
type: reference
status: active
owner: shared
created: 2026-07-13
updated: 2026-07-17
---

# ComfyUI Install — VERIFIED AS-BUILT (2026-07-13)

**This document records what was *actually installed and run*, replacing the
`[VERIFY]` placeholders in `comfyui_pipeline.md`.** Written by the Claude Code
session that performed the first real Manbeardog generations on Toni's machine.

Status: **ComfyUI is installed, running, and producing Bible-consistent
Stage 1 identity candidates.** The forge is live.

---

## Environment (measured)

| Fact | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 4070, 12 GB VRAM, driver 610.62 |
| Host RAM | 64 GB (38 GB free at run) |
| Disk | D: 414 GB free (install target), C: 733 GB free |
| ComfyUI version | **0.27.0** (portable standalone, NVIDIA build) |
| Bundled Python | **3.13.12** |
| Install path | **`D:\ComfyUI\`** (renamed from `ComfyUI_windows_portable`) |
| App root | `D:\ComfyUI\ComfyUI\` (models, custom_nodes, input, output here) |
| Launcher | `D:\ComfyUI\run_nvidia_gpu.bat` (or `..._fast_fp16_accumulation.bat`) |
| Server | `http://127.0.0.1:8188` |

**Headless launch used** (no browser, logs captured):
```
D:\ComfyUI\python_embeded\python.exe -s ComfyUI\main.py --disable-auto-launch
   (WorkingDirectory D:\ComfyUI)
```

---

## Exact download sources (all tokenless, public, verified live)

| Asset | Folder | URL |
|---|---|---|
| ComfyUI portable | — | `https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z` |
| Checkpoint (SDXL photoreal) | `models/checkpoints` | `https://huggingface.co/SG161222/RealVisXL_V5.0/resolve/main/RealVisXL_V5.0_fp16.safetensors` (6.6 GB) |
| VAE (fp16-fix) | `models/vae` | `https://huggingface.co/madebyollin/sdxl-vae-fp16-fix/resolve/main/sdxl_vae.safetensors` (0.32 GB) |
| IPAdapter Plus Face SDXL | `models/ipadapter` | `https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus-face_sdxl_vit-h.safetensors` (0.81 GB) |
| CLIP Vision ViT-H | `models/clip_vision` | `https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors` (2.4 GB, saved as `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors`) |

> **Checkpoint decision:** RealVisXL V5.0 chosen over Juggernaut XL v10 because
> it is ungated on Hugging Face (scriptable, no Civitai token) and is the
> strongest pure-photoreal SDXL — matching the cinematic realism of the
> reference PNGs. This supersedes the `Juggernaut XL v10 [VERIFY]` note.
> `models/ipadapter` did **not** exist by default — it must be created.

## Custom nodes (git clone into `D:\ComfyUI\ComfyUI\custom_nodes\`)

| Node | Repo | Verified class names loaded |
|---|---|---|
| ComfyUI-Manager | `https://github.com/ltdrdata/ComfyUI-Manager` | loads, updates caches on boot |
| ComfyUI_IPAdapter_plus | `https://github.com/cubiq/ComfyUI_IPAdapter_plus` | `IPAdapterUnifiedLoader`, `IPAdapterAdvanced`, `IPAdapterModelLoader`, `CLIPVisionLoader` |

> `ip-adapter-plus-face` does **not** need `insightface` (that is only for the
> FaceID family). No compiler pain required for Stage 1.

---

## The working Stage 1 identity workflow (API format)

Submit via `POST http://127.0.0.1:8188/prompt` with body `{"prompt": <graph>, "client_id":"nero"}`.
Node names below are **confirmed present in ComfyUI 0.27.0 + cubiq node** via
`GET /object_info` — not guessed.

```
CheckpointLoaderSimple("RealVisXL_V5.0_fp16.safetensors")  -> MODEL, CLIP, VAE
VAELoader("sdxl_vae.safetensors")                          -> VAE
CLIPTextEncode(positive, CLIP)                             -> COND+
CLIPTextEncode(negative, CLIP)                             -> COND-
LoadImage("NERO.png")   # copied into D:\ComfyUI\ComfyUI\input\
IPAdapterUnifiedLoader(MODEL, preset="PLUS FACE (portraits)") -> MODEL, IPADAPTER
IPAdapterAdvanced(MODEL, IPADAPTER, image=LoadImage,
                  weight=0.8, weight_type="linear",
                  combine_embeds="concat", embeds_scaling="V only",
                  start_at=0.0, end_at=1.0)                -> MODEL(conditioned)
EmptyLatentImage(832x1216, batch_size=4)
KSampler(seed, steps=40, cfg=7.0, dpmpp_2m, karras, denoise=1.0)
VAEDecode -> SaveImage(prefix="nero/s1_face")
```

Saved reusable API JSON: `D:\_nero_dl\wf_s1_identity.json` (identity),
`D:\_nero_dl\wf_s1_forge.json` (plain SDXL forge test).

---

## Benchmarks (measured, first-run, RTX 4070)

| Config | Approx time | VRAM peak |
|---|---|---|
| SDXL only, 832x1216, 40 steps, batch 1 (incl. first checkpoint load) | ~25-35 s | ~7.7 GB |
| SDXL + IPAdapter Plus Face, 832x1216, 40 steps, **batch 4** | ~45-55 s (~11-14 s/img, model resident) | ~9.5 GB |

Batch 4 with IPAdapter fits comfortably in 12 GB. Ollama's `qwen3:14b` (~9 GB)
was **not** loaded during runs — VRAM co-existence rule held.

---

## Lessons that cost iterations (read before Stage 2)

1. **Text-only prompting drifts hard.** A pure SDXL pass on the full Bible
   prompt rendered wolf *ears on the head* + wrong hair. IPAdapter + `NERO.png`
   is non-optional for identity. This is why Stage 1 exists.
2. **"Wolf-head pauldrons" → the model paints a live companion wolf** in any
   scene with environment room. Two fixes: (a) shoot identity on a **dark void
   background** to remove scene space; (b) Stage 2 must lock the pauldron
   *sculpture* with an actual reference (img2img/reference from `NERO.png` or a
   full-body ref) rather than fighting the text prior.
3. **Negatives that mattered:** `wolf ears, animal ears, kemonomimi, forehead
   gem, live wolf, wolf companion, dog, husky, single ponytail, transparent
   sunglasses`. These killed the recurring failure modes.
4. **Twin ponytails** are still the weak spot — the model favors one dominant
   side ponytail. Candidate for higher IPAdapter weight or an explicit
   symmetry/ControlNet pass.
5. **Operational:** the machine-control channel times out ~25-30 s per call —
   long generations must be **submitted then polled** in short bursts via the
   ComfyUI HTTP API (`/prompt`, `/history/{id}`, `/queue`, `/system_stats`),
   never awaited inline.

---

## Reproduce a run from scratch (quick)

1. Launch: `D:\ComfyUI\run_nvidia_gpu.bat` (or headless line above). Wait for
   `http://127.0.0.1:8188/system_stats` to answer.
2. Ensure identity anchor present: `D:\ComfyUI\ComfyUI\input\NERO.png`.
3. `POST /prompt` with `wf_s1_identity.json` (edit seed/prompt as needed).
4. Poll `GET /history/{prompt_id}` until `status.completed`.
5. Images land in `D:\ComfyUI\ComfyUI\output\nero\`. Curate; copy keepers to
   `visual\source\concepts\manbeardog_v1\identity\face_exploration\` + manifest.

Governance unchanged: Bible wins over aesthetics; keepers are a human decision.
