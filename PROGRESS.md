# Nero — Progress Tracker

The single place to see where things stand. I update this every increment.
For the *why* and the long-term plan, see [docs/VISION.md](docs/VISION.md).

**Legend:** ✅ shipped · 🔨 building now · 🧪 in review (PR) · ⏭️ next · 🗓️ planned

---

## 🔨 Building now
- **Real-time voice agent — Increment 1: local neural voice** 🔨 — Nero speaks
  with a real, **local** English voice (Kokoro; nothing leaves the PC). New
  `app/tts.py` (engine-abstracted), `POST /api/speak` + `GET /api/voice`, a
  `verify_tts.py` that saves a playable sample, and optional
  `requirements-voice.txt`. Croatian (Meta MMS-TTS) and the real-time loop
  (continuous listen · barge-in via faster-whisper + Silero VAD) come next.

## ✅ Shipped (on `main`)
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
