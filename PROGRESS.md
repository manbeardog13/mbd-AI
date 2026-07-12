# Nero — Progress Tracker

The single place to see where things stand. I update this every increment.
For the *why* and the long-term plan, see [docs/VISION.md](docs/VISION.md).

**Legend:** ✅ shipped · 🔨 building now · 🧪 in review (PR) · ⏭️ next · 🗓️ planned

---

## ⏭️ Next
- **Phase 1 — more capabilities, one PR each:** `fs.list`, `git.log` (read-only),
  then the **human-in-the-loop terminal**, then the Approve/Deny **confirmation
  UX** with the first MEDIUM+ (write) capability.

## ✅ Shipped (on `main`)
- **Phase 1 — "The Hands" · first slice** ✅ (PR #10) — the primitive that lets
  Nero *act*, **verified end-to-end on the RTX 4070**: the **agent loop**
  (reason → tool → observe → repeat, bounded, never hangs), the **Capability
  Registry** (one guarded dispatch seam; the model reasons over capabilities
  discovered at runtime, not a hard-coded list), the **security gate** (every
  MEDIUM+ action needs confirmation; project jail; fail-closed), **Executive
  Memory** (the working-state register — goal/project/branch/task/blocker/
  next_action; branch & project observed from git, not guessed), and the first
  read-only capabilities **`git.status`** and **`fs.read`** (jailed, bounded —
  a path escaping the jail is gated). Endpoints `POST /api/agent`, `GET
  /api/agent/capabilities`, `GET/DELETE /api/executive`; agent + capability
  metrics in `/api/metrics`. Live PC verify: a real qwen3:14b drove the loop via
  `git.status`; adversarial battery gated 32 unconfirmed attempts (0 escapes);
  Executive Memory observed the real git branch. 32 offline tests + four new
  `verify_*.py`.
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
