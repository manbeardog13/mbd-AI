---
id: root.progress
title: "Nero — Progress Tracker"
layer: operational
type: log
status: active
owner: toni
created: 2026-07-12
updated: 2026-07-18
---

# Nero — Progress Tracker

**Charter:** the increment log — what shipped, what's in flight. The plan lives in
[docs/ROADMAP.md](docs/ROADMAP.md); the narrative snapshot in
[docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md). Phase *names* ("The Hands") are
canonical; older entries may use two legacy numbering eras.

The single place to see where things stand. I update this every increment.
For the *why* and the long-term plan, see [docs/VISION.md](docs/VISION.md).

**Current priority (2026-07-18): repository governance and orchestrator
preparation.** Local-only work on `codex/ORCHESTRAION` now includes the live
GitHub/Git/worktree baseline, protected-trunk policy, disabled ruleset template,
pinned least-privilege CI, CODEOWNERS, dependency review, CodeQL, `repoctl.py`,
deterministic verification, reconciliation plan, ADR-0027, and the OR-0 through
OR-5 roadmap. Remote history, default branch, rulesets, pushes, PRs, and merges
remain unchanged pending Toni's exact approvals.

**Legend:** ✅ shipped · 🔨 building now · 🧪 in review (PR) · ⏭️ next · 🗓️ planned

---

## 🧪 In review (PR)
- **Canonical knowledge base + attention architecture** 🧪 — on the pushed
  rescue branch awaiting merge: `docs/canon/` (self-auditing via
  `verify_canon.py` + 7 tests), migration Phases 0/A/B/C/E executed with all
  verifiers green, ADRs 0017–0021 (canon · skill lifecycle · Proxima
  retirement ✅ executed · identity plane · attention L0–L3), capsule V2
  reconciled with per-lane deploy verification, engine-handoff + review-inbox
  specs, DHEF packets open for Codex (`ac362276` inbox build, `fa2367b4`
  changes-requested).
- **Phase 1 — "The Hands" · first slice** 🧪 — the primitive that lets Nero
  *act*: the **agent loop** (reason → tool → observe → repeat, bounded and
  cancellable), the **Capability Registry** (one guarded dispatch seam; the model
  reasons over capabilities discovered at runtime, not a hard-coded list), the
  **security gate** (every MEDIUM+ action needs confirmation; project jail;
  fail-closed), **Executive Memory** (the working-state register — goal/project/
  branch/task/blocker/next_action; branch & project observed from git, not
  guessed), and the first capability **`git.status`**. New endpoints `POST
  /api/agent`, `GET /api/agent/capabilities`, `GET/DELETE /api/executive`; agent
  + capability metrics in `/api/metrics`. 32 offline tests + `verify_security.py`,
  `verify_capabilities.py`, `verify_executive_memory.py`, `verify_agent.py` all
  green (the live agent run verifies on the PC where Ollama runs). Next Phase-1
  capabilities, one PR each: `fs.read`, `fs.list`, `git.log`, then the
  human-in-the-loop terminal.

## ✅ Shipped (on `main`)
- **V3 governance layer** ✅ — the Constitution (v1.1), ADRs 0001–0008, the phased
  Roadmap, and the Phase-1 technical design in `docs/`. Two decisions settled:
  **ADR-0006 "Local-First with Intelligence Escalation"** and the **Principle of
  Least Intelligence**.
- **UI redesign + voice in the app** ✅ (PR #9) — the NERO Design System, a
  ChatGPT-style two-button voice composer, hands-free conversation mode, and
  Nero's **local neural voice** playing her replies (`POST /api/speak`) with
  browser-voice fallback, barge-in, and iOS Web-Audio playback.
- **Voice agent — Increment 1: local neural English voice** ✅ — Nero speaks with
  a real, local Kokoro voice (via ONNX Runtime; no torch; Python 3.13). `app/tts.py`,
  `POST /api/speak` + `GET /api/voice`, `verify_tts.py`. Verified 8/8 on the RTX 4070.
- **Phase 2 — World Model / continuity** ✅ — a live, structured picture of what
  Toni's working on, updated in the background and read into every reply, so she
  resumes *knowing where you left off*. Verified 7/7 end-to-end on the RTX 4070.
- **Memory core** ✅ — layered/typed memory (semantic · episodic · preference ·
  experience) with confidence · importance · **decay** · timestamps · entities;
  `nomic-embed` semantic **retrieval** with graceful fallback; **reflection**
  (she decides what to remember, dedupes/reinforces); `/api/metrics`. Reflection
  + world updates use Ollama **structured output** so small models emit JSON.
- **Development Directive** (`docs/DIRECTIVE.md`) + **verification framework**
  (`verify/verify_everything.py` — 7 subsystem checks)
- **Phase 1 — Identity:** goals, principles, confidence-based answering
- **v0.1 foundation** — local chat via Ollama, streaming, **voice** (talk/listen +
  Siri Shortcut), **bilingual EN/HR**, **TARS humor dial**, memory-facts,
  female persona "Nero", one-command setup, Tailscale remote access, PWA
- Hardened by **four adversarial multi-lens reviews** (~29 issues fixed pre-merge)

## ⏭️ Next (Toni's chosen order)
1. Finish the **voice agent** (Increment 1 building now → Croatian → real-time
   loop with continuous listen + barge-in)
2. **Computer control** — a local "Cowork": see the screen, drive mouse/keyboard
   (rides on the Tool System + planner)
3. **Apply the Design System v1.0** to the live frontend

## 🗓️ Planned (see VISION.md for full sequencing)
- Experience Engine · Insight Engine (Second Brain) · intent router + thought
  budget · knowledge graph · observability dashboard
- (later, opt-in, local-only) desktop senses + proactivity · multi-agent · digital twin

---

## How to follow along

| Where | What you see |
|-------|--------------|
| **[Open pull requests](https://github.com/manbeardog13/mbd-AI/pulls)** | Live work-in-progress — every commit + diff as I build |
| **[Commits on main](https://github.com/manbeardog13/mbd-AI/commits/main)** | Completed, merged history |
| **This chat** | My step-by-step reports and decisions |
| `python verify/verify_everything.py` | Nero's health on **your** PC (source of truth) |
