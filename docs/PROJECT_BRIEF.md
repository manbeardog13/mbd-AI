# Nero — Project Status Brief

*A living, honest snapshot of where Nero stands — kept current as she evolves.
It doubles as a self-contained handoff you can give to an external advisor
(e.g. ChatGPT) to get sharper guidance: what actually exists today, the known
gaps, the roadmap, and pointed open questions. Blunt, specific feedback is
welcome — what to cut as readily as what to add.*

*Last updated: Phase 2 (World Model) **merged & verified 7/7** on the RTX 4070.
Now building the **voice agent — Increment 1: local neural English voice**
(Kokoro), in review (PR #8). Owner's build order: voice → computer control →
apply the new design system.*

---

## 1. What Nero is

A **personal AI companion** named **Nero** (she/her) that runs **100% locally**
on the owner's own PC. Private, offline inference — nothing leaves the machine.
Reachable from anywhere over a private encrypted network (Tailscale).

The explicit goal is to grow from "a chatbot" into a **cognitive companion**.
**North Star: continuity** — she should wake up already knowing what the owner
was doing and quietly help without being asked. The full architecture is in
[VISION.md](VISION.md); the governing philosophy (local-first, verification-
first) is in [DIRECTIVE.md](DIRECTIVE.md).

## 2. The owner & hardware

- **Owner:** Toni.
- **Wants:** feels like a real person; accessible "like Siri" (voice, hands-free);
  no login friction; **bilingual English + Croatian**; a **TARS humor dial**; a
  female voice.
- **Hardware (confirmed):** Windows 11 PC, **NVIDIA RTX 4070 (12 GB VRAM)**,
  **64 GB RAM**. Everything is tuned to this.

## 3. Current architecture (what actually exists today)

**Stack**
- **Backend:** Python **FastAPI**, async streaming via `httpx`.
- **Models (all local via Ollama):**
  - chat → **`qwen3:14b`** (~9 GB, fits fully on the 4070)
  - reflection → **`qwen3:4b`** (unloaded right after each use so it doesn't
    crowd VRAM)
  - embeddings → **`nomic-embed-text`** (768-dim)
  - "Thinking" (Qwen3 `<think>` reasoning) is **disabled by default** for direct
    replies and clean reflection output; a `thinking: true` config flag re-enables it.
- **Storage:** **SQLite** (conversations, messages, memories).
- **Frontend:** a single **vanilla HTML/CSS/JS** web app (responsive, PWA-installable).
- **Access:** local network + Tailscale (device-only; no app login).
- **Setup:** one-command `bootstrap.py` (venv + deps + pulls all 3 models + launch).

**Identity & behavior** (built from config into the system prompt each turn)
- Name Nero (she/her, tolerant of name variants), owner Toni, personality.
- **Goals** and **principles** she weighs decisions against.
- **Confidence-based answering** ("I know" / "I think…" / "I'm not sure").
- **Bilingual** — auto-detects English/Croatian per message and replies in kind.
- **Humor dial** (0–100, TARS-style, adjustable live in the UI).

**Memory (this is now real, not a stub)**
- **Typed memories** (semantic · episodic · preference · experience · procedural),
  each with **confidence, importance, timestamp, source, entities, embedding,
  last-reinforced**. Safe schema migration for older DBs.
- **Retrieval:** ranks by **confidence × time-decay × relevance**; relevance is
  semantic (cosine over `nomic-embed`) when embeddings are comparable, else a
  lexical/recency fallback — always on one comparable scale. Only the top-k most
  relevant memories are injected into the prompt.
- **Decay:** unreinforced memories fade (half-life); recalled/repeated ones are
  reinforced toward confidence 1.
- **Reflection:** after each exchange, a background pass (small model, `think=false`)
  extracts durable facts, **dedupes** against existing memories (text + embedding),
  and reinforces or adds. Writes are serialized (lock) to avoid duplicate races.
- **Voice:** browser TTS (prefers a female voice; speaks Croatian for Croatian
  replies), STT (EN/HR), an iPhone **Siri Shortcut**.
- **Observability:** `GET /api/metrics` exposes retrieval latency + counts.

**World Model (continuity — Phase 2, new)**
- A small, structured, always-current picture of what Toni's working on:
  **current project · task · working context · blockers · next steps · recent
  focus**, in a SQLite `world_state` key/value table.
- **Updated in the background** after each exchange (small model, `think=false`,
  reflection model unloaded after) — the LLM returns only the fields that
  changed as JSON; parsing is hardened (tolerates prose/fences, drops truncated
  `<think>` guesses, collapses values to a single safe line).
- **Read into the system prompt** before every reply, so she resumes *knowing
  where you left off*. The read is best-effort and off the event loop — a DB
  hiccup degrades to "no continuity block", never breaks the chat.
- `GET /api/world` (inspect) · `DELETE /api/world[/{key}]` (owner reset) ·
  `world` counters in `/api/metrics` · `world_model_enabled` config switch.

**Quality process (per the Directive)**
- A **verification framework** — `python verify/verify_everything.py` runs
  `verify_{gpu,ollama,config,memory,world_model,embeddings,reflection}.py`; each
  subsystem ships its own check. Offline checks are green in CI; GPU/Ollama
  checks pass on the owner's PC.
- Hardened by **four adversarial multi-lens reviews** (foundation, memory,
  Windows setup, world model) — ~29 real issues caught and fixed before merge.
- On the RTX 4070: config, gpu, ollama, memory, embeddings, and world_model
  logic all green. `verify_reflection` stored 0 memories — live diagnostics
  revealed the real cause: **qwen3:4b ignores `think=False` and reasons in plain
  prose** (no `<think>` tags), rambling 4000+ chars and never reaching the JSON.
  Fixed by constraining output with **Ollama's structured-output `format`** (a
  JSON schema), which makes prose grammatically impossible. Applied to *both*
  reflection and the world model (same model, same latent bug — the world would
  silently never have updated on a real machine), and added a **live
  end-to-end world-model verify** (the offline-only check had masked it).
  Re-verify on the owner's PC is pending before merge.

