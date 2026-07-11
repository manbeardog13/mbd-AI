# Nero — Progress Tracker

The single place to see where things stand. I update this every increment.
For the *why* and the long-term plan, see [docs/VISION.md](docs/VISION.md).

**Legend:** ✅ shipped · 🔨 building now · 🧪 in review (PR) · ⏭️ next · 🗓️ planned

---

## 🔨 Building now
- **Phase 2 — World Model / continuity** 🧪 — a live, structured picture of what
  Toni's working on (project · task · working context · blockers · next steps ·
  recent focus). Nero updates it in the background after each exchange and reads
  it at the start of every reply, so she resumes *knowing where you left off*.
  Ships with unit tests, an offline self-test (`verify_world_model.py`),
  `/api/world` + `/api/metrics`, and a `world_model_enabled` config switch.

## 🧪 Built, in review — [PR #2](https://github.com/manbeardog13/mbd-AI/pull/2)
- **Memory core** ✅ — layered/typed memory (semantic · episodic · preference ·
  experience) with confidence · importance · **decay** · timestamps · entities;
  `nomic-embed` semantic **retrieval** with graceful fallback; **reflection**
  (she decides what to remember, dedupes/reinforces); `/api/metrics`. Ships with
  unit tests, an offline self-test, and `verify_memory/embeddings/reflection.py`.
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
- **Tool System** (Phase 3) — give Nero real actions: read/write files, run
  commands, search the web, all local and permissioned
- **Intelligent silence** — live "thinking… / searching memory…" status (small)

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
