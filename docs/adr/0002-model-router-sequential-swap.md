# ADR-0002 — The model layer is a sequential, VRAM-aware swap router

**Status:** Accepted

## Context
The hardware is a single **RTX 4070 = 12 GB VRAM**. The primary chat model
(`qwen3:14b`) already uses ~9–10 GB. A "router" that keeps a fast model **and** a
large model **and** a vision model **and** a speech model hot in VRAM needs
~21–31 GB — physically impossible here. One GPU also means **one inference lane**:
anything GPU-bound serializes. Switching the resident model costs seconds of
load time (a few seconds warm, up to ~15 s cold).

## Decision
- **One primary generalist model stays resident** (today `qwen3:14b`; a 30B-MoE
  like Qwen3-30B-A3B is a candidate if it fits and helps).
- Only **tiny helpers co-reside**: `nomic-embed` (~0.5 GB) and a rules/embedding
  intent classifier (no GPU).
- **Vision / larger models are loaded on demand** by evicting the generalist,
  and the swap cost is surfaced to the user as an honest *"thinking harder…"*
  state. Swaps are minimized by batching same-tier work.
- **Speech stays off the GPU:** Kokoro TTS on ONNX/CPU; STT browser-side or
  faster-whisper (CPU/opportunistic).
- The router's job is mostly *avoiding* the LLM (retrieval, deterministic code,
  cache — see the Constitution) and, when a model is needed, picking the tier and
  paying the swap only when justified.

## Consequences
- ✅ Honest and achievable on 12 GB; no false "concurrent multi-model" promise.
- ✅ Frees us to make "instant" real via the non-LLM fast path.
- ⚠️ Tier changes cost seconds — the UX must absorb this (a visible state, not a
  freeze), and we minimize swaps.
- ⚠️ "Reduce model size under load" is not live-resizable in Ollama; the only
  lever is unload/reload. The Resource Orchestrator pauses *background* GPU work,
  it does not shrink the foreground model.

## Alternatives considered
- **Hot four-tier concurrent router (V2)** — rejected: exceeds VRAM by 2–3×.
- **CPU-only large model** — rejected for interactive use: too slow (single-digit
  tok/s) for the "instant" pillar.