**Repo layout**
```
bootstrap.py · start.bat/.sh · run.py · config.example.yaml
app/  main.py · config.py · db.py · memory.py · llm.py · prompt.py · static/
verify/  verify_*.py           docs/  DIRECTIVE · VISION · PROJECT_BRIEF · MODELS · SETUP · …
tests/   test_memory.py        PROGRESS.md
```

## 4. Known gaps / not built yet

- **Knowledge graph** — memories store `entities`, but they aren't yet *connected*
  into a graph.
- **No Insight Engine** — she remembers, but doesn't yet synthesize patterns.
- **No tools / planner / skills** — she can only converse, not act (and so no
  computer control yet; that rides on the Tool System — item 3 above).
- **No proactivity / desktop sensing** — purely reactive.
- **Single active conversation thread** (multi-conversation not built).
- **Retrieval is a linear scan** over SQLite (fine at current scale; no vector DB yet).
- **Observability is minimal** (`/api/metrics`); no dashboard.
- **Voice** — a *local neural English voice* (Kokoro) now exists server-side
  (`app/tts.py`, `POST /api/speak`), but it isn't wired into the chat UI yet
  (still browser TTS there), there's no local STT (faster-whisper) yet, and the
  real-time loop (continuous listen, barge-in) and Croatian (MMS-TTS) are still
  to come.

## 5. Roadmap

- ✅ **Done:** v0.1 foundation · Phase 1 (identity: goals/principles/confidence +
  the full memory subsystem) · **Phase 2 (World Model / continuity)** · the
  cognitive loop is now wired (perceive → retrieve → update world model → reply
  → reflect → learn) · Development Directive + verification framework · Qwen3
  defaults · thinking disabled.
- 🔜 **Next (owner's chosen order):**
  1. **Real-time voice agent** (in progress). ✅ Increment 1 — local neural
     English voice (Kokoro via ONNX Runtime, no PyTorch, Python 3.13), verified
     8/8. 🔨 Increment 2 (in review, PR #9) — that voice now plays in the chat UI
     (`/api/speak`), with graceful fallback to the browser voice for Croatian or
     when unavailable (incl. iOS autoplay), plus barge-in. Next: local STT
     (faster-whisper), the real-time loop (continuous listen, <1s latency), and
     Croatian (Meta MMS-TTS).
  2. **Computer control** — a *local "Cowork"*: see the screen, drive
     mouse/keyboard, act in real apps, with hard safety rails. Rides on the
     **Tool System + planner**, so that foundation lands here.
  3. **Apply the Design System v1.0** to the live frontend (violet, floating
     cards, responsive desktop/tablet/mobile — previewed as an artifact).
- 🗓️ **Then:** intent router + thought budget · **Experience Engine** (workflows,
  not just facts) · knowledge-graph connections · **Insight Engine** (Second Brain)
  · observability dashboard.
- 🗓️ **Later (opt-in, local):** desktop sensing + proactivity + attention ·
  browser intelligence · multi-agent · digital twin.

## 6. Open questions where outside advice is most valuable

1. **World model tuning** — now built as a 6-field key/value picture, updated by
   a background LLM step returning changed-fields JSON. Is that the right shape,
   or should it carry structure (nested tasks, timestamps, confidence per field)?
2. **Continuity mechanics** — beyond the live world model: session summaries, a
   "since we last spoke" digest, decay of stale world fields?
3. **Knowledge graph** — how to connect memories (entities/relations) so it's
   genuinely useful; when to graduate from a linear scan to a vector DB.
4. **Insight Engine** — how often to run pattern-analysis, and how to surface
   insights without becoming noisy.
5. **Reflection tuning** — is a 4B model good enough at extraction? Dedup
   thresholds? Should importance/confidence be model-set or heuristic?
6. **Proactivity on Windows** — a safe, private way to sense context (active app,
   files, GPU) + an attention/importance model that helps without nagging.
7. **Voice** — is **Piper** the right local, low-latency, female (Croatian-capable)
   neural voice? Best way to stream it.
8. **Evaluation** — for a *personal* companion, how do we tell if a change makes
   her genuinely better / more "alive"?
9. **Over-engineering check** — the two highest-ROI next steps, and what to cut.

---

*Maintenance note: refresh this brief at the end of each phase so it always
reflects reality — it's the fastest way to onboard a human or an AI advisor.*
