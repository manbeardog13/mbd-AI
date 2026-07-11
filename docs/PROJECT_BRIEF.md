# Nero — Project Status Brief

*A living, honest snapshot of where Nero stands — kept current as she evolves.
It doubles as a self-contained handoff you can give to an external advisor
(e.g. ChatGPT) to get sharper guidance: it captures what actually exists today,
the known gaps, the roadmap, and pointed open questions. Blunt, specific
feedback is welcome — what to cut as readily as what to add.*

*Last updated: v0.1 foundation (pre-merge), before the Memory & Identity core.*

---

## 1. What Nero is

A **personal AI companion** named **Nero** (she/her) that runs **100% locally**
on the owner's own PC. Private, offline inference — nothing leaves the machine.
Reachable from anywhere over a private encrypted network (Tailscale).

The explicit goal is to grow from "a chatbot" into a **cognitive companion**.
**North Star: continuity** — she should wake up already knowing what the owner
was doing and quietly help without being asked.

Guiding principle: the **model (brain) is swappable**, so the architecture is
built to outlive any single model. Build the "mind" once; upgrade the brain over
time.

## 2. The owner & hard constraints

- **Owner:** Toni.
- **Wants:** feels like a real person (not a command bot); accessible "like Siri"
  (voice, hands-free); no login friction; **bilingual English + Croatian**
  (auto-detect per message); a **TARS-from-Interstellar humor dial**; a smooth
  **female voice**.
- **Hardware:** Windows 10/11 PC, single **NVIDIA GPU with ~10–12 GB VRAM**.
- **Constraints:** local-only / private; minimal-friction setup; must run well on
  that GPU; swappable model.

## 3. Current architecture (v0.1 — what actually exists today)

**Stack**
- **Backend:** Python **FastAPI**; async streaming via `httpx`.
- **Brain:** **Ollama** running **`qwen2.5:14b`** locally (swappable via config).
- **Memory store:** **SQLite** (stdlib `sqlite3`).
- **Frontend:** a single **vanilla HTML/CSS/JS** web app (no framework, no build
  step) — responsive, works on phone + desktop, installable (PWA manifest).
- **Access:** Tailscale (device-only; Tailscale *is* the auth — no app login).
- **Setup:** one-command `bootstrap.py` (creates venv, installs deps, checks
  Ollama, pulls the model, launches); `start.bat`/`start.sh` to relaunch.

**How her personality/behavior works today**
- On **every message**, the backend builds a **system prompt** from config +
  memory. It contains: identity (name, she/her, tolerance for name
  variants/nicknames), a personality paragraph, a **language directive**
  (auto-detect and reply in English or Croatian), a **humor directive** derived
  from a 0–100 dial, and any long-term facts.
- **Humor dial** is live-adjustable from the web UI (a slider), persisted
  server-side; it reshapes tone from "all business" to "full comedian."

**Memory today (important — this is the seed, not the vision yet)**
- **Conversation history:** stored in SQLite; the last N messages are injected as
  context each turn.
- **Long-term "facts":** a single flat table of strings, injected **wholesale**
  into every system prompt. The owner can add/remove them in the UI.
- There is **no** layering, **no** confidence scores, **no** decay, **no**
  automatic capture, and **no** semantic/embedding retrieval yet. Memory
  currently grows the prompt roughly linearly.

**Voice today**
- **Text-to-speech:** browser `speechSynthesis` — prefers a female voice; picks a
  Croatian voice for Croatian replies and English for English (by detecting
  Croatian diacritics); user can pick the voice; a small pitch/rate tweak for
  smoothness.
- **Speech-to-text:** browser Web Speech API mic (English/Croatian selectable).
  Requires an HTTPS/secure context (provided via `tailscale serve`).
- **iPhone:** a Siri Shortcut ("Hey Siri, ask Nero…") posts to the same API and
  speaks the reply — true hands-free.
- Voice quality is limited by the OS's installed voices. A fully-local **neural**
  voice (Piper) is planned for a "glassier" sound.

**Repo layout**
```
bootstrap.py            one-command setup & launch
start.bat / start.sh    quick relaunch
run.py                  runs the FastAPI server
config.example.yaml     template -> config.yaml (private) on first run
app/
  main.py               FastAPI routes (chat stream, memories, settings, status)
  config.py             loads config + live overrides (humor/voice) from settings.json
  db.py                 SQLite: conversations, messages, facts
  llm.py                streams from local Ollama
  prompt.py             builds the system prompt (identity, languages, humor, memories)
  static/               the web app (index.html, app.js, style.css)
docs/                   SETUP, MODELS, VOICE_AND_SIRI, REMOTE_ACCESS, ALWAYS_ON, VISION
```

## 4. Current limitations / known gaps

- Memory is **flat** — no layers, confidence, decay, or retrieval; it just gets
  dumped into the prompt, which won't scale.
- **No reflection/learning loop** — she doesn't yet decide what to remember.
- **No world model** — she re-infers context every turn.
- **No tools / no planner** — she can only talk, not act.
- **No embeddings / semantic search.**
- **No observability** (no view into memory hits, latency, reasoning).
- **Single conversation thread** (multi-conversation is planned).
- Voice is only as good as the OS voices (neural TTS planned).

## 5. The roadmap (see [VISION.md](VISION.md) for the full architecture)

Phased, each phase its own reviewed change:

- **Phase 1 (next):** *Memory & Identity core* — layered memory (semantic /
  episodic / preference) with **confidence + decay**; **reflection** so Nero
  decides what to remember after an exchange; a dedicated **identity file**
  (persona + **goals** + **principles**); **confidence-based answers**; live
  "thinking…" status.
- **Phase 2:** *World model* (continuity) + wiring the full cognitive loop
  (Perceive → Retrieve → Update world model → Plan → Act → Reflect → Learn).
- **Phase 3:** tools + a **planner**; a **skills plugin** system; an
  **observability dashboard**.
- **Later:** desktop **sensing + proactivity + attention scoring** (opt-in,
  local); slow personality drift.

## 6. Open questions where outside advice is most valuable

1. **Local memory architecture** — best lightweight design for layered memory
   with confidence + decay + retrieval for a single-user local app? SQLite + a
   local embedding model (e.g. `nomic-embed-text` via Ollama)? How should the
   decay/reinforcement math work?
2. **Keeping the prompt small** — retrieval + periodic summarization strategy so
   only relevant memories are injected as the store grows.
3. **Reflection cadence & cost** — every turn / end-of-session / importance-
   triggered? Worth a smaller/faster model just for reflection + extraction?
   How to dedupe/merge memories.
4. **World model** — how to represent and continuously update it cheaply, locally.
5. **Continuity mechanics** — session summaries, a "since we last spoke" digest?
6. **Proactivity on Windows** — safe, privacy-respecting context sensing (active
   window, battery, GPU, files) + an attention/importance design.
7. **Voice** — is Piper right for a local, low-latency, "glassy" female voice
   with Croatian support? Streaming TTS approach?
8. **Bilingual reliability** — pitfalls making one model reliably switch EN/HR;
   better Croatian-capable models at ~12 GB.
9. **Evaluation** — lightweight way to tell if a change makes her better / more
   "alive."
10. **Over-engineering check** — the two highest-ROI next steps, and what to cut.

---

*Maintenance note: update this brief at the end of each phase so it always
reflects reality — it's the fastest way to onboard a human or an AI advisor.*
