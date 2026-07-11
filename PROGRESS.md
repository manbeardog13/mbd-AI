# Nero — Progress Tracker

The single place to see where things stand. I update this every increment.
For the *why* and the long-term plan, see [docs/VISION.md](docs/VISION.md).

**Legend:** ✅ shipped · 🔨 building now · 🧪 in review (PR) · ⏭️ next · 🗓️ planned

---

## 🔨 Building now
- **Memory core** (Phase 1, memory half) — layered memory (type · confidence ·
  importance · decay · timestamps · entities), `nomic-embed` retrieval with a
  graceful fallback, and reflection (she decides what to remember). Lands in PR #2
  with `verify_memory.py`, `verify_embeddings.py`, tests + a benchmark.

## 🧪 Built, in review — [PR #2](https://github.com/manbeardog13/mbd-AI/pull/2)
- **Development Directive** (`docs/DIRECTIVE.md`) + **verification framework**
  (`verify/verify_everything.py`, `verify_gpu/ollama/config`)
- **Phase 1 — Identity:** goals, principles, confidence-based answering
- Vision expanded (knowledge graph, Insight Engine, cognitive-OS horizon)

## ✅ Shipped (on `main`)
- **v0.1 foundation** — local chat via Ollama, streaming, **voice** (talk/listen +
  Siri Shortcut), **bilingual EN/HR**, **TARS humor dial**, memory-facts,
  female persona "Nero", one-command setup, Tailscale remote access, PWA
- Hardened by an adversarial multi-lens review (**6 issues fixed** before merge)

## ⏭️ Next
- Finish + self-verify the memory core; **intelligent silence** ("thinking…" status)
- **World model / continuity** and the full cognitive loop (Phase 2)

## 🗓️ Planned (see VISION.md for full sequencing)
- Insight Engine (Second Brain) · tools + planner · skills plugins · observability
- (later, opt-in, local-only) desktop senses + proactivity · multi-agent · digital twin

---

## How to follow along

| Where | What you see |
|-------|--------------|
| **[PR #2](https://github.com/manbeardog13/mbd-AI/pull/2)** | Live work-in-progress — every commit + diff as I build |
| **[Commits on main](https://github.com/manbeardog13/mbd-AI/commits/main)** | Completed, merged history |
| **This chat** | My step-by-step reports and decisions |
| `python verify/verify_everything.py` | Nero's health on **your** PC (source of truth) |
